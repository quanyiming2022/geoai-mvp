# AOI effective range vs model input window

User-authorized follow-up after Workspace Agent acceptance. Preserve SkySense++ adapter/preprocessing/512 input, frozen benchmarks and all no-AOI legacy behavior.

1. Allow optional AOI on real tile jobs; append migration to freeze AOI geometry and server-derived geographic query-window bounds without rewriting historical snapshots. Existing RLS and immutable snapshot enforcement remain.
2. Map endpoint validates selected point is covered by the selected, authorized AOI. For small AOIs choose a full native window covering their pixel envelope when feasible. Model context may extend outside AOI.
3. Rasterize the frozen AOI only after inference; mask probability/binary/valid output products. Exact PostGIS intersection and polygon decomposition before result insertion ensure zero outside-area results, review or export. Save effective geometry on immutable result metadata, not by modifying an input snapshot after execution.
4. Pass AOI through Agent and manual map flow. Green AOI / effective region, blue dashed model input window. User-facing assistant describes a small-area test, not pixel internals.
5. Test outside click rejection, small AOI, unchanged complete model input, exact clipped results/areas/export, frozen AOI after edit/delete, viewer/outsider rejection and unchanged no-AOI pipeline. Run all existing regressions and real GPU smoke. Commit one release after verification; stop.
