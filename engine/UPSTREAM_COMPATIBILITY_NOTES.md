# UPSTREAM_COMPATIBILITY_NOTES

These notes freeze the Phase 0 boundary; they do not modify or merge either
running_page repository.

- The production source is `coffaye/running_page`; `yihong0618/running_page` is
  a manually reviewed upstream.
- The production fork currently keeps RunTable under
  `src/components/RunTable/`; upstream places the classic table under a theme
  namespace. UI work must therefore be isolated from this engine.
- The production Vite build accepts `PATH_PREFIX`; report URLs must be resolved
  relative to the runtime base and must not assume `/`.
- Existing `run_page/generator/db.py` owns the public summary schema. The engine
  reads its output and does not alter that schema in Phase 1.
- Existing Pages workflow can be reused later. No workflow or deployment change
  belongs in Phase 1.
