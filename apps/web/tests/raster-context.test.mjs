import {test} from 'node:test';
import assert from 'node:assert/strict';
import {coveringRasters,initialRaster} from '../lib/raster-context.mjs';
test('AOI chooses a unique covering raster only when target is not explicit',()=>{
 const rasters=[{id:'wrong',bbox:[10,10,11,11]},{id:'correct',bbox:[0,0,1,1]}];
 const aoi={geometry:{coordinates:[[[.1,.1],[.3,.1],[.3,.3],[.1,.3],[.1,.1]]]}};
 assert.deepEqual(coveringRasters(rasters,aoi.geometry).map(r=>r.id),['correct']);
 assert.equal(initialRaster(rasters,aoi),'correct');
 assert.equal(initialRaster(rasters,aoi,'wrong'),'wrong');
 assert.equal(initialRaster(rasters,null),'');
});
