"use client";
import type * as GeoJSON from 'geojson';
import { useEffect, useRef, useState, useMemo } from 'react';
import type { Map, StyleSpecification, GeoJSONSource } from 'maplibre-gl';
import { offlineStyle } from '../lib/map-style.mjs';
import type { RasterAsset } from '../lib/session';

import { useFormStatus } from 'react-dom';
import { createAoi } from '../app/actions';
function SaveAoi({ valid }: { valid: boolean }) { const { pending } = useFormStatus(); return <button disabled={!valid || pending}>{pending ? '正在保存…' : '保存 AOI'}</button>; }
export type Aoi = { id: string; name: string; area_m2: number; geometry: GeoJSON.Polygon };
export default function ProjectMap({ rasters = [], aois = [], projectId, editable }: { rasters?: RasterAsset[]; aois?: Aoi[]; projectId: string; editable: boolean }) {
  const [mode, setMode] = useState<'polygon' | 'rectangle' | null>(null);
  const [points, setPoints] = useState<[number, number][]>([]);
  const geometry = useMemo<GeoJSON.Polygon | null>(() => mode === 'rectangle' && points.length === 2 ? { type: 'Polygon', coordinates: [[points[0], [points[1][0], points[0][1]], points[1], [points[0][0], points[1][1]], points[0]]] } : mode === 'polygon' && points.length >= 3 ? { type: 'Polygon', coordinates: [[...points, points[0]]] } : null, [mode, points]);
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
      map.addLayer({ id: source, type: 'raster', source, paint: { 'raster-opacity': 0.9 } }, map.getLayer('aoi-fill') ? 'aoi-fill' : map.getLayer('draft-fill') ? 'draft-fill' : undefined);
      if (shown.current.size === 0) map.fitBounds([[raster.bbox[0],raster.bbox[1]],[raster.bbox[2],raster.bbox[3]]],{padding:30,duration:0,maxZoom:17});
      shown.current.add(raster.id);
    }
  }, [rasters,loaded]);
  useEffect(() => {
    const map = instance.current; if (!loaded || !map) return;
    const data: GeoJSON.FeatureCollection = { type: 'FeatureCollection', features: aois.map(a => ({ type: 'Feature', properties: { name: a.name }, geometry: a.geometry })) };
    if (!map.getSource('aois')) {
      map.addSource('aois', { type: 'geojson', data });
      map.addLayer({ id: 'aoi-fill', source: 'aois', type: 'fill', paint: { 'fill-color': '#10b981', 'fill-opacity': 0.18 } });
      map.addLayer({ id: 'aoi-line', source: 'aois', type: 'line', paint: { 'line-color': '#10b981', 'line-width': 3 } });
    } else (map.getSource('aois') as GeoJSONSource).setData(data);
  }, [aois, loaded]);
  useEffect(() => {
    const map = instance.current; if (!loaded || !map || !mode) return;
    map.doubleClickZoom.disable(); map.getCanvas().style.cursor = 'crosshair';
    const click = (event: import('maplibre-gl').MapMouseEvent) => setPoints(old => old.length >= (mode === 'rectangle' ? 2 : 998) ? old : [...old, [event.lngLat.wrap().lng, event.lngLat.lat]]);
    map.on('click', click);
    return () => { map.off('click', click); map.doubleClickZoom.enable(); map.getCanvas().style.cursor = ''; };
  }, [loaded, mode]);
  useEffect(() => {
    const map = instance.current; if (!loaded || !map) return;
    const data: GeoJSON.FeatureCollection = { type: 'FeatureCollection', features: geometry ? [{ type: 'Feature', properties: {}, geometry }] : points.map(coordinates => ({ type: 'Feature', properties: {}, geometry: { type: 'Point', coordinates } })) };
    if (!map.getSource('draft')) {
      map.addSource('draft', { type: 'geojson', data });
      map.addLayer({ id: 'draft-fill', source: 'draft', type: 'fill', filter: ['==', '$type', 'Polygon'], paint: { 'fill-color': '#f59e0b', 'fill-opacity': 0.25 } });
      map.addLayer({ id: 'draft-line', source: 'draft', type: 'line', filter: ['==', '$type', 'Polygon'], paint: { 'line-color': '#f59e0b', 'line-width': 3 } });
      map.addLayer({ id: 'draft-points', source: 'draft', type: 'circle', filter: ['==', '$type', 'Point'], paint: { 'circle-color': '#f59e0b', 'circle-radius': 5 } });
    } else (map.getSource('draft') as GeoJSONSource).setData(data);
  }, [geometry, points, loaded]);
  return <section className="map-panel" aria-label="项目地图"><div className="map-toolbar"><span>离线坐标画布</span><button className="secondary compact" disabled={failed || status !== '地图已就绪'} onClick={() => instance.current?.jumpTo({ center: [0, 0], zoom: 1, bearing: 0, pitch: 0 })}>重置视图</button></div><div className="card"><strong>图层</strong>{rasters.filter(r => r.status === 'ready').map(r => <div key={r.id}><label><input type="checkbox" defaultChecked onChange={e => instance.current?.setLayoutProperty(`raster-${r.id}`, 'visibility', e.target.checked ? 'visible' : 'none')}/>{r.filename}</label><label>透明度 <input aria-label={`${r.filename} 透明度`} type="range" min="0" max="1" step="0.05" defaultValue="0.9" onChange={e => instance.current?.setPaintProperty(`raster-${r.id}`, 'raster-opacity', Number(e.target.value))}/></label></div>)}
    <h3>AOI 研究区域</h3>{aois.map(a => <p key={a.id}>{a.name} · {(a.area_m2 / 10000).toFixed(2)} ha</p>)}
    {editable && <><button type="button" disabled={!loaded} onClick={() => { setPoints([]); setMode('rectangle'); }}>绘制矩形 AOI</button> <button type="button" disabled={!loaded} onClick={() => { setPoints([]); setMode('polygon'); }}>绘制多边形 AOI</button>{mode && <><p role="status">{mode === 'rectangle' ? '在地图点击两个对角点' : '在地图依次点击至少三个顶点'} · 已选 {points.length} 点</p><button className="secondary compact" onClick={() => { setPoints([]); setMode(null); }}>取消绘制</button><form action={createAoi}><input type="hidden" name="project_id" value={projectId}/><input type="hidden" name="geometry" value={geometry ? JSON.stringify(geometry) : ''}/><label>AOI 名称<input name="name" required maxLength={120}/></label><SaveAoi valid={!!geometry && Math.max(...points.map(p => p[0])) - Math.min(...points.map(p => p[0])) <= 180}/><p className="muted">当前 AOI 不支持跨越日期变更线。</p></form></>}</>}
    </div><div className="map-canvas" ref={element}/><div className="map-footer"><span role="status">{status}</span><span data-testid="map-zoom">缩放 {zoom}</span><span>{position}</span><span>WGS84 · EPSG:4326</span></div></section>;
}
