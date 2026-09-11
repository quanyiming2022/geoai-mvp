import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
test('assistant keeps AOI context and does not render editable pixel coordinates',()=>{
 const source=readFileSync('components/task-assistant.tsx','utf8');
 assert.match(source,/choice\('aoi_id','AOI 搜索范围'/);
 assert.doesNotMatch(source,/起始行|起始列|type="number"/);
 assert.match(source,/capability_unavailable/);
 assert.match(source,/在地图上选择单瓦片测试区域/);
});
test('manual single-tile form keeps internal contract fields and map selection',()=>{
 const source=readFileSync('components/tile-extraction-form.tsx','utf8');
 assert.match(source,/type="hidden" name="query_col"/);
 assert.match(source,/type="hidden" name="query_row"/);
 assert.doesNotMatch(source,/起始列|起始行/);
 assert.match(source,/workspace-tile-selected/);
 assert.match(source,/workspace-select-tile/);
});
