CREATE TABLE public.aois (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 project_id uuid NOT NULL REFERENCES public.projects(id) ON DELETE CASCADE,
 created_by uuid NOT NULL REFERENCES auth.users(id),
 name text NOT NULL CHECK(length(btrim(name)) BETWEEN 1 AND 120),
 geometry extensions.geometry(Polygon,4326) NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now(),
 CHECK(extensions.ST_IsValid(geometry) AND NOT extensions.ST_IsEmpty(geometry)),
 CHECK(extensions.ST_NPoints(geometry) BETWEEN 4 AND 1000),
 CHECK(extensions.ST_XMin(geometry)>=-180 AND extensions.ST_XMax(geometry)<=180 AND extensions.ST_YMin(geometry)>=-85.0511 AND extensions.ST_YMax(geometry)<=85.0511),
 CHECK(extensions.ST_Area(geometry::extensions.geography)>0)
);
CREATE INDEX aois_project_idx ON public.aois(project_id);
CREATE INDEX aois_creator_idx ON public.aois(created_by);
CREATE INDEX aois_geometry_idx ON public.aois USING gist(geometry);
ALTER TABLE public.aois ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.aois FROM anon,authenticated;
GRANT SELECT ON public.aois TO authenticated;
GRANT INSERT(project_id,created_by,name,geometry) ON public.aois TO authenticated;
CREATE POLICY aoi_read ON public.aois FOR SELECT TO authenticated
 USING(geoai_internal.project_role(project_id) IS NOT NULL);
CREATE POLICY aoi_create ON public.aois FOR INSERT TO authenticated
 WITH CHECK(geoai_internal.project_role(project_id) IN ('owner','editor') AND created_by=(SELECT auth.uid()));
NOTIFY pgrst,'reload schema';
