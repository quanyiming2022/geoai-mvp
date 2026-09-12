"""Reusable assets; authenticated SQL and database mutation fences are authoritative."""
from typing import Literal
from uuid import UUID
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from .auth import CurrentUser
from .spatial import UserSQLRepository

router = APIRouter(tags=["raster-library"])

class AssetName(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=255)

class ConfirmDelete(BaseModel):
    model_config = ConfigDict(extra="forbid")
    confirmed: Literal[True]

class AssetLibraryRepository(UserSQLRepository):
    columns = "id,name,filename,owner_id,created_at,status,crs,width,height,bands,resolution,bbox,size,checksum,error_code,geoai_internal.asset_usage_count(id) AS reference_count,COALESCE(owner_id=auth.uid(),false) OR geoai_internal.is_platform_admin() AS can_manage"

    def list(self, search="", status=None, limit=100, offset=0):
        return self.execute(f"SELECT {self.columns} FROM public.raster_assets WHERE deleted_at IS NULL AND name ILIKE %s AND (%s::text IS NULL OR status=%s) ORDER BY created_at DESC,id LIMIT %s OFFSET %s", ("%"+search+"%",status,status,limit,offset))

    def mutate(self, asset, operation, name=None):
        rows=self.execute("SELECT geoai_internal.asset_usage_count(id) AS reference_count,COALESCE(owner_id=auth.uid(),false) OR geoai_internal.is_platform_admin() AS can_manage FROM public.raster_assets WHERE id=%s AND deleted_at IS NULL", (asset,))
        if not rows:
            raise HTTPException(404,"影像不存在")
        if not rows[0]["can_manage"]:
            raise HTTPException(403,"仅影像所有者或平台管理员可以管理资产")
        if operation=="delete" and rows[0]["reference_count"]:
            raise HTTPException(409,{"code":"ASSET_REFERENCED","reference_count":rows[0]["reference_count"],"message":f"该影像仍被 {rows[0]['reference_count']} 个项目使用，请先移除项目引用。"})
        self.execute("SELECT geoai_internal.manage_raster_asset(%s,%s,%s)",(asset,operation,name))
        return {"ok":True}

    def project(self, project, asset, operation, name=None):
        self.execute("SELECT geoai_internal.manage_project_asset(%s,%s,%s,%s)",(project,asset,operation,name))
        return {"ok":True}

@router.get("/raster-assets")
def assets(current:CurrentUser,search:str=Query(default="",max_length=255),status:Literal["uploaded","processing","ready","failed"]|None=None,limit:int=Query(default=100,ge=1,le=200),offset:int=Query(default=0,ge=0)):
    return AssetLibraryRepository(current.user["id"]).list(search,status,limit,offset)

@router.patch("/raster-assets/{asset_id}")
def rename(asset_id:UUID,data:AssetName,current:CurrentUser):
    return AssetLibraryRepository(current.user["id"]).mutate(asset_id,"rename",data.name)

@router.delete("/raster-assets/{asset_id}")
def delete(asset_id:UUID,data:ConfirmDelete,current:CurrentUser):
    return AssetLibraryRepository(current.user["id"]).mutate(asset_id,"delete")

@router.post("/projects/{project_id}/rasters/{asset_id}/link")
def link(project_id:UUID,asset_id:UUID,current:CurrentUser):
    return AssetLibraryRepository(current.user["id"]).project(project_id,asset_id,"link")

@router.patch("/projects/{project_id}/rasters/{asset_id}")
def alias(project_id:UUID,asset_id:UUID,data:AssetName,current:CurrentUser):
    return AssetLibraryRepository(current.user["id"]).project(project_id,asset_id,"rename",data.name)

@router.delete("/projects/{project_id}/rasters/{asset_id}/link")
def unlink(project_id:UUID,asset_id:UUID,data:ConfirmDelete,current:CurrentUser):
    return AssetLibraryRepository(current.user["id"]).project(project_id,asset_id,"unlink")
