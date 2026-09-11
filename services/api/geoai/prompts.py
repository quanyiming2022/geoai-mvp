import json
from threading import BoundedSemaphore
from uuid import UUID, uuid4
from fastapi import APIRouter, HTTPException
from pydantic import Field
import httpx
import rasterio
from .auth import CurrentUser
from .spatial import AoiInput, RenameInput, UserSQLRepository
from .projects import accessible
from .rasters import asset_for_user, provider
from .config import Settings
from .prompt_processing import support_crop


class PromptInput(AoiInput):
    raster_asset_id: UUID
    class_label: str = Field(default='', max_length=120)
    description: str = Field(default='', max_length=2000)


class PromptRepository(UserSQLRepository):
    columns = "id,project_id,raster_asset_id,name,class_label,description,extensions.ST_AsGeoJSON(geometry)::json AS geometry,bbox,source_crs,support_image_object,support_mask_object,created_by,created_at"

    def list(self, project_id):
        return self.execute(f"SELECT {self.columns} FROM public.visual_prompts WHERE project_id=%s ORDER BY created_at DESC", (project_id,))

    def get(self, resource_id):
        rows = self.execute(f"SELECT {self.columns} FROM public.visual_prompts WHERE id=%s", (resource_id,))
        return rows[0] if rows else None

    def validate(self, raster_id, geometry):
        rows = self.execute("SELECT extensions.ST_IsValid(g) AND extensions.ST_Covers(footprint,g) AND extensions.ST_Area(g::extensions.geography)>0 AS valid, geoai_internal.project_role(project_id) AS role FROM public.raster_assets, LATERAL (SELECT extensions.ST_SetSRID(extensions.ST_GeomFromGeoJSON(%s),4326) AS g) q WHERE id=%s AND status='ready'", (geometry, raster_id))
        if not rows or rows[0]['role'] not in ('owner','editor'):
            raise HTTPException(403, 'Prompt creation requires editor access')
        if not rows[0]['valid']:
            raise HTTPException(422, 'Sample must be valid and inside the raster')

    def create(self, prompt_id, project_id, data, crs):
        points = [p for ring in data.geometry.coordinates for p in ring]
        bbox = [min(p[0] for p in points), min(p[1] for p in points), max(p[0] for p in points), max(p[1] for p in points)]
        prefix = f'{project_id}/prompts/{prompt_id}'
        return self.execute(f"INSERT INTO public.visual_prompts(id,project_id,raster_asset_id,name,class_label,description,geometry,bbox,source_crs,support_image_object,support_mask_object,created_by) VALUES (%s,%s,%s,%s,%s,%s,extensions.ST_SetSRID(extensions.ST_GeomFromGeoJSON(%s),4326),%s::jsonb,%s,%s,%s,%s) RETURNING {self.columns}", (prompt_id,project_id,data.raster_asset_id,data.name,data.class_label,data.description,data.geometry.model_dump_json(),json.dumps(bbox),crs,prefix+'/image.tif',prefix+'/mask.tif',self.user_id))[0]


crop_slots = BoundedSemaphore(2)
router = APIRouter(tags=['visual-prompts'])


@router.get('/projects/{project_id}/prompts')
def list_prompts(project_id: UUID, current: CurrentUser):
    accessible(project_id, current)
    return PromptRepository(current.user['id']).list(project_id)


@router.post('/projects/{project_id}/prompts', status_code=201)
def create_prompt(project_id: UUID, data: PromptInput, current: CurrentUser):
    accessible(project_id, current)
    asset, cfg = asset_for_user(data.raster_asset_id, current)
    if asset['project_id'] != str(project_id):
        raise HTTPException(422, 'Raster belongs to another project')
    repo = PromptRepository(current.user['id'])
    repo.validate(data.raster_asset_id, data.geometry.model_dump_json())
    expected = f"{project_id}/rasters/{asset['id']}/cog.tif"
    if asset.get('cog_object_key') != expected:
        raise HTTPException(409, 'Invalid COG reference')
    if not crop_slots.acquire(blocking=False):
        raise HTTPException(429, 'Support crop busy; retry shortly')
    storage = provider(cfg, internal=True)
    prompt_id = uuid4()
    preserve = False
    attempted = []
    try:
        image, mask, crs = support_crop(storage.create_signed_url(cfg.storage_bucket, expected, 60), data.geometry.model_dump())
        for name, blob in (('image',image),('mask',mask)):
            key = f'{project_id}/prompts/{prompt_id}/{name}.tif'
            attempted.append(key)
            storage.put_object(cfg.storage_bucket, key, blob, 'image/tiff')
        # Preserve objects on uncertain database outcome; never delete a possibly committed sample.
        preserve = True
        try:
            return repo.create(prompt_id, project_id, data, crs)
        except HTTPException as exc:
            if exc.status_code < 500:
                preserve = False
            raise
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    except (httpx.HTTPError, rasterio.errors.RasterioError):
        raise HTTPException(503, 'Support crop unavailable') from None
    finally:
        if not preserve:
            for key in attempted:
                try:
                    storage.delete_object(cfg.storage_bucket, key)
                except httpx.HTTPError:
                    pass  # Original failure remains visible; cleanup is best effort.
        storage.close()
        crop_slots.release()


@router.get('/prompts/{prompt_id}/{kind}/download')
def download_prompt(prompt_id: UUID, kind: str, current: CurrentUser):
    if kind not in ('image','mask'):
        raise HTTPException(404, 'Not found')
    row = PromptRepository(current.user['id']).get(prompt_id)
    if not row:
        raise HTTPException(404, 'Prompt not found')
    cfg = Settings()
    storage = provider(cfg)
    try:
        key = f"{row['project_id']}/prompts/{prompt_id}/{kind}.tif"
        return {'url': storage.create_signed_url(cfg.storage_bucket,key,60)}
    finally:
        storage.close()


@router.post('/projects/{project_id}/prompts/preview')
def preview_prompt(project_id:UUID,data:PromptInput,current:CurrentUser):
    import base64
    import numpy as np
    from rasterio.io import MemoryFile
    accessible(project_id,current)
    asset,cfg=asset_for_user(data.raster_asset_id,current)
    if asset['project_id']!=str(project_id):
        raise HTTPException(422,'Raster belongs to another project')
    PromptRepository(current.user['id']).validate(data.raster_asset_id,data.geometry.model_dump_json())
    expected=f"{project_id}/rasters/{asset['id']}/cog.tif"
    if asset.get('cog_object_key')!=expected:
        raise HTTPException(409,'Invalid COG reference')
    if not crop_slots.acquire(blocking=False):
        raise HTTPException(429,'Support crop busy')
    storage=provider(cfg,internal=True)
    try:
        image,mask,_=support_crop(storage.create_signed_url(cfg.storage_bucket,expected,60),data.geometry.model_dump())
        previews={}
        for name,blob in [('image',image),('mask',mask)]:
            with MemoryFile(blob) as memory,memory.open() as ds:
                pixels=ds.read()
                if name=='mask':
                    pixels=(pixels*255).astype('uint8')
                elif pixels.dtype!=np.uint8:
                    ranges=asset.get('display_ranges')
                    if not ranges:
                        raise ValueError('Preview requires display ranges')
                    pixels=np.stack([np.clip((band-low)/max(high-low,1e-6)*255,0,255).astype('uint8') for band,(low,high) in zip(pixels[:3],ranges[:3])])
                with MemoryFile() as out:
                    with out.open(driver='PNG',width=ds.width,height=ds.height,count=min(3,len(pixels)),dtype='uint8') as png:
                        png.write(pixels[:3])
                    previews[name]='data:image/png;base64,'+base64.b64encode(out.read()).decode()
        return previews
    except ValueError as error:
        raise HTTPException(422,str(error)) from None
    except (httpx.HTTPError,rasterio.errors.RasterioError):
        raise HTTPException(503,'Preview unavailable') from None
    finally:
        storage.close()
        crop_slots.release()


@router.patch('/projects/{project_id}/prompts/{resource_id}')
def rename_prompt(project_id: UUID, resource_id: UUID, data: RenameInput, current: CurrentUser):
    accessible(project_id, current)
    return UserSQLRepository(current.user['id']).rename('prompt', project_id, resource_id, data)
