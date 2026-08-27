# Cadence semantics

Phase 0 decoded three public running FIT files. Their session messages use
`avg_running_cadence` with values around 83, 93 and 91. The Garmin FIT profile
defines this as a native `session.avg_cadence` sub-field for `sport=running`,
with decoded unit `strides/min`; it is not a developer field. The selected files
also contain `avg_step_length`, but no independent field proves that one stride
must be multiplied by two for this device/export.

The public `running_page` SQLite/JSON summary has no cadence field. Therefore
the v1.1 contract stores both provenance and uncertainty:

- `cadenceRawValue`: decoded value, when supplied;
- `cadenceRawUnit`: `strides/min` or the source unit;
- `cadenceRawField`, `cadenceRawMessage`, `cadenceRawOrigin`: provenance;
- `cadenceNormalizedSpm`: `null` until an export-specific conversion is
  independently verified.

No `cadenceSpm` alias remains. The model projection deliberately omits the raw
numeric cadence and exposes only `cadenceNormalizedSpm` plus a status of
`raw_unit_unconfirmed_or_unavailable`. Renderer and analyzers must not treat
the observed 83/93/91 values as steps per minute.
