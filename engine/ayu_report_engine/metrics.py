"""Whitelisted deterministic metric references and model input projection."""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any

from .context import DailyRunContext
from .errors import SchemaValidationError


@dataclass(frozen=True)
class MetricValue:
    ref: str
    value: Any
    unit: str | None
    source: str


@dataclass(frozen=True)
class MetricSpec:
    attr: str | None
    unit: str | None
    label: str
    collection: bool = False


_SPECS: dict[str, MetricSpec] = {
    "summary.distanceM": MetricSpec("distance_m", "m", "距离"),
    "summary.timerTimeSec": MetricSpec("timer_time_sec", "s", "Timer time"),
    "summary.elapsedTimeSec": MetricSpec("elapsed_time_sec", "s", "Elapsed time"),
    "summary.movingTimeSec": MetricSpec("moving_time_sec", "s", "Moving time"),
    "summary.displayDurationSec": MetricSpec(None, "s", "显示训练时长"),
    "summary.averagePaceSecPerKm": MetricSpec(
        "average_pace_sec_per_km", "s/km", "平均配速"
    ),
    "summary.averageHrBpm": MetricSpec("average_hr_bpm", "bpm", "平均心率"),
    "summary.maxHrBpm": MetricSpec("max_hr_bpm", "bpm", "最大心率"),
    "summary.cadenceNormalizedSpm": MetricSpec(
        "cadence_normalized_spm", "steps/min", "已归一化步频"
    ),
    "summary.powerW": MetricSpec("power_w", "W", "平均功率"),
    "summary.ascentM": MetricSpec("ascent_m", "m", "爬升"),
    "summary.trainingEffectAerobic": MetricSpec(
        "training_effect_aerobic", None, "Aerobic training effect"
    ),
    "summary.trainingEffectAnaerobic": MetricSpec(
        "training_effect_anaerobic", None, "Anaerobic training effect"
    ),
    "summary.trainingLoadPeak": MetricSpec("training_load_peak", None, "Training load peak"),
    "summary.recoveryPercent": MetricSpec("recovery_percent", "%", "恢复比例"),
    "summary.recoveryHours": MetricSpec("recovery_hours", "h", "预计恢复时间"),
    "summary.runningFitness": MetricSpec("running_fitness", None, "Running fitness"),
    "summary.lapSummary": MetricSpec("laps", None, "分圈摘要", collection=True),
    "summary.splitSummary": MetricSpec("splits", None, "Split 摘要", collection=True),
    "planned.structuredWorkout": MetricSpec(
        "structured_workout", None, "设备课表", collection=True
    ),
}

ALLOWED_METRIC_REFS = frozenset(_SPECS)


def metric_specs() -> dict[str, MetricSpec]:
    return dict(_SPECS)


def _source(context: DailyRunContext) -> str:
    return context.evidence[0].source_type if context.evidence else "unknown"


def resolve_metric_ref(context: DailyRunContext, ref: str) -> MetricValue | None:
    spec = _SPECS.get(ref)
    if spec is None:
        raise SchemaValidationError(f"metricRef is not allowed: {ref!r}")
    value = context.display_duration_sec if ref == "summary.displayDurationSec" else getattr(
        context, spec.attr
    )
    if value is None:
        return None
    if spec.collection and not value:
        return None
    return MetricValue(ref=ref, value=value, unit=spec.unit, source=_source(context))


def validate_metric_refs(report: Any, context: DailyRunContext) -> None:
    """Fail fast when model references an unknown or unavailable fact."""

    refs: list[str] = []
    for item in report.evidence:
        ref = item.get("metricRef")
        if not isinstance(ref, str) or ref not in ALLOWED_METRIC_REFS:
            raise SchemaValidationError(f"invalid evidence metricRef: {ref!r}")
        refs.append(ref)
    for block_name in ("load", "recovery"):
        block = getattr(report, block_name)
        if block is None:
            continue
        block_refs = block.get("metricRefs", [])
        if not isinstance(block_refs, list) or any(
            not isinstance(ref, str) for ref in block_refs
        ):
            raise SchemaValidationError(f"{block_name}.metricRefs must be an array of strings")
        refs.extend(block_refs)
    for ref in refs:
        if resolve_metric_ref(context, ref) is None:
            raise SchemaValidationError(f"metricRef points to unavailable metric: {ref}")


def context_for_model(context: DailyRunContext) -> dict[str, Any]:
    """Project only safe, deterministic facts into the model request.

    Raw cadence is intentionally omitted because its FIT unit is strides/min and
    has not been proven equivalent to normalized steps/min. Raw routes, paths,
    device data and source identifiers are also never included.
    """

    workout = context.structured_workout
    return {
        "schemaVersion": context.schema_version,
        "localDate": context.local_date,
        "startDatetimeLocal": context.start_datetime_local,
        "timezone": context.timezone,
        "timezoneSource": context.timezone_source,
        "sport": context.sport,
        "subtype": context.subtype,
        "title": context.title,
        "distanceM": context.distance_m,
        "timerTimeSec": context.timer_time_sec,
        "elapsedTimeSec": context.elapsed_time_sec,
        "movingTimeSec": context.moving_time_sec,
        "displayDurationSec": context.display_duration_sec,
        "displayDurationSource": context.display_duration_source,
        "averageSpeedMps": context.average_speed_mps,
        "averagePaceSecPerKm": context.average_pace_sec_per_km,
        "averageHrBpm": context.average_hr_bpm,
        "maxHrBpm": context.max_hr_bpm,
        "cadenceNormalizedSpm": context.cadence_normalized_spm,
        "cadenceStatus": (
            "normalized"
            if context.cadence_normalized_spm is not None
            else "raw_unit_unconfirmed_or_unavailable"
        ),
        "strideM": context.stride_m,
        "powerW": context.power_w,
        "ascentM": context.ascent_m,
        "laps": list(context.laps) if context.laps is not None else None,
        "splits": list(context.splits) if context.splits is not None else None,
        "plannedWorkout": workout,
        "workoutIntent": context.workout_intent,
        "trainingEffectAerobic": context.training_effect_aerobic,
        "trainingEffectAnaerobic": context.training_effect_anaerobic,
        "trainingLoadPeak": context.training_load_peak,
        "recoveryPercent": context.recovery_percent,
        "recoveryHours": context.recovery_hours,
        "runningFitness": context.running_fitness,
    }


def context_for_model_json(context: DailyRunContext) -> str:
    return json.dumps(context_for_model(context), ensure_ascii=False, sort_keys=True)
