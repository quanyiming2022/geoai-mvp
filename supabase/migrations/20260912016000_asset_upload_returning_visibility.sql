-- INSERT RETURNING is checked before AFTER INSERT creates the project link.
-- Evaluate the new tuple's owner/uploader directly rather than re-reading it.
DROP POLICY raster_read ON public.raster_assets;
CREATE POLICY raster_read ON public.raster_assets FOR SELECT TO authenticated USING(
 owner_id=auth.uid()
 OR (created_by=auth.uid() AND geoai_internal.project_role(project_id) IN ('owner','editor'))
 OR geoai_internal.can_read_asset(id)
);
NOTIFY pgrst,'reload schema';
