"use client";
import { useEffect, useRef, useState } from 'react';
import type { Map, StyleSpecification } from 'maplibre-gl';
import { offlineStyle } from '../lib/map-style.mjs';
import type { RasterAsset } from '../lib/session';

export default function ProjectMap({ rasters = [] }: { rasters?: RasterAsset[] }) {
  const element = useRef<HTMLDivElement>(null);
  const instance = useRef<Map | null>(null);
  const [status, setStatus] = useState('正在加载地图…');
  const [loaded, setLoaded] = useState(false);
  const [failed, setFailed] = useState(false);
  const [position, setPosition] = useState('经度 0.0000 · 纬度 0.0000');
  const [zoom, setZoom] = useState('1.00');
  useEffect(() => {
    let cancelled = false; let map: Map | undefined; let observer: ResizeObserver | undefined; let timeout: ReturnType<typeof setTimeout> | undefined;
    const fail = () => { if (!cancelled) { setFailed(true); setStatus('地图无法加载，请确认浏览器支持 WebGL 后刷新。'); } };
    import('maplibre-gl').then(({ Map: MapClass, NavigationControl, ScaleControl, setWorkerUrl }) => {
      if (cancelled || !element.current) return;
      try {
        setWorkerUrl('/maplibre/maplibre-gl-worker.mjs');
        timeout = setTimeout(fail, 30000);
        map = new MapClass({ container: element.current, style: offlineStyle() as StyleSpecification, center: [0, 0], zoom: 1, maxZoom: 22, attributionControl: false });
        instance.current = map;
        map.addControl(new NavigationControl(), 'top-right');
        map.addControl(new ScaleControl({ unit: 'metric' }), 'bottom-left');
        map.on('load', () => { clearTimeout(timeout); if (!cancelled) { setFailed(false); setStatus('地图已就绪'); setLoaded(true); } });
        map.on('error', fail);
        map.on('zoomend', () => { if (map && !cancelled) setZoom(map.getZoom().toFixed(2)); });
        map.on('mousemove', event => { if (!cancelled) setPosition(`经度 ${event.lngLat.wrap().lng.toFixed(4)} · 纬度 ${event.lngLat.lat.toFixed(4)}`); });
        observer = new ResizeObserver(() => map?.resize()); observer.observe(element.current);
      } catch { fail(); }
    }).catch(fail);
    return () => { cancelled = true; clearTimeout(timeout); observer?.disconnect(); map?.remove(); instance.current = null; };
  }, []);
  const shown = useRef<Set<string>>(new Set());
  useEffect(() => {
    const map = instance.current; if (!loaded || !map) return;
    for (const raster of rasters) {
      if (raster.status !== 'ready' || !raster.bbox || shown.current.has(raster.id)) continue;
      const source = `raster-${raster.id}`;
      map.addSource(source, { type: 'raster', tiles: [`${window.location.origin}/api/rasters/${raster.id}/tiles/{z}/{x}/{y}`], tileSize: 256, bounds: raster.bbox, maxzoom: 22 });
      map.addLayer({ id: source, type: 'raster', source, paint: { 'raster-opacity': 0.9 } });
      if (shown.current.size === 0) map.fitBounds([[raster.bbox[0],raster.bbox[1]],[raster.bbox[2],raster.bbox[3]]],{padding:30,duration:0,maxZoom:17});
      shown.current.add(raster.id);
    }
  }, [rasters,loaded]);
  return <section className="map-panel" aria-label="项目地图"><div className="map-toolbar"><span>离线坐标画布</span><button className="secondary compact" disabled={failed || status !== '地图已就绪'} onClick={() => instance.current?.jumpTo({ center: [0, 0], zoom: 1, bearing: 0, pitch: 0 })}>重置视图</button></div><div className="map-canvas" ref={element}/><div className="map-footer"><span role="status">{status}</span><span data-testid="map-zoom">缩放 {zoom}</span><span>{position}</span><span>WGS84 · EPSG:4326</span></div></section>;
}
