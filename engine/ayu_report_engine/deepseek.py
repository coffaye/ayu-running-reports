"""Explicit DeepSeek Responses API analyzer with safe retries and metadata."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import math
import os
from pathlib import Path
import socket
import time
from typing import Any, Callable, Mapping, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .context import DailyRunContext
from .errors import EngineError, SchemaValidationError
from .metrics import ALLOWED_METRIC_REFS, context_for_model, resolve_metric_ref
from .prompt import build_instructions
from .report import StructuredReport, report_from_model_output
from .schema import STRUCTURED_REPORT_SCHEMA_NAME, structured_report_model_json_schema
from .version import ENGINE_VERSION

DEFAULT_BASE_URL = "https://api.deepseek.com"
DEFAULT_MODEL = "deepseek-v4-flash"
DEFAULT_REASONING_EFFORT = "high"
DEFAULT_MAX_OUTPUT_TOKENS = 16384
DEFAULT_TIMEOUT_SECONDS = 60.0
MAX_RETRIES = 1
ALLOWED_REASONING_EFFORTS = frozenset({"none", "minimal", "low", "medium", "high", "xhigh", "max"})
ENV_FILE_NAMES = (".env.local", ".env")
ENV_FILE_KEYS = frozenset(
    {
        "DEEPSEEK_API_KEY",
        "DEEPSEEK_BASE_URL",
        "DEEPSEEK_MODEL",
        "DEEPSEEK_REASONING_EFFORT",
        "DEEPSEEK_MAX_OUTPUT_TOKENS",
        "DEEPSEEK_TIMEOUT_SECONDS",
    }
)


class DeepSeekError(EngineError):
    """Safe API failure with a category, never provider body or credentials."""

    def __init__(
        self,
        message: str,
        *,
        category: str,
        status_code: int | None = None,
        retryable: bool = False,
        retry_after: float | None = None,
    ) -> None:
        super().__init__(message)
        self.category = category
        self.status_code = status_code
        self.retryable = retryable
        self.retry_after = retry_after


class MissingAPIKeyError(DeepSeekError):
    def __init__(self) -> None:
        super().__init__(
            "DEEPSEEK_API_KEY is required for explicit deepseek analyzer use",
            category="missing_api_key",
        )


@dataclass(frozen=True, repr=False)
class DeepSeekConfig:
    api_key: str | None = field(default=None, repr=False)
    base_url: str = DEFAULT_BASE_URL
    model: str = DEFAULT_MODEL
    reasoning_effort: str = DEFAULT_REASONING_EFFORT
    max_output_tokens: int = DEFAULT_MAX_OUTPUT_TOKENS
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS

    def __post_init__(self) -> None:
        if not isinstance(self.reasoning_effort, str):
            raise ValueError("reasoning_effort must be a string")
        effort = self.reasoning_effort.strip().lower()
        if effort not in ALLOWED_REASONING_EFFORTS:
            raise ValueError(f"unsupported reasoning effort: {self.reasoning_effort}")
        object.__setattr__(self, "reasoning_effort", effort)
        if not isinstance(self.model, str) or not self.model.strip():
            raise ValueError("model must be non-empty")
        if not isinstance(self.base_url, str) or not self.base_url.strip():
            raise ValueError("base_url must be non-empty")
        if (
            isinstance(self.max_output_tokens, bool)
            or not isinstance(self.max_output_tokens, int)
            or self.max_output_tokens <= 0
        ):
            raise ValueError("max_output_tokens must be positive")
        if (
            isinstance(self.timeout_seconds, bool)
            or not isinstance(self.timeout_seconds, (int, float))
            or not math.isfinite(float(self.timeout_seconds))
            or self.timeout_seconds <= 0
        ):
            raise ValueError("timeout_seconds must be positive")

    @classmethod
    def from_env(
        cls,
        *,
        load_local_files: bool = False,
        env_file: str | os.PathLike[str] | None = None,
    ) -> "DeepSeekConfig":
        local = _local_env_values(env_file=env_file) if load_local_files else {}

        def setting(name: str, default: str) -> str:
            value = os.getenv(name)
            return value if value is not None else local.get(name, default)

        def positive_int(name: str, default: int) -> int:
            raw = setting(name, str(default)).strip()
            try:
                value = int(raw)
            except ValueError as exc:
                raise ValueError(f"{name} must be an integer") from exc
            if value <= 0:
                raise ValueError(f"{name} must be positive")
            return value

        def positive_float(name: str, default: float) -> float:
            raw = setting(name, str(default)).strip()
            try:
                value = float(raw)
            except ValueError as exc:
                raise ValueError(f"{name} must be a number") from exc
            if value <= 0:
                raise ValueError(f"{name} must be positive")
            return value

        return cls(
            api_key=setting("DEEPSEEK_API_KEY", "").strip() or None,
            base_url=setting("DEEPSEEK_BASE_URL", DEFAULT_BASE_URL).strip() or DEFAULT_BASE_URL,
            model=setting("DEEPSEEK_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL,
            reasoning_effort=setting("DEEPSEEK_REASONING_EFFORT", DEFAULT_REASONING_EFFORT).strip(),
            max_output_tokens=positive_int("DEEPSEEK_MAX_OUTPUT_TOKENS", DEFAULT_MAX_OUTPUT_TOKENS),
            timeout_seconds=positive_float("DEEPSEEK_TIMEOUT_SECONDS", DEFAULT_TIMEOUT_SECONDS),
        )

    def __repr__(self) -> str:
        key_state = "configured" if self.api_key else "missing"
        return (
            "DeepSeekConfig(api_key=<%s>, base_url=%r, model=%r, reasoning_effort=%r, "
            "max_output_tokens=%r, timeout_seconds=%r)"
            % (
                key_state,
                self.base_url,
                self.model,
                self.reasoning_effort,
                self.max_output_tokens,
                self.timeout_seconds,
            )
        )


@dataclass(frozen=True)
class TransportResponse:
    status_code: int
    body: Mapping[str, Any]
    headers: Mapping[str, str] = field(default_factory=dict)


class Transport(Protocol):
    def __call__(
        self,
        url: str,
        headers: Mapping[str, str],
        payload: Mapping[str, Any],
        timeout: float,
    ) -> TransportResponse:
        ...


@dataclass(frozen=True)
class AnalyzerMetadata:
    provider: str
    model_requested: str
    model_returned: str | None
    response_id: str | None
    latency_ms: int
    input_tokens: int | None
    output_tokens: int | None
    reasoning_tokens: int | None
    total_tokens: int | None
    reasoning_effort: str
    retry_count: int
    http_status: int | None = None
    response_status: str | None = None
    analyzer_version: str = ENGINE_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "modelRequested": self.model_requested,
            "modelReturned": self.model_returned,
            "responseId": self.response_id,
            "latencyMs": self.latency_ms,
            "inputTokens": self.input_tokens,
            "outputTokens": self.output_tokens,
            "reasoningTokens": self.reasoning_tokens,
            "totalTokens": self.total_tokens,
            "reasoningEffort": self.reasoning_effort,
            "retryCount": self.retry_count,
            "httpStatus": self.http_status,
            "responseStatus": self.response_status,
            "analyzerVersion": self.analyzer_version,
        }


@dataclass(frozen=True)
class AnalysisResult:
    report: StructuredReport
    metadata: AnalyzerMetadata


def _retry_after(headers: Mapping[str, str]) -> float | None:
    raw = next((value for key, value in headers.items() if key.lower() == "retry-after"), None)
    if raw is None:
        return None
    try:
        return max(0.0, min(float(raw), 8.0))
    except (TypeError, ValueError):
        return None


def _default_transport(
    url: str,
    headers: Mapping[str, str],
    payload: Mapping[str, Any],
    timeout: float,
) -> TransportResponse:
    request = Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers=dict(headers),
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            try:
                body = json.loads(response.read().decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                raise DeepSeekError(
                    "DeepSeek response body is not valid JSON",
                    category="malformed_response",
                ) from None
            if not isinstance(body, Mapping):
                body = {}
            return TransportResponse(response.status, body, dict(response.headers.items()))
    except HTTPError as exc:
        # Consume and discard the provider body; it may echo request material.
        try:
            exc.read()
        except Exception:
            pass
        return TransportResponse(exc.code, {}, dict(exc.headers.items()) if exc.headers else {})
    except (URLError, TimeoutError, socket.timeout, OSError) as exc:
        raise DeepSeekError(
            "DeepSeek request timed out or network failed",
            category="timeout" if isinstance(exc, (TimeoutError, socket.timeout)) else "network",
            retryable=True,
        ) from None


def _http_error(response: TransportResponse) -> DeepSeekError:
    code = response.status_code
    retryable = code == 408 or code == 429 or code >= 500
    category = (
        "bad_request"
        if code == 400
        else "authentication"
        if code in {401, 403}
        else "timeout"
        if code == 408
        else "rate_limit"
        if code == 429
        else "server"
        if code >= 500
        else "http_error"
    )
    return DeepSeekError(
        f"DeepSeek API returned HTTP {code}",
        category=category,
        status_code=code,
        retryable=retryable,
        retry_after=_retry_after(response.headers),
    )


def _extract_output_text(body: Mapping[str, Any]) -> str:
    output = body.get("output")
    if not isinstance(output, list):
        raise DeepSeekError("DeepSeek response has no output messages", category="malformed_response")
    parts: list[str] = []
    for item in output:
        if not isinstance(item, Mapping) or item.get("type") != "message":
            # Reasoning and tool items are deliberately ignored.
            continue
        content = item.get("content")
        if not isinstance(content, list):
            continue
        for part in content:
            if isinstance(part, Mapping) and part.get("type") == "output_text":
                text = part.get("text")
                if isinstance(text, str):
                    parts.append(text)
    if not parts:
        raise DeepSeekError("DeepSeek response has no final output text", category="malformed_response")
    return "".join(parts)


def _usage(body: Mapping[str, Any], key: str) -> int | None:
    usage = body.get("usage")
    if not isinstance(usage, Mapping):
        return None
    value = usage.get(key)
    if value is None and key == "reasoning_tokens":
        details = usage.get("output_tokens_details")
        value = details.get(key) if isinstance(details, Mapping) else None
    return int(value) if isinstance(value, int) and not isinstance(value, bool) else None


def _read_env_file(path: Path) -> dict[str, str]:
    """Read only known DeepSeek settings from a local dotenv-style file."""

    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return {}
    values: dict[str, str] = {}
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("export "):
            stripped = stripped[7:].lstrip()
        if "=" not in stripped:
            continue
        name, value = stripped.split("=", 1)
        name = name.strip()
        if name not in ENV_FILE_KEYS:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        values[name] = value
    return values


def _local_env_values(*, env_file: str | os.PathLike[str] | None = None) -> dict[str, str]:
    if env_file is not None:
        return _read_env_file(Path(env_file))
    for directory in (Path.cwd(), *Path.cwd().parents):
        for name in ENV_FILE_NAMES:
            values = _read_env_file(directory / name)
            if values:
                return values
    return {}


class DeepSeekAnalyzer:
    """Explicit, non-default analyzer for DeepSeek Responses API calls."""

    def __init__(
        self,
        config: DeepSeekConfig | None = None,
        *,
        transport: Transport | None = None,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.config = config or DeepSeekConfig.from_env()
        self._transport = transport or _default_transport
        self._sleep = sleep
        self._clock = clock

    @property
    def endpoint(self) -> str:
        """The request URL, safe to report because it never contains a key."""

        return self.config.base_url.rstrip("/") + "/responses"

    def _payload(self, context: DailyRunContext) -> dict[str, Any]:
        available_refs = sorted(
            ref for ref in ALLOWED_METRIC_REFS if resolve_metric_ref(context, ref) is not None
        )
        instructions = (
            build_instructions()
            + "\n当前可用 metricRef（只允许引用这些）："
            + json.dumps(available_refs, ensure_ascii=False)
        )
        return {
            "model": self.config.model,
            "instructions": instructions,
            "input": json.dumps(context_for_model(context), ensure_ascii=False, sort_keys=True),
            "reasoning": {"effort": self.config.reasoning_effort},
            "max_output_tokens": self.config.max_output_tokens,
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": STRUCTURED_REPORT_SCHEMA_NAME,
                    "schema": structured_report_model_json_schema(),
                }
            },
        }

    def analyze(self, context: DailyRunContext) -> StructuredReport:
        return self.analyze_with_metadata(context).report

    def analyze_with_metadata(self, context: DailyRunContext) -> AnalysisResult:
        if not self.config.api_key:
            raise MissingAPIKeyError()
        url = self.endpoint
        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        payload = self._payload(context)
        started = self._clock()
        retry_count = 0
        while True:
            try:
                try:
                    response = self._transport(url, headers, payload, self.config.timeout_seconds)
                except (TimeoutError, socket.timeout):
                    raise DeepSeekError(
                        "DeepSeek request timed out",
                        category="timeout",
                        retryable=True,
                    ) from None
                except (URLError, OSError):
                    raise DeepSeekError(
                        "DeepSeek request network failed",
                        category="network",
                        retryable=True,
                    ) from None
                if response.status_code < 200 or response.status_code >= 300:
                    raise _http_error(response)
                if not isinstance(response.body, Mapping):
                    raise DeepSeekError(
                        "DeepSeek response is not an object",
                        category="malformed_response",
                    )
                status = response.body.get("status")
                if status == "incomplete":
                    details = response.body.get("incomplete_details")
                    reason = details.get("reason") if isinstance(details, Mapping) else None
                    raise DeepSeekError(
                        "DeepSeek response incomplete; report was not rendered",
                        category="content_filter" if reason == "content_filter" else "incomplete",
                        retryable=False,
                    )
                if status == "failed":
                    raise DeepSeekError(
                        "DeepSeek response failed; report was not rendered",
                        category="provider_failed",
                        retryable=False,
                    )
                if status != "completed":
                    raise DeepSeekError(
                        "DeepSeek response has unsupported status",
                        category="malformed_response",
                        retryable=False,
                    )
                text = _extract_output_text(response.body)
                try:
                    model_output = json.loads(text)
                except json.JSONDecodeError:
                    raise DeepSeekError(
                        "DeepSeek output is not valid JSON",
                        category="malformed_response",
                        retryable=False,
                    ) from None
                try:
                    report = report_from_model_output(model_output, context)
                except SchemaValidationError as exc:
                    raise DeepSeekError(
                        "DeepSeek output failed local validation",
                        category="validation",
                        retryable=False,
                    ) from exc
                metadata = AnalyzerMetadata(
                    provider="deepseek",
                    model_requested=self.config.model,
                    model_returned=response.body.get("model")
                    if isinstance(response.body.get("model"), str)
                    else None,
                    response_id=response.body.get("id")
                    if isinstance(response.body.get("id"), str)
                    else None,
                    latency_ms=max(0, round((self._clock() - started) * 1000)),
                    input_tokens=_usage(response.body, "input_tokens"),
                    output_tokens=_usage(response.body, "output_tokens"),
                    reasoning_tokens=_usage(response.body, "reasoning_tokens"),
                    total_tokens=_usage(response.body, "total_tokens"),
                    reasoning_effort=self.config.reasoning_effort,
                    retry_count=retry_count,
                    http_status=response.status_code,
                    response_status=status,
                )
                return AnalysisResult(report=report, metadata=metadata)
            except DeepSeekError as exc:
                if not exc.retryable or retry_count >= MAX_RETRIES:
                    raise
                retry_count += 1
                delay = exc.retry_after if exc.retry_after is not None else min(2**retry_count, 8)
                self._sleep(delay)
