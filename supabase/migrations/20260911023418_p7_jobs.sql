CREATE TABLE public.jobs (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), project_id uuid NOT NULL REFERENCES public.projects(id) ON DELETE CASCADE,
 created_by uuid NOT NULL REFERENCES auth.users(id), idempotency_key uuid NOT NULL,
 kind text NOT NULL CONSTRAINT jobs_kind_check CHECK(kind IN ('diagnostic')),
 status text NOT NULL DEFAULT 'queued' CHECK(status IN ('queued','running','succeeded','failed','cancelled')),
 progress integer NOT NULL DEFAULT 0 CHECK(progress BETWEEN 0 AND 100), attempts integer NOT NULL DEFAULT 0,
 claim_token uuid, result jsonb, error_code text, created_at timestamptz NOT NULL DEFAULT now(), started_at timestamptz, finished_at timestamptz,
 UNIQUE(project_id,created_by,idempotency_key), UNIQUE(id,project_id)
);
CREATE INDEX jobs_project_idx ON public.jobs(project_id);
CREATE INDEX jobs_creator_idx ON public.jobs(created_by);
CREATE INDEX jobs_queue_idx ON public.jobs(created_at) WHERE status='queued';
ALTER TABLE public.jobs ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.jobs FROM anon,authenticated;
GRANT SELECT ON public.jobs TO authenticated;
GRANT INSERT(project_id,created_by,idempotency_key,kind) ON public.jobs TO authenticated;
GRANT UPDATE(status) ON public.jobs TO authenticated;
CREATE POLICY job_read ON public.jobs FOR SELECT TO authenticated USING(geoai_internal.project_role(project_id) IS NOT NULL);
CREATE POLICY job_create ON public.jobs FOR INSERT TO authenticated WITH CHECK(geoai_internal.project_role(project_id) IN ('owner','editor') AND created_by=(SELECT auth.uid()));
CREATE POLICY job_control ON public.jobs FOR UPDATE TO authenticated USING(status IN ('queued','running','failed') AND geoai_internal.project_role(project_id) IN ('owner','editor')) WITH CHECK(status IN ('queued','cancelled') AND geoai_internal.project_role(project_id) IN ('owner','editor'));
NOTIFY pgrst,'reload schema';
