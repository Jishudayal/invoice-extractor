"""Step 2.1 — the six non-money fields from the rules pipeline, on real OCR.

Skipped when the tesseract binary or the sample images are unavailable.
"""

import shutil
from decimal import Decimal
from pathlib import Path

import pytest

from invoice_extractor.config import Settings
from invoice_extractor.normalize import parse_money
from invoice_extractor.ocr import run_ocr
from invoice_extractor.pipelines.rules_pipeline import extract_fields

# Expected non-money fields, verified against the real invoices.
EXPECTED = {
    "batch1-0331.jpg": {
        "invoice_number": "94138597",
        "invoice_date": "02/05/2018",
        "seller_name": "Ochoa-Scott",
        "seller_tax_id": "921-82-1053",
        "client_name": "Green LLC",
        "client_tax_id": "965-99-1263",
    },
    "batch1-0345.jpg": {
        "invoice_number": "92919413",
        "invoice_date": "10/04/2020",
        "seller_name": "Jones and Sons",
        "seller_tax_id": "952-76-3987",
        "client_name": "Hamilton-Simmons",
        "client_tax_id": "992-84-7640",
    },
}

# Expected SUMMARY totals (net, vat, gross) as parsed Decimals. Asserting on the
# parsed value rather than the raw string keeps the test robust to OCR spacing.
EXPECTED_TOTALS = {
    "batch1-0331.jpg": (Decimal("1612.50"), Decimal("161.25"), Decimal("1773.75")),
    "batch1-0345.jpg": (Decimal("5992.66"), Decimal("599.27"), Decimal("6591.93")),
}

pytestmark = pytest.mark.skipif(
    shutil.which("tesseract") is None,
    reason="requires the tesseract binary",
)


def _locate(name: str) -> Path | None:
    for base in (Path("data/batch1_1"), Path("batch1_1")):
        candidate = base / name
        if candidate.exists():
            return candidate
    return None


@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_rules_extracts_header_and_party_fields(name):
    path = _locate(name)
    if path is None:
        pytest.skip(f"sample image {name} not available")
    fields = extract_fields(run_ocr(path))
    for key, expected in EXPECTED[name].items():
        assert getattr(fields, key) == expected, key


@pytest.mark.parametrize("name", sorted(EXPECTED_TOTALS))
def test_rules_extracts_summary_totals_that_reconcile(name):
    path = _locate(name)
    if path is None:
        pytest.skip(f"sample image {name} not available")
    fields = extract_fields(run_ocr(path))
    net = parse_money(fields.net_worth)
    vat = parse_money(fields.vat)
    gross = parse_money(fields.gross_worth)
    assert (net, vat, gross) == EXPECTED_TOTALS[name]
    assert net + vat == gross


def test_rules_pipeline_builds_from_registry_and_runs():
    # Importing the module registered the pipeline; build it and run one image.
    from invoice_extractor import pipelines

    path = _locate("batch1-0331.jpg")
    if path is None:
        pytest.skip("sample image not available")
    pipeline = pipelines.build("rules", Settings())
    result = pipeline.extract(path)
    assert result.pipeline == "rules"
    assert result.error is None
    assert result.fields.invoice_number == "94138597"
