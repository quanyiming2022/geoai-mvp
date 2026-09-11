CREATE TABLE geoai_internal.platform_admins(user_id uuid PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,created_at timestamptz NOT NULL DEFAULT now());
ALTER TABLE geoai_internal.platform_admins ENABLE ROW LEVEL SECURITY;
GRANT SELECT ON geoai_internal.platform_admins TO authenticated;
CREATE POLICY admin_self ON geoai_internal.platform_admins FOR SELECT TO authenticated USING(user_id=(SELECT auth.uid()));
CREATE FUNCTION geoai_internal.is_platform_admin() RETURNS boolean LANGUAGE sql STABLE SECURITY INVOKER SET search_path='' AS $$ SELECT EXISTS(SELECT 1 FROM geoai_internal.platform_admins WHERE user_id=auth.uid()) $$;
REVOKE ALL ON FUNCTION geoai_internal.is_platform_admin() FROM PUBLIC,anon;
GRANT EXECUTE ON FUNCTION geoai_internal.is_platform_admin() TO authenticated;
CREATE TABLE geoai_internal.model_releases(
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),name text NOT NULL CHECK(length(name) BETWEEN 1 AND 120),model_name text NOT NULL,model_version text NOT NULL,
 checkpoint_digest text CHECK(checkpoint_digest ~ '^[0-9a-f]{64}$'),usage_policy text NOT NULL CHECK(usage_policy IN ('internal_only','research_only','commercial')),
 created_at timestamptz NOT NULL DEFAULT now(), UNIQUE(model_name,model_version),
 CHECK(model_name NOT ILIKE '%skysense%' OR usage_policy='research_only')
);
CREATE TABLE geoai_internal.model_endpoints(
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),name text NOT NULL CHECK(length(name) BETWEEN 1 AND 120),
 provider_type text NOT NULL CHECK(provider_type IN ('lan_http','runpod','local_gpu','mock')),
 base_url text NOT NULL,health_path text NOT NULL DEFAULT '/health',model_info_path text NOT NULL DEFAULT '/model-info',inference_path text NOT NULL DEFAULT '/v1/inference/oneshot-segmentation',
 request_schema_version text NOT NULL DEFAULT '1' CHECK(request_schema_version='1'),timeout_seconds integer NOT NULL DEFAULT 120 CHECK(timeout_seconds BETWEEN 1 AND 300),
 enabled boolean NOT NULL DEFAULT false,usage_policy text NOT NULL CHECK(usage_policy IN ('internal_only','research_only','commercial')),
 model_release_id uuid NOT NULL REFERENCES geoai_internal.model_releases(id),
 auth_type text NOT NULL DEFAULT 'none' CHECK(auth_type IN ('none','bearer','api_key')),secret_ref text CHECK(secret_ref ~ '^MODEL_ENDPOINT_[A-Z0-9_]+$'),
 health_status text NOT NULL DEFAULT 'offline' CHECK(health_status IN ('offline','healthy','degraded')),health_code text,last_checked_at timestamptz,last_healthy_at timestamptz,model_info jsonb,
 created_at timestamptz NOT NULL DEFAULT now(),updated_at timestamptz NOT NULL DEFAULT now(),
 CHECK((auth_type='none' AND secret_ref IS NULL) OR (auth_type<>'none' AND secret_ref IS NOT NULL))
);
CREATE INDEX endpoints_release_idx ON geoai_internal.model_endpoints(model_release_id);
ALTER TABLE geoai_internal.model_releases ENABLE ROW LEVEL SECURITY;
ALTER TABLE geoai_internal.model_endpoints ENABLE ROW LEVEL SECURITY;
GRANT SELECT,INSERT,UPDATE,DELETE ON geoai_internal.model_releases,geoai_internal.model_endpoints TO authenticated;
CREATE POLICY release_read ON geoai_internal.model_releases FOR SELECT TO authenticated USING(true);
CREATE POLICY release_admin ON geoai_internal.model_releases FOR ALL TO authenticated USING(geoai_internal.is_platform_admin()) WITH CHECK(geoai_internal.is_platform_admin());
CREATE POLICY endpoint_admin ON geoai_internal.model_endpoints FOR ALL TO authenticated USING(geoai_internal.is_platform_admin()) WITH CHECK(geoai_internal.is_platform_admin());
-- Private schema stays outside PostgREST; ordinary users receive a sanitized API projection only.
