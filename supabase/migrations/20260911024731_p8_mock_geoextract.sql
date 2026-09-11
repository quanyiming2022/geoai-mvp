ALTER TABLE public.aois ADD CONSTRAINT aoi_project_unique UNIQUE(id,project_id);
ALTER TABLE public.visual_prompts ADD CONSTRAINT prompt_raster_project_unique UNIQUE(id,raster_asset_id,project_id);
ALTER TABLE public.jobs DROP CONSTRAINT jobs_kind_check;
ALTER TABLE public.jobs ADD COLUMN raster_asset_id uuid, ADD COLUMN prompt_id uuid, ADD COLUMN aoi_id uuid;
ALTER TABLE public.jobs ADD CONSTRAINT jobs_kind_check CHECK(kind IN ('diagnostic','geoextract'));
ALTER TABLE public.jobs ADD CONSTRAINT job_inputs_check CHECK((kind='diagnostic' AND raster_asset_id IS NULL AND prompt_id IS NULL AND aoi_id IS NULL) OR (kind='geoextract' AND raster_asset_id IS NOT NULL AND prompt_id IS NOT NULL AND aoi_id IS NOT NULL));
ALTER TABLE public.jobs ADD FOREIGN KEY(raster_asset_id,project_id) REFERENCES public.raster_assets(id,project_id), ADD FOREIGN KEY(prompt_id,raster_asset_id,project_id) REFERENCES public.visual_prompts(id,raster_asset_id,project_id), ADD FOREIGN KEY(aoi_id,project_id) REFERENCES public.aois(id,project_id);
CREATE INDEX jobs_prompt_idx ON public.jobs(prompt_id);
CREATE INDEX jobs_raster_idx ON public.jobs(raster_asset_id);
CREATE INDEX jobs_aoi_idx ON public.jobs(aoi_id);
GRANT INSERT(raster_asset_id,prompt_id,aoi_id) ON public.jobs TO authenticated;
CREATE TABLE public.extraction_results (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), project_id uuid NOT NULL REFERENCES public.projects(id) ON DELETE CASCADE,
 job_id uuid NOT NULL, prompt_id uuid NOT NULL REFERENCES public.visual_prompts(id),
 geometry extensions.geometry(Polygon,4326) NOT NULL,
 area_m2 double precision GENERATED ALWAYS AS (extensions.ST_Area(geometry::extensions.geography)) STORED,
 mean_confidence double precision NOT NULL CHECK(mean_confidence BETWEEN 0 AND 1),
 max_confidence double precision NOT NULL CHECK(max_confidence BETWEEN 0 AND 1),
 review_status text NOT NULL DEFAULT 'candidate' CHECK(review_status IN ('candidate','accepted','rejected')),
 source_metadata jsonb NOT NULL, created_at timestamptz NOT NULL DEFAULT now(),
 FOREIGN KEY(job_id,project_id) REFERENCES public.jobs(id,project_id) ON DELETE CASCADE,
 CHECK(extensions.ST_IsValid(geometry) AND NOT extensions.ST_IsEmpty(geometry))
);
CREATE INDEX results_project_idx ON public.extraction_results(project_id);
CREATE INDEX results_job_idx ON public.extraction_results(job_id);
CREATE INDEX results_prompt_idx ON public.extraction_results(prompt_id);
CREATE INDEX results_geometry_idx ON public.extraction_results USING gist(geometry);
ALTER TABLE public.extraction_results ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.extraction_results FROM anon,authenticated;
GRANT SELECT ON public.extraction_results TO authenticated;
GRANT UPDATE(review_status) ON public.extraction_results TO authenticated;
CREATE POLICY result_read ON public.extraction_results FOR SELECT TO authenticated USING(geoai_internal.project_role(project_id) IS NOT NULL);
CREATE POLICY result_review ON public.extraction_results FOR UPDATE TO authenticated USING(geoai_internal.project_role(project_id) IN ('owner','editor')) WITH CHECK(geoai_internal.project_role(project_id) IN ('owner','editor'));
CREATE TABLE public.review_actions (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), result_id uuid NOT NULL REFERENCES public.extraction_results(id) ON DELETE CASCADE,
 reviewer uuid NOT NULL REFERENCES auth.users(id), action text NOT NULL CHECK(action IN ('accepted','rejected')), created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX review_result_idx ON public.review_actions(result_id);
CREATE INDEX review_reviewer_idx ON public.review_actions(reviewer);
ALTER TABLE public.review_actions ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.review_actions FROM anon,authenticated;
GRANT SELECT ON public.review_actions TO authenticated;
CREATE POLICY review_read ON public.review_actions FOR SELECT TO authenticated USING(EXISTS(SELECT 1 FROM public.extraction_results r WHERE r.id=result_id));
-- Trigger-only definer writes immutable audit history after column-scoped user updates.
CREATE FUNCTION geoai_internal.audit_result_review() RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
BEGIN
 IF NEW.review_status IS DISTINCT FROM OLD.review_status THEN
   IF NEW.review_status NOT IN ('accepted','rejected') OR auth.uid() IS NULL THEN RAISE EXCEPTION 'Invalid review' USING ERRCODE='42501'; END IF;
   INSERT INTO public.review_actions(result_id,reviewer,action) VALUES(NEW.id,auth.uid(),NEW.review_status);
 END IF;
 RETURN NEW;
END $$;
REVOKE ALL ON FUNCTION geoai_internal.audit_result_review() FROM PUBLIC,anon,authenticated;
CREATE TRIGGER result_review_audit AFTER UPDATE OF review_status ON public.extraction_results FOR EACH ROW EXECUTE FUNCTION geoai_internal.audit_result_review();
NOTIFY pgrst,'reload schema';
