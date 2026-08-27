"""Deterministic Ayu HTML renderer with a browser Canvas PNG exporter."""

from __future__ import annotations

import html
import json
from typing import Any

from .context import DailyRunContext
from .metrics import metric_specs, resolve_metric_ref, validate_metric_refs
from .report import StructuredReport, validate_structured_report


def _escape(value: object) -> str:
    return html.escape(str(value), quote=True)


def _display(value: object, unit: str = "") -> str:
    if value is None:
        return "不可用"
    if isinstance(value, (list, tuple)):
        return f"{len(value)} 条记录"
    if isinstance(value, dict):
        return "已提供结构化数据"
    if isinstance(value, float):
        shown = f"{value:.2f}".rstrip("0").rstrip(".")
    else:
        shown = str(value)
    return f"{shown} {unit}".strip() if unit else shown


def _evidence_display(metric_ref: str, value: object, unit: str | None) -> str:
    """Render collection metrics without leaking dict keys or raw objects."""

    if metric_ref == "planned.structuredWorkout":
        return "已提供结构化课表"
    if metric_ref == "summary.lapSummary":
        return f"{len(value)} 个分圈" if isinstance(value, (list, tuple)) else "已提供分圈摘要"
    if metric_ref == "summary.splitSummary":
        return f"{len(value)} 个分段" if isinstance(value, (list, tuple)) else "已提供分段摘要"
    return _display(value, unit or "")


def _safe_model(report: StructuredReport, context: DailyRunContext) -> dict[str, Any]:
    source = context.evidence[0].source_type if context.evidence else "unknown"
    completion = report.completion
    resolved_evidence = []
    for item in report.evidence:
        metric = resolve_metric_ref(context, item["metricRef"])
        if metric is None:
            raise ValueError(f"evidence metric is unavailable: {item['metricRef']}")
        resolved_evidence.append(
            {
                "metricRef": metric.ref,
                "label": metric_specs()[metric.ref].label,
                "value": (
                    None
                    if metric_specs()[metric.ref].collection
                    else metric.value
                ),
                "unit": metric.unit,
                "displayValue": _evidence_display(metric.ref, metric.value, metric.unit),
                "source": metric.source,
                "interpretation": item["interpretation"],
            }
        )
    return {
        "date": report.report_date,
        "runId": report.run_id,
        "verdict": report.verdict,
        "trainingPurpose": report.training_purpose,
        "completionStatus": completion.get("status"),
        "trainingType": completion.get("trainingType"),
        "score": completion.get("score"),
        "distanceM": context.distance_m,
        "timerTimeSec": context.timer_time_sec,
        "elapsedTimeSec": context.elapsed_time_sec,
        "movingTimeSec": context.moving_time_sec,
        "displayDurationSec": context.display_duration_sec,
        "displayDurationSource": context.display_duration_source,
        "paceSecPerKm": context.average_pace_sec_per_km,
        "heartRateBpm": context.average_hr_bpm,
        "powerW": context.power_w,
        "load": report.load,
        "recovery": report.recovery,
        "loadFacts": {
            "trainingEffectAerobic": context.training_effect_aerobic,
            "trainingEffectAnaerobic": context.training_effect_anaerobic,
            "trainingLoadPeak": context.training_load_peak,
        },
        "recoveryFacts": {
            "percent": context.recovery_percent,
            "hours": context.recovery_hours,
            "runningFitness": context.running_fitness,
        },
        "evidence": resolved_evidence,
        "shadowRunner": report.shadowrunner,
        "bottleneck": report.bottleneck,
        "applicableDomain": report.applicable_domain,
        "marginalGain": report.marginal_gain,
        "minimalReversibleNextStep": report.minimal_reversible_next_step,
        "nextTrainingSuggestion": report.next_training_suggestion,
        "uncertainty": list(report.uncertainty),
        "source": source,
    }


def render_html(report: StructuredReport, context: DailyRunContext) -> str:
    """Render one standalone report; no network or external runtime dependency."""

    validate_structured_report(report.to_dict())
    validate_metric_refs(report, context)
    model = _safe_model(report, context)
    model_json = json.dumps(model, ensure_ascii=False, sort_keys=True).replace(
        "</", "<\\/"
    )
    completion_status = report.completion.get("status") or "未知"
    training_type = report.completion.get("trainingType") or "未知"
    score = _display(report.completion.get("score"), "/ 10")
    evidence_rows = "".join(
        "<li><span class=\"evidence-field\">"
        + _escape(item.get("label"))
        + "</span><span>"
        + _escape(item.get("displayValue", _display(item.get("value"), item.get("unit", ""))))
        + "</span><span class=\"muted\">"
        + _escape(item.get("interpretation"))
        + "</span></li>"
        for item in model["evidence"]
    ) or '<li><span class="muted">暂无可用实测证据</span></li>'
    uncertainty_rows = "".join(
        f"<li>{_escape(item)}</li>" for item in report.uncertainty
    ) or '<li class="muted">未记录额外不确定性</li>'
    source = model["source"]
    return f'''<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Ayu Running · {_escape(report.report_date)}</title>
  <style>
    :root {{ color-scheme: dark; --bg:#080B09; --soft:#0D120F; --green:#56FFA3; --text:#F2F6F3; --muted:rgba(242,246,243,.62); --line:rgba(86,255,163,.28); }}
    * {{ box-sizing:border-box; }}
    html, body {{ margin:0; background:var(--bg); color:var(--text); font-family:"Microsoft YaHei","PingFang SC",system-ui,sans-serif; }}
    body {{ background-image:linear-gradient(rgba(86,255,163,.035) 1px,transparent 1px),linear-gradient(90deg,rgba(86,255,163,.035) 1px,transparent 1px); background-size:90px 90px; }}
    .shell {{ width:min(1120px,calc(100% - 32px)); margin:0 auto; padding:28px 0 72px; }}
    header {{ display:flex; align-items:center; justify-content:space-between; gap:16px; border-bottom:1px solid var(--line); padding-bottom:18px; }}
    .brand {{ font:600 1.05rem/1.2 "IBM Plex Mono",ui-monospace,monospace; letter-spacing:.03em; }}
    .brand .ayu {{ color:var(--green); }} .brand .running {{ color:#fff; }}
    .download {{ border:1px solid var(--green); border-radius:999px; background:transparent; color:var(--green); padding:9px 16px; cursor:pointer; }}
    .hero {{ padding:72px 0 52px; border-bottom:1px solid var(--line); }}
    .eyebrow {{ color:var(--green); font:600 .72rem/1.4 "IBM Plex Mono",monospace; letter-spacing:.13em; }}
    h1 {{ max-width:900px; margin:16px 0; font-size:clamp(2.2rem,7vw,5.9rem); line-height:.98; letter-spacing:-.045em; }}
    .meta {{ color:var(--muted); font: .82rem/1.6 "IBM Plex Mono",monospace; }}
    section {{ padding:40px 0; border-bottom:1px solid rgba(242,246,243,.12); }}
    h2 {{ margin:0 0 18px; color:var(--green); font:600 .78rem/1.4 "IBM Plex Mono",monospace; letter-spacing:.09em; }}
    .grid {{ display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:16px; }}
    .metric {{ background:var(--soft); padding:18px; min-height:82px; }}
    .metric-label {{ color:var(--muted); font:.72rem/1.3 "IBM Plex Mono",monospace; }}
    .metric-value {{ margin-top:6px; font:1.2rem/1.3 "IBM Plex Mono",monospace; }}
    .status {{ color:var(--green); }} .dot {{ display:inline-block; width:7px; height:7px; border-radius:50%; background:var(--green); margin-right:8px; vertical-align:middle; }}
    ul {{ margin:0; padding-left:20px; }} li {{ margin:8px 0; line-height:1.55; }}
    .evidence-field {{ color:var(--green); font-family:"IBM Plex Mono",monospace; margin-right:14px; }}
    .muted {{ color:var(--muted); }}
    footer {{ padding-top:24px; color:var(--muted); font: .74rem/1.4 "IBM Plex Mono",monospace; text-align:right; }}
    @media (max-width:800px) {{ .shell {{ width:min(100% - 24px,680px); }} .hero {{ padding:48px 0 36px; }} .grid {{ grid-template-columns:1fr; }} header {{ align-items:flex-start; }} }}
  </style>
</head>
<body>
  <div class="shell">
    <header><div class="brand"><span class="ayu">Ayu</span> <span class="running">Running</span></div><button id="download-png" class="download" type="button">下载 PNG</button></header>
    <main>
      <div class="hero"><div class="eyebrow">{_escape(source)} · {_escape(report.report_date)}</div><h1>{_escape(report.verdict)}</h1><div class="meta">run_id {_escape(report.run_id)} · {_escape(_display(context.distance_m, "m"))} · {_escape(_display(context.display_duration_sec, "s"))} · {_escape(context.display_duration_source)}</div></div>
      <section data-png-section><h2>TODAY 今日结论</h2><p>{_escape(report.verdict)}</p><p class="status"><span class="dot"></span>{_escape(completion_status)} · {_escape(training_type)}</p></section>
      <section data-png-section><h2>TRAINING 训练性质</h2><div class="grid"><div class="metric"><div class="metric-label">训练目的</div><div class="metric-value">{_escape(report.training_purpose or "未知")}</div></div><div class="metric"><div class="metric-label">完成评分</div><div class="metric-value">{_escape(score)}</div></div><div class="metric"><div class="metric-label">训练意图</div><div class="metric-value">{_escape(training_type)}</div></div></div></section>
      <section data-png-section><h2>EVIDENCE 关键证据</h2><ul>{evidence_rows}</ul></section>
      <section data-png-section><h2>LOAD 负荷与恢复</h2><div class="grid"><div class="metric"><div class="metric-label">训练负荷</div><div class="metric-value">{_escape(_display(context.training_load_peak))}</div></div><div class="metric"><div class="metric-label">恢复时间</div><div class="metric-value">{_escape(_display(context.recovery_hours, "h"))}</div></div><div class="metric"><div class="metric-label">恢复比例</div><div class="metric-value">{_escape(_display(context.recovery_percent, "%"))}</div></div></div><p class="muted">{_escape((report.load or {}).get("assessment") or "")}</p><p class="muted">{_escape((report.recovery or {}).get("assessment") or "")}</p></section>
      <section data-png-section><h2>SHADOWRUNNER 阶段—瓶颈</h2><p>{_escape(report.bottleneck or "未知")}</p><p class="muted">适用域：{_escape(report.applicable_domain or "未知")} · 边际收益：{_escape(report.marginal_gain or "未知")}</p></section>
      <section data-png-section><h2>NEXT 下一步</h2><p>{_escape(report.minimal_reversible_next_step or "未知")}</p><p>{_escape(report.next_training_suggestion or "未知")}</p><ul>{uncertainty_rows}</ul></section>
    </main>
    <footer>Ayu Running</footer>
  </div>
  <script id="report-data" type="application/json">{model_json}</script>
  <script>
    const MODEL = JSON.parse(document.getElementById('report-data').textContent);
    const EXPORT_WIDTH = 2480;
    const MIN_HEIGHT = 3508;
    const canvasText = (value) => value === null || value === undefined ? '不可用' : String(value);
    const wrap = (ctx, value, maxWidth) => {{
      const chars = Array.from(canvasText(value)); let line = ''; const lines = [];
      for (const char of chars) {{ const next = line + char; if (line && ctx.measureText(next).width > maxWidth) {{ lines.push(line); line = char; }} else line = next; }}
      if (line) lines.push(line); return lines.length ? lines : [''];
    }};
    async function downloadPng() {{
      if (document.fonts && document.fonts.ready) await document.fonts.ready;
      const scale = 2, logicalWidth = EXPORT_WIDTH / scale, margin = 72, contentWidth = logicalWidth - margin * 2;
      const measure = document.createElement('canvas'); const mctx = measure.getContext('2d'); mctx.font = '28px "Microsoft YaHei", "PingFang SC", sans-serif';
      const recoveryHours = MODEL.recoveryFacts && MODEL.recoveryFacts.hours;
      const blocks = [
        ['TODAY 今日结论', MODEL.verdict],
        ['TRAINING 训练性质', MODEL.trainingPurpose || '未知'],
        ['EVIDENCE 关键证据', (MODEL.evidence || []).map(item => item.label + ' ' + canvasText(item.displayValue) + '：' + item.interpretation).join('；') || '暂无可用实测证据'],
        ['LOAD 负荷与恢复', '训练负荷 ' + canvasText(MODEL.loadFacts && MODEL.loadFacts.trainingLoadPeak) + ' · 恢复 ' + (recoveryHours === null || recoveryHours === undefined ? '不可用' : canvasText(recoveryHours) + ' h')],
        ['SHADOWRUNNER 阶段—瓶颈', MODEL.bottleneck || '未知'],
        ['NEXT 下一步', MODEL.minimalReversibleNextStep || '未知']
      ];
      let logicalHeight = 150, y = 150; const wrapped = [];
      for (const [label, value] of blocks) {{ const lines = wrap(mctx, value, contentWidth); wrapped.push([label, lines]); y += 58 + lines.length * 42 + 34; }}
      const measuredBottom = y; logicalHeight = Math.max(MIN_HEIGHT / scale, measuredBottom + 72);
      const canvas = document.createElement('canvas'); canvas.width = EXPORT_WIDTH; canvas.height = Math.ceil(logicalHeight * scale); const ctx = canvas.getContext('2d'); ctx.scale(scale, scale);
      ctx.fillStyle = '#080B09'; ctx.fillRect(0, 0, logicalWidth, logicalHeight); ctx.strokeStyle = 'rgba(86,255,163,.28)'; ctx.lineWidth = 1; ctx.beginPath(); ctx.moveTo(margin, 70); ctx.lineTo(logicalWidth - margin, 70); ctx.stroke();
      ctx.font = '600 28px "IBM Plex Mono", monospace'; ctx.fillStyle = '#56FFA3'; ctx.fillText('Ayu', margin, 42); ctx.fillStyle = '#F2F6F3'; ctx.fillText(' Running', margin + 58, 42);
      ctx.font = '24px "IBM Plex Mono", monospace'; ctx.fillStyle = 'rgba(242,246,243,.62)'; ctx.fillText(MODEL.date, logicalWidth - margin - ctx.measureText(MODEL.date).width, 42);
      y = 150; ctx.font = '600 22px "IBM Plex Mono", monospace';
      for (const [label, lines] of wrapped) {{ ctx.fillStyle = '#56FFA3'; ctx.fillText(label, margin, y); y += 42; ctx.font = '28px "Microsoft YaHei", "PingFang SC", sans-serif'; ctx.fillStyle = '#F2F6F3'; for (const line of lines) {{ ctx.fillText(line, margin, y); y += 42; }} y += 34; ctx.font = '600 22px "IBM Plex Mono", monospace'; }}
      ctx.strokeStyle = 'rgba(86,255,163,.28)'; ctx.beginPath(); ctx.moveTo(margin, measuredBottom - 18); ctx.lineTo(logicalWidth - margin, measuredBottom - 18); ctx.stroke();
      canvas.toBlob(blob => {{ if (!blob) return; const url = URL.createObjectURL(blob); const a = document.createElement('a'); a.href = url; a.download = 'Ayu_Running_' + MODEL.date + '.png'; a.click(); URL.revokeObjectURL(url); }}, 'image/png');
    }}
    document.getElementById('download-png').addEventListener('click', downloadPng);
  </script>
</body>
</html>'''
