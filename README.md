# Invoice Extractor

Extracts nine key fields from invoice images using **independent pipelines** and
cross-validates the results.

> **Status:** in development. Full documentation (architecture, validation logic,
> Azure deployment notes, limitations) lands in the final phase.

## Required fields

Seller Name · Seller Tax ID · Client Name · Client Tax ID · Invoice Number ·
Invoice Date · Net Worth · VAT · Gross Worth

## Pipelines

- **Pipeline A** — OCR (Tesseract) → Azure OpenAI structured extraction.
- **Pipeline B** — OCR (Tesseract) → deterministic rules parser. Runs with **no credentials**.
- **Pipeline C** *(optional, off by default)* — Azure Document Intelligence `prebuilt-invoice`.

The pipelines are meaningfully different by design, so comparing them is a real
validation signal rather than two views of the same method.

## Get the invoice images

The 51-image working slice (`batch1-0331` … `batch1-0381`) is downloaded from
Kaggle on demand — the images are not committed to the repo. (The brief says 50
images; the named range is 51 inclusive. The pipeline processes the named range
and reports the count.)

```bash
pip install -e ".[data]"
# set KAGGLE_USERNAME / KAGGLE_KEY (or ~/.kaggle/kaggle.json), then:
python scripts/download_invoices.py      # -> data/batch1_1/
```

## Quickstart (development)

```bash
python -m venv .venv && source .venv/bin/activate

pip install -e ".[dev]"                  # core + tests — runs Pipeline B with no creds
invoice-extract --offline                # defaults to data/batch1_1

# To enable the cloud pipelines, install their extras and add credentials:
pip install -e ".[dev,llm,azure]"        # llm = Azure OpenAI (A), azure = Azure DI (C)
cp .env.example .env                     # then fill in the Azure values
```

Requires the Tesseract OCR binary (`brew install tesseract` on macOS).
