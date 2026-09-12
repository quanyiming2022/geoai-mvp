-- Original prediction geometry/source metadata remain immutable execution evidence.
ALTER TABLE public.extraction_results
 ADD COLUMN result_name text NOT NULL DEFAULT '提取结果' CHECK(length(btrim(result_name)) BETWEEN 1 AND 120),
 ADD COLUMN description text NOT NULL DEFAULT '' CHECK(length(description)<=2000),
 ADD COLUMN current_geometry extensions.geometry(Polygon,4326),
 ADD COLUMN revision integer NOT NULL DEFAULT 1,
 ADD COLUMN updated_at timestamptz NOT NULL DEFAULT now(),
 ADD COLUMN updated_by uuid REFERENCES auth.users(id) ON DELETE SET NULL,
 ADD COLUMN deleted_at timestamptz,
 ADD CONSTRAINT result_current_geometry_valid CHECK(current_geometry IS NULL OR (extensions.ST_IsValid(current_geometry) AND NOT extensions.ST_IsEmpty(current_geometry)));
CREATE TABLE public.result_revisions(
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 result_id uuid NOT NULL REFERENCES public.extraction_results(id) ON DELETE CASCADE,
 revision integer NOT NULL, operation text NOT NULL,
 before_state jsonb NOT NULL, after_state jsonb NOT NULL,
 updated_by uuid REFERENCES auth.users(id) ON DELETE SET NULL,
 created_at timestamptz NOT NULL DEFAULT now(),UNIQUE(result_id,revision)
);
ALTER TABLE public.result_revisions ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.result_revisions FROM PUBLIC,anon,authenticated;
GRANT SELECT ON public.result_revisions TO authenticated;
CREATE POLICY revisions_read ON public.result_revisions FOR SELECT TO authenticated USING(EXISTS(SELECT 1 FROM public.extraction_results r WHERE r.id=result_id));
GRANT UPDATE(result_name,description,current_geometry,deleted_at) ON public.extraction_results TO authenticated;
CREATE FUNCTION geoai_internal.guard_result_resource() RETURNS trigger LANGUAGE plpgsql SET search_path='' AS $$
BEGIN
 IF ROW(NEW.id,NEW.project_id,NEW.job_id,NEW.prompt_id,extensions.ST_AsEWKB(NEW.geometry),NEW.mean_confidence,NEW.max_confidence,NEW.source_metadata,NEW.created_at) IS DISTINCT FROM ROW(OLD.id,OLD.project_id,OLD.job_id,OLD.prompt_id,extensions.ST_AsEWKB(OLD.geometry),OLD.mean_confidence,OLD.max_confidence,OLD.source_metadata,OLD.created_at) THEN
  RAISE EXCEPTION 'Original prediction is immutable' USING ERRCODE='42501';
 END IF;
 IF OLD.deleted_at IS NOT NULL THEN RAISE EXCEPTION 'Result deleted' USING ERRCODE='23514'; END IF;
 NEW.revision=OLD.revision+1;NEW.updated_at=now();NEW.updated_by=auth.uid();
 RETURN NEW;
END $$;
REVOKE ALL ON FUNCTION geoai_internal.guard_result_resource() FROM PUBLIC,anon,authenticated;
CREATE TRIGGER result_resource_guard BEFORE UPDATE ON public.extraction_results FOR EACH ROW EXECUTE FUNCTION geoai_internal.guard_result_resource();
CREATE FUNCTION geoai_internal.audit_result_resource() RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
BEGIN
 INSERT INTO public.result_revisions(result_id,revision,operation,before_state,after_state,updated_by)
 VALUES(NEW.id,NEW.revision,CASE WHEN NEW.deleted_at IS DISTINCT FROM OLD.deleted_at THEN 'delete' WHEN extensions.ST_AsEWKB(NEW.current_geometry) IS DISTINCT FROM extensions.ST_AsEWKB(OLD.current_geometry) THEN 'geometry' WHEN NEW.review_status IS DISTINCT FROM OLD.review_status THEN 'review' ELSE 'metadata' END,
 jsonb_build_object('name',OLD.result_name,'description',OLD.description,'geometry',extensions.ST_AsGeoJSON(COALESCE(OLD.current_geometry,OLD.geometry),17)::jsonb,'review_status',OLD.review_status,'deleted_at',OLD.deleted_at),
 jsonb_build_object('name',NEW.result_name,'description',NEW.description,'geometry',extensions.ST_AsGeoJSON(COALESCE(NEW.current_geometry,NEW.geometry),17)::jsonb,'review_status',NEW.review_status,'deleted_at',NEW.deleted_at),auth.uid());
 RETURN NEW;
END $$;
REVOKE ALL ON FUNCTION geoai_internal.audit_result_resource() FROM PUBLIC,anon,authenticated;
CREATE TRIGGER result_resource_audit AFTER UPDATE ON public.extraction_results FOR EACH ROW EXECUTE FUNCTION geoai_internal.audit_result_resource();
NOTIFY pgrst,'reload schema';
