# Invoice Extractor

Extracts nine key fields from invoice images using **two independent, meaningfully
different pipelines**, cross-validates them, and produces a reconciled result with
a full agreement report — plus true accuracy against a hand-labelled gold set.

Built for the *Lead Engineer – Cloud & AI* assessment: the emphasis is on a
small, production-shaped system — sound number handling, a real validation layer,
clean packaging, and Azure/security awareness — rather than a one-off script.

## Required fields

Seller Name · Seller Tax ID · Client Name · Client Tax ID · Invoice Number ·
Invoice Date · Net Worth · VAT · Gross Worth

## Architecture

```
                         ┌──────────────────────────────────────────┐
 invoice image  ──▶ OCR  │  Pipeline A: OCR text → Azure OpenAI       │
 (Tesseract,             │              structured extraction (gpt-4o)│──┐
  shared front-end)      │  Pipeline B: OCR boxes → deterministic     │  │
                         │              rules / regex parser          │──┤
                         │  Pipeline C (opt-in): Azure Document        │  │
                         │              Intelligence prebuilt-invoice  │──┤
                         └──────────────────────────────────────────┘  │
                                                                         ▼
                              normalize → compare → reconcile → CSV deliverables
```

- **Pipeline A — OCR + LLM.** Tesseract OCR text → Azure OpenAI (`gpt-4o`,
  `temperature=0`, schema-constrained structured outputs) → fields.
- **Pipeline B — OCR + rules.** Tesseract word boxes → deterministic parser that
  uses **coordinate geometry** (left column = seller, right = client) and label
  anchors. Fully local, **needs no credentials**.
- **Pipeline C — Azure Document Intelligence** *(optional, opt-in)*. The
  `prebuilt-invoice` model — a different paradigm again (a layout-aware cloud
  model). Off by default; enabled with `--include-azure`.

### Why A and B are *meaningfully* different (and why that matters)

They share only the OCR step, then diverge completely: A reasons over flattened
text, B reads coordinates. They therefore **fail differently**, which is the whole
point of cross-validation. A real example from the run over all 51 invoices —
`batch1-0357`:

| | seller_name | client_name |
|---|---|---|
| **Pipeline A (LLM)** | `Houston-Brooks Moore, Hill and Ford` ❌ (merged both) | `Client` ❌ (grabbed the label) |
| **Pipeline B (rules)** | `Houston-Brooks` ✅ | `Moore, Hill and Ford` ✅ |
| **Reconciled output** | `Houston-Brooks` ✅ | `Moore, Hill and Ford` ✅ |

The LLM tripped on the two-column layout; the box-based rules pipeline did not;
the comparison flagged it and **reconciliation produced the correct final value**.
That single genuine disagreement is stronger evidence the system works than a
suspiciously perfect score.

## Quickstart

Requires **Python 3.11** and the **Tesseract** OCR binary
(`brew install tesseract` on macOS; `apt-get install tesseract-ocr` on Debian).

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"                 # core + tests (rules pipeline, keyless)

# 1) Get the images (Kaggle creds in .env or ~/.kaggle/kaggle.json)
pip install -e ".[data]"
python scripts/download_invoices.py      # -> data/batch1_1/ (51 images)

# 2) Run — keyless, rules only:
invoice-extract --offline                # -> deliverables/output.csv

# 3) Run both pipelines (needs Azure OpenAI creds in .env):
pip install -e ".[llm]"
cp .env.example .env                     # fill in AZURE_OPENAI_*
invoice-extract                          # -> output.csv + comparison_report.csv + summary.csv

# 4) Optionally add Pipeline C (needs a Document Intelligence resource):
pip install -e ".[azure]"
invoice-extract --include-azure

# 5) True accuracy against the gold set:
python scripts/evaluate.py               # -> deliverables/accuracy.csv
```

> **Note on the count.** The brief says 50 images but specifies `batch1-0331` to
> `batch1-0381`, which is **51 files inclusive**. This implementation processes
> the named filename range and reports the count.

## Configuration

All secrets live in `.env` (git-ignored) — never in source. Copy `.env.example`
and fill in what you need; the rules pipeline needs nothing.

| Variable | Used by |
|---|---|
| `AZURE_OPENAI_ENDPOINT` / `AZURE_OPENAI_API_KEY` / `AZURE_OPENAI_DEPLOYMENT_NAME` / `AZURE_OPENAI_API_VERSION` | Pipeline A |
| `AZURE_DI_ENDPOINT` / `AZURE_DI_KEY` | Pipeline C |
| `KAGGLE_USERNAME` / `KAGGLE_KEY` | dataset download |
| `TESSERACT_CMD` | path to tesseract, if not on `PATH` |

## Outputs (`deliverables/`)

| File | What it is |
|---|---|
| `output.csv` | Final reconciled fields per invoice, with `source_strategy` and `validation_flags`. |
| `comparison_report.csv` | Per file, per field: each pipeline's raw + normalized value, `match`, `severity`, `notes`. |
| `summary.csv` | Per-field match rate across all invoices. |
| `accuracy.csv` | True accuracy (per field + overall) for each pipeline and the final output, vs the gold set. |

## Validation logic

The core idea: compare pipelines on **meaning, not formatting**.

- **Normalization** (`normalize.py`) parses each field to a canonical form before
  comparing — money to `Decimal` (handling European `1 612,50` spacing and OCR
  `$`-spacing), dates to ISO, tax IDs to `###-##-####`. So `$1 612,50` (LLM) and
  `1 612,50` (rules) **agree**; they are flagged `formatting_only`, not a mismatch.
- **Comparison** (`compare.py`) emits the long-format report and per-field match
  rates. A match requires *both* pipelines to produce the same value — "both
  missing" is flagged, not counted as agreement (so two failing pipelines can't
  look good).
- **Reconciliation** (`reconcile.py`) decides the final value:
  agree → use it; disagree on **money** → prefer the pipeline whose totals
  reconcile (`net + vat == gross`); disagree on any other field → prefer the
  deterministic **rules** pipeline; unresolved → emit and flag. Each row records
  `source_strategy` (`agreement` / `reconciled` / a single pipeline) and
  `validation_flags`.

**Agreement is not accuracy.** Two pipelines can agree and both be wrong, so
`comparison_report.csv` / `summary.csv` measure *agreement*, while `accuracy.csv`
measures *true accuracy* against an independent, hand-labelled **gold set** of 10
invoices (`gold/gold_labels.csv`). The gold labels were **hand-transcribed from
the images, then cross-checked against Pipeline B** (0 diffs) — not generated by a
pipeline.

## Results

Over all 51 invoices (rules + Azure OpenAI), 0 extraction failures:

- **Agreement** (`summary.csv`): 100% on 7 fields; 98% on `seller_name` and
  `client_name` — the single real disagreement (`batch1-0357`, above), correctly
  resolved.
- **True accuracy** (`accuracy.csv`, 10 gold invoices, includes the stray-`%`
  traps `0354`/`0361`): **100%** for Pipeline A, Pipeline B, and the final output.
  100% is expected on this clean, fixed-template synthetic data — the value here
  is the measurement discipline and showing both pipelines independently reach
  the hand-labelled truth.
- **Cost / latency**: Pipeline A ≈ **2.7 s/invoice**, **$0.156** total for 51
  (gpt-4o, token-based estimate). Pipeline B is local and effectively free/instant.

## Azure & deployment readiness

The system is structured to deploy on Azure without being over-built for a
51-image batch:

- **Secrets** come from the environment / `.env`; in production they'd come from
  **Azure Key Vault**. Nothing secret is in source, and `.env` is git-ignored.
- **Cloud-native shape:** Pipeline A (Azure OpenAI) and Pipeline C (Azure
  Document Intelligence) are already cloud calls. The batch runner is a plain
  function over a folder — it would drop into an **Azure Container App** or
  **Function** triggered by a Blob upload, reading images from Blob and writing
  the CSVs back, with minimal change.
- **Deliberate scope:** flat, dependency-light, well-tested scripts — not a
  Prefect/Blob/Parquet orchestration stack — because the task is 51 flat
  invoices. Knowing what *not* to build is part of the design.

## Project structure

```
src/invoice_extractor/
  config.py          # typed settings from .env (pydantic-settings)
  models.py          # InvoiceFields (the spine), PipelineResult, ReconciledInvoice
  ocr.py             # Tesseract front-end: text + word boxes
  normalize.py       # money / date / tax-id / amount normalization
  compare.py         # cross-pipeline comparison + summary
  reconcile.py       # reconciliation policy -> final output
  evaluate.py        # accuracy vs the gold set
  csv_writer.py      # output.csv writer
  runner.py          # batch run loop (per-image isolation, pipeline selection)
  cli.py             # `invoice-extract` entry point
  pipelines/         # rules_pipeline, llm_pipeline, azure_pipeline + registry
scripts/             # download_invoices, evaluate, smoke_llm, smoke_azure
gold/gold_labels.csv # hand-labelled ground truth (committed)
tests/               # pytest suite
```

## Testing

```bash
ruff check src tests scripts
pytest -q
```

The suite is credential-free: tests that need the Tesseract binary or the dataset
images **skip gracefully** when absent, and the Azure pipelines are unit-tested
with fakes (no network). CI (`.github/workflows/ci.yml`) runs lint + tests on
every push.

## Limitations

- **Agreement ≠ accuracy** beyond the 10-invoice gold set — wider accuracy is
  inferred from agreement + arithmetic consistency.
- **One fixed template, clean synthetic renders.** Pipeline B's geometry (e.g. the
  seller/client column split) is tuned to this layout and would need adaptation
  for other invoice designs; Pipeline A and C generalise better.
- **Single VAT rate (10%)** in this dataset. The SUMMARY parser anchors on the
  `Total` row, which handles a single rate; multi-rate summaries are not exercised.
- **Pipeline C** is implemented, mock-tested, opt-in (`--include-azure`), and
  **live-verified** against a Document Intelligence resource (8/9 fields on a
  sample invoice). On this synthetic template, `prebuilt-invoice` returned
  `CustomerTaxId` but **not** `VendorTaxId` (the seller tax id), so it is not
  fully accurate on this layout. It is not part of the committed deliverables
  (those are rules + llm); enable it with `--include-azure`.
- **LLM determinism:** `temperature=0` + structured outputs make Pipeline A stable
  but not byte-identical across runs.
