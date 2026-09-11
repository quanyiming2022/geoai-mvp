CREATE TABLE public.raster_assets (
 id uuid PRIMARY KEY,
 project_id uuid NOT NULL REFERENCES public.projects(id) ON DELETE CASCADE,
 created_by uuid NOT NULL REFERENCES auth.users(id),
 filename text NOT NULL CHECK (length(filename) BETWEEN 1 AND 255),
 bucket text NOT NULL,
 object_key text NOT NULL UNIQUE,
 mime_type text NOT NULL DEFAULT 'image/tiff' CHECK (mime_type = 'image/tiff'),
 size bigint NOT NULL CHECK (size > 0),
 checksum text NOT NULL CHECK (checksum ~ '^[0-9a-f]{64}$'),
 status text NOT NULL DEFAULT 'uploaded' CHECK (status IN ('uploaded','processing','ready','failed')),
 error_code text,
 created_at timestamptz NOT NULL DEFAULT now(),
 CHECK (object_key = project_id::text || '/rasters/' || id::text || '/source.tif')
);
CREATE INDEX raster_assets_project_idx ON public.raster_assets(project_id);
CREATE INDEX raster_assets_creator_idx ON public.raster_assets(created_by);
ALTER TABLE public.raster_assets ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.raster_assets FROM anon, authenticated;
GRANT SELECT ON public.raster_assets TO authenticated;
GRANT INSERT(id,project_id,created_by,filename,bucket,object_key,size,checksum) ON public.raster_assets TO authenticated;
CREATE POLICY raster_read ON public.raster_assets FOR SELECT TO authenticated
 USING (geoai_internal.project_role(project_id) IS NOT NULL);
CREATE POLICY raster_upload ON public.raster_assets FOR INSERT TO authenticated
 WITH CHECK (geoai_internal.project_role(project_id) IN ('owner','editor') AND created_by = (SELECT auth.uid()));
NOTIFY pgrst, 'reload schema';
