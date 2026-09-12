import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
test('assistant keeps AOI context and does not render editable pixel coordinates',()=>{
 const source=readFileSync('components/task-assistant.tsx','utf8');
 assert.match(source,/aoi_id/);
 assert.doesNotMatch(source,/<select|高级设置/);
 assert.doesNotMatch(source,/起始行|起始列|type="number"/);
 assert.match(source,/restoreAnswer/);
 assert.match(source,/answer\.draft_id&&/);
 assert.doesNotMatch(source,/onPickWindow|setMapPending/);
 assert.doesNotMatch(source,/在地图上选择测试位置/);
});
test('AOI form keeps internal contract fields without map selection',()=>{
 const source=readFileSync('components/tile-extraction-form.tsx','utf8');
 assert.match(source,/type="hidden" name="query_col"/);
 assert.match(source,/type="hidden" name="query_row"/);
 assert.doesNotMatch(source,/起始列|起始行/);
 assert.doesNotMatch(source,/workspace-tile-selected/);
 assert.doesNotMatch(source,/workspace-select-tile|局部测试/);
});

test('agent is non-modal and project switching retains the existing dirty guard',()=>{
 const floating=readFileSync('components/floating-agent.tsx','utf8');
 const map=readFileSync('components/project-map.tsx','utf8');
 const navigation=readFileSync('components/workspace-navigation.tsx','utf8');
 assert.doesNotMatch(floating,/showModal|backdrop|overflow.*hidden.*body/);
 assert.match(floating,/onPointerDown={drag}/);
 assert.match(map,/new Event\('workspace-switch'\)/);
 assert.match(navigation,/geometryDirty\|\|settingsDirty/);
 assert.match(navigation,/当前工作区有未保存更改/);
 const assistant=readFileSync('components/task-assistant.tsx','utf8');
 assert.match(assistant,/continuation_id:continuation\?\.continuation_id/);
 assert.match(assistant,/sessionStorage.setItem/);
 assert.match(assistant,/answer\.draft_id,confirmed:true/);
});

test('model input remains internal with no point-selection overlay',()=>{
 const map=readFileSync('components/project-map.tsx','utf8');
 assert.doesNotMatch(map,/test-window-line|workspace-select-tile|tilePick/);
 assert.match(map,/workspace-auto-tile/);
});
