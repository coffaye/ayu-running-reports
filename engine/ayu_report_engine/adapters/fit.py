"""FIT adapter based only on fields observed in the Phase 0 fixtures.

The adapter deliberately emits no coordinates, route, or raw record stream. It
accepts decoded FIT messages as a separate function so tests can use sanitized
messages without committing personal FIT files.
"""

from __future__ import annotations

from datetime import datetime
import math
from typing import Any, Mapping

from ..context import DailyRunContext, SourceEvidence
from ..errors import DataSourceError
from ..identity import run_id_from_datetime
from ..version import ENGINE_VERSION

ADAPTER_VERSION = "fit-v1"


def _number(message: Mapping[str, Any], key: str) -> float | None:
    value = message.get(key)
    if value is None or isinstance(value, bool):
        return None
    if not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        return None
    return float(value)


def _datetime_value(value: object) -> datetime | None:
    return value if isinstance(value, datetime) else None


def _date_string(value: datetime) -> str:
    return value.strftime("%Y-%m-%d")


def _iso(value: datetime) -> str:
    return value.isoformat()


def _safe_metric(message: Mapping[str, Any], key: str) -> float | None:
    value = _number(message, key)
    return value if value is None or value >= 0 else None


def _first_present(*values: float | None) -> float | None:
    """Choose the first measured value; preserve a real zero."""

    for value in values:
        if value is not None:
            return value
    return None


def _lap_rows(messages: list[Mapping[str, Any]]) -> tuple[dict[str, Any], ...] | None:
    if not messages:
        return None
    rows = []
    for index, lap in enumerate(messages):
        row: dict[str, Any] = {
            "index": index,
            "timerTimeSec": _safe_metric(lap, "total_timer_time"),
            "elapsedTimeSec": _safe_metric(lap, "total_elapsed_time"),
            "distanceM": _safe_metric(lap, "total_distance"),
            "averageSpeedMps": _safe_metric(lap, "enhanced_avg_speed"),
            "averageHrBpm": _safe_metric(lap, "avg_heart_rate"),
            "maxHrBpm": _safe_metric(lap, "max_heart_rate"),
            "cadenceRawValue": _first_present(
                _safe_metric(lap, "avg_running_cadence"),
                _safe_metric(lap, "avg_cadence"),
            ),
            "cadenceRawUnit": (
                "strides/min"
                if lap.get("avg_running_cadence") is not None
                else "rpm"
                if lap.get("avg_cadence") is not None
                else None
            ),
            "powerW": _safe_metric(lap, "avg_power"),
            "ascentM": _safe_metric(lap, "total_ascent"),
            "intensity": lap.get("intensity"),
            "trigger": lap.get("lap_trigger"),
        }
        rows.append(row)
    return tuple(rows)


def _split_rows(messages: list[Mapping[str, Any]]) -> tuple[dict[str, Any], ...] | None:
    if not messages:
        return None
    rows = []
    for index, split in enumerate(messages):
        rows.append(
            {
                "index": index,
                "timerTimeSec": _safe_metric(split, "total_timer_time"),
                "elapsedTimeSec": _safe_metric(split, "total_elapsed_time"),
                "distanceM": _first_present(
                    _safe_metric(split, "distance"),
                    _safe_metric(split, "total_distance"),
                ),
                "averageSpeedMps": _first_present(
                    _safe_metric(split, "avg_speed"),
                    _safe_metric(split, "enhanced_avg_speed"),
                ),
                "averageHrBpm": _safe_metric(split, "avg_heart_rate"),
                "powerW": _safe_metric(split, "avg_power"),
            }
        )
    return tuple(rows)


def _structured_workout(
    workouts: list[Mapping[str, Any]], steps: list[Mapping[str, Any]]
) -> Mapping[str, Any] | None:
    if not workouts and not steps:
        return None
    first = workouts[0] if workouts else {}
    normalized_steps = []
    for index, step in enumerate(steps):
        normalized_steps.append(
            {
                "index": index,
                "durationTimeSec": _safe_metric(step, "duration_time"),
                "durationType": step.get("duration_type"),
                "targetType": step.get("target_type"),
                "targetSpeedLowMps": _safe_metric(step, "custom_target_speed_low"),
                "targetSpeedHighMps": _safe_metric(step, "custom_target_speed_high"),
                "intensity": step.get("intensity"),
            }
        )
    return {
        "name": first.get("wkt_name"),
        "description": first.get("wkt_description"),
        "steps": normalized_steps or None,
    }


def context_from_fit_messages(
    messages: Mapping[str, list[Mapping[str, Any]]],
    *,
    source_ref: str = "sanitized.fit",
) -> DailyRunContext:
    """Create a context from a decoded FIT message mapping."""

    sessions = messages.get("session_mesgs") or []
    if not sessions:
        raise DataSourceError("FIT has no session message")
    session = sessions[0]
    start = _datetime_value(session.get("start_time")) or _datetime_value(
        session.get("timestamp")
    )
    if start is None:
        activities = messages.get("activity_mesgs") or []
        start = _datetime_value(activities[0].get("timestamp")) if activities else None
    if start is None:
        raise DataSourceError("FIT has no reliable start timestamp")

    # A FIT local_timestamp is a local clock reading, not an IANA timezone.
    # Preserve it when present and explicitly mark its timezone as unknown.
    local_clock = session.get("local_timestamp")
    if isinstance(local_clock, datetime):
        start_local = local_clock.replace(tzinfo=None)
        timezone = None
        timezone_source = "unknown"
    else:
        start_local = start
        timezone = "UTC" if start.tzinfo is not None else None
        timezone_source = "source" if timezone else "unknown"

    distance = _safe_metric(session, "total_distance")
    timer_time = _safe_metric(session, "total_timer_time")
    elapsed_time = _safe_metric(session, "total_elapsed_time")
    if distance is None or (timer_time is None and elapsed_time is None):
        raise DataSourceError("FIT session lacks distance or duration")
    speed = _first_present(
        _safe_metric(session, "enhanced_avg_speed"),
        _safe_metric(session, "avg_speed"),
    )
    sport = session.get("sport")
    if not isinstance(sport, str) or not sport.strip():
        raise DataSourceError("FIT session lacks sport")
    workout = _structured_workout(
        messages.get("workout_mesgs") or [], messages.get("workout_step_mesgs") or []
    )
    raw_cadence = _first_present(
        _safe_metric(session, "avg_running_cadence"),
        _safe_metric(session, "avg_cadence"),
    )
    raw_cadence_field = (
        "avg_running_cadence"
        if session.get("avg_running_cadence") is not None
        else "avg_cadence"
        if session.get("avg_cadence") is not None
        else None
    )
    raw_cadence_unit = (
        "strides/min" if raw_cadence_field == "avg_running_cadence" else "rpm"
        if raw_cadence_field
        else None
    )
    evidence_fields = [
        "runId",
        "localDate",
        "startDatetimeLocal",
        "sport",
        "distanceM",
        "timerTimeSec",
        "elapsedTimeSec",
        "displayDurationSource",
    ]
    for field_name, source_name in (
        ("averageSpeedMps", "enhanced_avg_speed"),
        ("averageHrBpm", "avg_heart_rate"),
        ("maxHrBpm", "max_heart_rate"),
        ("cadenceRawValue", raw_cadence_field),
        ("powerW", "avg_power"),
        ("ascentM", "total_ascent"),
        ("trainingEffectAerobic", "total_training_effect"),
        ("trainingEffectAnaerobic", "total_anaerobic_training_effect"),
        ("trainingLoadPeak", "training_load_peak"),
    ):
        if source_name is not None and session.get(source_name) is not None:
            evidence_fields.append(field_name)
    if workout is not None:
        evidence_fields.append("structuredWorkout")
    evidence = SourceEvidence(
        source_type="fit",
        source_ref=source_ref,
        adapter_version=ADAPTER_VERSION,
        captured_at=None,
        fields=tuple(evidence_fields),
    )
    average_pace = 1000 / speed if speed and speed > 0 else None
    stride_mm = _safe_metric(session, "avg_step_length")
    return DailyRunContext(
        run_id=run_id_from_datetime(start),
        local_date=_date_string(start_local),
        start_datetime_local=_iso(start_local),
        timezone=timezone,
        timezone_source=timezone_source,
        sport=sport.strip().lower(),
        subtype=session.get("sub_sport") if isinstance(session.get("sub_sport"), str) else None,
        distance_m=distance,
        timer_time_sec=timer_time,
        elapsed_time_sec=elapsed_time,
        moving_time_sec=None,
        display_duration_source="timer_time" if timer_time is not None else "elapsed_time",
        average_speed_mps=speed,
        average_pace_sec_per_km=average_pace,
        average_hr_bpm=_safe_metric(session, "avg_heart_rate"),
        max_hr_bpm=_safe_metric(session, "max_heart_rate"),
        cadence_raw_value=raw_cadence,
        cadence_raw_unit=raw_cadence_unit,
        cadence_raw_field=raw_cadence_field,
        cadence_raw_message="session" if raw_cadence is not None else None,
        cadence_raw_origin="native" if raw_cadence is not None else None,
        cadence_normalized_spm=None,
        stride_m=stride_mm / 1000 if stride_mm is not None else None,
        power_w=_safe_metric(session, "avg_power"),
        ascent_m=_safe_metric(session, "total_ascent"),
        laps=_lap_rows(messages.get("lap_mesgs") or []),
        splits=_split_rows(messages.get("split_mesgs") or []),
        structured_workout=workout,
        workout_intent="structured" if workout is not None else "unknown",
        training_effect_aerobic=_safe_metric(session, "total_training_effect"),
        training_effect_anaerobic=_safe_metric(session, "total_anaerobic_training_effect"),
        training_load_peak=_safe_metric(session, "training_load_peak"),
        evidence=(evidence,),
    )


def context_from_fit_bytes(fit_bytes: bytes, *, source_ref: str = "activity.fit") -> DailyRunContext:
    """Decode a FIT file using the already-used Garmin FIT SDK dependency."""

    if not isinstance(fit_bytes, (bytes, bytearray)) or not fit_bytes:
        raise DataSourceError("FIT input is empty")
    try:
        from garmin_fit_sdk import Decoder, Stream

        messages, errors = Decoder(
            Stream.from_byte_array(bytearray(fit_bytes))
        ).read(convert_datetimes_to_dates=True, convert_types_to_strings=True)
    except Exception as exc:
        raise DataSourceError("FIT decode failed") from exc
    if errors:
        raise DataSourceError("FIT decode returned errors")
    return context_from_fit_messages(messages, source_ref=source_ref)
