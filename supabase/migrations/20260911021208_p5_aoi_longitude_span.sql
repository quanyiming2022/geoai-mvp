ALTER TABLE public.aois ADD CONSTRAINT aois_longitude_span CHECK(extensions.ST_XMax(geometry)-extensions.ST_XMin(geometry)<=180);
