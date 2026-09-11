ALTER TABLE public.jobs ADD COLUMN model_endpoint_id uuid REFERENCES geoai_internal.model_endpoints(id), ADD COLUMN model_release_id uuid REFERENCES geoai_internal.model_releases(id), ADD COLUMN endpoint_revision bigint, ADD COLUMN query_col integer, ADD COLUMN query_row integer, ADD COLUMN seed bigint;
ALTER TABLE public.jobs DROP CONSTRAINT jobs_kind_check;
ALTER TABLE public.jobs ADD CONSTRAINT jobs_kind_check CHECK(kind IN ('diagnostic','geoextract','geoextract_tile'));
ALTER TABLE public.jobs DROP CONSTRAINT job_inputs_check;
ALTER TABLE public.jobs ADD CONSTRAINT job_inputs_check CHECK(
 (kind='diagnostic' AND raster_asset_id IS NULL AND prompt_id IS NULL AND aoi_id IS NULL) OR
 (kind='geoextract' AND raster_asset_id IS NOT NULL AND prompt_id IS NOT NULL AND aoi_id IS NOT NULL) OR
 (kind='geoextract_tile' AND raster_asset_id IS NOT NULL AND prompt_id IS NOT NULL AND aoi_id IS NULL));
ALTER TABLE public.jobs ADD CONSTRAINT tile_inputs_check CHECK(
 (kind<>'geoextract_tile' AND model_endpoint_id IS NULL AND model_release_id IS NULL AND endpoint_revision IS NULL AND query_col IS NULL AND query_row IS NULL AND seed IS NULL) OR
 (kind='geoextract_tile' AND model_endpoint_id IS NOT NULL AND model_release_id IS NOT NULL AND endpoint_revision IS NOT NULL AND query_col IS NOT NULL AND query_col>=0 AND query_row IS NOT NULL AND query_row>=0 AND seed IS NOT NULL AND seed BETWEEN 0 AND 4294967295));
ALTER TABLE public.visual_prompts ADD CONSTRAINT prompt_project_unique UNIQUE(id,project_id);
-- Replace only the composite same-raster FK; a trigger preserves that rule for P8.
DO $$ DECLARE n text; BEGIN
 FOR n IN SELECT conname FROM pg_constraint WHERE conrelid='public.jobs'::regclass AND confrelid='public.visual_prompts'::regclass AND contype='f' LOOP
  EXECUTE format('ALTER TABLE public.jobs DROP CONSTRAINT %I',n);
 END LOOP;
END $$;
ALTER TABLE public.jobs ADD FOREIGN KEY(prompt_id,project_id) REFERENCES public.visual_prompts(id,project_id);
GRANT INSERT(model_endpoint_id,model_release_id,endpoint_revision,query_col,query_row,seed) ON public.jobs TO authenticated;
CREATE INDEX jobs_endpoint_idx ON public.jobs(model_endpoint_id);
CREATE INDEX jobs_release_idx ON public.jobs(model_release_id);
-- Only sanitized enabled endpoints are available to project users; origins/secrets stay private.
CREATE FUNCTION geoai_internal.available_model_endpoints() RETURNS TABLE(id uuid,name text,model_release_id uuid,model_name text,model_version text,usage_policy text,config_revision bigint,health_status text) LANGUAGE sql STABLE SECURITY DEFINER SET search_path='' AS $$
 SELECT e.id,e.name,r.id,r.model_name,r.model_version,r.usage_policy,e.config_revision,e.health_status FROM geoai_internal.model_endpoints e JOIN geoai_internal.model_releases r ON r.id=e.model_release_id WHERE auth.uid() IS NOT NULL AND e.enabled AND e.provider_type='lan_http' AND r.checkpoint_digest IS NOT NULL;
$$;
REVOKE ALL ON FUNCTION geoai_internal.available_model_endpoints() FROM PUBLIC,anon;
GRANT EXECUTE ON FUNCTION geoai_internal.available_model_endpoints() TO authenticated;
CREATE FUNCTION geoai_internal.validate_tile_job() RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
BEGIN
 IF NEW.kind='geoextract' AND NOT EXISTS(SELECT 1 FROM public.visual_prompts p WHERE p.id=NEW.prompt_id AND p.raster_asset_id=NEW.raster_asset_id AND p.project_id=NEW.project_id) THEN
  RAISE EXCEPTION 'P8 prompt source mismatch' USING ERRCODE='23514';
 END IF;
 IF NEW.kind='geoextract_tile' THEN
  IF NOT EXISTS(SELECT 1 FROM geoai_internal.model_endpoints e JOIN geoai_internal.model_releases r ON r.id=e.model_release_id WHERE e.id=NEW.model_endpoint_id AND e.enabled AND e.provider_type='lan_http' AND e.model_release_id=NEW.model_release_id AND e.config_revision=NEW.endpoint_revision AND r.checkpoint_digest IS NOT NULL) THEN
   RAISE EXCEPTION 'Endpoint unavailable or changed' USING ERRCODE='23514';
  END IF;
  IF NOT EXISTS(SELECT 1 FROM public.raster_assets r WHERE r.id=NEW.raster_asset_id AND r.project_id=NEW.project_id AND r.status='ready' AND r.width::bigint>=NEW.query_col::bigint+512 AND r.height::bigint>=NEW.query_row::bigint+512 AND r.bands>=3) THEN
   RAISE EXCEPTION 'Invalid source resolution window' USING ERRCODE='23514';
  END IF;
 END IF;
 RETURN NEW;
END $$;
REVOKE ALL ON FUNCTION geoai_internal.validate_tile_job() FROM PUBLIC,anon,authenticated;
CREATE TRIGGER tile_job_inputs BEFORE INSERT ON public.jobs FOR EACH ROW EXECUTE FUNCTION geoai_internal.validate_tile_job();
NOTIFY pgrst,'reload schema';
