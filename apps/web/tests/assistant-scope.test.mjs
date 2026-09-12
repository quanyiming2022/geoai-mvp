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
 assert.doesNotMatch(assistant,/localStorage\.getItem\(storageKey\+'\:current'/);
 assert.doesNotMatch(assistant,/localStorage\.setItem\(storageKey\+'\:current'/);
 assert.doesNotMatch(assistant,/sessionStorage\.getItem\(storageKey\)/);
 assert.doesNotMatch(assistant,/sessionStorage\.setItem\(storageKey,/);
 assert.match(assistant,/storageKey\+'\:conversations'/);
 assert.match(assistant,/answer\.draft_id,confirmed:true/);
});

test('floating assistant has one visible minimize control',()=>{
 const floating=readFileSync('components/floating-agent.tsx','utf8');
 const styles=readFileSync('app/style.css','utf8');
 assert.match(floating,/hidden={open}/);
 assert.match(floating,/aria-label="收起助手"/);
 assert.match(styles,/\.agent-launcher\[hidden\]\s*\{display:none\}/);
});

test('assistant AOI creation resumes from the latest pending task',()=>{
 const assistant=readFileSync('components/task-assistant.tsx','utf8');
 const map=readFileSync('components/project-map.tsx','utf8');
 assert.match(assistant,/resourcePendingRef/);
 assert.match(assistant,/const pending=resourcePendingRef\.current/);
 assert.match(assistant,/workspace-assistant-reset/);
 assert.match(map,/workspace-assistant-reset/);
});

test('mock workflow can create an AOI and selects the saved AOI',()=>{
 const source=readFileSync('components/extraction-form.tsx','utf8');
 assert.match(source,/workspace-agent-ui/);
 assert.match(source,/action:'create_aoi'/);
 assert.match(source,/workspace-resource-created/);
 assert.match(source,/setAoiId\(detail\.id\)/);
});

test('mock workflow reports submission outcome without leaving the workspace',()=>{
 const source=readFileSync('components/extraction-form.tsx','utf8');
 const actions=readFileSync('app/actions.ts','utf8');
 assert.match(source,/await createExtractionJob\(data\)/);
 assert.match(source,/role="status"/);
 assert.match(source,/router\.refresh\(\)/);
 assert.match(actions,/const job=await api<\{id:string\}>/);
 assert.match(actions,/return \{data:job\}/);
});

test('workflow AOI is rejected before save when it exceeds the target raster',()=>{
 const source=readFileSync('components/project-map.tsx','utf8');
 assert.match(source,/geometryInsideRaster/);
 assert.match(source,/previewAoiCoverage/);
 assert.ok(source.indexOf('previewAoiCoverage(data)')<source.indexOf("kind==='prompt'?createPrompt(data):createAoi(data)"));
 assert.match(source,/本次 AOI 未保存，请重新绘制/);
 assert.match(source,/AOI 必须完整位于目标影像内/);
 assert.match(source,/重新绘制/);
});

test('workspace and extraction workflows start without implicit raster or AOI selection',()=>{
 const map=readFileSync('components/project-map.tsx','utf8');
 const mock=readFileSync('components/extraction-form.tsx','utf8');
 const worker=readFileSync('components/tile-extraction-form.tsx','utf8');
 assert.match(map,/useState<string\|null>\(null\)/);
 assert.doesNotMatch(map,/saved\.selectedRaster/);
 assert.doesNotMatch(map,/selectedRaster,selectedObject,selectedResult/);
 assert.match(mock,/const \[aoiId,setAoiId\]=useState\(''\)/);
 assert.doesNotMatch(mock,/useState\(aois\[0\]\?\.id/);
 assert.match(worker,/useState\(initialContext\?\.aoi_id\?\?''\)/);
 assert.match(worker,/useState\(initialContext\?\.raster_id\?\?''\)/);
 assert.doesNotMatch(worker,/aois\.length===1/);
 assert.doesNotMatch(worker,/initialRaster\(/);
});

test('archived assistant conversations can be deleted individually',()=>{
 const source=readFileSync('components/task-assistant.tsx','utf8');
 assert.match(source,/function deleteConversation/);
 assert.match(source,/aria-label=\{`删除历史对话/);
 assert.match(source,/saveConversations\(conversations\.filter/);
});

test('model input remains internal with no point-selection overlay',()=>{
 const map=readFileSync('components/project-map.tsx','utf8');
 assert.doesNotMatch(map,/test-window-line|workspace-select-tile|tilePick/);
 assert.match(map,/workspace-auto-tile/);
});
