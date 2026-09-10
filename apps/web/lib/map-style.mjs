/** Local WGS84 reference grid. No third-party network or dataset required. */
export function offlineStyle() {
  const features = [];
  for (let lng = -180; lng <= 180; lng += 10) {
    features.push({ type: 'Feature', properties: {}, geometry: { type: 'LineString', coordinates: [[lng, -80], [lng, 80]] } });
  }
  for (let lat = -80; lat <= 80; lat += 10) {
    features.push({ type: 'Feature', properties: {}, geometry: { type: 'LineString', coordinates: [[-180, lat], [180, lat]] } });
  }
  return { version: 8, sources: { grid: { type: 'geojson', data: { type: 'FeatureCollection', features } } },
    layers: [{ id: 'background', type: 'background', paint: { 'background-color': '#edf2ee' } },
      { id: 'grid', type: 'line', source: 'grid', paint: { 'line-color': '#b4c8be', 'line-width': 1, 'line-opacity': 0.55 } }] };
}
