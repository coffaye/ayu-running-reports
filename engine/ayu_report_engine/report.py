"""Structured semantic report and local validation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
import math
import re
from typing import Any, Mapping

from .context import DailyRunContext
from .errors import SchemaValidationError
from .identity import normalize_run_id
from .metrics import ALLOWED_METRIC_REFS, validate_metric_refs
from .schema import structured_report_json_schema
from .version import ENGINE_VERSION, PROMPT_VERSION, RENDERER_VERSION, SCHEMA_VERSION, runtime_engine_commit

_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_NARRATIVE_FORBIDDEN = (
    "metricRef",
    "summary.",
    "plannedWorkout",
    "structuredWorkout",
    "workoutIntent",
    "averageHrBpm",
    "maxHrBpm",
    "averagePaceSecPerKm",
    "displayDurationSec",
    "timerTimeSec",
    "elapsedTimeSec",
    "movingTimeSec",
    "cadenceNormalizedSpm",
    "recoveryPercent",
    "recoveryHours",
    "runningFitness",
    "trainingLoadPeak",
    "trainingEffectAerobic",
    "trainingEffectAnaerobic",
    "distanceM",
    "powerW",
    "ascentM",
)


def _check_text(value: object, field: str, *, nullable: bool = False) -> None:
    if value is None and nullable:
        return
    if not isinstance(value, str):
        raise SchemaValidationError(f"{field} must be a string")


def _check_narrative(value: object, field: str, *, nullable: bool = False) -> None:
    """Keep user-facing semantic strings free of raw values and schema keys."""

    _check_text(value, field, nullable=nullable)
    if value is None and nullable:
        return
    assert isinstance(value, str)
    if re.search(r"\d", value):
        raise SchemaValidationError(f"{field} must not contain raw numeric values")
    if "null" in value.lower():
        raise SchemaValidationError(f"{field} must not contain the literal null")
    if any(token in value for token in _NARRATIVE_FORBIDDEN):
        raise SchemaValidationError(f"{field} must not contain schema field names")


def _check_number(value: object, field: str, *, nullable: bool = True) -> None:
    if value is None and nullable:
        return
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise SchemaValidationError(f"{field} must be numeric or null")
    if not math.isfinite(float(value)):
        raise SchemaValidationError(f"{field} must be finite")


def _check_semantic_block(value: object, field: str) -> None:
    if not isinstance(value, Mapping):
        raise SchemaValidationError(f"{field} must be an object")
    if set(value) != {"assessment", "metricRefs"}:
        raise SchemaValidationError(f"{field} must contain assessment and metricRefs only")
    _check_narrative(value.get("assessment"), f"{field}.assessment", nullable=True)
    refs = value.get("metricRefs")
    if not isinstance(refs, list) or any(not isinstance(ref, str) for ref in refs):
        raise SchemaValidationError(f"{field}.metricRefs must be an array of strings")
    if any(ref not in ALLOWED_METRIC_REFS for ref in refs):
        raise SchemaValidationError(f"{field}.metricRefs contains an unapproved metricRef")


@dataclass(frozen=True)
class StructuredReport:
    run_id: str
    report_date: str
    verdict: str
    training_purpose: str | None
    completion: Mapping[str, Any]
    evidence: tuple[Mapping[str, Any], ...]
    physiology_cost: str | None
    load: Mapping[str, Any] | None
    recovery: Mapping[str, Any] | None
    shadowrunner: Mapping[str, Any]
    bottleneck: str | None
    applicable_domain: str | None
    marginal_gain: str | None
    minimal_reversible_next_step: str | None
    next_training_suggestion: str | None
    uncertainty: tuple[str, ...]
    schema_version: str = SCHEMA_VERSION
    engine_version: str = ENGINE_VERSION
    engine_commit: str | None = None
    prompt_version: str = PROMPT_VERSION
    renderer_version: str = RENDERER_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(self, "run_id", normalize_run_id(self.run_id))
        if self.schema_version != SCHEMA_VERSION:
            raise SchemaValidationError("unsupported StructuredReport schemaVersion")
        _check_text(self.engine_version, "engineVersion")
        _check_text(self.engine_commit, "engineCommit", nullable=True)
        _check_text(self.prompt_version, "promptVersion")
        _check_text(self.renderer_version, "rendererVersion")
        if not isinstance(self.report_date, str) or not _DATE.fullmatch(self.report_date):
            raise SchemaValidationError("reportDate must be YYYY-MM-DD")
        try:
            datetime.strptime(self.report_date, "%Y-%m-%d")
        except ValueError as exc:
            raise SchemaValidationError("reportDate is not a real calendar date") from exc
        _check_narrative(self.verdict, "verdict")
        _check_narrative(self.training_purpose, "trainingPurpose", nullable=True)
        if not isinstance(self.completion, Mapping):
            raise SchemaValidationError("completion must be an object")
        if set(self.completion) != {"status", "trainingType", "score"}:
            raise SchemaValidationError("completion has unexpected fields")
        _check_narrative(self.completion.get("status"), "completion.status", nullable=True)
        _check_narrative(self.completion.get("trainingType"), "completion.trainingType", nullable=True)
        score = self.completion.get("score")
        _check_number(score, "completion.score")
        if score is not None and not 0 <= float(score) <= 10:
            raise SchemaValidationError("completion.score must be between 0 and 10")
        if not isinstance(self.evidence, tuple):
            raise SchemaValidationError("evidence must be a tuple internally")
        for index, item in enumerate(self.evidence):
            if not isinstance(item, Mapping) or set(item) != {"metricRef", "interpretation"}:
                raise SchemaValidationError(
                    f"evidence[{index}] must contain metricRef and interpretation only"
                )
            _check_text(item.get("metricRef"), f"evidence[{index}].metricRef")
            _check_narrative(item.get("interpretation"), f"evidence[{index}].interpretation")
            if item.get("metricRef") not in ALLOWED_METRIC_REFS:
                raise SchemaValidationError(f"evidence[{index}].metricRef is not allowed")
        _check_narrative(self.physiology_cost, "physiologyCost", nullable=True)
        if self.load is not None:
            _check_semantic_block(self.load, "load")
        if self.recovery is not None:
            _check_semantic_block(self.recovery, "recovery")
        if not isinstance(self.shadowrunner, Mapping):
            raise SchemaValidationError("shadowRunner must be an object")
        required_shadow = {
            "stage",
            "bottleneck",
            "applicableDomain",
            "marginalGain",
            "minimalReversibleNextStep",
        }
        if set(self.shadowrunner) != required_shadow:
            raise SchemaValidationError("shadowRunner has unexpected fields")
        for name, value in self.shadowrunner.items():
            _check_narrative(value, f"shadowRunner.{name}", nullable=True)
        for top_name, nested_name in (
            ("bottleneck", "bottleneck"),
            ("applicable_domain", "applicableDomain"),
            ("marginal_gain", "marginalGain"),
            ("minimal_reversible_next_step", "minimalReversibleNextStep"),
        ):
            top_value = getattr(self, top_name)
            nested_value = self.shadowrunner.get(nested_name)
            if top_value is not None and nested_value is not None and top_value != nested_value:
                raise SchemaValidationError(f"{top_name} conflicts with shadowRunner.{nested_name}")
        for name, value in (
            ("bottleneck", self.bottleneck),
            ("applicableDomain", self.applicable_domain),
            ("marginalGain", self.marginal_gain),
            ("minimalReversibleNextStep", self.minimal_reversible_next_step),
            ("nextTrainingSuggestion", self.next_training_suggestion),
        ):
            _check_narrative(value, name, nullable=True)
        if not isinstance(self.uncertainty, tuple) or any(
            not isinstance(value, str) for value in self.uncertainty
        ):
            raise SchemaValidationError("uncertainty must be a tuple of strings internally")
        for index, value in enumerate(self.uncertainty):
            _check_narrative(value, f"uncertainty[{index}]")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schemaVersion": self.schema_version,
            "engineVersion": self.engine_version,
            "engineCommit": self.engine_commit or runtime_engine_commit(),
            "promptVersion": self.prompt_version,
            "rendererVersion": self.renderer_version,
            "runId": self.run_id,
            "reportDate": self.report_date,
            "verdict": self.verdict,
            "trainingPurpose": self.training_purpose,
            "completion": dict(self.completion),
            "evidence": [dict(item) for item in self.evidence],
            "physiologyCost": self.physiology_cost,
            "load": dict(self.load) if self.load is not None else None,
            "recovery": dict(self.recovery) if self.recovery is not None else None,
            "shadowRunner": dict(self.shadowrunner),
            "bottleneck": self.bottleneck,
            "applicableDomain": self.applicable_domain,
            "marginalGain": self.marginal_gain,
            "minimalReversibleNextStep": self.minimal_reversible_next_step,
            "nextTrainingSuggestion": self.next_training_suggestion,
            "uncertainty": list(self.uncertainty),
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, sort_keys=True)


def validate_structured_report(value: Mapping[str, Any]) -> None:
    """Validate a complete engine report against the canonical schema shape."""

    schema = structured_report_json_schema()
    if not isinstance(value, Mapping):
        raise SchemaValidationError("StructuredReport must be an object")
    if value.get("schemaVersion") != SCHEMA_VERSION:
        raise SchemaValidationError("StructuredReport schemaVersion is unsupported")
    required = set(schema["required"])
    missing = sorted(required - set(value))
    if missing:
        raise SchemaValidationError(f"StructuredReport missing fields: {', '.join(missing)}")
    unexpected = sorted(set(value) - set(schema["properties"]))
    if unexpected:
        raise SchemaValidationError(f"StructuredReport has unexpected fields: {', '.join(unexpected)}")
    try:
        StructuredReport(
            run_id=value["runId"],
            report_date=value["reportDate"],
            verdict=value["verdict"],
            training_purpose=value["trainingPurpose"],
            completion=value["completion"],
            evidence=tuple(value["evidence"]),
            physiology_cost=value["physiologyCost"],
            load=value["load"],
            recovery=value["recovery"],
            shadowrunner=value["shadowRunner"],
            bottleneck=value["bottleneck"],
            applicable_domain=value["applicableDomain"],
            marginal_gain=value["marginalGain"],
            minimal_reversible_next_step=value["minimalReversibleNextStep"],
            next_training_suggestion=value["nextTrainingSuggestion"],
            uncertainty=tuple(value["uncertainty"]),
            schema_version=value["schemaVersion"],
            engine_version=value["engineVersion"],
            engine_commit=value["engineCommit"],
            prompt_version=value["promptVersion"],
            renderer_version=value["rendererVersion"],
        )
    except (KeyError, TypeError) as exc:
        raise SchemaValidationError("StructuredReport has invalid shape") from exc


def validate_model_output(value: Mapping[str, Any]) -> None:
    """Validate the model-only semantic payload before identity injection."""

    schema = structured_report_json_schema(include_runtime_fields=False)
    if not isinstance(value, Mapping):
        raise SchemaValidationError("DeepSeek output must be an object")
    missing = sorted(set(schema["required"]) - set(value))
    if missing:
        raise SchemaValidationError(f"DeepSeek output missing fields: {', '.join(missing)}")
    unexpected = sorted(set(value) - set(schema["properties"]))
    if unexpected:
        raise SchemaValidationError(f"DeepSeek output has unexpected fields: {', '.join(unexpected)}")
    StructuredReport(
        run_id="1",
        report_date="2000-01-01",
        verdict=value["verdict"],
        training_purpose=value["trainingPurpose"],
        completion=value["completion"],
        evidence=tuple(value["evidence"]),
        physiology_cost=value["physiologyCost"],
        load=value["load"],
        recovery=value["recovery"],
        shadowrunner=value["shadowRunner"],
        bottleneck=value["bottleneck"],
        applicable_domain=value["applicableDomain"],
        marginal_gain=value["marginalGain"],
        minimal_reversible_next_step=value["minimalReversibleNextStep"],
        next_training_suggestion=value["nextTrainingSuggestion"],
        uncertainty=tuple(value["uncertainty"]),
    )


def report_from_model_output(value: Mapping[str, Any], context: DailyRunContext) -> StructuredReport:
    validate_model_output(value)
    report = StructuredReport(
        run_id=context.run_id,
        report_date=context.local_date,
        verdict=value["verdict"],
        training_purpose=value["trainingPurpose"],
        completion=value["completion"],
        evidence=tuple(value["evidence"]),
        physiology_cost=value["physiologyCost"],
        load=value["load"],
        recovery=value["recovery"],
        shadowrunner=value["shadowRunner"],
        bottleneck=value["bottleneck"],
        applicable_domain=value["applicableDomain"],
        marginal_gain=value["marginalGain"],
        minimal_reversible_next_step=value["minimalReversibleNextStep"],
        next_training_suggestion=value["nextTrainingSuggestion"],
        uncertainty=tuple(value["uncertainty"]),
    )
    validate_metric_refs(report, context)
    validate_structured_report(report.to_dict())
    return report
