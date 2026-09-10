import { test } from 'node:test';
import assert from 'node:assert/strict';
import { offlineStyle } from '../lib/map-style.mjs';
test('offline map uses finite WGS84 coordinates and no remote resources', () => {
  const style = offlineStyle();
  assert.equal(style.version, 8);
  assert.ok(style.sources.grid.data.features.length > 40);
  for (const feature of style.sources.grid.data.features) for (const [lng, lat] of feature.geometry.coordinates) {
    assert.ok(Number.isFinite(lng) && lng >= -180 && lng <= 180);
    assert.ok(Number.isFinite(lat) && lat >= -85 && lat <= 85);
  }
  assert.equal(JSON.stringify(style).includes('http'), false);
});
