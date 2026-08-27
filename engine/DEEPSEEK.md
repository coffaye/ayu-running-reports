# DeepSeek Analyzer contract

`DeepSeekAnalyzer` is never selected implicitly. The regular fixture CLI and
all tests remain offline. A real request requires `DEEPSEEK_API_KEY` and the
explicit `--analyzer deepseek` flag (or the explicit benchmark module).

## Configuration

Environment variables are centralized in `DeepSeekConfig.from_env()`:

- `DEEPSEEK_API_KEY` (required only for a live request)
- `DEEPSEEK_BASE_URL` (default `https://api.deepseek.com`)
- `DEEPSEEK_MODEL` (default `deepseek-v4-flash`)
- `DEEPSEEK_REASONING_EFFORT` (default `high`; `none`, `minimal`, `low`,
  `medium`, `high`, `xhigh`, `max`)
- `DEEPSEEK_MAX_OUTPUT_TOKENS` (default `8192`)
- `DEEPSEEK_TIMEOUT_SECONDS` (default `60`)

The request is `POST {base_url}/responses` with `instructions`, a JSON string
projection of `DailyRunContext`, `reasoning: {"effort": ...}`, and
`text.format`:

```json
{
  "type": "json_schema",
  "name": "ayu_running_daily_report",
  "schema": "structured_report_model_json_schema()"
}
```

No tools, FIT bytes, route data, device serial, file path, account, or raw
cadence value is sent.

The model-only schema is generated from the same Python schema source as the
complete `StructuredReport`; runtime identity and version fields are injected
by the Engine. The output is then checked for JSON shape, local semantic
meaning, and whitelisted `metricRef` availability before rendering.

Only timeout/network, 429, 408 and transient 5xx responses receive at most one
retry. `Retry-After` is honored up to eight seconds; otherwise a bounded
exponential delay is used. 400, 401/403, malformed output, incomplete output,
content filtering, schema failures and semantic failures are terminal. Usage
and latency metadata are returned separately; reasoning text is ignored and
never persisted.

## Explicit benchmark

```text
python -m ayu_report_engine.benchmark --live --output deepseek-benchmark.json
```

The benchmark runs sanitized cases A (basic run), B (structured long workout)
and C (missing metrics) at both low and high effort. It records safe latency,
token counts, validation status and empty rubric slots for human scoring; it
does not save reasoning. Without a key it exits without making a request.
