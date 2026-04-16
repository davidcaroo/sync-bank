# PDF Extraction Endpoint

## Endpoint
- POST /extraer-pdf
- Content-Type: multipart/form-data
- Field: file (PDF)
- Query: preview=true|false

## Environment Variables
- PDF_MAX_BYTES (default 15000000)
- PDF_MAX_PAGES (default 5)
- PDF_OCR_LANG (default spa)
- PDF_MIN_TEXT_CHARS (default 30)
- PDF_MAX_PROMPT_CHARS (default 12000)

## Response
Returns a JSON payload with extracted facturas, confidence score, warnings, and raw text.

## Local Test
Run a self-test:

```
python scripts/test_extraer_pdf.py --self-test
```

Run with a PDF:

```
python scripts/test_extraer_pdf.py --pdf C:\path\to\invoice.pdf
```

## Windows Notes
- PyMuPDF wheels are not available for Python 3.13/3.14 on Windows. Use Python 3.11/3.12 or Docker.
