-- Preserve legacy storage namespaces and bytes; project ownership becomes a link.
ALTER TABLE public.raster_assets DROP CONSTRAINT raster_assets_project_id_fkey;
ALTER TABLE public.raster_assets DROP CONSTRAINT raster_assets_created_by_fkey;
ALTER TABLE public.raster_assets ALTER COLUMN created_by DROP NOT NULL;
ALTER TABLE public.raster_assets ADD FOREIGN KEY(created_by) REFERENCES auth.users(id) ON DELETE SET NULL;
ALTER TABLE public.raster_assets ADD COLUMN name text, ADD COLUMN owner_id uuid REFERENCES auth.users(id) ON DELETE SET NULL, ADD COLUMN deleted_at timestamptz;
UPDATE public.raster_assets r SET name=r.filename,owner_id=p.owner_id FROM public.projects p WHERE p.id=r.project_id;
ALTER TABLE public.raster_assets ALTER COLUMN name SET NOT NULL;
ALTER TABLE public.raster_assets ADD CONSTRAINT asset_name_check CHECK(length(trim(name)) BETWEEN 1 AND 255);
CREATE INDEX raster_checksum_idx ON public.raster_assets(checksum) WHERE deleted_at IS NULL;
CREATE TABLE public.project_assets(project_id uuid NOT NULL REFERENCES public.projects(id) ON DELETE CASCADE,raster_asset_id uuid NOT NULL REFERENCES public.raster_assets(id),display_name text NOT NULL CHECK(length(trim(display_name)) BETWEEN 1 AND 255),created_at timestamptz NOT NULL DEFAULT now(),deleted_at timestamptz,PRIMARY KEY(project_id,raster_asset_id));
INSERT INTO public.project_assets(project_id,raster_asset_id,display_name) SELECT project_id,id,filename FROM public.raster_assets;
ALTER TABLE public.project_assets ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.project_assets FROM anon,authenticated;
GRANT SELECT ON public.project_assets TO authenticated;
CREATE INDEX project_assets_asset_idx ON public.project_assets(raster_asset_id) WHERE deleted_at IS NULL;
CREATE POLICY project_asset_read ON public.project_assets FOR SELECT TO authenticated USING(geoai_internal.project_role(project_id) IS NOT NULL);
CREATE FUNCTION geoai_internal.can_read_asset(asset uuid) RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER SET search_path='' AS $$
 SELECT auth.uid() IS NOT NULL AND (geoai_internal.is_platform_admin() OR EXISTS(SELECT 1 FROM public.raster_assets r WHERE r.id=asset AND r.owner_id=auth.uid()) OR EXISTS(SELECT 1 FROM public.project_assets p WHERE p.raster_asset_id=asset AND p.deleted_at IS NULL AND geoai_internal.project_role(p.project_id) IS NOT NULL) OR EXISTS(SELECT 1 FROM public.jobs j WHERE j.raster_asset_id=asset AND geoai_internal.project_role(j.project_id) IS NOT NULL));
$$;
REVOKE ALL ON FUNCTION geoai_internal.can_read_asset(uuid) FROM PUBLIC,anon;
GRANT EXECUTE ON FUNCTION geoai_internal.can_read_asset(uuid) TO authenticated;
CREATE FUNCTION geoai_internal.linked_raster(project uuid,asset uuid) RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER SET search_path='' AS $$ SELECT EXISTS(SELECT 1 FROM public.project_assets p JOIN public.raster_assets r ON r.id=p.raster_asset_id WHERE p.project_id=project AND r.id=asset AND p.deleted_at IS NULL AND r.deleted_at IS NULL) $$;
REVOKE ALL ON FUNCTION geoai_internal.linked_raster(uuid,uuid) FROM PUBLIC,anon;
GRANT EXECUTE ON FUNCTION geoai_internal.linked_raster(uuid,uuid) TO authenticated;
DROP POLICY raster_read ON public.raster_assets;
CREATE POLICY raster_read ON public.raster_assets FOR SELECT TO authenticated USING(geoai_internal.can_read_asset(id));
DROP POLICY raster_retry ON public.raster_assets;
CREATE POLICY raster_retry ON public.raster_assets FOR UPDATE TO authenticated USING(deleted_at IS NULL AND (owner_id=auth.uid() OR geoai_internal.is_platform_admin() OR EXISTS(SELECT 1 FROM public.project_assets p WHERE p.raster_asset_id=id AND p.deleted_at IS NULL AND geoai_internal.project_role(p.project_id) IN ('owner','editor')))) WITH CHECK(deleted_at IS NULL);
CREATE FUNCTION geoai_internal.register_asset() RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
BEGIN
 IF TG_WHEN='BEFORE' THEN
  NEW.name=COALESCE(NEW.name,NEW.filename);SELECT owner_id INTO NEW.owner_id FROM public.projects WHERE id=NEW.project_id;RETURN NEW;
 END IF;
 INSERT INTO public.project_assets(project_id,raster_asset_id,display_name) VALUES(NEW.project_id,NEW.id,NEW.filename);RETURN NEW;
END $$;
REVOKE ALL ON FUNCTION geoai_internal.register_asset() FROM PUBLIC,anon,authenticated;
CREATE TRIGGER register_asset_before BEFORE INSERT ON public.raster_assets FOR EACH ROW EXECUTE FUNCTION geoai_internal.register_asset();
CREATE TRIGGER register_asset_after AFTER INSERT ON public.raster_assets FOR EACH ROW EXECUTE FUNCTION geoai_internal.register_asset();
DO $$ DECLARE cols text; BEGIN
 SELECT string_agg(CASE column_name WHEN 'project_id' THEN 'p.project_id' WHEN 'filename' THEN 'p.display_name AS filename' ELSE 'r.'||quote_ident(column_name) END,',' ORDER BY ordinal_position) INTO cols FROM information_schema.columns WHERE table_schema='public' AND table_name='raster_assets';
 EXECUTE 'CREATE VIEW public.project_rasters WITH (security_invoker=true) AS SELECT '||cols||',r.project_id AS storage_project_id FROM public.raster_assets r JOIN public.project_assets p ON p.raster_asset_id=r.id WHERE p.deleted_at IS NULL AND r.deleted_at IS NULL';
END $$;
GRANT SELECT ON public.project_rasters TO authenticated;
DO $$ DECLARE table_name text;n text;BEGIN
 FOREACH table_name IN ARRAY ARRAY['visual_prompts','jobs'] LOOP
  FOR n IN SELECT conname FROM pg_constraint WHERE conrelid=('public.'||table_name)::regclass AND confrelid='public.raster_assets'::regclass AND contype='f' LOOP EXECUTE format('ALTER TABLE public.%I DROP CONSTRAINT %I',table_name,n);END LOOP;
  EXECUTE format('ALTER TABLE public.%I ADD FOREIGN KEY(raster_asset_id) REFERENCES public.raster_assets(id)',table_name);
 END LOOP;
END $$;
CREATE FUNCTION geoai_internal.guard_project_raster() RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$ BEGIN
 IF NEW.raster_asset_id IS NOT NULL AND NOT geoai_internal.linked_raster(NEW.project_id,NEW.raster_asset_id) THEN RAISE EXCEPTION 'Raster is not linked to project' USING ERRCODE='23514';END IF;RETURN NEW;
END $$;
REVOKE ALL ON FUNCTION geoai_internal.guard_project_raster() FROM PUBLIC,anon,authenticated;
CREATE TRIGGER project_raster_insert BEFORE INSERT ON public.visual_prompts FOR EACH ROW EXECUTE FUNCTION geoai_internal.guard_project_raster();
CREATE TRIGGER project_raster_insert BEFORE INSERT ON public.jobs FOR EACH ROW EXECUTE FUNCTION geoai_internal.guard_project_raster();
CREATE FUNCTION geoai_internal.manage_project_asset(project uuid,asset uuid,operation text,alias text DEFAULT NULL) RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
DECLARE r public.raster_assets;
BEGIN
 IF geoai_internal.project_role(project) IS NULL OR geoai_internal.project_role(project) NOT IN ('owner','editor') THEN RAISE EXCEPTION 'Editor access required' USING ERRCODE='42501';END IF;
 SELECT * INTO r FROM public.raster_assets WHERE id=asset FOR UPDATE;
 IF NOT FOUND OR r.deleted_at IS NOT NULL OR NOT geoai_internal.can_read_asset(asset) THEN RAISE EXCEPTION 'Asset unavailable' USING ERRCODE='42501';END IF;
 IF operation='link' THEN INSERT INTO public.project_assets(project_id,raster_asset_id,display_name) VALUES(project,asset,r.name) ON CONFLICT(project_id,raster_asset_id) DO UPDATE SET deleted_at=NULL;
 ELSIF operation='rename' THEN UPDATE public.project_assets SET display_name=alias WHERE project_id=project AND raster_asset_id=asset AND deleted_at IS NULL;IF NOT FOUND THEN RAISE EXCEPTION 'Link missing' USING ERRCODE='23514';END IF;
 ELSIF operation='unlink' THEN UPDATE public.project_assets SET deleted_at=now() WHERE project_id=project AND raster_asset_id=asset AND deleted_at IS NULL;
 ELSE RAISE EXCEPTION 'Invalid operation' USING ERRCODE='23514';END IF;
END $$;
REVOKE ALL ON FUNCTION geoai_internal.manage_project_asset(uuid,uuid,text,text) FROM PUBLIC,anon;
GRANT EXECUTE ON FUNCTION geoai_internal.manage_project_asset(uuid,uuid,text,text) TO authenticated;
CREATE FUNCTION geoai_internal.manage_raster_asset(asset uuid,operation text,new_name text DEFAULT NULL) RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
DECLARE r public.raster_assets;uses integer;
BEGIN
 SELECT * INTO r FROM public.raster_assets WHERE id=asset FOR UPDATE;
 IF NOT FOUND OR auth.uid() IS NULL OR NOT (COALESCE(r.owner_id=auth.uid(),false) OR geoai_internal.is_platform_admin()) THEN RAISE EXCEPTION 'Asset owner access required' USING ERRCODE='42501';END IF;
 IF r.deleted_at IS NOT NULL THEN RAISE EXCEPTION 'Asset deleted' USING ERRCODE='23514';END IF;
 IF operation='rename' THEN UPDATE public.raster_assets SET name=new_name WHERE id=asset;
 ELSIF operation='delete' THEN
  SELECT count(*) INTO uses FROM public.project_assets WHERE raster_asset_id=asset AND deleted_at IS NULL;
  IF uses>0 THEN RAISE EXCEPTION 'Asset is still used by % projects',uses USING ERRCODE='23514';END IF;
  IF r.status IN ('uploaded','processing') THEN RAISE EXCEPTION 'Processing must finish before deletion' USING ERRCODE='23514';END IF;
  UPDATE public.raster_assets SET deleted_at=now() WHERE id=asset;
 ELSE RAISE EXCEPTION 'Invalid operation' USING ERRCODE='23514';END IF;
END $$;
REVOKE ALL ON FUNCTION geoai_internal.manage_raster_asset(uuid,text,text) FROM PUBLIC,anon;
GRANT EXECUTE ON FUNCTION geoai_internal.manage_raster_asset(uuid,text,text) TO authenticated;
CREATE FUNCTION geoai_internal.asset_usage_count(asset uuid) RETURNS bigint LANGUAGE sql STABLE SECURITY DEFINER SET search_path='' AS $$ SELECT CASE WHEN geoai_internal.can_read_asset(asset) THEN (SELECT count(*) FROM public.project_assets WHERE raster_asset_id=asset AND deleted_at IS NULL) ELSE NULL END $$;
REVOKE ALL ON FUNCTION geoai_internal.asset_usage_count(uuid) FROM PUBLIC,anon;
GRANT EXECUTE ON FUNCTION geoai_internal.asset_usage_count(uuid) TO authenticated;

-- Resolve geometry comparison explicitly under a locked search_path.
CREATE OR REPLACE FUNCTION geoai_internal.guard_spatial_version() RETURNS trigger LANGUAGE plpgsql SET search_path='' AS $$
BEGIN
 IF OLD.deleted_at IS NOT NULL THEN RAISE EXCEPTION 'Resource deleted' USING ERRCODE='23514'; END IF;
 IF TG_TABLE_NAME='visual_prompts' THEN
  IF extensions.ST_AsEWKB(NEW.geometry) IS DISTINCT FROM extensions.ST_AsEWKB(OLD.geometry) AND (NEW.artifact_version IS NULL OR NEW.artifact_version IS NOT DISTINCT FROM OLD.artifact_version) THEN
   RAISE EXCEPTION 'Geometry requires newly generated support artifacts' USING ERRCODE='23514';
  END IF;
  IF NOT EXISTS(SELECT 1 FROM public.project_rasters r WHERE r.id=NEW.raster_asset_id AND r.project_id=NEW.project_id AND extensions.ST_Covers(r.footprint,NEW.geometry)) THEN
   RAISE EXCEPTION 'Prompt outside source raster' USING ERRCODE='23514';
  END IF;
 END IF;
 NEW.revision=OLD.revision+1; NEW.updated_at=now(); NEW.updated_by=auth.uid();
 RETURN NEW;
END $$;

CREATE OR REPLACE FUNCTION geoai_internal.validate_tile_job() RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
BEGIN
 IF NEW.kind='geoextract' AND NOT EXISTS(SELECT 1 FROM public.visual_prompts p WHERE p.id=NEW.prompt_id AND p.raster_asset_id=NEW.raster_asset_id AND p.project_id=NEW.project_id) THEN
  RAISE EXCEPTION 'P8 prompt source mismatch' USING ERRCODE='23514';
 END IF;
 IF NEW.kind='geoextract_tile' THEN
  IF NOT EXISTS(SELECT 1 FROM geoai_internal.model_endpoints e JOIN geoai_internal.model_releases r ON r.id=e.model_release_id WHERE e.id=NEW.model_endpoint_id AND e.enabled AND e.provider_type='lan_http' AND e.model_release_id=NEW.model_release_id AND e.config_revision=NEW.endpoint_revision AND r.checkpoint_digest IS NOT NULL) THEN
   RAISE EXCEPTION 'Endpoint unavailable or changed' USING ERRCODE='23514';
  END IF;
  IF NOT EXISTS(SELECT 1 FROM public.project_rasters r WHERE r.id=NEW.raster_asset_id AND r.project_id=NEW.project_id AND r.status='ready' AND r.width::bigint>=NEW.query_col::bigint+512 AND r.height::bigint>=NEW.query_row::bigint+512 AND r.bands>=3) THEN
   RAISE EXCEPTION 'Invalid source resolution window' USING ERRCODE='23514';
  END IF;
 END IF;
 RETURN NEW;
END $$;
REVOKE ALL ON FUNCTION geoai_internal.validate_tile_job() FROM PUBLIC,anon,authenticated;

-- Additional provenance for future submissions only; historical snapshots are unchanged.
CREATE OR REPLACE FUNCTION geoai_internal.capture_job_inputs(j public.jobs,basis text) RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
DECLARE p public.visual_prompts; a public.aois; s public.raster_assets; q public.raster_assets;
BEGIN
 IF j.kind='diagnostic' THEN RETURN NULL; END IF;
 SELECT * INTO p FROM public.visual_prompts WHERE id=j.prompt_id AND project_id=j.project_id FOR SHARE;
 IF NOT FOUND OR p.deleted_at IS NOT NULL THEN RAISE EXCEPTION 'Prompt unavailable' USING ERRCODE='23514'; END IF;
 SELECT * INTO s FROM public.raster_assets WHERE id=p.raster_asset_id;
 SELECT * INTO q FROM public.raster_assets WHERE id=j.raster_asset_id;
 IF j.aoi_id IS NOT NULL THEN
  SELECT * INTO a FROM public.aois WHERE id=j.aoi_id AND project_id=j.project_id FOR SHARE;
  IF NOT FOUND OR a.deleted_at IS NOT NULL THEN RAISE EXCEPTION 'AOI unavailable' USING ERRCODE='23514'; END IF;
 END IF;
 RETURN jsonb_build_object('schema_version',1,'capture_basis',basis,
  'prompt',jsonb_build_object('id',p.id,'name',p.name,'class_label',p.class_label,'description',p.description,'revision',p.revision,'artifact_version',p.artifact_version,
   'geometry',extensions.ST_AsGeoJSON(p.geometry,17)::jsonb,'raster_asset_id',p.raster_asset_id,'support_image_object',p.support_image_object,'support_mask_object',p.support_mask_object),
  'aoi',CASE WHEN a.id IS NULL THEN NULL ELSE jsonb_build_object('id',a.id,'name',a.name,'revision',a.revision,'geometry',extensions.ST_AsGeoJSON(a.geometry,17)::jsonb) END,
  'support_raster',jsonb_build_object('id',s.id,'storage_project_id',s.project_id,'checksum',s.checksum,'name',s.name,'cog_object_key',s.cog_object_key,'display_ranges',s.display_ranges,'bucket',s.bucket),
  'aoi_geometry_snapshot',CASE WHEN a.id IS NULL THEN NULL ELSE extensions.ST_AsGeoJSON(a.geometry,17)::jsonb END,
  'query_window_bounds',j.query_window_bounds,
  'query_window_pixel_offset',CASE WHEN j.kind='geoextract_tile' THEN jsonb_build_object('col_off',j.query_col,'row_off',j.query_row,'width',512,'height',512) ELSE NULL END,
  'effective_analysis_geometry',CASE WHEN j.kind='geoextract_tile' AND a.id IS NOT NULL AND j.query_window_bounds IS NOT NULL THEN extensions.ST_AsGeoJSON(extensions.ST_Intersection(a.geometry,extensions.ST_SetSRID(extensions.ST_GeomFromGeoJSON(j.query_window_bounds),4326)),17)::jsonb WHEN a.id IS NOT NULL THEN extensions.ST_AsGeoJSON(a.geometry,17)::jsonb ELSE j.query_window_bounds END,
  'effective_prediction_rule',CASE WHEN a.id IS NULL THEN 'prediction intersect valid source pixels' ELSE 'prediction intersect aoi_geometry_snapshot' END,
  'query_raster',jsonb_build_object('id',q.id,'storage_project_id',q.project_id,'checksum',q.checksum,'name',q.name,'cog_object_key',q.cog_object_key,'display_ranges',q.display_ranges,'bucket',q.bucket));
END $$;

NOTIFY pgrst,'reload schema';
