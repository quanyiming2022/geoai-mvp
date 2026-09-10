import { test } from 'node:test';
import assert from 'node:assert/strict';
import { needsRefresh } from '../lib/token-expiry.mjs';
const token = exp => `header.${Buffer.from(JSON.stringify({ exp })).toString('base64url')}.signature`;
test('refresh present expired and nearly expired cookies; do not trust claims for authorization', () => {
  const now = 1000000;
  assert.equal(needsRefresh(token(900), now), true);
  assert.equal(needsRefresh(token(1059), now), true);
  assert.equal(needsRefresh(token(1200), now), false);
  assert.equal(needsRefresh('invalid', now), true);
  assert.equal(needsRefresh(undefined, now), true);
});
