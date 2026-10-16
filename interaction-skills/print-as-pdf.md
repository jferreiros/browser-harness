# Print As PDF

Cover both direct PDF generation via CDP and sites that only expose a visible "Print" button which must be clicked before handling the browser print flow.

## Direct generation: Page.printToPDF (field-tested)

```bash
browser-harness -c '
import base64, time
new_tab("file:///path/to/doc.html")
wait_for_load()
# wait_for_load() does NOT wait for <img> — poll until every image decoded
for _ in range(20):
    if js("Array.from(document.images).every(i => i.complete && i.naturalWidth > 0)"): break
    time.sleep(0.5)
r = cdp("Page.printToPDF", printBackground=True, preferCSSPageSize=True)
open("/path/out.pdf", "wb").write(base64.b64decode(r["data"]))
'
```

- `cdp()` takes CDP params as **kwargs**, not a dict — `cdp("Page.printToPDF", {"printBackground": True})` fails with `Message may have string 'sessionId' property` because the dict lands in the `session_id` positional.
- `preferCSSPageSize=True` honors the page's `@page { size: A4 portrait; margin: ... }`. Without it, pass `paperWidth=8.27, paperHeight=11.69` (inches).
- `pageRanges="3"` prints a single page — cheap way to spot-check: print one page, `sips -s format png page.pdf --out page.png`, read the image. (`sips` only converts the FIRST page of a multi-page PDF, so single-page exports are the way to inspect page N.)
- Headless Chrome (`--headless --print-to-pdf`) as a separate process hung under the agent sandbox; printing through the user's running Chrome via CDP works.

## Chrome print-pipeline limitations (Skia PDF)

- **`backdrop-filter` is silently ignored** — glass/frosted panels lose their blur and render as their plain semi-transparent background. Fix: `@media print` fallback with a near-opaque background on those elements, or the text becomes unreadable over busy content.
- **Large-blur `box-shadow` rasterizes as ugly gray smudge bands** (worse combined with `zoom` on the element). Fix: `@media print { .card { box-shadow: none; } }`.
- Backgrounds need `printBackground=True` AND `* { print-color-adjust: exact; -webkit-print-color-adjust: exact; }` to survive.
- `zoom` on elements lays out correctly in print; base64-embedded @font-face fonts embed fine in the PDF.
