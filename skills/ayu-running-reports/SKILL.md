---
name: ayu-running-reports
description: 连接并检查 COROS MCP，使用内置的 COROS Workout Review 与 ShadowRunner 阶段—瓶颈框架，生成固定 Ayu Running 黑绿视觉的单次、每日、每周或每月跑步复盘 HTML，并内置一张代码绘制的 A4 PNG 下载。用于用户要求连接或排查 COROS、复盘跑步、判断训练完成质量/瓶颈/负荷/恢复，或生成 Ayu Running 日报、周报、月报时；无需用户重复说明格式。
---

# Ayu Running Reports

把连接、验数、训练判断和报告交付当作一条连续工作流。先确认数据可用，再解释训练，最后生成固定视觉的 HTML 与 A4 PNG。不要把 COROS 指标换一种说法堆成数据墙。

本 Skill 融合了 `coros-workout-review` 与其内置的 ShadowRunner 决策框架，并叠加 Ayu Running 的周期报告、UI 和 PNG 规范。来源与许可见 [NOTICE.md](NOTICE.md)。

## 入口与模式

先识别用户要做什么：

1. **连接或排障**：读取 [references/upstream/client-connections.md](references/upstream/client-connections.md) 与 [references/upstream/connection-diagnostics.md](references/upstream/connection-diagnostics.md)，完成最小验证后停止，不擅自读取更多数据。
2. **单次或日报**：定位指定日期或最近一次跑步，读取详情与分圈，做完整训练复盘并生成日报。
3. **周报或月报**：读取所需日期范围，聚合总量，并挑关键训练深入分析，不把所有活动等权处理。
4. **只要文字判断**：仍按证据与安全规则分析；只有用户要报告或交付物时才生成 HTML/PNG。

周期报告必须读取 [references/report-modes.md](references/report-modes.md) 中对应模式。不要再次询问已经固定的版式偏好。

## COROS 连接状态

优先使用插件随附的 COROS 远程 MCP。认证只能在 COROS 官方浏览器授权页完成；绝不索取密码、验证码、Cookie、OAuth code 或 Token。

内部按以下状态判断，向用户只给简短自然语言结论：

- `NOT_CONFIGURED`：找不到 COROS 工具；引导在 Codex 插件中安装/启用 COROS，或检查本插件 MCP。
- `AUTH_REQUIRED`：工具存在但返回登录、401 或 403；重新走官方浏览器授权。
- `CONNECTED_UNTESTED`：工具可见但尚未验数；只读取最近一条摘要做最小验证。
- `CONNECTED_EMPTY`：调用成功但目标日期范围无活动；查同步、账号与日期，不能说成连接失败。
- `PARTIAL`：有记录但缺详情或分圈；降级复盘并降低置信度。
- `READY`：活动摘要、详情可读，分圈可读或已明确缺失；开始复盘。
- `SERVICE_ERROR`：超时或服务错误；最多重试一次，再给恢复动作。

## 数据读取梯度

使用用户时区；默认 `Asia/Shanghai`。只读取回答问题所需的最短范围：

1. 用活动列表定位跑步；运动类型优先 `[100,101,102,103]`。
2. 用活动详情读取实际存在的距离、时长、配速/速度、心率、功率、步频、步幅、爬升和训练效果。
3. 用分圈/结构化训练段还原热身、主训练、恢复和放松。自动公里圈不能替代真实训练段。
4. 只有用户明确问某个时间窗时才查询自定义时间窗。
5. 判断近期关系时才读取训练负荷、恢复和能力评估；说明这些是设备模型，不是医学结论。
6. 查询下一训练日或计划上下文；若详情命令不可调用，不编造目标配速、组间恢复或训练步骤，写明以手表同步课表为准。

日报、周报和月报的具体查询范围见 [references/report-modes.md](references/report-modes.md)。COROS 返回值是设备指标的来源；自行推导的同比、漂移或平均必须标为计算值。

任何情况下都不展示 Plan ID、活动 ID、device ID、坐标、地图、完整路线、精确起终点、FIT 下载链接或其他内部标识。缺失值是未知，不是 0。

## 强制分析链

生成结论前完整读取 [references/upstream/review-methodology.md](references/upstream/review-methodology.md)。需要判断长期瓶颈、外部方案或训练取舍时，再读取 [references/shadowrunner/frameworks.md](references/shadowrunner/frameworks.md)。需要更自然的中文判断节奏时读取 [references/shadowrunner/voice-and-views.md](references/shadowrunner/voice-and-views.md)。

顺序不可跳过：

1. **先筛风险**：疼痛、胸闷、晕厥、异常气短、神经症状或持续异常疲劳命中时，停止训练实验，只整理事实、风险与应带给专业人士的问题。
2. **还原结构**：热身、主训练、恢复、放松；识别不了就明确写“结构未知”。
3. **判断目的与阶段**：轻松、稳态、渐进、阈值、间歇、长距离、比赛或未知；再结合目标判断建立习惯、积累能力、专项准备、维持或恢复阶段。
4. **区分输出与代价**：配速/功率是外部输出，心率是生理反应代理；动作、环境和恢复是不同维度，不能互相冒充原因。
5. **找主瓶颈**：从执行、输出稳定性、生理代价、动作结果、环境、恢复和数据质量中，选择证据最强的一个，最多保留两个候选。
6. **核对适用域与边际收益**：他人方案、设备建议和单次结果都不能直接外推；同时计算恢复、时间、生活干扰和回滚成本。
7. **给最小可逆下一步**：一次只改变或观察一个变量，写明保持不变项、观察指标、复盘时点和停止条件。
8. **允许改口**：新证据出现后，说明旧判断为何变化，保留被支持和被推翻的假设。

把陈述分为事实、解释和假设。任何因果句都要能回答证据来自哪里；只有相关性时写“同时出现”或“可能有关”。单次活动不能单独证明长期进步、退步、平台期或能力上限。

## 写作标准

- 先给一句明确判断，再给最多三条关键证据。
- 直接、短、具体；阶段与边界讲清楚，不堆免责声明。
- 主判断最多一个，备选解释最多两个；写清支持、反证/未知和置信度。
- 数据描述发生了什么；体感、环境、睡眠与生活信息只有真实存在时才参与解释。
- 不因心率漂移直接断言炎热、脱水、疾病或过度训练。
- 不把“很累”等同于“有效”，也不把慢配速等同于轻松跑失败。
- 不用人格、意志力、PB、跑量或排名定义跑者。
- 不给个体化周跑量、精确配速/功率/心率、间歇组数、恢复天数、补给、药物或康复处方，不承诺比赛成绩。

## 可选天气补全

默认不用第三方天气。只有 COROS/FIT 温湿度缺失或明显不可信、且用户明确要求并逐次同意时，读取 [references/upstream/openweathermap.md](references/upstream/openweathermap.md)。

- API key 只能从本机 secret 或环境读取，不在聊天、文件、命令参数、URL 或日志中索取/回显。
- 配置 key 不等于位置授权；调用前说明只发送约 `0.1°` 粗化位置和最小活动时间窗。
- 天气结果标为“外部天气上下文”，不覆盖可信设备值，不作为疲劳的确定原因。
- 失败最多重试一次，然后询问用户大致温湿度或保持未知，不扩大数据权限。

## 报告交付

当用户要报告时，始终生成独立响应式 HTML，并包含 `下载 A4 PNG` 按钮：

- 日报：`ayu_running_daily_YYYY-MM-DD.html`
- 周报：`ayu_running_weekly_YYYY-Www.html`
- 月报：`ayu_running_monthly_YYYY-MM.html`

构建或修改页面前读取 [references/design-system.md](references/design-system.md)，实现 PNG 前读取 [references/png-export.md](references/png-export.md)。HTML 的 hero 是动态训练结论；最顶部品牌始终是绿色 `Ayu` + 白色 `Running`，页脚为 `Ayu Running`。

PNG 必须由浏览器内的 HTML/JavaScript 代码直接绘制和下载，不使用图像生成模型，不调用系统打印。它是一张 A4 比例的执行摘要，不是整页网页截图，视觉与当前黑绿报告一致。

## 验证门槛

交付前必须：

1. 在真实浏览器检查桌面与移动端，无横向溢出，导航锚点和活动状态正常，控制台无错误。
2. 点击 PNG 按钮，确认发生 `.png` 文件下载且没有系统打印对话框。
3. 检查图片像素尺寸与 A4 比例；打开原图检查中文字体、断行、孤立标点、裁切和对比度。
4. 核对报告没有内部 ID、位置或其他隐私泄漏；安全规则完整见 [references/upstream/privacy-safety.md](references/upstream/privacy-safety.md)。

不要在这些检查通过前宣称完成。
