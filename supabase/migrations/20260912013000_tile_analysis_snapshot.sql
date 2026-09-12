-- Additional provenance for future submissions only; historical snapshots are unchanged.
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
  'query_window_pixel_offset',CASE WHEN j.kind='geoextract_tile' THEN jsonb_build_object('col_off',j.query_col,'row_off',j.query_row,'width',512,'height',512) ELSE NULL END,
  'effective_analysis_geometry',CASE WHEN j.kind='geoextract_tile' AND a.id IS NOT NULL AND j.query_window_bounds IS NOT NULL THEN extensions.ST_AsGeoJSON(extensions.ST_Intersection(a.geometry,extensions.ST_SetSRID(extensions.ST_GeomFromGeoJSON(j.query_window_bounds),4326)),17)::jsonb WHEN a.id IS NOT NULL THEN extensions.ST_AsGeoJSON(a.geometry,17)::jsonb ELSE j.query_window_bounds END,
  'effective_prediction_rule',CASE WHEN a.id IS NULL THEN 'prediction intersect valid source pixels' ELSE 'prediction intersect aoi_geometry_snapshot' END,
  'query_raster',jsonb_build_object('id',q.id,'cog_object_key',q.cog_object_key,'display_ranges',q.display_ranges,'bucket',q.bucket));
END $$;
