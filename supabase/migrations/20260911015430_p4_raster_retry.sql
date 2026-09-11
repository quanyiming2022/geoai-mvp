GRANT UPDATE(status) ON public.raster_assets TO authenticated;
CREATE POLICY raster_retry ON public.raster_assets FOR UPDATE TO authenticated
 USING (status='failed' AND geoai_internal.project_role(project_id) IN ('owner','editor'))
 WITH CHECK (status='uploaded' AND geoai_internal.project_role(project_id) IN ('owner','editor'));
NOTIFY pgrst, 'reload schema';
