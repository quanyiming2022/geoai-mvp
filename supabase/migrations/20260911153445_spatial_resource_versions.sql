-- Active resource maintenance preserves all historical foreign keys and objects.
ALTER TABLE public.aois ADD COLUMN revision bigint NOT NULL DEFAULT 1,
 ADD COLUMN updated_at timestamptz NOT NULL DEFAULT now(), ADD COLUMN updated_by uuid REFERENCES auth.users(id),
 ADD COLUMN deleted_at timestamptz;
ALTER TABLE public.visual_prompts ADD COLUMN revision bigint NOT NULL DEFAULT 1,
 ADD COLUMN updated_at timestamptz NOT NULL DEFAULT now(), ADD COLUMN updated_by uuid REFERENCES auth.users(id),
 ADD COLUMN deleted_at timestamptz, ADD COLUMN artifact_version uuid;
UPDATE public.aois SET updated_at=created_at,updated_by=created_by;
UPDATE public.visual_prompts SET updated_at=created_at,updated_by=created_by;
GRANT UPDATE(geometry,deleted_at) ON public.aois TO authenticated;
GRANT UPDATE(geometry,class_label,bbox,source_crs,support_image_object,support_mask_object,artifact_version,deleted_at) ON public.visual_prompts TO authenticated;
DO $$ DECLARE item record; BEGIN
 FOR item IN SELECT conname FROM pg_constraint WHERE conrelid='public.visual_prompts'::regclass AND contype='c' AND (pg_get_constraintdef(oid) LIKE '%support_image_object%' OR pg_get_constraintdef(oid) LIKE '%support_mask_object%') LOOP
  EXECUTE format('ALTER TABLE public.visual_prompts DROP CONSTRAINT %I',item.conname);
 END LOOP;
END $$;
ALTER TABLE public.visual_prompts ADD CONSTRAINT prompt_artifact_paths CHECK(
 support_image_object=project_id::text||'/prompts/'||id::text||CASE WHEN artifact_version IS NULL THEN '' ELSE '/versions/'||artifact_version::text END||'/image.tif'
 AND support_mask_object=project_id::text||'/prompts/'||id::text||CASE WHEN artifact_version IS NULL THEN '' ELSE '/versions/'||artifact_version::text END||'/mask.tif');

CREATE TABLE public.spatial_resource_events (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),project_id uuid NOT NULL REFERENCES public.projects(id) ON DELETE CASCADE,
 resource_id uuid NOT NULL,resource_kind text NOT NULL,actor uuid REFERENCES auth.users(id),
 action text NOT NULL,old_revision bigint NOT NULL,new_revision bigint NOT NULL,created_at timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE public.spatial_resource_events ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.spatial_resource_events FROM PUBLIC,anon,authenticated;
GRANT SELECT ON public.spatial_resource_events TO authenticated;
CREATE POLICY spatial_event_read ON public.spatial_resource_events FOR SELECT TO authenticated USING(geoai_internal.project_role(project_id) IS NOT NULL);
CREATE INDEX spatial_event_project_idx ON public.spatial_resource_events(project_id);
CREATE INDEX spatial_event_actor_idx ON public.spatial_resource_events(actor);

CREATE FUNCTION geoai_internal.guard_spatial_version() RETURNS trigger LANGUAGE plpgsql SET search_path='' AS $$
BEGIN
 IF OLD.deleted_at IS NOT NULL THEN RAISE EXCEPTION 'Resource deleted' USING ERRCODE='23514'; END IF;
 IF TG_TABLE_NAME='visual_prompts' THEN
  IF NEW.geometry IS DISTINCT FROM OLD.geometry AND (NEW.artifact_version IS NULL OR NEW.artifact_version IS NOT DISTINCT FROM OLD.artifact_version) THEN
   RAISE EXCEPTION 'Geometry requires newly generated support artifacts' USING ERRCODE='23514';
  END IF;
  IF NOT EXISTS(SELECT 1 FROM public.raster_assets r WHERE r.id=NEW.raster_asset_id AND r.project_id=NEW.project_id AND extensions.ST_Covers(r.footprint,NEW.geometry)) THEN
   RAISE EXCEPTION 'Prompt outside source raster' USING ERRCODE='23514';
  END IF;
 END IF;
 NEW.revision=OLD.revision+1; NEW.updated_at=now(); NEW.updated_by=auth.uid();
 RETURN NEW;
END $$;
REVOKE ALL ON FUNCTION geoai_internal.guard_spatial_version() FROM PUBLIC,anon,authenticated;
CREATE TRIGGER spatial_version BEFORE UPDATE ON public.aois FOR EACH ROW EXECUTE FUNCTION geoai_internal.guard_spatial_version();
CREATE TRIGGER spatial_version BEFORE UPDATE ON public.visual_prompts FOR EACH ROW EXECUTE FUNCTION geoai_internal.guard_spatial_version();
CREATE FUNCTION geoai_internal.audit_spatial_version() RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
BEGIN
 INSERT INTO public.spatial_resource_events(project_id,resource_id,resource_kind,actor,action,old_revision,new_revision)
 VALUES(NEW.project_id,NEW.id,TG_TABLE_NAME,auth.uid(),CASE WHEN NEW.deleted_at IS NULL THEN 'edit' ELSE 'delete' END,OLD.revision,NEW.revision);
 RETURN NEW;
END $$;
REVOKE ALL ON FUNCTION geoai_internal.audit_spatial_version() FROM PUBLIC,anon,authenticated;
CREATE TRIGGER spatial_audit AFTER UPDATE ON public.aois FOR EACH ROW EXECUTE FUNCTION geoai_internal.audit_spatial_version();
CREATE TRIGGER spatial_audit AFTER UPDATE ON public.visual_prompts FOR EACH ROW EXECUTE FUNCTION geoai_internal.audit_spatial_version();

ALTER TABLE public.jobs ADD COLUMN execution_snapshot jsonb;
-- Private helper is not an exposed RPC. Only the insert trigger and migration can call it.
CREATE FUNCTION geoai_internal.capture_job_inputs(j public.jobs,basis text) RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
DECLARE p public.visual_prompts; a public.aois; s public.raster_assets; q public.raster_assets;
BEGIN
 IF j.kind='diagnostic' THEN RETURN NULL; END IF;
 SELECT * INTO p FROM public.visual_prompts WHERE id=j.prompt_id AND project_id=j.project_id FOR SHARE;
 IF NOT FOUND OR p.deleted_at IS NOT NULL THEN RAISE EXCEPTION 'Prompt unavailable' USING ERRCODE='23514'; END IF;
 SELECT * INTO s FROM public.raster_assets WHERE id=p.raster_asset_id AND project_id=j.project_id;
 SELECT * INTO q FROM public.raster_assets WHERE id=j.raster_asset_id AND project_id=j.project_id;
 IF j.aoi_id IS NOT NULL THEN
  SELECT * INTO a FROM public.aois WHERE id=j.aoi_id AND project_id=j.project_id FOR SHARE;
  IF NOT FOUND OR a.deleted_at IS NOT NULL THEN RAISE EXCEPTION 'AOI unavailable' USING ERRCODE='23514'; END IF;
 END IF;
 RETURN jsonb_build_object('schema_version',1,'capture_basis',basis,
  'prompt',jsonb_build_object('id',p.id,'name',p.name,'class_label',p.class_label,'description',p.description,'revision',p.revision,'artifact_version',p.artifact_version,
   'geometry',extensions.ST_AsGeoJSON(p.geometry,17)::jsonb,'raster_asset_id',p.raster_asset_id,'support_image_object',p.support_image_object,'support_mask_object',p.support_mask_object),
  'aoi',CASE WHEN a.id IS NULL THEN NULL ELSE jsonb_build_object('id',a.id,'name',a.name,'revision',a.revision,'geometry',extensions.ST_AsGeoJSON(a.geometry,17)::jsonb) END,
  'support_raster',jsonb_build_object('id',s.id,'cog_object_key',s.cog_object_key,'display_ranges',s.display_ranges,'bucket',s.bucket),
  'query_raster',jsonb_build_object('id',q.id,'cog_object_key',q.cog_object_key,'display_ranges',q.display_ranges,'bucket',q.bucket));
END $$;
REVOKE ALL ON FUNCTION geoai_internal.capture_job_inputs(public.jobs,text) FROM PUBLIC,anon,authenticated;
-- Legacy metadata may have been renamed since submission; do not pretend to reconstruct it.
UPDATE public.jobs j SET execution_snapshot=geoai_internal.capture_job_inputs(j,'legacy_current_state_at_migration') WHERE kind<>'diagnostic';
CREATE FUNCTION geoai_internal.freeze_job_inputs() RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
BEGIN
 IF TG_OP='INSERT' THEN NEW.execution_snapshot=geoai_internal.capture_job_inputs(NEW,'submission');
 ELSIF NEW.execution_snapshot IS DISTINCT FROM OLD.execution_snapshot THEN RAISE EXCEPTION 'Job inputs immutable' USING ERRCODE='42501'; END IF;
 RETURN NEW;
END $$;
REVOKE ALL ON FUNCTION geoai_internal.freeze_job_inputs() FROM PUBLIC,anon,authenticated;
CREATE TRIGGER freeze_job_inputs BEFORE INSERT OR UPDATE ON public.jobs FOR EACH ROW EXECUTE FUNCTION geoai_internal.freeze_job_inputs();
GRANT SELECT(execution_snapshot) ON public.jobs TO authenticated;
NOTIFY pgrst,'reload schema';
