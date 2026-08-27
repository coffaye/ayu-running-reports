# Ayu Running Reports

一个可选择使用的 Codex 个人插件：连接 COROS MCP，以证据优先的训练复盘与 ShadowRunner 阶段—瓶颈框架，稳定生成 Ayu Running 黑绿 HTML 日报、周报或月报，并由浏览器代码直接导出固定宽度的纵向 PNG。

## 能力

- COROS 连接、授权与数据完整性诊断
- 单次跑步、每日、每周和每月训练复盘
- 训练结构、输出质量、生理代价、负荷与恢复分析
- ShadowRunner 阶段—瓶颈、适用域、边际收益和最小可逆下一步
- 固定 Ayu Running 黑绿 HTML 视觉
- PNG 宽度固定为 `2480 px`，高度至少 `3508 px`；内容过多时只纵向增长，不压缩、不裁切
- PNG 保持当前黑绿视觉且不带任何页脚（不绘制 `DATA · COROS MCP · 日期`、`AYU RUNNING` 或页脚分隔线）；不使用生图模型、PDF 或系统打印
- 默认快速生成：普通报告只做轻量静态检查，不自动启动浏览器、点击下载或执行视觉验收

## 共享 Report Engine（Phase 1.1 + Phase 2）

`engine/` 提供 Codex Skill、CLI 和未来 GitHub Actions 共用的离线核心：
`DailyRunContext`、running_page/SQLite/FIT adapters、`StructuredReport` schema、
无网络 FixtureAnalyzer、显式 DeepSeek Responses API Analyzer，以及确定性的
Ayu HTML/Canvas PNG renderer。v1.1 已区分 timer/elapsed/moving time，并将 FIT
原始 cadence 保留为带单位 provenance 的值；未经核实的 raw cadence 不会进入模型判断。
普通导入、测试和 fixture CLI 不调用 DeepSeek；只有显式选择 `--analyzer deepseek`
且提供 `DEEPSEEK_API_KEY` 时才会联网，也不读取实时 COROS 或修改 `running_page`。

未来 Action 必须将 Engine 固定到 semantic tag 或 commit SHA，并注入
`AYU_ENGINE_COMMIT`；不得无版本地跟随 `main`。原始 FIT、路线和账号信息不进入本仓库。

显式本地 DeepSeek 示例（不会把 key 写入命令行）：

```text
$env:DEEPSEEK_API_KEY = "..."
python -m ayu_report_engine --run-id 1900000000000 --json tests/fixtures/activities.json --output report.html --analyzer deepseek
```

真实验证先运行一次最小 smoke：
`python -m ayu_report_engine.smoke --live`，再运行
`python -m ayu_report_engine.benchmark --live` 做 A/B/C × low/high。仅在用户明确
执行且配置 key 后运行；live 结果写入 gitignored `engine/.benchmark/`，包含安全
metadata、验证标记、语义报告快照、确定性 HTML 和保守成本估算，不保存 reasoning、
Authorization 或 provider raw response。普通 pytest 始终离线。

## 使用

在安装并启用插件后，可直接说：

```text
生成我今天的 Ayu Running COROS 跑步日报。
```

或显式调用：

```text
使用 $ayu-running-reports 复盘我本周训练，并输出周报和 PNG。
```

首次使用 COROS 时，只在 COROS 官方浏览器授权页登录。不要把密码、验证码、Cookie 或 Token 发进聊天。

## 本地安装

克隆本仓库后，将它作为本地 Codex 插件源使用；插件清单位于 `.codex-plugin/plugin.json`，COROS MCP 配置位于 `.mcp.json`，Skill 位于 `skills/ayu-running-reports/`。

## 来源与许可

本项目融合并改编了 [赛博黑影儿 · ShadowRunner 与 COROS 训练复盘](https://github.com/leeeboo/public-skills)。上游文字与非程序化元数据采用 CC BY-NC-SA 4.0；本改编保留署名、修改说明和同许可分发要求。详情见 `skills/ayu-running-reports/NOTICE.md` 与 `LICENSE`。
