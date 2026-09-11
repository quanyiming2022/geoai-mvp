ALTER TABLE public.raster_assets
 ADD COLUMN width integer, ADD COLUMN height integer, ADD COLUMN bands integer,
 ADD COLUMN dtype text, ADD COLUMN nodata double precision, ADD COLUMN crs text,
 ADD COLUMN resolution double precision[], ADD COLUMN bbox double precision[],
 ADD COLUMN footprint extensions.geometry(Polygon,4326),
 ADD COLUMN cog_object_key text, ADD COLUMN thumbnail_object_key text,
 ADD COLUMN processing_token uuid, ADD COLUMN started_at timestamptz, ADD COLUMN finished_at timestamptz;
CREATE INDEX raster_assets_footprint_idx ON public.raster_assets USING gist(footprint);
CREATE INDEX raster_assets_processing_idx ON public.raster_assets(status,created_at);
NOTIFY pgrst, 'reload schema';
