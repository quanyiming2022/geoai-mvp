// A UI candidate hint only. The API still validates native COG coverage.
export function coveringRasters(rasters,geometry){
 if(!geometry)return [];
 const points=geometry.coordinates.flat(Infinity);
 const xs=points.filter((_,i)=>i%2===0),ys=points.filter((_,i)=>i%2===1);
 const b=[Math.min(...xs),Math.min(...ys),Math.max(...xs),Math.max(...ys)];
 return rasters.filter(r=>r.bbox&&r.bbox[0]<=b[0]&&r.bbox[1]<=b[1]&&r.bbox[2]>=b[2]&&r.bbox[3]>=b[3]);
}
export function initialRaster(rasters,aoi,explicit){
 if(explicit&&rasters.some(r=>r.id===explicit))return explicit;
 const matches=coveringRasters(rasters,aoi?.geometry);
 return matches.length===1?matches[0].id:rasters.length===1?rasters[0].id:'';
}
