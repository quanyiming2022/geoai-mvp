# P9C — Natural-language task planning

Scope: optional LLM planning on top of P9, not language-conditioned pixel inference. Manual workflows remain available. No P10/P11 large-area processing.

## Control Center

`/control/models/language` supports three separately retained configurations: local (default), LAN, and cloud. Only verified platform administrators can read/write connection settings or run connection tests. Regular users see only mode/model availability. Configuration is saved in existing persistent Redis (AOF), without changing existing PostgreSQL tables or RLS policies.

Local: native Ollama on Mac, API container calls `http://host.docker.internal:11434`. Docker Desktop macOS does not provide Metal GPU passthrough, so inference runs outside the Linux container. GeoAI services remain local Docker services.

LAN / cloud: Ollama or OpenAI-compatible protocol. Add exact origins to local `.env` `LLM_ALLOWED_ORIGINS` (comma separated), then recreate the API service. Credentials only in `.env` as `LLM_LAN_API_KEY` / `LLM_CLOUD_API_KEY`; the UI stores references only. Cloud requires HTTPS and per-request consent to send text plus catalog metadata. No image/mask/token upload, no automatic cloud fallback. Remote modes remain unverified until configured.

## Workflow

Workspace → Task Assistant → describe an existing visual prompt, target raster, channel and optional native pixel offset → generate read-only draft → inspect named resources → confirm → original jobs API.

- LLM output is parsed against a strict schema. IDs must belong to the current RLS-scoped catalog; no network URLs, commands, geometry invention or model-defined tools.
- Worker query is exactly 512×512 source pixels. Mock follows the existing same-raster prompt/AOI contract.
- Draft stored server-side for 30 minutes, bound to user/project, with one idempotency key. Client sends draft ID and explicit confirmation only. Existing endpoint revisions, permissions and spatial constraints are checked during job creation.
- Current read tools: recent job status; planning/help with resource catalog. No deletion, review, member or infrastructure mutation from language.
- Missing/ambiguous examples and full-image/language-exclusion requests should prompt clarification. LLM semantics can be imperfect: users must review drafts. The model does not execute them.
- Limits: 2,000 character instruction, 100 resources/category, one in-flight request/user, bounded model response and timeout. Metadata is kept local by default.

## Local runtime provenance

Ollama v0.33.3 official macOS archive SHA256:
`342db03df80bb9db84ff64246031bd5f70c09b59ff52fa5cc9aaae3476cc4a9d`

Installed user-local at `~/.local/share/geoai/ollama/0.33.3`; LaunchAgent `com.geoai.ollama`, loopback listener only, `OLLAMA_NO_CLOUD=1` (runtime cloud features disabled). Models at `~/.local/share/geoai/ollama/models`; logs at `~/Library/Logs/GeoAI`.

Default model: `qwen3:4b-instruct-2507-q4_K_M` (about 2.5 GB; Apache 2.0 on registry). Downloaded manifest digest: `0edcdef34593eac1aa2be9c7d06c432dcf81945adca5eca2f27662c18f168ba0`; size 2,497,293,803 bytes. No weights are stored in Git.

Sources: [Ollama macOS](https://docs.ollama.com/macos), [GPU/Docker limitations](https://docs.ollama.com/faq), [structured outputs](https://docs.ollama.com/capabilities/structured-outputs), [model](https://ollama.com/library/qwen3:4b-instruct-2507-q4_K_M).

## Local verification (2026-09-11)

- Production Docker build, typecheck, lint: PASS.
- Backend: 71 tests PASS; frontend: 3 tests PASS.
- Existing live project permission acceptance, P8 raster/COG/Mock/review/export/RLS acceptance, and P9 synthetic native-tile HTTP acceptance: PASS.
- Web `/api/health`: PASS. Redis/API restart retained saved three-profile configuration with local active; all Docker services healthy.
- Browser administrator saved local configuration. Assistant open/close retained manual AOI name, assistant text, identical map canvas and zoom. No business record was saved for this interaction check.
- Browser screenshots: ignored `artifacts/p9c-local-1440.png`, `p9c-assistant-1440.png`, `p9c-assistant-1920.png`, `p9c-model-unavailable.png`. 1920×1080 horizontal overflow: false.
- Code review: manual-draft unmount, repeated cloud consent and timeout lock ownership issues fixed; re-review found no remaining concrete blockers.
- Local model download and read-only inference: PASS (see below). Full P9C confirmation acceptance remains pending.

### Current completion gate

P9C is NOT COMPLETE. The user explicitly authorized an interim development-branch commit/push on 2026-09-11 before the remaining model/configuration acceptance. This snapshot is not a completion tag. The model pull completed and SHA256 verification succeeded. Native Metal inference and Docker API connectivity are verified below.

Automatic approval review rejected creating temporary ordinary test accounts/projects for P9C acceptance as a persistent write needing specific authorization. An explicit user authorization request is pending. Do not bypass that rejection or run `acceptance_p9c.py` until authorized. Existing P8/P9 tests recorded above were run before that rejection. LAN/cloud real connectivity remains pending user endpoint/credentials, and P9B GPU/checkpoint inference remains separately pending.

Interim snapshot: local Qwen3-4B-Instruct-2507 Q4_K_M download still pending (about 97% at pre-push inspection); Ollama is the runtime, Qwen is the model. Retain this lightweight multilingual instruction model until measured Chinese task-planning acceptance justifies a replacement.

## Local model activation and assistant entry follow-up

- Saved configuration verified: `active_mode=local`, enabled, model `qwen3:4b-instruct-2507-q4_K_M`, all three profiles retained in Redis.
- Docker API uses this saved profile and returns valid structured JSON: PASS, 478 ms for the small warm connection probe.
- Real Chinese checks (synthetic catalog, no database writes): status 11,795 ms; Mock draft 10,449 ms; unsupported whole-image/automatic annotation request returns help 11,077 ms. Evidence: `artifacts/p9c-local-readonly.json`.
- Initial free-form UUID decoding repeated until the 700-token output limit; optional fields could also be omitted. Fixed using a project-scoped enum decoding schema with every field required (explicit null for unused fields). Server-side resource and permission validation remains unchanged. Regression covers the schema constraints.
- Workspace assistant is now a single speech-bubble icon in the right context-panel heading, with tooltip, accessible label and focus styling. It is removed from the project navigation header and remains outside the map mouse toolbar. Existing side sheet and form preservation remain intact.
- Entry screenshots: `artifacts/p9c-assistant-entry-1440.png` and `artifacts/p9c-assistant-entry-1920.png`.
- This resolves local runtime/configuration readiness, not P9B GPU inference or the pending full P9C confirmation E2E gate.

Browser live read-only check: new context-panel entry → Chinese status request → API → local Qwen → current project status, PASS at 8,127 ms. Screenshot `artifacts/p9c-status-live.png`. No task was created.
