# Ayu Report Engine

This is the shared, offline-capable boundary for Ayu Running reports. It is
intentionally separate from the Codex Skill instructions:

```text
running_page JSON / SQLite / FIT
        -> adapter
        -> DailyRunContext
        -> ReportAnalyzer
        -> StructuredReport
        -> deterministic HTML renderer
        -> browser Canvas PNG download
```

Phase 1 contains no network client and makes no DeepSeek request.
`FixtureAnalyzer` is a deterministic test implementation of the future
`ReportAnalyzer` protocol. A future Actions caller must pin this repository to
a semantic tag or commit SHA and inject `AYU_ENGINE_COMMIT`; it must never
silently follow `main`.

The FIT adapter only emits fields observed in the Phase 0 fixtures. Raw FIT
files and production routes are deliberately not stored in this repository.
Missing values remain `null`; in particular, missing structured workout data is
represented by `structuredWorkout: null` and `workoutIntent: "unknown"`.
