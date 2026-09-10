-- INSERT RETURNING must see its new owner row without a STABLE function snapshot lookup.
ALTER POLICY project_read ON public.projects USING (owner_id = (SELECT auth.uid()) OR geoai_internal.project_role(id) IS NOT NULL);
NOTIFY pgrst, 'reload schema';
