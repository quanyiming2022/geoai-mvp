# Workspace Agent v1 implementation plan

**Spec:** user attachment `f7f2980c-608a-458f-a6bc-4a919204d4ab/pasted-text.txt`.
**Goal:** natural goals resolved against authenticated workspace resources, with deterministic capability/permission checks and confirmed existing Job submission.
**Architecture:** `agent_goals.py` contains pure Goal/Resolver/Capability logic; `workspace_agent.py` orchestrates bounded read/UI/confirmation tools. Existing Job, CRUD, model worker, probability and RLS behavior remain unchanged. The existing panel is progressively disclosed, not a workspace layout redesign.

- [x] Save preceding P9C correctness fix separately (`d1236bc`).
- [x] Add typed AgentGoal, authenticated unified context, unique/ambiguous name resolution, real endpoint policy and conservative full-AOI rejection.
- [x] Add read-only recent job/result interpretation, bounded UI tools and confirmed cancellation through existing APIs. No arbitrary URL, shell, SQL or file tools.
- [x] Replace default parameter form with compact context, text input, plan/clarification and contextual action buttons; maintain per-workspace conversational state.
- [x] Validate real-browser cases A–F, dirty guard, local LLM parsing, real GPU job, completion/result selection and offline behavior.
- [x] Run backend/frontend/build/typecheck/lint/P8/P9 regressions, archive evidence and commit. Stop; do not start P10/P11.

Latest user steering adopted: non-modal draggable conversation panel; no advanced resource table; explicit conversation states and owner-bound server continuations; live context separate from pending snapshot. Browser A–F, floating interaction and dirty guard completed. User then requested AOI-effective-range clipping, to be completed after Agent and included in one final release commit; do not start P10/P11.
