# Built-in A4 PNG export

Every report HTML must include a working button labeled `下载 A4 PNG`. Do not use `window.print()`, PDF generation, screenshot APIs, or an image-generation model.

## Required behavior

- Generate and download a real PNG entirely in the browser with HTML/JavaScript code.
- Use a portrait A4 aspect ratio (`210:297`). Default to `2480 × 3508 px` for a 300-DPI-equivalent deliverable; a smaller preview canvas may be used only if memory constraints require it.
- Match the report's black-green design: `#080B09` background, `#56FFA3` accents, white primary text, faint grid, thin dividers, and minimal rounded emphasis.
- Put the period, main conclusion, primary metrics, strongest evidence, main concern, load/recovery context, and upcoming focus on the image.
- Keep the PNG deliberately concise. It is an executive summary composed specifically for A4, not a screenshot of the entire HTML.
- Draw at logical A4 coordinates and scale the canvas context to the output resolution so spacing remains deterministic.
- Use installed Chinese system fonts such as `Microsoft YaHei`, `PingFang SC`, and sans-serif fallbacks. Await `document.fonts.ready` before drawing.
- Wrap text by measured width, reserve line height explicitly, and stop or shorten content before the safe bottom margin.
- Export with `canvas.toBlob(..., 'image/png')`, create a temporary object URL, trigger a download, then revoke the URL.
- Name downloads consistently, for example `Ayu_Running_2026-08-26.png`.

## Validation

1. Trigger the button in a real browser and confirm a `.png` download event.
2. Inspect dimensions with an image library and confirm the `210:297` aspect ratio within rounding tolerance.
3. Open the original-size PNG and visually inspect the full image and key cropped regions.
4. Fix clipped text, lone punctuation, low contrast, malformed Chinese glyphs, or content extending below the safe A4 margin.
