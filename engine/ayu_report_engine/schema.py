"""Programmatic JSON Schema definitions used by validation and DeepSeek."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from .metrics import ALLOWED_METRIC_REFS

STRUCTURED_REPORT_SCHEMA_NAME = "ayu_running_daily_report"


def _metric_ref_schema() -> dict[str, Any]:
    return {"type": "string", "enum": sorted(ALLOWED_METRIC_REFS)}


def _semantic_properties() -> dict[str, Any]:
    return {
        "verdict": {"type": "string", "minLength": 1},
        "trainingPurpose": {"type": ["string", "null"]},
        "completion": {
            "type": "object",
            "additionalProperties": False,
            "required": ["status", "trainingType", "score"],
            "properties": {
                "status": {"type": ["string", "null"]},
                "trainingType": {"type": ["string", "null"]},
                "score": {"type": ["number", "null"], "minimum": 0, "maximum": 10},
            },
        },
        "evidence": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["metricRef", "interpretation"],
                "properties": {
                    "metricRef": _metric_ref_schema(),
                    "interpretation": {"type": "string", "minLength": 1},
                },
            },
        },
        "physiologyCost": {"type": ["string", "null"]},
        "load": {
            "type": ["object", "null"],
            "additionalProperties": False,
            "required": ["assessment", "metricRefs"],
            "properties": {
                "assessment": {"type": ["string", "null"]},
                "metricRefs": {"type": "array", "items": _metric_ref_schema()},
            },
        },
        "recovery": {
            "type": ["object", "null"],
            "additionalProperties": False,
            "required": ["assessment", "metricRefs"],
            "properties": {
                "assessment": {"type": ["string", "null"]},
                "metricRefs": {"type": "array", "items": _metric_ref_schema()},
            },
        },
        "shadowRunner": {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "stage",
                "bottleneck",
                "applicableDomain",
                "marginalGain",
                "minimalReversibleNextStep",
            ],
            "properties": {
                "stage": {"type": ["string", "null"]},
                "bottleneck": {"type": ["string", "null"]},
                "applicableDomain": {"type": ["string", "null"]},
                "marginalGain": {"type": ["string", "null"]},
                "minimalReversibleNextStep": {"type": ["string", "null"]},
            },
        },
        "bottleneck": {"type": ["string", "null"]},
        "applicableDomain": {"type": ["string", "null"]},
        "marginalGain": {"type": ["string", "null"]},
        "minimalReversibleNextStep": {"type": ["string", "null"]},
        "nextTrainingSuggestion": {"type": ["string", "null"]},
        "uncertainty": {"type": "array", "items": {"type": "string"}},
    }


def structured_report_json_schema(*, include_runtime_fields: bool = True) -> dict[str, Any]:
    """Return the sole StructuredReport schema source.

    The model-output variant omits runtime identity/version fields. The engine
    injects those deterministic fields after the response is validated.
    """

    semantic = _semantic_properties()
    properties = deepcopy(semantic)
    required = list(semantic)
    if include_runtime_fields:
        runtime = {
            "schemaVersion": {"type": "string", "const": "1.1"},
            "engineVersion": {"type": "string"},
            "engineCommit": {"type": ["string", "null"]},
            "promptVersion": {"type": "string"},
            "rendererVersion": {"type": "string"},
            "runId": {"type": "string", "pattern": "^[1-9][0-9]*$"},
            "reportDate": {"type": "string", "pattern": "^[0-9]{4}-[0-9]{2}-[0-9]{2}$"},
        }
        properties = {**runtime, **properties}
        required = list(runtime) + required
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://ayu-running.example/schemas/structured-report-1.1.json",
        "title": "Ayu StructuredReport",
        "type": "object",
        "additionalProperties": False,
        "required": required,
        "properties": properties,
    }


def daily_run_context_json_schema() -> dict[str, Any]:
    """Return the v1.1 DailyRunContext schema from the same contract source."""

    metric = {"type": ["number", "null"], "minimum": 0}
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://ayu-running.example/schemas/daily-run-context-1.1.json",
        "title": "Ayu DailyRunContext",
        "type": "object",
        "additionalProperties": True,
        "required": [
            "schemaVersion",
            "runId",
            "localDate",
            "startDatetimeLocal",
            "timezone",
            "timezoneSource",
            "sport",
            "distanceM",
            "displayDurationSource",
            "structuredWorkout",
            "workoutIntent",
            "evidence",
        ],
        "properties": {
            "schemaVersion": {"type": "string", "const": "1.1"},
            "engineVersion": {"type": "string"},
            "engineCommit": {"type": ["string", "null"]},
            "promptVersion": {"type": "string"},
            "rendererVersion": {"type": "string"},
            "runId": {"type": "string", "pattern": "^[1-9][0-9]*$"},
            "localDate": {"type": "string", "pattern": "^[0-9]{4}-[0-9]{2}-[0-9]{2}$"},
            "startDatetimeLocal": {"type": "string", "minLength": 10},
            "timezone": {"type": ["string", "null"]},
            "timezoneSource": {"enum": ["source", "config", "derived", "unknown"]},
            "sport": {"type": "string", "minLength": 1},
            "subtype": {"type": ["string", "null"]},
            "title": {"type": ["string", "null"]},
            "distanceM": {"type": "number", "minimum": 0},
            "timerTimeSec": metric,
            "elapsedTimeSec": metric,
            "movingTimeSec": metric,
            "displayDurationSource": {
                "enum": ["moving_time", "timer_time", "elapsed_time", "unknown"]
            },
            "averageSpeedMps": metric,
            "averagePaceSecPerKm": metric,
            "averageHrBpm": metric,
            "maxHrBpm": metric,
            "cadenceRawValue": metric,
            "cadenceRawUnit": {"type": ["string", "null"]},
            "cadenceRawField": {"type": ["string", "null"]},
            "cadenceRawMessage": {"type": ["string", "null"]},
            "cadenceRawOrigin": {
                "type": ["string", "null"],
                "enum": ["native", "developer", "unknown", None],
            },
            "cadenceNormalizedSpm": metric,
            "strideM": metric,
            "powerW": metric,
            "ascentM": metric,
            "laps": {"type": ["array", "null"]},
            "splits": {"type": ["array", "null"]},
            "structuredWorkout": {"type": ["object", "null"]},
            "workoutIntent": {"type": "string", "enum": ["structured", "unknown"]},
            "trainingEffectAerobic": metric,
            "trainingEffectAnaerobic": metric,
            "trainingLoadPeak": metric,
            "recoveryPercent": metric,
            "recoveryHours": metric,
            "runningFitness": {"type": ["number", "null"]},
            "evidence": {"type": "array", "items": {"type": "object"}},
        },
    }


def structured_report_model_json_schema() -> dict[str, Any]:
    return structured_report_json_schema(include_runtime_fields=False)
