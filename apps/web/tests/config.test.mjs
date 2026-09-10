import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
test('browser code contains no infrastructure credentials', () => {
  for (const file of ['app/page.tsx', 'app/layout.tsx']) {
    assert.doesNotMatch(readFileSync(new URL('../' + file, import.meta.url), 'utf8'), /SERVICE_ROLE|JWT_SECRET|DATABASE_URL/);
  }
});
