# PDF Generation Notes

## Supported engines

The invoice PDF pipeline is now designed for HTML-compatible engines only:

1. `WeasyPrint` - best option for invoice print fidelity and CSS paged media
2. `pdfkit` + `wkhtmltopdf` - good fallback when the binary is installed
3. `xhtml2pdf` - Python-only fallback for simpler environments

## Why ReportLab is no longer the default fallback

ReportLab cannot render the Jinja invoice HTML/CSS directly. The previous fallback created a simplified PDF by scraping a few strings from the template output, which caused:

- missing invoice fields
- broken layout alignment
- no reliable page breaks
- logos and CSS differences from the browser view

For production invoices, it is better to fail clearly than silently generate an incomplete document.

## Recommended setup

### Best quality

```bash
pip install weasyprint
```

### Windows-friendly fallback

```bash
pip install xhtml2pdf
```

### wkhtmltopdf option

Install the `wkhtmltopdf` binary, then:

```bash
pip install pdfkit
```
