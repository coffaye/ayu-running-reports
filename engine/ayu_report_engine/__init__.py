"""Ayu Running's shared report-engine boundary.

The package keeps network access opt-in: importing it, using fixture analysis,
or running ordinary tests never calls DeepSeek.  The explicit
``DeepSeekAnalyzer`` path normalizes local files, validates semantic report
data, and renders a deterministic report without exposing provider payloads.
"""

from .analysis import FixtureAnalyzer, ReportAnalyzer
from .context import DailyRunContext, SourceEvidence
from .deepseek import (
    AnalysisResult,
    AnalyzerMetadata,
    DeepSeekAnalyzer,
    DeepSeekConfig,
    DeepSeekError,
    MissingAPIKeyError,
)
from .errors import (
    DataMismatchError,
    DataSourceError,
    IdentityError,
    SchemaValidationError,
)
from .report import (
    StructuredReport,
    report_from_model_output,
    validate_model_output,
    validate_structured_report,
)
from .render import render_html
from .schema import (
    STRUCTURED_REPORT_SCHEMA_NAME,
    daily_run_context_json_schema,
    structured_report_json_schema,
    structured_report_model_json_schema,
)

__all__ = [
    "DailyRunContext",
    "DeepSeekAnalyzer",
    "DeepSeekConfig",
    "DeepSeekError",
    "MissingAPIKeyError",
    "AnalysisResult",
    "AnalyzerMetadata",
    "DataMismatchError",
    "DataSourceError",
    "FixtureAnalyzer",
    "IdentityError",
    "ReportAnalyzer",
    "SchemaValidationError",
    "SourceEvidence",
    "StructuredReport",
    "report_from_model_output",
    "validate_model_output",
    "render_html",
    "validate_structured_report",
    "STRUCTURED_REPORT_SCHEMA_NAME",
    "daily_run_context_json_schema",
    "structured_report_json_schema",
    "structured_report_model_json_schema",
]
