# Built-in A4 PNG export

Every report HTML must include a working button labeled `下载 PNG`. Do not use `window.print()`, PDF generation, screenshot APIs, or an image-generation model.

## Required behavior

- Generate and download a real PNG entirely in the browser with HTML/JavaScript code.
- Keep the PNG width fixed at `2480 px` (`1240` logical units × 2) and use `3508 px` (`1754` logical units × 2) as the minimum portrait height. This is an A4-width export: when measured content exceeds the safe bottom margin, increase only the canvas height; never squeeze, clip, or widen the content.
- Match the report's black-green design: `#080B09` background, `#56FFA3` accents, white primary text, faint grid, thin dividers, and minimal rounded emphasis.
- Put the period, main conclusion, primary metrics, strongest evidence, main concern, load/recovery context, and upcoming focus on the image.
- Keep the PNG deliberately concise. It is an executive summary composed specifically for A4, not a screenshot of the entire HTML.
- Draw at logical A4 coordinates and scale the canvas context to the output resolution so spacing remains deterministic.
- Use installed Chinese system fonts such as `Microsoft YaHei`, `PingFang SC`, and sans-serif fallbacks. Await `document.fonts.ready` before drawing.
- Wrap text by measured width, reserve line height explicitly, and lay sections out in vertical flow. Preflight the wrapped line counts before creating the canvas, then push later sections down and grow the height as needed.
- The exported PNG has no footer at all: do not draw the HTML footer, footer divider, source/date line such as `DATA · COROS MCP · ...`, `AYU RUNNING`, or any other footer element. A blank lower margin is acceptable.
- Export with `canvas.toBlob(..., 'image/png')`, create a temporary object URL, trigger a download, then revoke the URL.
- Name downloads consistently, for example `Ayu_Running_2026-08-26.png`.

## Validation

1. Trigger the button in a real browser and confirm a `.png` download event.
2. Inspect dimensions with an image library and confirm the width is `2480 px` and the height is at least `3508 px`; long-content fixtures must increase height while keeping width unchanged.
3. Open the original-size PNG and visually inspect the full image and key cropped regions.
4. Confirm the bottom margin is clean and contains no footer text, footer rule, source/date label, or brand label.
5. Fix clipped text, lone punctuation, low contrast, malformed Chinese glyphs, or content extending below the dynamically calculated bottom margin.
