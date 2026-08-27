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

The v1.1 contract separates `timerTimeSec`, `elapsedTimeSec` and
`movingTimeSec`. The display duration uses `moving_time`, then `timer_time`,
then `elapsed_time` as a deterministic fallback, and records the selected
`displayDurationSource`. See [CADENCE_SEMANTICS.md](CADENCE_SEMANTICS.md) for
the raw-versus-normalized cadence boundary.

`FixtureAnalyzer` is a deterministic test implementation of the
`ReportAnalyzer` protocol. `DeepSeekAnalyzer` is available only through an
explicit CLI/module invocation and requires `DEEPSEEK_API_KEY`; imports, tests
and the fixture CLI never make network calls. A future Actions caller must pin
this repository to a semantic tag or commit SHA and inject `AYU_ENGINE_COMMIT`;
it must never silently follow `main`.

The FIT adapter only emits fields observed in the Phase 0 fixtures. FIT
training effect fields are native session values with profile scale 10 and no
display unit; `training_load_peak` is a native scaled session value with no
generic points/TSS/TRIMP interpretation. Raw FIT files and production routes
are deliberately not stored in this repository. Missing values remain `null`;
in particular, missing structured workout data is represented by
`structuredWorkout: null` and `workoutIntent: "unknown"`.

Phase 2.1 live verification is opt-in and local only. Set the key in the shell
or a gitignored `.env.local`/`.env`, run `python -m ayu_report_engine.smoke
--live`, then `python -m ayu_report_engine.benchmark --live`. The latter reuses
the matching successful smoke result when available (otherwise it performs the
one-request preflight), then runs A/B/C at low and high effort,
renders six deterministic HTML reports under `engine/.benchmark/reports/`,
and stores only safe metadata, semantic report snapshots, validation flags and
cost estimates. The default live output cap is 16384 tokens so high-effort
structured cases do not truncate; it can be overridden with
`DEEPSEEK_MAX_OUTPUT_TOKENS`. It does not save reasoning or provider raw
responses.
