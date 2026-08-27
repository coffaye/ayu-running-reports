"""Structured semantic report and lightweight schema validation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
import math
import re
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

_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _check_text(value: object, field: str, *, nullable: bool = False) -> None:
    if value is None and nullable:
        return
    if not isinstance(value, str):
        raise SchemaValidationError(f"{field} must be a string")


def _check_number(value: object, field: str, *, nullable: bool = True) -> None:
    if value is None and nullable:
        return
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise SchemaValidationError(f"{field} must be numeric or null")
    if not math.isfinite(float(value)):
        raise SchemaValidationError(f"{field} must be finite")


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
        if not _DATE.fullmatch(self.report_date):
            raise SchemaValidationError("reportDate must be YYYY-MM-DD")
        try:
            datetime.strptime(self.report_date, "%Y-%m-%d")
        except ValueError as exc:
            raise SchemaValidationError("reportDate is not a real calendar date") from exc
        _check_text(self.verdict, "verdict")
        _check_text(self.training_purpose, "trainingPurpose", nullable=True)
        if not isinstance(self.completion, Mapping):
            raise SchemaValidationError("completion must be an object")
        _check_text(self.completion.get("status"), "completion.status", nullable=True)
        _check_text(
            self.completion.get("trainingType"),
            "completion.trainingType",
            nullable=True,
        )
        score = self.completion.get("score")
        _check_number(score, "completion.score")
        if score is not None and not 0 <= float(score) <= 10:
            raise SchemaValidationError("completion.score must be between 0 and 10")
        if not isinstance(self.evidence, tuple):
            raise SchemaValidationError("evidence must be a tuple internally")
        for index, item in enumerate(self.evidence):
            if not isinstance(item, Mapping):
                raise SchemaValidationError(f"evidence[{index}] must be an object")
            _check_text(item.get("field"), f"evidence[{index}].field")
            _check_text(item.get("unit"), f"evidence[{index}].unit")
            _check_text(item.get("source"), f"evidence[{index}].source")
            _check_number(item.get("value"), f"evidence[{index}].value")
        _check_text(self.physiology_cost, "physiologyCost", nullable=True)
        if self.load is not None and not isinstance(self.load, Mapping):
            raise SchemaValidationError("load must be an object or null")
        if self.recovery is not None and not isinstance(self.recovery, Mapping):
            raise SchemaValidationError("recovery must be an object or null")
        if not isinstance(self.shadowrunner, Mapping):
            raise SchemaValidationError("shadowRunner must be an object")
        for name, value in (
            ("bottleneck", self.bottleneck),
            ("applicableDomain", self.applicable_domain),
            ("marginalGain", self.marginal_gain),
            ("minimalReversibleNextStep", self.minimal_reversible_next_step),
            ("nextTrainingSuggestion", self.next_training_suggestion),
        ):
            _check_text(value, name, nullable=True)
        if not isinstance(self.uncertainty, tuple) or any(
            not isinstance(value, str) for value in self.uncertainty
        ):
            raise SchemaValidationError("uncertainty must be a tuple of strings internally")

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
    """Validate model output before it reaches a renderer."""

    if not isinstance(value, Mapping):
        raise SchemaValidationError("StructuredReport must be an object")
    required = {
        "schemaVersion",
        "runId",
        "reportDate",
        "verdict",
        "trainingPurpose",
        "completion",
        "evidence",
        "physiologyCost",
        "load",
        "recovery",
        "shadowRunner",
        "bottleneck",
        "applicableDomain",
        "marginalGain",
        "minimalReversibleNextStep",
        "nextTrainingSuggestion",
        "uncertainty",
    }
    missing = sorted(required - set(value))
    if missing:
        raise SchemaValidationError(f"StructuredReport missing fields: {', '.join(missing)}")
    if not isinstance(value.get("evidence"), list):
        raise SchemaValidationError("evidence must be an array")
    if not isinstance(value.get("uncertainty"), list) or any(
        not isinstance(item, str) for item in value.get("uncertainty", [])
    ):
        raise SchemaValidationError("uncertainty must be an array of strings")
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
            engine_version=value.get("engineVersion", ENGINE_VERSION),
            engine_commit=value.get("engineCommit"),
            prompt_version=value.get("promptVersion", PROMPT_VERSION),
            renderer_version=value.get("rendererVersion", RENDERER_VERSION),
        )
    except (KeyError, TypeError) as exc:
        raise SchemaValidationError("StructuredReport has invalid shape") from exc
