CREATE FUNCTION geoai_internal.validate_job_transition() RETURNS trigger LANGUAGE plpgsql SET search_path='' AS $$
BEGIN
 IF current_user='authenticated' AND NEW.status IS DISTINCT FROM OLD.status THEN
   IF NOT ((OLD.status IN ('queued','running') AND NEW.status='cancelled') OR (OLD.status='failed' AND NEW.status='queued')) THEN
     RAISE EXCEPTION 'Invalid job transition' USING ERRCODE='42501';
   END IF;
   IF NEW.status='cancelled' THEN NEW.finished_at=now(); END IF;
   IF NEW.status='queued' THEN NEW.progress=0; NEW.error_code=NULL; NEW.finished_at=NULL; NEW.result=NULL; END IF;
 END IF;
 RETURN NEW;
END $$;
REVOKE ALL ON FUNCTION geoai_internal.validate_job_transition() FROM PUBLIC,anon,authenticated;
CREATE TRIGGER jobs_transition BEFORE UPDATE ON public.jobs FOR EACH ROW EXECUTE FUNCTION geoai_internal.validate_job_transition();
