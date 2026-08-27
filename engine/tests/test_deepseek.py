from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import tempfile
import unittest

ENGINE_ROOT = Path(__file__).parents[1]

from ayu_report_engine.adapters.fit import context_from_fit_messages
from ayu_report_engine.adapters.running_page import load_running_page_context
from ayu_report_engine.deepseek import (
    DeepSeekAnalyzer,
    DeepSeekConfig,
    DeepSeekError,
    MissingAPIKeyError,
    TransportResponse,
)
from ayu_report_engine.schema import daily_run_context_json_schema, structured_report_json_schema

FIXTURES = Path(__file__).parent / "fixtures"


def fit_context():
    raw = json.loads((FIXTURES / "fit_messages.json").read_text(encoding="utf-8"))
    raw["session_mesgs"][0]["start_time"] = datetime(
        2030, 3, 4, 22, 0, tzinfo=timezone.utc
    )
    return context_from_fit_messages(raw)


def valid_model_output() -> dict:
    return {
        "verdict": "结构化课表完成情况需要结合实测证据判断",
        "trainingPurpose": "结构化课表",
        "completion": {"status": "unknown", "trainingType": "structured", "score": None},
        "evidence": [
            {"metricRef": "summary.averageHrBpm", "interpretation": "输入提供了平均心率。"},
            {"metricRef": "summary.trainingLoadPeak", "interpretation": "输入提供了设备训练负荷。"},
        ],
        "physiologyCost": None,
        "load": {
            "assessment": "设备负荷指标可用于本次训练的相对描述。",
            "metricRefs": ["summary.trainingLoadPeak"],
        },
        "recovery": {"assessment": None, "metricRefs": []},
        "shadowRunner": {
            "stage": "证据整理",
            "bottleneck": None,
            "applicableDomain": None,
            "marginalGain": None,
            "minimalReversibleNextStep": None,
        },
        "bottleneck": None,
        "applicableDomain": None,
        "marginalGain": None,
        "minimalReversibleNextStep": None,
        "nextTrainingSuggestion": None,
        "uncertainty": ["未提供主观用力感"],
    }


class MockTransport:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def __call__(self, url, headers, payload, timeout):
        self.calls.append((url, dict(headers), payload, timeout))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def completed_response(output=None):
    return TransportResponse(
        200,
        {
            "id": "resp_test",
            "status": "completed",
            "model": "deepseek-v4-flash",
            "output": [
                {"type": "reasoning", "content": [{"type": "reasoning_text", "text": "hidden"}]},
                {
                    "type": "message",
                    "content": [{"type": "output_text", "text": json.dumps(output or valid_model_output(), ensure_ascii=False)}],
                },
            ],
            "usage": {
                "input_tokens": 100,
                "output_tokens": 80,
                "output_tokens_details": {"reasoning_tokens": 50},
                "reasoning_tokens": 50,
                "total_tokens": 180,
            },
        },
    )


class DeepSeekTests(unittest.TestCase):
    def config(self, **kwargs):
        values = {
            "api_key": "placeholder",
            "base_url": "https://example.invalid",
            "model": "deepseek-v4-flash",
            "reasoning_effort": "low",
            "max_output_tokens": 8192,
            "timeout_seconds": 1,
        }
        values.update(kwargs)
        return DeepSeekConfig(**values)

    def test_request_payload_and_schema_source(self):
        transport = MockTransport([completed_response()])
        result = DeepSeekAnalyzer(self.config(), transport=transport).analyze_with_metadata(fit_context())
        url, headers, payload, _ = transport.calls[0]
        self.assertEqual(url, "https://example.invalid/responses")
        self.assertEqual(payload["model"], "deepseek-v4-flash")
        self.assertEqual(payload["reasoning"], {"effort": "low"})
        self.assertEqual(payload["text"]["format"]["type"], "json_schema")
        self.assertEqual(payload["text"]["format"]["name"], "ayu_running_daily_report")
        self.assertEqual(payload["text"]["format"]["schema"], structured_report_json_schema(include_runtime_fields=False))
        self.assertEqual(payload["max_output_tokens"], 8192)
        input_data = json.loads(payload["input"])
        self.assertNotIn("runId", input_data)
        self.assertIsNone(input_data["cadenceNormalizedSpm"])
        self.assertNotIn("cadenceRawValue", input_data)
        self.assertNotIn("summary_polyline", payload["input"])
        self.assertNotIn("Authorization", json.dumps(payload))
        self.assertEqual(result.metadata.reasoning_tokens, 50)

    def test_low_high_benchmark_contract_uses_identical_input_and_prompt(self):
        payloads = []
        for effort in ("low", "high"):
            transport = MockTransport([completed_response()])
            DeepSeekAnalyzer(
                self.config(reasoning_effort=effort), transport=transport
            ).analyze(fit_context())
            payloads.append(transport.calls[0][2])
        self.assertEqual(payloads[0]["input"], payloads[1]["input"])
        self.assertEqual(payloads[0]["instructions"], payloads[1]["instructions"])
        self.assertEqual(payloads[0]["reasoning"], {"effort": "low"})
        self.assertEqual(payloads[1]["reasoning"], {"effort": "high"})

    def test_completed_ignores_reasoning_and_parses_usage(self):
        result = DeepSeekAnalyzer(self.config(), transport=MockTransport([completed_response()])).analyze_with_metadata(fit_context())
        self.assertEqual(result.report.run_id, fit_context().run_id)
        self.assertEqual(result.metadata.input_tokens, 100)
        self.assertEqual(result.metadata.output_tokens, 80)
        self.assertEqual(result.metadata.total_tokens, 180)
        self.assertEqual(result.metadata.http_status, 200)
        self.assertEqual(result.metadata.response_status, "completed")

    def test_missing_key_is_explicit(self):
        analyzer = DeepSeekAnalyzer(self.config(api_key=None), transport=MockTransport([]))
        with self.assertRaises(MissingAPIKeyError):
            analyzer.analyze(fit_context())

    def test_env_configuration_defaults_and_overrides(self):
        names = (
            "DEEPSEEK_API_KEY",
            "DEEPSEEK_BASE_URL",
            "DEEPSEEK_MODEL",
            "DEEPSEEK_REASONING_EFFORT",
            "DEEPSEEK_MAX_OUTPUT_TOKENS",
            "DEEPSEEK_TIMEOUT_SECONDS",
        )
        old = {name: os.environ.get(name) for name in names}
        try:
            for name in names:
                os.environ.pop(name, None)
            defaults = DeepSeekConfig.from_env()
            self.assertEqual(defaults.model, "deepseek-v4-flash")
            self.assertEqual(defaults.reasoning_effort, "high")
            os.environ.update(
                {
                    "DEEPSEEK_API_KEY": "placeholder",
                    "DEEPSEEK_BASE_URL": "https://example.invalid/",
                    "DEEPSEEK_MODEL": "custom-model",
                    "DEEPSEEK_REASONING_EFFORT": "max",
                    "DEEPSEEK_MAX_OUTPUT_TOKENS": "4096",
                    "DEEPSEEK_TIMEOUT_SECONDS": "12",
                }
            )
            configured = DeepSeekConfig.from_env()
            self.assertEqual(configured.base_url, "https://example.invalid/")
            self.assertEqual(configured.model, "custom-model")
            self.assertEqual(configured.max_output_tokens, 4096)
            self.assertEqual(configured.timeout_seconds, 12)
        finally:
            for name, value in old.items():
                if value is None:
                    os.environ.pop(name, None)
                else:
                    os.environ[name] = value

    def test_local_env_file_is_opt_in_and_shell_wins(self):
        names = ("DEEPSEEK_API_KEY", "DEEPSEEK_MODEL", "DEEPSEEK_REASONING_EFFORT")
        old = {name: os.environ.get(name) for name in names}
        try:
            for name in names:
                os.environ.pop(name, None)
            with tempfile.TemporaryDirectory() as directory:
                env_file = Path(directory) / ".env.local"
                env_file.write_text(
                    "DEEPSEEK_API_KEY=file-secret\nDEEPSEEK_MODEL=file-model\nDEEPSEEK_REASONING_EFFORT=low\n",
                    encoding="utf-8",
                )
                loaded = DeepSeekConfig.from_env(load_local_files=True, env_file=env_file)
                self.assertEqual(loaded.model, "file-model")
                self.assertEqual(loaded.reasoning_effort, "low")
                self.assertEqual(loaded.api_key, "file-secret")
                os.environ["DEEPSEEK_MODEL"] = "shell-model"
                self.assertEqual(
                    DeepSeekConfig.from_env(load_local_files=True, env_file=env_file).model,
                    "shell-model",
                )
                # The default mode must not read a dotenv file.
                self.assertIsNone(DeepSeekConfig.from_env().api_key)
        finally:
            for name, value in old.items():
                if value is None:
                    os.environ.pop(name, None)
                else:
                    os.environ[name] = value

    def test_config_repr_and_error_do_not_expose_key(self):
        config = self.config(api_key="placeholder")
        self.assertNotIn("placeholder", repr(config))
        error = DeepSeekError("safe message", category="bad_request")
        self.assertNotIn("placeholder", repr(error))

    def test_incomplete_and_failed_are_terminal(self):
        for body, category in (
            ({"status": "incomplete", "incomplete_details": {"reason": "max_output_tokens"}}, "incomplete"),
            ({"status": "incomplete", "incomplete_details": {"reason": "content_filter"}}, "content_filter"),
            ({"status": "failed", "error": {"code": "bad"}}, "provider_failed"),
        ):
            transport = MockTransport([TransportResponse(200, body)])
            with self.subTest(category=category):
                with self.assertRaises(DeepSeekError) as raised:
                    DeepSeekAnalyzer(self.config(), transport=transport).analyze(fit_context())
                self.assertEqual(raised.exception.category, category)
                self.assertEqual(len(transport.calls), 1)

    def test_malformed_provider_and_local_validation_fail(self):
        responses = [
            TransportResponse(200, {"status": "completed", "output": []}),
            completed_response({**valid_model_output(), "completion": {"status": "x", "trainingType": "structured", "score": 11}}),
            completed_response({**valid_model_output(), "evidence": [{"metricRef": "summary.notAllowed", "interpretation": "非法指标"}]}),
            completed_response({**valid_model_output(), "evidence": [{"metricRef": "summary.averageHrBpm", "interpretation": "value", "value": 150}]}),
        ]
        for expected in ("malformed_response", "validation", "validation", "validation"):
            transport = MockTransport([responses.pop(0)])
            with self.subTest(expected=expected):
                with self.assertRaises(DeepSeekError) as raised:
                    DeepSeekAnalyzer(self.config(), transport=transport).analyze(fit_context())
                self.assertEqual(raised.exception.category, expected)

    def test_invalid_metric_ref_and_null_metric_fail_fast(self):
        context = load_running_page_context(FIXTURES / "activities.json", None, "1900000000000")
        for output in (
            {**valid_model_output(), "evidence": [{"metricRef": "summary.notAllowed", "interpretation": "x"}]},
            {**valid_model_output(), "evidence": [{"metricRef": "summary.averageHrBpm", "interpretation": "x"}]},
        ):
            transport = MockTransport([completed_response(output)])
            with self.assertRaises(DeepSeekError) as raised:
                DeepSeekAnalyzer(self.config(), transport=transport).analyze(context)
            self.assertEqual(raised.exception.category, "validation")

    def test_narrative_cannot_leak_values_or_schema_names(self):
        outputs = (
            {**valid_model_output(), "verdict": "完成10公里训练"},
            {**valid_model_output(), "uncertainty": ["recoveryHours 未提供"]},
            {**valid_model_output(), "evidence": [{"metricRef": "summary.averageHrBpm", "interpretation": "字段为 null"}]},
        )
        for output in outputs:
            transport = MockTransport([completed_response(output)])
            with self.assertRaises(DeepSeekError) as raised:
                DeepSeekAnalyzer(self.config(), transport=transport).analyze(fit_context())
            self.assertEqual(raised.exception.category, "validation")

    def test_timeout_429_and_5xx_retry_once(self):
        for first in (
            TimeoutError("mock timeout"),
            DeepSeekError("timeout", category="timeout", retryable=True),
            TransportResponse(429, {}, {"Retry-After": "0"}),
            TransportResponse(503, {}),
        ):
            sleeps = []
            transport = MockTransport([first, completed_response()])
            analyzer = DeepSeekAnalyzer(self.config(), transport=transport, sleep=sleeps.append)
            analyzer.analyze(fit_context())
            self.assertEqual(len(transport.calls), 2)
            self.assertEqual(len(sleeps), 1)

    def test_400_and_401_do_not_retry(self):
        for status, category in ((400, "bad_request"), (401, "authentication")):
            transport = MockTransport([TransportResponse(status, {}) , completed_response()])
            with self.subTest(status=status):
                with self.assertRaises(DeepSeekError) as raised:
                    DeepSeekAnalyzer(self.config(), transport=transport).analyze(fit_context())
                self.assertEqual(raised.exception.category, category)
                self.assertEqual(len(transport.calls), 1)

    def test_retry_upper_bound(self):
        transport = MockTransport([
            TransportResponse(503, {}),
            TransportResponse(503, {}),
            completed_response(),
        ])
        with self.assertRaises(DeepSeekError):
            DeepSeekAnalyzer(self.config(), transport=transport, sleep=lambda _: None).analyze(fit_context())
        self.assertEqual(len(transport.calls), 2)

    def test_canonical_schema_is_generated_artifact(self):
        static = json.loads((ENGINE_ROOT / "schemas" / "structured_report.schema.json").read_text(encoding="utf-8"))
        self.assertEqual(static, structured_report_json_schema())
        context_static = json.loads((ENGINE_ROOT / "schemas" / "daily_run_context.schema.json").read_text(encoding="utf-8"))
        self.assertEqual(context_static, daily_run_context_json_schema())


if __name__ == "__main__":
    unittest.main()
