"""Analyzer boundary and a deterministic, network-free fixture analyzer."""

from __future__ import annotations

from typing import Protocol

from .context import DailyRunContext
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
        for field_name, value, unit in (
            ("distanceM", context.distance_m, "m"),
            ("durationSec", context.duration_sec, "s"),
            ("averageSpeedMps", context.average_speed_mps, "m/s"),
            ("averageHrBpm", context.average_hr_bpm, "bpm"),
            ("powerW", context.power_w, "W"),
            ("ascentM", context.ascent_m, "m"),
        ):
            if value is not None:
                evidence.append(
                    {
                        "field": field_name,
                        "value": value,
                        "unit": unit,
                        "source": context.evidence[0].source_type
                        if context.evidence
                        else "unknown",
                        "interpretation": None,
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
        return StructuredReport(
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
                "trainingEffectAerobic": context.training_effect_aerobic,
                "trainingEffectAnaerobic": context.training_effect_anaerobic,
                "trainingLoadPeak": context.training_load_peak,
            },
            recovery={
                "percent": context.recovery_percent,
                "hours": context.recovery_hours,
                "runningFitness": context.running_fitness,
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
