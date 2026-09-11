-- Only names are mutable; geometry, provenance, objects and job references remain unchanged.
GRANT UPDATE(name) ON public.aois, public.visual_prompts TO authenticated;
CREATE POLICY aoi_rename ON public.aois FOR UPDATE TO authenticated
 USING (geoai_internal.project_role(project_id) IN ('owner','editor'))
 WITH CHECK (geoai_internal.project_role(project_id) IN ('owner','editor'));
CREATE POLICY prompt_rename ON public.visual_prompts FOR UPDATE TO authenticated
 USING (geoai_internal.project_role(project_id) IN ('owner','editor'))
 WITH CHECK (geoai_internal.project_role(project_id) IN ('owner','editor'));
NOTIFY pgrst,'reload schema';
