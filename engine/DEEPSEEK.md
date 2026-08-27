# DeepSeek Analyzer contract

`DeepSeekAnalyzer` is never selected implicitly. The regular fixture CLI and
all tests remain offline. A real request requires `DEEPSEEK_API_KEY` and the
explicit `--analyzer deepseek` flag (or an explicit `--live` module).

## Configuration

Environment variables are centralized in `DeepSeekConfig.from_env()`:

- `DEEPSEEK_API_KEY` (required only for a live request)
- `DEEPSEEK_BASE_URL` (default `https://api.deepseek.com`)
- `DEEPSEEK_MODEL` (default `deepseek-v4-flash`)
- `DEEPSEEK_REASONING_EFFORT` (default `high`; `none`, `minimal`, `low`,
  `medium`, `high`, `xhigh`, `max`)
- `DEEPSEEK_MAX_OUTPUT_TOKENS` (default `16384`; high-effort structured cases previously hit the lower cap)
- `DEEPSEEK_TIMEOUT_SECONDS` (default `60`)

For local development, keep the key in the shell environment (preferred), or
in a gitignored `.env.local`/`.env` at the working directory. Dotenv files are
read only by explicit live commands; shell variables win, and only the six
`DEEPSEEK_*` settings are parsed. The key is never printed or serialized.

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

The live benchmark uses prompt version `ayu-daily-v5`: each request includes
the metric references actually available in that context, and the local
validator rejects raw numeric values, literal `null`, or JSON/camelCase field
names in user-facing semantic strings. This keeps values in the deterministic
metric display and prevents schema leakage into HTML/PNG.

Only timeout/network, 429, 408 and transient 5xx responses receive at most one
retry. `Retry-After` is honored up to eight seconds; otherwise a bounded
exponential delay is used. 400, 401/403, malformed output, incomplete output,
content filtering, schema failures and semantic failures are terminal. Usage
and latency metadata are returned separately; reasoning text is ignored and
never persisted.

## Explicit smoke test and benchmark

Run one minimal request before spending tokens on the six-case comparison:

```text
python -m ayu_report_engine.smoke --live
```

The smoke result records only endpoint, model, response status, latency,
token usage and validation. It does not persist reasoning or provider bodies.

```text
python -m ayu_report_engine.benchmark --live
```

The benchmark runs sanitized cases A (basic run), B (structured long workout)
and C (missing metrics) at both low and high effort, after the smoke passes. If
the matching successful `engine/.benchmark/smoke.json` from the explicit smoke
command is present, it is reused so no duplicate preflight request is made;
otherwise benchmark performs the one-request preflight itself. It writes the
ignored `engine/.benchmark/` directory with safe metadata, schema
and semantic validation, deterministic HTML for each result, a semantic report
snapshot, a conservative mechanical pre-score and cache-hit/miss cost
estimates. It never saves reasoning, authorization headers or provider raw
responses. Without a key it exits without making a request.

The cost estimate uses the current DeepSeek V4 Flash list prices and assumes
cache-miss input for the conservative figure; confirm prices before budgeting:
<https://api-docs.deepseek.com/quick_start/pricing/>.

`quality` is only a deterministic pre-score for review triage. Final low/high
selection must inspect the actual report content against the Phase 2.1 rubric;
the Engine never silently chooses an effort.
