# Workspace Agent v1 — local validation

Validated 2026-09-12 on macOS arm64 with local Next.js/FastAPI/Supabase/Redis/Ollama and the registered LAN SkySense++ Worker. P9C scope fix is separately committed as `d1236bc`; this work continues on `feat/p9-real-model-worker` from frozen P9B `4533a79`.

## Architecture and interaction

`AgentGoal` parses intent and explicit name hints. Authenticated WorkspaceContext supplies current resources, view, jobs, role, model policy and endpoint health. Deterministic resolution rejects invented/unmentioned names and asks only about ambiguous resources. Capability and role checks precede draft creation. Redis continuation records are bound to user/project and expire after 30 minutes; clarification/map callbacks resume the stored goal without another LLM parse. Only explicit selection of the test alternative changes full-AOI intent to a tile test.

Conversation states: READY, NEED_CLARIFICATION, NEED_CONFIRMATION, EXECUTING, COMPLETED, BLOCKED, ERROR. The non-modal, draggable 410px chat window contains history, natural input and contextual buttons; there is no resource configuration form. Map, lists, Inspector and Jobs remain interactive. Position and bounded conversation state persist per user/project in sessionStorage; closing/minimizing preserves them. Refresh starts minimized and restores conversation. A pending map selection can be resumed through its retained action. New conversation explicitly resets the session; it is disabled during active inference.

Live selection and pending execution context are separate. A confirmation uses a server-stored draft, not whichever AOI was most recently clicked. “开始” confirms that draft; a new message uses live selection. Job polling does not replace an unrelated pending clarification/confirmation. Existing manual workflow remains available.

Tools: authenticated context/resource reads, recent job/error/result, map selection/zoom, raster layer visibility, native test-window selection, confirmed existing Job creation, owner-bound cancellation confirmation invoking existing Job control, and the existing guarded project chooser. No shell/SQL/arbitrary URL tools, automatic deletion, SAM, new model adapter, whole-area inference, multi-shot or P10/P11.

## Browser evidence

Isolated ordinary-owner projects and copied SPOT6/approved building geometry were used; original P9B fixtures and source resources were not modified.

| Scenario | Result |
|---|---|
| A: current prompt/range → full AOI | PASS; identified resources, blocked capability, no draft/job, explicit map alternative |
| B: map selection → automatic plan → confirmation → real SkySense++ | PASS; both button and natural “开始” paths |
| C: recent job without ID | PASS; actual status/runtime/result count |
| D: show recent result | PASS; MapLibre selection, fit and Results/Inspector update |
| E: two AOIs/no selection | PASS; AOI choice buttons, click resumes original goal; model-invented name caught and fixed |
| F: actual GPU service offline | PASS; node unavailable, no new job; guaranteed finally restoration, model_loaded true and endpoint healthy |
| Live vs pending | PASS; selected another AOI while confirmation retained original 12aoi |
| Dirty guard | PASS; unfinished AOI → Agent switch → existing unsaved changes dialog; continue stays in project |
| Floating interaction | PASS; map zoom/drag, AOI list, Inspector next result and Jobs expansion while chat open |
| Minimize/drag/reload | PASS; retained history and position; map 808×785 unchanged when opening chat at 1440×900 |

Local screenshots (not committed raster data): `artifacts/agent-v1-final-1440x900.png`, `agent-v1-final-1920x1080.png`, `agent-v1-floating-clarification.png`, `agent-v1-floating-map-wait.png`, `agent-v1-dirty-guard.png`, `agent-v1-offline.png`, `agent-v1-result-map.png`. Earlier `agent-v1-real-plan.png` records the intermediate drawer before the latest non-modal requirement; use final screenshots for UI acceptance.

## Real inference evidence

Both jobs used `synthetic=false`, SkySense++ research-v1, research_only, checkpoint `32a08982baea125f60feb95fe0a04dfe450ec9c12ee846384cbadd8ff6c5661c`. Inputs remain native 512²; seed 57 follows the unchanged manual test default (not a rerun of frozen seed-42 benchmark).

| Job | Native window col,row | Probability mean / std | Foreground ratio | Worker runtime ms | Peak GPU bytes | GIS candidates |
|---|---|---|---|---|---|---|
| acc43a16-c1f2-48b5-8b0d-2ba7cb309578 | 728,716 | .058545 / .094428 | .013451 | 249.72 | 12059968000 | 3 |
| 56718a99-f917-4124-aeda-210a1ddd0b39 | 676,722 | .050610 / .066561 | .005440 | 247.91 | 12059968000 | 4 |

Runtime is the Worker-reported inference duration, not end-to-end latency. These are engineering smoke tests, **not** building capability or accuracy certification. Existing P9B findings remain: same-image responds, cross-tile weak, farmland false positives significant. No IoU/F1 is invented. Full JSON retained locally in `artifacts/agent-v1-real-jobs.json`.

## Regression

Backend, frontend, typecheck, lint and local Docker production builds passed. Original P8, P9 native tile, P9 synthetic HTTP/cancellation and P9C real local Qwen → confirm → Mock → review/export scripts passed. New `scripts/acceptance_workspace_agent.py` validates authenticated context fields, viewer read-only, outsider/foreign-resource rejection, owner-bound confirmation, recent job and cancellation expiry; temporary users/membership are cleaned in finally.

Final aggregate counts and subsequent AOI-vs-window spatial fix are recorded in `docs/single-tile-aoi-validation.md`. Agent completion does not authorize P10/P11. The user subsequently requested AOI-effective-result clipping in the same release; the two smoke jobs above predate that spatial fix and must not be cited as clipping evidence.
