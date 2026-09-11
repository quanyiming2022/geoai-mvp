-- Resolve geometry comparison explicitly under a locked search_path.
CREATE OR REPLACE FUNCTION geoai_internal.guard_spatial_version() RETURNS trigger LANGUAGE plpgsql SET search_path='' AS $$
BEGIN
 IF OLD.deleted_at IS NOT NULL THEN RAISE EXCEPTION 'Resource deleted' USING ERRCODE='23514'; END IF;
 IF TG_TABLE_NAME='visual_prompts' THEN
  IF extensions.ST_AsEWKB(NEW.geometry) IS DISTINCT FROM extensions.ST_AsEWKB(OLD.geometry) AND (NEW.artifact_version IS NULL OR NEW.artifact_version IS NOT DISTINCT FROM OLD.artifact_version) THEN
   RAISE EXCEPTION 'Geometry requires newly generated support artifacts' USING ERRCODE='23514';
  END IF;
  IF NOT EXISTS(SELECT 1 FROM public.raster_assets r WHERE r.id=NEW.raster_asset_id AND r.project_id=NEW.project_id AND extensions.ST_Covers(r.footprint,NEW.geometry)) THEN
   RAISE EXCEPTION 'Prompt outside source raster' USING ERRCODE='23514';
  END IF;
 END IF;
 NEW.revision=OLD.revision+1; NEW.updated_at=now(); NEW.updated_by=auth.uid();
 RETURN NEW;
END $$;
