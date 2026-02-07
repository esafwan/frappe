# Plan: Join Multiple JPEGs into a PDF using Existing Frappe Tools

## Key Finding

**No new API, whitelisted method, or custom function is needed.** Frappe already ships with all the libraries required. There are multiple approaches using what's already available.

---

## Available Libraries (already in `pyproject.toml`)

| Library | Version | Location | Use |
|---------|---------|----------|-----|
| **Pillow** | ~12.0.0 | `pyproject.toml:18` | Image loading + native PDF save |
| **pypdf** | 6.6.0 | `pyproject.toml:23` | PDF merge/manipulation |
| **pdfkit** | ~1.0.0 | `pyproject.toml:52` | HTML-to-PDF via wkhtmltopdf |
| **WeasyPrint** | 66.0 | `pyproject.toml:29` | HTML/CSS-to-PDF |

---

## Approach 1 (Simplest — Pillow only, no new methods)

Pillow can natively save multiple images as a single multi-page PDF. This requires **zero** Frappe-specific methods.

### Usage in Server Script, Custom Script, or Bench Console

```python
from PIL import Image
import frappe
import os

# 1. Get file docs (adjust filters as needed)
files = frappe.get_all("File", filters={"file_name": ["like", "%.jpg"]}, fields=["file_url", "name"], limit=10)

# 2. Load images via PIL
images = []
for f in files:
    file_path = frappe.get_site_path("public", f.file_url.lstrip("/"))
    # Could also be: frappe.get_site_path(f.file_url.lstrip("/")) for private files
    img = Image.open(file_path).convert("RGB")  # PDF needs RGB, not RGBA/P
    images.append(img)

# 3. Save all as a single PDF — Pillow does this natively
if images:
    first, *rest = images
    output_path = frappe.get_site_path("public", "files", "combined_output.pdf")
    first.save(output_path, "PDF", save_all=True, append_images=rest)

    # 4. (Optional) Create a File doc so it appears in Frappe
    f = frappe.new_doc("File")
    f.file_name = "combined_output.pdf"
    f.file_url = "/files/combined_output.pdf"
    f.is_private = 0
    f.save(ignore_permissions=True)
    frappe.db.commit()
```

### Why this works
- `Image.save(..., "PDF", save_all=True, append_images=[...])` is a **built-in Pillow feature** — no extra library needed.
- Each image becomes one page in the PDF, scaled to its native resolution.

### Limitations
- Page size matches image pixel dimensions (no A4 fitting by default).
- No headers/footers/margins.

---

## Approach 2 (A4-fitted pages — Pillow + pypdf, no new methods)

If you need standard A4 pages with images centered/fitted, use Pillow to create individual PDFs at A4 size, then merge with pypdf.

```python
from PIL import Image
from pypdf import PdfWriter
import frappe
import io

A4_WIDTH_PT = 595    # A4 width in points (72 dpi)
A4_HEIGHT_PT = 842   # A4 height in points

file_urls = ["/files/img1.jpg", "/files/img2.jpg", "/files/img3.jpg"]

writer = PdfWriter()

for url in file_urls:
    file_path = frappe.get_site_path("public", url.lstrip("/"))
    img = Image.open(file_path).convert("RGB")

    # Scale image to fit A4 while maintaining aspect ratio
    img_w, img_h = img.size
    scale = min(A4_WIDTH_PT / img_w, A4_HEIGHT_PT / img_h)
    new_w = int(img_w * scale)
    new_h = int(img_h * scale)
    img = img.resize((new_w, new_h), Image.LANCZOS)

    # Create a white A4 canvas and paste image centered
    canvas = Image.new("RGB", (A4_WIDTH_PT, A4_HEIGHT_PT), "white")
    x = (A4_WIDTH_PT - new_w) // 2
    y = (A4_HEIGHT_PT - new_h) // 2
    canvas.paste(img, (x, y))

    # Save single page to buffer
    buf = io.BytesIO()
    canvas.save(buf, "PDF")
    buf.seek(0)

    # Append to writer
    from pypdf import PdfReader
    reader = PdfReader(buf)
    writer.add_page(reader.pages[0])

# Write final PDF
output_path = frappe.get_site_path("public", "files", "combined_a4.pdf")
with open(output_path, "wb") as f:
    writer.write(f)
```

---

## Approach 3 (HTML route — using existing `frappe.utils.pdf.get_pdf`)

Use the existing `get_pdf()` function (already used by Print Format) to render images embedded in HTML.

```python
import frappe
from frappe.utils.pdf import get_pdf
import base64

file_urls = ["/files/img1.jpg", "/files/img2.jpg", "/files/img3.jpg"]

html_parts = []
for url in file_urls:
    file_path = frappe.get_site_path("public", url.lstrip("/"))
    with open(file_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    html_parts.append(f'''
        <div style="page-break-after: always; text-align: center;">
            <img src="data:image/jpeg;base64,{b64}"
                 style="max-width: 100%; max-height: 100%; object-fit: contain;" />
        </div>
    ''')

html = "\n".join(html_parts)

# get_pdf() uses wkhtmltopdf under the hood — already available
pdf_content = get_pdf(html)

# Save or serve
output_path = frappe.get_site_path("public", "files", "combined_html.pdf")
with open(output_path, "wb") as f:
    f.write(pdf_content)
```

### Key reference
- `frappe.utils.pdf.get_pdf()` — `frappe/utils/pdf.py:87`
- Already handles options like page size, margins, orientation.

---

## Approach Comparison

| Criteria | Approach 1 (Pillow) | Approach 2 (Pillow+pypdf) | Approach 3 (get_pdf) |
|----------|---------------------|---------------------------|----------------------|
| Lines of code | ~10 | ~25 | ~15 |
| New dependencies | None | None | None |
| A4 page sizing | No | Yes | Yes (via wkhtmltopdf options) |
| Page margins | No | Manual | Yes (CSS/options) |
| Headers/footers | No | No | Yes (via print format) |
| Speed | Fastest | Fast | Slower (spawns wkhtmltopdf) |
| Requires wkhtmltopdf | No | No | Yes |

---

## Where to Run These

All three approaches work in any of these **existing** Frappe execution contexts — no new endpoint needed:

1. **Server Script** (DocType Event or API type) — configurable from the UI
2. **Bench console** — `bench console` then paste the code
3. **Custom App command** — `bench execute myapp.module.function`
4. **Background Job** — `frappe.enqueue()`
5. **Print Format (Jinja)** — for Approach 3, embed images in a print format template, then use the existing "Download PDF" button

---

## Recommendation

**Use Approach 1** for quick/simple merging (e.g., from a Server Script).
**Use Approach 2** if you need properly sized A4 pages.
**Use Approach 3** if you need the full print format experience (margins, headers, footers, letterhead).

All three use **only existing Frappe dependencies** — no new methods, APIs, or pip installs required.
