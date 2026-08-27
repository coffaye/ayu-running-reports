"""Conservative, deterministic benchmark pre-scoring for semantic reports.

This is a review aid, not a replacement for human judgment. It scores only
properties the Engine can verify locally: available metric references,
uncertainty for missing facts, and presence of the required ShadowRunner and
recommendation fields. The benchmark stores both component scores and a note
that qualitative review remains required.
"""

from __future__ import annotations

import re
from typing import Any

from .context import DailyRunContext
from .metrics import resolve_metric_ref
from .report import StructuredReport

RUBRIC_MAX = {
    "factual_grounding": 25,
    "no_hallucinated_metrics": 20,
    "workout_interpretation": 15,
    "evidence_quality": 15,
    "shadowrunner_quality": 10,
    "recommendation_quality": 10,
    "uncertainty_handling": 5,
}


def _text(report: StructuredReport) -> str:
    values: list[str] = [report.verdict, report.training_purpose or ""]
    values.extend(item["interpretation"] for item in report.evidence)
    values.extend(
        value or ""
        for value in (
            report.physiology_cost,
            (report.load or {}).get("assessment") if report.load else None,
            (report.recovery or {}).get("assessment") if report.recovery else None,
            report.bottleneck,
            report.applicable_domain,
            report.marginal_gain,
            report.minimal_reversible_next_step,
            report.next_training_suggestion,
        )
    )
    values.extend(report.uncertainty)
    return " ".join(values)


def score_report(report: StructuredReport, context: DailyRunContext) -> dict[str, Any]:
    """Return safe component scores plus review notes for one report."""

    available_evidence = all(resolve_metric_ref(context, item["metricRef"]) is not None for item in report.evidence)
    load_refs_ok = not report.load or all(resolve_metric_ref(context, ref) is not None for ref in report.load["metricRefs"])
    recovery_refs_ok = not report.recovery or all(resolve_metric_ref(context, ref) is not None for ref in report.recovery["metricRefs"])
    refs_ok = available_evidence and load_refs_ok and recovery_refs_ok

    missing_facts = sum(
        value is None
        for value in (
            context.average_hr_bpm,
            context.power_w,
            context.recovery_percent,
            context.structured_workout,
        )
    )
    uncertainty_score = 5 if (missing_facts == 0 or report.uncertainty) else 0
    shadow_values = (
        report.shadowrunner.get("stage"),
        report.shadowrunner.get("bottleneck"),
        report.shadowrunner.get("minimalReversibleNextStep"),
    )
    if all(value for value in shadow_values):
        shadow_score = RUBRIC_MAX["shadowrunner_quality"]
    elif any(value for value in shadow_values):
        shadow_score = 5
    else:
        shadow_score = 0

    if context.structured_workout:
        workout_score = 15 if report.training_purpose and report.completion.get("trainingType") else 7
    else:
        workout_score = 10 if report.completion.get("trainingType") in {None, "unknown"} else 5
    recommendation_score = 10 if report.minimal_reversible_next_step or report.next_training_suggestion else 0
    evidence_score = 15 if refs_ok and report.evidence else (8 if refs_ok else 0)
    grounding_score = 25 if refs_ok else 0
    # Numeric literals in prose are a review signal, not an automatic failure;
    # the schema intentionally keeps source values out of model fields.
    numeric_signal = bool(re.search(r"(?<![A-Za-z])\d+(?:\.\d+)?", _text(report)))
    hallucination_score = 10 if refs_ok and numeric_signal else 20 if refs_ok else 0
    notes = ["mechanical pre-score; qualitative human review remains required"]
    if numeric_signal:
        notes.append("numeric literal in semantic prose requires evidence review")
    if missing_facts and not report.uncertainty:
        notes.append("missing context facts are not acknowledged in uncertainty")
    scores = {
        "factual_grounding": grounding_score,
        "no_hallucinated_metrics": hallucination_score,
        "workout_interpretation": workout_score,
        "evidence_quality": evidence_score,
        "shadowrunner_quality": shadow_score,
        "recommendation_quality": recommendation_score,
        "uncertainty_handling": uncertainty_score,
    }
    return {
        "scores": scores,
        "total": sum(scores.values()),
        "max": sum(RUBRIC_MAX.values()),
        "notes": notes,
    }
