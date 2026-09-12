-- A reusable visual prompt may come from a different project-linked raster.
-- The target/query raster remains authoritative for AOI coverage.
CREATE OR REPLACE FUNCTION geoai_internal.validate_tile_job() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
BEGIN
 IF NEW.kind='geoextract' THEN
  IF NOT EXISTS(
   SELECT 1
   FROM public.project_rasters q
   JOIN public.visual_prompts p ON p.project_id=q.project_id
   JOIN public.aois a ON a.project_id=q.project_id
   WHERE q.id=NEW.raster_asset_id
     AND p.id=NEW.prompt_id
     AND a.id=NEW.aoi_id
     AND q.project_id=NEW.project_id
     AND p.deleted_at IS NULL
     AND a.deleted_at IS NULL
     AND q.status='ready'
     AND extensions.ST_Covers(q.footprint,a.geometry)
  ) THEN
   RAISE EXCEPTION 'Mock inputs unavailable or AOI outside target raster' USING ERRCODE='23514';
  END IF;
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

NOTIFY pgrst,'reload schema';
