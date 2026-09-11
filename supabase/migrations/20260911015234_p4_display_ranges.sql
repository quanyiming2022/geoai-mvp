ALTER TABLE public.raster_assets ADD COLUMN display_ranges jsonb;
NOTIFY pgrst, 'reload schema';
