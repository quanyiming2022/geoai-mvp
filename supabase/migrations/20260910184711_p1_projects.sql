CREATE TABLE public.projects (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 owner_id uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
 name text NOT NULL CHECK (length(btrim(name)) BETWEEN 1 AND 120),
 description text NOT NULL DEFAULT '' CHECK (length(description) <= 2000),
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX projects_owner_idx ON public.projects(owner_id);
CREATE TABLE public.project_members (
 project_id uuid NOT NULL REFERENCES public.projects(id) ON DELETE CASCADE,
 user_id uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
 role text NOT NULL CHECK (role IN ('editor','viewer')),
 created_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(project_id,user_id)
);
CREATE INDEX project_members_user_idx ON public.project_members(user_id);
ALTER TABLE public.projects ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.project_members ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.projects, public.project_members FROM anon, authenticated;
GRANT SELECT ON public.projects, public.project_members TO authenticated;
GRANT INSERT(owner_id,name,description) ON public.projects TO authenticated;
GRANT UPDATE(name,description) ON public.projects TO authenticated;
GRANT INSERT(project_id,user_id,role), UPDATE(role), DELETE ON public.project_members TO authenticated;

-- Internal permission lookups avoid recursive projects/members RLS. No arbitrary user argument.
-- Functions only expose the caller's permission, never rows, secrets or user directories.
CREATE FUNCTION geoai_internal.project_role(target uuid) RETURNS text
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = '' AS $$
 SELECT CASE WHEN p.owner_id = (SELECT auth.uid()) THEN 'owner'
 ELSE (SELECT m.role FROM public.project_members m
       WHERE m.project_id = target AND m.user_id = (SELECT auth.uid())) END
 FROM public.projects p WHERE p.id = target AND (SELECT auth.uid()) IS NOT NULL
$$;
REVOKE ALL ON FUNCTION geoai_internal.project_role(uuid) FROM PUBLIC, anon;
GRANT USAGE ON SCHEMA geoai_internal TO authenticated;
GRANT EXECUTE ON FUNCTION geoai_internal.project_role(uuid) TO authenticated;

CREATE POLICY project_read ON public.projects FOR SELECT TO authenticated
 USING (geoai_internal.project_role(id) IS NOT NULL);
CREATE POLICY project_create ON public.projects FOR INSERT TO authenticated
 WITH CHECK (owner_id = (SELECT auth.uid()));
CREATE POLICY project_edit ON public.projects FOR UPDATE TO authenticated
 USING (geoai_internal.project_role(id) IN ('owner','editor'))
 WITH CHECK (geoai_internal.project_role(id) IN ('owner','editor'));
CREATE POLICY member_read ON public.project_members FOR SELECT TO authenticated
 USING (geoai_internal.project_role(project_id) IS NOT NULL);
CREATE POLICY member_add ON public.project_members FOR INSERT TO authenticated
 WITH CHECK (geoai_internal.project_role(project_id) = 'owner' AND user_id <> (SELECT auth.uid()));
CREATE POLICY member_edit ON public.project_members FOR UPDATE TO authenticated
 USING (geoai_internal.project_role(project_id) = 'owner')
 WITH CHECK (geoai_internal.project_role(project_id) = 'owner' AND user_id <> (SELECT auth.uid()));
CREATE POLICY member_remove ON public.project_members FOR DELETE TO authenticated
 USING (geoai_internal.project_role(project_id) = 'owner');
NOTIFY pgrst, 'reload schema';
