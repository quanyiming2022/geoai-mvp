# v0.2.0-p9c.5 — Cross-image extraction workflow

This P9C hardening release separates the reusable visual-prompt source from
the extraction target image. It does not change the frozen SkySense++ adapter,
preprocessing, slot mapping, query-half parsing, Worker contract, or production
threshold behavior.

- Mock GeoExtract now requires an explicit target image. Drawing an AOI uses
  that target and never jumps to the visual prompt's source image.
- The workspace assistant no longer infers a target image from the selected
  visual prompt. Ambiguous target images are resolved independently.
- Mock validation and the database trigger allow a project prompt from image A
  to run against image B, while requiring the AOI to be inside image B.
- The immutable job snapshot records distinct `support_raster` and
  `query_raster` identities. Result and export provenance identify image B.
- Manual Mock and real Worker submissions now share task monitoring with the
  assistant: queued/running/completed/failed feedback is visible, and a
  successful result is selected and fitted on the map automatically.

Local verification: Web tests 17 PASS, API tests 156 PASS, typecheck/lint PASS,
production Docker build PASS, isolated browser acceptance PASS, P8 full
cross-image acceptance PASS, P9 native tile PASS, P9 synthetic HTTP PASS, and
P9C local LLM draft/confirmation acceptance PASS. Supabase migration execution
and checksum tracking PASS. The pinned Supabase CLI advisor could not
authenticate against the custom self-hosted database defaults; API/RLS and
direct database behavior were instead exercised by the full acceptance suite.
