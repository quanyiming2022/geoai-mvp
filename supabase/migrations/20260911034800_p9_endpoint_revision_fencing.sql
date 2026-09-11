ALTER TABLE geoai_internal.model_endpoints ADD COLUMN config_revision bigint NOT NULL DEFAULT 1;
CREATE FUNCTION geoai_internal.invalidate_endpoint_configuration() RETURNS trigger LANGUAGE plpgsql SET search_path='' AS $$
BEGIN
 IF ROW(NEW.name,NEW.provider_type,NEW.base_url,NEW.health_path,NEW.model_info_path,NEW.inference_path,NEW.request_schema_version,NEW.timeout_seconds,NEW.enabled,NEW.usage_policy,NEW.model_release_id,NEW.auth_type,NEW.secret_ref)
 IS DISTINCT FROM ROW(OLD.name,OLD.provider_type,OLD.base_url,OLD.health_path,OLD.model_info_path,OLD.inference_path,OLD.request_schema_version,OLD.timeout_seconds,OLD.enabled,OLD.usage_policy,OLD.model_release_id,OLD.auth_type,OLD.secret_ref)
 OR NEW.config_revision IS DISTINCT FROM OLD.config_revision THEN
  NEW.config_revision=OLD.config_revision+1;
  NEW.updated_at=now(); NEW.health_status='offline'; NEW.health_code=NULL;
  NEW.model_info=NULL; NEW.last_checked_at=NULL; NEW.last_healthy_at=NULL;
 END IF;
 RETURN NEW;
END $$;
REVOKE ALL ON FUNCTION geoai_internal.invalidate_endpoint_configuration() FROM PUBLIC,anon,authenticated;
CREATE TRIGGER endpoint_configuration_revision BEFORE UPDATE ON geoai_internal.model_endpoints FOR EACH ROW EXECUTE FUNCTION geoai_internal.invalidate_endpoint_configuration();
CREATE FUNCTION geoai_internal.invalidate_release_endpoints() RETURNS trigger LANGUAGE plpgsql SET search_path='' AS $$
BEGIN
 UPDATE geoai_internal.model_endpoints SET usage_policy=NEW.usage_policy,config_revision=config_revision+1 WHERE model_release_id=NEW.id;
 RETURN NEW;
END $$;
REVOKE ALL ON FUNCTION geoai_internal.invalidate_release_endpoints() FROM PUBLIC,anon,authenticated;
CREATE TRIGGER release_endpoint_revision AFTER UPDATE ON geoai_internal.model_releases FOR EACH ROW EXECUTE FUNCTION geoai_internal.invalidate_release_endpoints();
