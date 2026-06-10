"""End-to-end check: real OCR -> find_amounts -> the SUMMARY totals reconcile.

Proves the Phase 1 pieces (OCR + normalisation) work together on real images and
that the Net + VAT = Gross oracle is recoverable from actual OCR output. Skipped
when the tesseract binary or the sample images are unavailable.
"""

import shutil
from decimal import Decimal
from pathlib import Path

import pytest

from invoice_extractor.normalize import find_amounts
from invoice_extractor.ocr import run_ocr

# Known SUMMARY totals (net, vat, gross) for invoices in the local sample.
KNOWN_TOTALS = {
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


@pytest.mark.parametrize("name", sorted(KNOWN_TOTALS))
def test_summary_totals_recovered_and_reconcile(name):
    path = _locate(name)
    if path is None:
        pytest.skip(f"sample image {name} not available")
    net, vat, gross = KNOWN_TOTALS[name]
    amounts = set(find_amounts(run_ocr(path).text))
    assert {net, vat, gross} <= amounts
    assert net + vat == gross
