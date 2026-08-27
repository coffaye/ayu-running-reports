"""Ayu Running's shared report-engine boundary.

The package intentionally contains no network client and never calls DeepSeek.
It normalizes local files, validates semantic report data, and renders a
deterministic report.  A future analyzer can implement ``ReportAnalyzer``
without changing the renderer or the Codex Skill contract.
"""

from .analysis import FixtureAnalyzer, ReportAnalyzer
from .context import DailyRunContext, SourceEvidence
from .errors import (
    DataMismatchError,
    DataSourceError,
    IdentityError,
    SchemaValidationError,
)
from .report import StructuredReport, validate_structured_report
from .render import render_html

__all__ = [
    "DailyRunContext",
    "DataMismatchError",
    "DataSourceError",
    "FixtureAnalyzer",
    "IdentityError",
    "ReportAnalyzer",
    "SchemaValidationError",
    "SourceEvidence",
    "StructuredReport",
    "render_html",
    "validate_structured_report",
]
