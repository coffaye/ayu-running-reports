"""Analyzer boundary and a deterministic, network-free fixture analyzer."""

from __future__ import annotations

from typing import Protocol

from .context import DailyRunContext
from .metrics import validate_metric_refs
from .report import StructuredReport


class ReportAnalyzer(Protocol):
    """Both FixtureAnalyzer and a future DeepSeekAnalyzer implement this API."""

    def analyze(self, context: DailyRunContext) -> StructuredReport:
        ...


class FixtureAnalyzer:
    """Produce honest semantic output for renderer tests without model calls."""

    def analyze(self, context: DailyRunContext) -> StructuredReport:
        workout = context.structured_workout
        purpose = "结构化课表" if workout is not None else None
        training_type = "structured" if workout is not None else None
        verdict = (
            "已识别结构化训练证据，完成质量需要实际课表对照"
            if workout is not None
            else "基础跑步数据已规范化，但训练意图未知"
        )
        evidence = []
        for metric_ref, value in (
            ("summary.distanceM", context.distance_m),
            ("summary.displayDurationSec", context.display_duration_sec),
            ("summary.averagePaceSecPerKm", context.average_pace_sec_per_km),
            ("summary.averageHrBpm", context.average_hr_bpm),
            ("summary.powerW", context.power_w),
            ("summary.ascentM", context.ascent_m),
        ):
            if value is not None:
                evidence.append(
                    {
                        "metricRef": metric_ref,
                        "interpretation": "确定性引擎提供的实测事实，待分析层解释。",
                    }
                )
        missing = [
            label
            for label, value in (
                ("heart-rate", context.average_hr_bpm),
                ("power", context.power_w),
                ("structured-workout", context.structured_workout),
                ("recovery", context.recovery_hours),
            )
            if value is None
        ]
        report = StructuredReport(
            run_id=context.run_id,
            report_date=context.local_date,
            verdict=verdict,
            training_purpose=purpose,
            completion={
                "status": None,
                "trainingType": training_type,
                "score": None,
            },
            evidence=tuple(evidence),
            physiology_cost=None,
            load={
                "assessment": None,
                "metricRefs": [
                    ref
                    for ref, value in (
                        ("summary.trainingEffectAerobic", context.training_effect_aerobic),
                        ("summary.trainingEffectAnaerobic", context.training_effect_anaerobic),
                        ("summary.trainingLoadPeak", context.training_load_peak),
                    )
                    if value is not None
                ],
            },
            recovery={
                "assessment": None,
                "metricRefs": [
                    ref
                    for ref, value in (
                        ("summary.recoveryPercent", context.recovery_percent),
                        ("summary.recoveryHours", context.recovery_hours),
                        ("summary.runningFitness", context.running_fitness),
                    )
                    if value is not None
                ],
            },
            shadowrunner={
                "stage": None,
                "bottleneck": None,
                "applicableDomain": None,
                "marginalGain": None,
                "minimalReversibleNextStep": None,
            },
            bottleneck=None,
            applicable_domain=None,
            marginal_gain=None,
            minimal_reversible_next_step=None,
            next_training_suggestion=None,
            uncertainty=tuple(f"{item} unavailable" for item in missing),
        )
        validate_metric_refs(report, context)
        return report
