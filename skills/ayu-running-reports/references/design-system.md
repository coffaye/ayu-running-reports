# Ayu Running design system

Use this visual system for every daily, weekly, and monthly report.

## Identity

- Product name: `Ayu Running`.
- Top fixed brand: `Ayu` in green and `Running` in white, preceded by a small green status dot.
- The hero title is the report's dynamic conclusion, not the product name.
- Footer right label: `Ayu Running`.
- PNG export exception: the exported PNG omits the HTML footer content entirely, including the source/date line and `Ayu Running` footer label; a single footer-free horizontal rule matching the top divider may close the report immediately below the measured final content, followed by a clean bottom margin.
- Score treatment: render the score value in white and the maximum denominator as a smaller green value; bind both from the report data.
- Status treatment: use a small green dot followed by the bound completion status, a `·` separator, and the bound training type; never hardcode example status values.
- Load treatment: keep short-term load, long-term load, and load ratio visually identical; put the bound load status in a separate green-dot/green-text item. Show the recovery estimate as a separate green-dot line with only the time estimate.
- Recovery percentage treatment: keep the percentage number large and white, with a smaller green `%`.
- Primary green: `#56FFA3`.
- Page background: `#080B09`; soft background: `#0D120F`.
- Primary text: `#F2F6F3`; secondary text around 70% opacity; metadata around 42% opacity.

## Layout language

Follow the DeepSeek Harness-inspired visual language without copying its content:

- Use a narrow centered content container, large vertical whitespace, oversized conclusion typography, thin low-contrast dividers, a faint 90 px grid, and subtle green radial atmosphere.
- Organize most content as continuous full-width sections. Do not create a wall of bordered cards.
- Render the upcoming-plan module as the same continuous full-width section language as the other modules; do not give it a unique enclosing frame, gradient, border, or pill solely to mark it as upcoming.
- Retain the white heading `明日课表：`, then show the upcoming workout name once in green. Do not append or repeat the workout name inside the white heading in either HTML or the Canvas PNG.
- Reserve rounded tinted surfaces for one or two genuinely important modules such as interval evidence or the upcoming plan.
- Do not add drop shadows to content modules.
- Use pill shapes only for the fixed navigation and the `下载 PNG` button. Completion status and `Optimized` must be plain inline text, not pills.
- Use monospace typography for metrics and small technical labels; use a clean Chinese system sans-serif for narrative text.
- Use spaces rather than slashes in PNG section labels, for example `TODAY 今日结论`, `LOAD 近期负荷`, and `TOMORROW 明日课表`.

## Required page structure

1. Fixed translucent header with Ayu Running and `下载 PNG`.
2. Hero with the dynamic training conclusion, a short session description, and one metadata row: `COROS MCP 已同步`, period/date, and primary metrics.
3. Sticky pill navigation.
4. Overview with score, conclusion, and open metric row.
5. Training structure and charts.
6. Evidence split into strengths and current concerns.
7. Training load and recovery.
8. Upcoming plan context when available.
9. Minimal footer.

## Interaction and responsive behavior

- Navigation anchors must have a visible green active state. Initialize `总览` as active, switch the active item as its section crosses the reading position during scrolling, update immediately on tab clicks, and force the final item active at the document bottom. Keep `aria-current` synchronized with the visual state.
- Desktop uses wide asymmetric grids. Under 800 px, collapse to a single column without horizontal overflow.
- Keep charts as inline SVG so the report remains standalone.
- Do not use external runtime dependencies for the report or PNG generation.
