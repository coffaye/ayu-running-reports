# Phase 0 facts freeze

This document records the read-only audit of `coffaye/running_page` at the
audited `master` head (`8d8dd10fa5ef38f240cd2a20268597dab7e35667`). No
production file was copied here.

## Public Git content

| Data | Git tracked | Public now | Sensitive fields | Future recommendation |
|---|---:|---:|---|---|
| `FIT_OUT/*.fit` | 712 files (+ `.gitkeep`) | Yes | timestamps, GPS records, heart rate, cadence, power and device metadata | Treat as public now; move future raw files to private storage and do not assume history can be erased by deleting the working tree |
| `TCX_OUT` | `.gitkeep` only | Yes | none currently | Keep empty unless a privacy decision is made |
| `GPX_OUT` | `.gitkeep` only | Yes | none currently | Keep empty unless a privacy decision is made |
| `activities` | `.gitkeep` only | Yes | none currently | Keep empty unless a privacy decision is made |
| `run_page/data.db` | 1 file, 6,508,544 bytes | Yes | dates, distance, HR, speed, elevation and route polyline | Treat as public summary data; do not add private fields |
| `src/static/activities.json` | 1 file, 5,164,778 bytes | Yes | dates, distance, HR, speed, elevation and route polyline | Keep summary-only and privacy-filtered |

## Identity and date semantics

- `activities.json` contains 689 integer `run_id` values, all unique.
- SQLite contains 711 integer primary-key IDs, all unique.
- The JSON data has 59 local dates with multiple activities; the maximum is
  three activities on one date. Date is therefore not a report identity.
- Three public FIT files were decoded and matched to JSON records by the UTC
  session start timestamp in milliseconds. The same deterministic convention
  is used by the Phase 1 FIT adapter.
- Re-importing the same decoded FIT messages produces the same ID. The adapter
  rejects a naive timestamp instead of depending on a runner timezone.
- JSON/SQLite `start_date_local` values are local-looking strings without an
  IANA timezone. The adapter therefore emits `timezone: null` and
  `timezoneSource: "unknown"` for that source. FIT fixtures expose UTC
  `start_time`; they do not provide a reliable IANA local timezone.

## FIT capability observed in real files

The following public files were decoded without storing their bytes here:

- short running session: `031dd270858544dc9bc70ee466c808d0.fit`
- multi-lap running session: `ff52d26dd8eb48a5a129cf39be0f033d.fit`
- explicit long-workout session: `1a0eb42fa7304f3e8d6b38ef064c9ba6.fit`

Observed message types include `session`, `lap`, `split`, `record`, `activity`,
`device_info`, `time_in_zone`, and (in the long-workout fixture)
`workout`/`workout_step`. Observed session fields include distance, elapsed and
timer duration, speed, average/max heart rate, cadence, step length, power,
ascent, aerobic/anaerobic training effect, and `training_load_peak`. The FIT
profile decodes `total_training_effect` and `total_anaerobic_training_effect`
with a scale of 10 and no display unit; `training_load_peak` has a native scale
of 65536 and no generic points/TSS/TRIMP unit. These values remain named device
metrics in the Engine and are never relabeled as another load system. The
three fixtures use the same native session fields and profile scales; the
decoded values differ by activity but their field semantics are consistent.

The two non-workout running fixtures contain no `workout` or `workout_step`
message. Their lap `intensity` label is not treated as proof of a structured
workout. Missing structure remains `structuredWorkout: null` and
`workoutIntent: "unknown"`.

The current running_page generator does not normalize these FIT-rich fields
into `data.db` or `activities.json`; Phase 1 reads them only through the
separate FIT adapter.

## Phase 1.1 semantic freeze

- `timerTimeSec`, `elapsedTimeSec` and `movingTimeSec` are separate. The
  running_page source supplies moving/elapsed time; selected FIT files supply
  timer/elapsed time and no reliable moving-time field.
- `displayDurationSource` selects `moving_time`, then `timer_time`, then
  `elapsed_time`; the selected value is `displayDurationSec`. No synthetic
  moving time is calculated.
- Training effect and training load retain the device/profile field names and
  decoded values. No points, TSS, TRIMP or EPOC unit is inferred.
- Planned workout data and inferred training type remain separate concepts.

## Pages chain facts

`run_data_sync.yml` supports manual dispatch, a nightly schedule, and a narrow
push path filter. It logs into COROS with Actions secrets, downloads activity
files, regenerates the summary data, commits with the Actions checkout token,
and calls `gh-pages.yml` through `workflow_call` when sync succeeds.

`gh-pages.yml` also supports manual dispatch and `workflow_call`. It builds with
`PATH_PREFIX=/$REPO_NAME`, uploads a Pages artifact, and deploys it. Its current
concurrency group is `pages` with `cancel-in-progress: true`; this is recorded
as a later integration concern and was not changed in Phase 0/1.
