import { copyFileSync, mkdirSync } from 'node:fs';
import { createRequire } from 'node:module';
import { dirname, join } from 'node:path';
const dist = join(dirname(createRequire(import.meta.url).resolve('maplibre-gl/package.json')), 'dist');
const dest = join(process.cwd(), 'public', 'maplibre');
mkdirSync(dest, { recursive: true });
for (const file of ['maplibre-gl-worker.mjs', 'maplibre-gl-shared.mjs']) copyFileSync(join(dist, file), join(dest, file));
