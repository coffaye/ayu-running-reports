"""Normalized data contract for all Ayu report sources."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
import json
import math
from typing import Any, Mapping

from .errors import SchemaValidationError
from .identity import normalize_run_id
from .version import (
    ENGINE_VERSION,
    PROMPT_VERSION,
    RENDERER_VERSION,
    SCHEMA_VERSION,
    runtime_engine_commit,
)


def _finite_or_none(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise SchemaValidationError(f"metric must be numeric or null: {value!r}")
    number = float(value)
    if not math.isfinite(number):
        raise SchemaValidationError("metric must be finite")
    return number


def parse_duration_seconds(value: object) -> float | None:
    """Parse JSON/SQLite duration forms without treating null as zero."""

    if value is None:
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return _finite_or_none(value)
    if not isinstance(value, str):
        raise SchemaValidationError(f"duration must be numeric, string, or null: {value!r}")
    raw = value.strip()
    if not raw:
        return None
    # SQLite Interval is serialized as 1970-01-01 HH:MM:SS.ffffff in the
    # public database; JSON uses HH:MM:SS.ffffff.
    if " " in raw and raw[:4].isdigit() and "-" in raw[:10]:
        raw = raw.split(" ", 1)[1]
    parts = raw.split(":")
    if len(parts) != 3:
        raise SchemaValidationError(f"unsupported duration string: {value!r}")
    try:
        hours = float(parts[0])
        minutes = float(parts[1])
        seconds = float(parts[2])
    except ValueError as exc:
        raise SchemaValidationError(f"unsupported duration string: {value!r}") from exc
    if hours < 0 or minutes < 0 or seconds < 0 or minutes >= 60 or seconds >= 60:
        raise SchemaValidationError(f"invalid duration string: {value!r}")
    return hours * 3600 + minutes * 60 + seconds


def _date_from_source(value: str) -> str:
    if len(value) < 10:
        raise SchemaValidationError("local datetime must contain YYYY-MM-DD")
    candidate = value[:10]
    try:
        datetime.strptime(candidate, "%Y-%m-%d")
    except ValueError as exc:
        raise SchemaValidationError(f"invalid local date: {candidate!r}") from exc
    return candidate


@dataclass(frozen=True)
class SourceEvidence:
    source_type: str
    source_ref: str | None
    adapter_version: str
    captured_at: str | None
    fields: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return {
            "sourceType": self.source_type,
            "sourceRef": self.source_ref,
            "adapterVersion": self.adapter_version,
            "capturedAt": self.captured_at,
            "fields": list(self.fields),
        }


@dataclass(frozen=True)
class DailyRunContext:
    """The only data shape the analyzer is allowed to consume."""

    run_id: str
    local_date: str
    start_datetime_local: str
    timezone: str | None
    timezone_source: str
    sport: str
    distance_m: float
    timer_time_sec: float | None = None
    elapsed_time_sec: float | None = None
    moving_time_sec: float | None = None
    display_duration_source: str = "unknown"
    subtype: str | None = None
    title: str | None = None
    average_speed_mps: float | None = None
    average_pace_sec_per_km: float | None = None
    average_hr_bpm: float | None = None
    max_hr_bpm: float | None = None
    cadence_raw_value: float | None = None
    cadence_raw_unit: str | None = None
    cadence_raw_field: str | None = None
    cadence_raw_message: str | None = None
    cadence_raw_origin: str | None = None
    cadence_normalized_spm: float | None = None
    stride_m: float | None = None
    power_w: float | None = None
    ascent_m: float | None = None
    laps: tuple[Mapping[str, Any], ...] | None = None
    splits: tuple[Mapping[str, Any], ...] | None = None
    structured_workout: Mapping[str, Any] | None = None
    workout_intent: str = "unknown"
    training_effect_aerobic: float | None = None
    training_effect_anaerobic: float | None = None
    training_load_peak: float | None = None
    recovery_percent: float | None = None
    recovery_hours: float | None = None
    running_fitness: float | None = None
    evidence: tuple[SourceEvidence, ...] = field(default_factory=tuple)
    schema_version: str = SCHEMA_VERSION
    engine_version: str = ENGINE_VERSION
    engine_commit: str | None = field(default_factory=runtime_engine_commit)
    prompt_version: str = PROMPT_VERSION
    renderer_version: str = RENDERER_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(self, "run_id", normalize_run_id(self.run_id))
        if self.schema_version != SCHEMA_VERSION:
            raise SchemaValidationError("unsupported DailyRunContext schemaVersion")
        for name in ("engine_version", "prompt_version", "renderer_version"):
            if not isinstance(getattr(self, name), str) or not getattr(self, name):
                raise SchemaValidationError(f"{name} must be a non-empty string")
        if self.engine_commit is not None and not isinstance(self.engine_commit, str):
            raise SchemaValidationError("engineCommit must be a string or null")
        if self.timezone_source not in {"source", "config", "derived", "unknown"}:
            raise SchemaValidationError("timezoneSource must be source/config/derived/unknown")
        if not self.sport or not isinstance(self.sport, str):
            raise SchemaValidationError("sport is required")
        if (
            isinstance(self.distance_m, bool)
            or not isinstance(self.distance_m, (int, float))
            or not math.isfinite(float(self.distance_m))
            or self.distance_m < 0
        ):
            raise SchemaValidationError("distanceM must be a finite non-negative number")
        if not isinstance(self.local_date, str):
            raise SchemaValidationError("localDate must be YYYY-MM-DD")
        _date_from_source(self.local_date)
        if self.local_date != self.local_date[:10]:
            raise SchemaValidationError("localDate must be YYYY-MM-DD")
        if self.display_duration_source not in {
            "moving_time",
            "timer_time",
            "elapsed_time",
            "unknown",
        }:
            raise SchemaValidationError(
                "displayDurationSource must be moving_time/timer_time/elapsed_time/unknown"
            )
        for name in (
            "timer_time_sec",
            "elapsed_time_sec",
            "moving_time_sec",
            "average_speed_mps",
            "average_pace_sec_per_km",
            "average_hr_bpm",
            "max_hr_bpm",
            "cadence_raw_value",
            "cadence_normalized_spm",
            "stride_m",
            "power_w",
            "ascent_m",
            "training_effect_aerobic",
            "training_effect_anaerobic",
            "training_load_peak",
            "recovery_percent",
            "recovery_hours",
            "running_fitness",
        ):
            _finite_or_none(getattr(self, name))
        duration_values = {
            "moving_time": self.moving_time_sec,
            "timer_time": self.timer_time_sec,
            "elapsed_time": self.elapsed_time_sec,
        }
        if not any(value is not None for value in duration_values.values()):
            raise SchemaValidationError("at least one duration field is required")
        if self.display_duration_source == "unknown":
            for source_name in ("moving_time", "timer_time", "elapsed_time"):
                if duration_values[source_name] is not None:
                    object.__setattr__(self, "display_duration_source", source_name)
                    break
        if self.display_duration_source != "unknown":
            if duration_values[self.display_duration_source] is None:
                raise SchemaValidationError(
                    "displayDurationSource must point to an available duration"
                )
        if self.cadence_raw_value is not None:
            for name in ("cadence_raw_unit", "cadence_raw_field", "cadence_raw_message"):
                if not isinstance(getattr(self, name), str) or not getattr(self, name):
                    raise SchemaValidationError(f"{name} is required with raw cadence")
            if self.cadence_raw_origin not in {"native", "developer", "unknown"}:
                raise SchemaValidationError("cadenceRawOrigin must be native/developer/unknown")
        if self.cadence_normalized_spm is not None and self.cadence_raw_value is None:
            raise SchemaValidationError("normalized cadence requires raw cadence provenance")
        if self.structured_workout is None and self.workout_intent != "unknown":
            raise SchemaValidationError("missing structured workout requires workoutIntent=unknown")

    @property
    def display_duration_sec(self) -> float | None:
        return {
            "moving_time": self.moving_time_sec,
            "timer_time": self.timer_time_sec,
            "elapsed_time": self.elapsed_time_sec,
        }.get(self.display_duration_source)

    @property
    def available_metrics(self) -> tuple[str, ...]:
        fields = []
        for field_name in (
            "distance_m",
            "timer_time_sec",
            "elapsed_time_sec",
            "moving_time_sec",
            "average_speed_mps",
            "average_pace_sec_per_km",
            "average_hr_bpm",
            "max_hr_bpm",
            "cadence_normalized_spm",
            "stride_m",
            "power_w",
            "ascent_m",
            "training_effect_aerobic",
            "training_effect_anaerobic",
            "training_load_peak",
            "recovery_percent",
            "recovery_hours",
            "running_fitness",
        ):
            if getattr(self, field_name) is not None:
                fields.append(field_name)
        return tuple(fields)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["schemaVersion"] = data.pop("schema_version")
        data["engineVersion"] = data.pop("engine_version")
        data["engineCommit"] = data.pop("engine_commit")
        data["promptVersion"] = data.pop("prompt_version")
        data["rendererVersion"] = data.pop("renderer_version")
        data["runId"] = data.pop("run_id")
        data["localDate"] = data.pop("local_date")
        data["startDatetimeLocal"] = data.pop("start_datetime_local")
        data["timezoneSource"] = data.pop("timezone_source")
        data["distanceM"] = data.pop("distance_m")
        data["timerTimeSec"] = data.pop("timer_time_sec")
        data["elapsedTimeSec"] = data.pop("elapsed_time_sec")
        data["movingTimeSec"] = data.pop("moving_time_sec")
        data["displayDurationSource"] = data.pop("display_duration_source")
        data["subtype"] = data.get("subtype")
        data["averageSpeedMps"] = data.pop("average_speed_mps")
        data["averagePaceSecPerKm"] = data.pop("average_pace_sec_per_km")
        data["averageHrBpm"] = data.pop("average_hr_bpm")
        data["maxHrBpm"] = data.pop("max_hr_bpm")
        data["cadenceRawValue"] = data.pop("cadence_raw_value")
        data["cadenceRawUnit"] = data.pop("cadence_raw_unit")
        data["cadenceRawField"] = data.pop("cadence_raw_field")
        data["cadenceRawMessage"] = data.pop("cadence_raw_message")
        data["cadenceRawOrigin"] = data.pop("cadence_raw_origin")
        data["cadenceNormalizedSpm"] = data.pop("cadence_normalized_spm")
        data["strideM"] = data.pop("stride_m")
        data["powerW"] = data.pop("power_w")
        data["ascentM"] = data.pop("ascent_m")
        data["structuredWorkout"] = data.pop("structured_workout")
        data["workoutIntent"] = data.pop("workout_intent")
        data["trainingEffectAerobic"] = data.pop("training_effect_aerobic")
        data["trainingEffectAnaerobic"] = data.pop("training_effect_anaerobic")
        data["trainingLoadPeak"] = data.pop("training_load_peak")
        data["recoveryPercent"] = data.pop("recovery_percent")
        data["recoveryHours"] = data.pop("recovery_hours")
        data["runningFitness"] = data.pop("running_fitness")
        data["evidence"] = [item.to_dict() for item in self.evidence]
        data["laps"] = list(self.laps) if self.laps is not None else None
        data["splits"] = list(self.splits) if self.splits is not None else None
        return data

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, sort_keys=True)
