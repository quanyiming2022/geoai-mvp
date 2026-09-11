ALTER TABLE public.raster_assets ADD CONSTRAINT raster_project_unique UNIQUE(id,project_id);
CREATE TABLE public.visual_prompts (
 id uuid PRIMARY KEY,
 project_id uuid NOT NULL REFERENCES public.projects(id) ON DELETE CASCADE,
 raster_asset_id uuid NOT NULL,
 name text NOT NULL CHECK(length(btrim(name)) BETWEEN 1 AND 120),
 class_label text NOT NULL DEFAULT '' CHECK(length(class_label)<=120),
 description text NOT NULL DEFAULT '' CHECK(length(description)<=2000),
 geometry extensions.geometry(Polygon,4326) NOT NULL,
 bbox jsonb NOT NULL, source_crs text NOT NULL,
 support_image_object text NOT NULL, support_mask_object text NOT NULL,
 created_by uuid NOT NULL REFERENCES auth.users(id), created_at timestamptz NOT NULL DEFAULT now(),
 FOREIGN KEY(raster_asset_id,project_id) REFERENCES public.raster_assets(id,project_id) ON DELETE CASCADE,
 CHECK(extensions.ST_IsValid(geometry) AND NOT extensions.ST_IsEmpty(geometry)),
 CHECK(extensions.ST_NPoints(geometry) BETWEEN 4 AND 1000),
 CHECK(extensions.ST_XMin(geometry)>=-180 AND extensions.ST_XMax(geometry)<=180 AND extensions.ST_YMin(geometry)>=-85.0511 AND extensions.ST_YMax(geometry)<=85.0511 AND extensions.ST_XMax(geometry)-extensions.ST_XMin(geometry)<=180),
 CHECK(support_image_object=project_id::text||'/prompts/'||id::text||'/image.tif'),
 CHECK(support_mask_object=project_id::text||'/prompts/'||id::text||'/mask.tif')
);
CREATE INDEX visual_prompts_project_idx ON public.visual_prompts(project_id);
CREATE INDEX visual_prompts_raster_idx ON public.visual_prompts(raster_asset_id);
CREATE INDEX visual_prompts_creator_idx ON public.visual_prompts(created_by);
ALTER TABLE public.visual_prompts ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.visual_prompts FROM anon,authenticated;
GRANT SELECT,INSERT ON public.visual_prompts TO authenticated;
CREATE POLICY prompt_read ON public.visual_prompts FOR SELECT TO authenticated USING(geoai_internal.project_role(project_id) IS NOT NULL);
CREATE POLICY prompt_create ON public.visual_prompts FOR INSERT TO authenticated WITH CHECK(geoai_internal.project_role(project_id) IN ('owner','editor') AND created_by=(SELECT auth.uid()));
NOTIFY pgrst,'reload schema';
