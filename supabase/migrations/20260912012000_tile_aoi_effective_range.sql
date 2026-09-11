-- Optional effective AOI for new tile jobs; no historical snapshot rewrites.
ALTER TABLE public.jobs ADD COLUMN query_window_bounds jsonb;
GRANT INSERT(query_window_bounds),SELECT(query_window_bounds) ON public.jobs TO authenticated;
ALTER TABLE public.jobs DROP CONSTRAINT job_inputs_check;
ALTER TABLE public.jobs ADD CONSTRAINT job_inputs_check CHECK(
 (kind='diagnostic' AND raster_asset_id IS NULL AND prompt_id IS NULL AND aoi_id IS NULL) OR
 (kind='geoextract' AND raster_asset_id IS NOT NULL AND prompt_id IS NOT NULL AND aoi_id IS NOT NULL) OR
 (kind='geoextract_tile' AND raster_asset_id IS NOT NULL AND prompt_id IS NOT NULL));
ALTER TABLE public.jobs ADD CONSTRAINT tile_bounds_check CHECK(query_window_bounds IS NULL OR (kind='geoextract_tile' AND query_window_bounds->>'type'='Polygon'));
CREATE OR REPLACE FUNCTION geoai_internal.capture_job_inputs(j public.jobs,basis text) RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
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
  'aoi_geometry_snapshot',CASE WHEN a.id IS NULL THEN NULL ELSE extensions.ST_AsGeoJSON(a.geometry,17)::jsonb END,
  'query_window_bounds',j.query_window_bounds,
  'effective_prediction_rule',CASE WHEN a.id IS NULL THEN 'prediction intersect valid source pixels' ELSE 'prediction intersect aoi_geometry_snapshot' END,
  'query_raster',jsonb_build_object('id',q.id,'cog_object_key',q.cog_object_key,'display_ranges',q.display_ranges,'bucket',q.bucket));
END $$;
REVOKE ALL ON FUNCTION geoai_internal.capture_job_inputs(public.jobs,text) FROM PUBLIC,anon,authenticated;

CREATE FUNCTION geoai_internal.guard_tile_effective_aoi() RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
DECLARE a extensions.geometry; w extensions.geometry;
BEGIN
 IF TG_OP='UPDATE' THEN
  IF NEW.query_window_bounds IS DISTINCT FROM OLD.query_window_bounds THEN RAISE EXCEPTION 'Query bounds immutable' USING ERRCODE='42501'; END IF;
 ELSIF NEW.kind='geoextract_tile' AND NEW.aoi_id IS NOT NULL THEN
  SELECT geometry INTO a FROM public.aois WHERE id=NEW.aoi_id AND project_id=NEW.project_id AND deleted_at IS NULL;
  IF NOT FOUND OR NEW.query_window_bounds IS NULL THEN RAISE EXCEPTION 'AOI or query bounds unavailable' USING ERRCODE='23514'; END IF;
  w=extensions.ST_SetSRID(extensions.ST_GeomFromGeoJSON(NEW.query_window_bounds),4326);
  IF NOT extensions.ST_IsValid(w) OR extensions.ST_Area(extensions.ST_Intersection(w,a))<=0 THEN RAISE EXCEPTION 'Model window must intersect AOI' USING ERRCODE='23514'; END IF;
 END IF;
 RETURN NEW;
END $$;
REVOKE ALL ON FUNCTION geoai_internal.guard_tile_effective_aoi() FROM PUBLIC,anon,authenticated;
CREATE TRIGGER tile_effective_aoi BEFORE INSERT OR UPDATE ON public.jobs FOR EACH ROW EXECUTE FUNCTION geoai_internal.guard_tile_effective_aoi();
NOTIFY pgrst,'reload schema';
