import shutil
from pathlib import Path

import pytest

from invoice_extractor.ocr import OcrResult, run_ocr


def _find_sample() -> Path | None:
    for base in (Path("data/batch1_1"), Path("batch1_1")):
        candidate = base / "batch1-0331.jpg"
        if candidate.exists():
            return candidate
    return None


SAMPLE = _find_sample()

pytestmark = pytest.mark.skipif(
    shutil.which("tesseract") is None or SAMPLE is None,
    reason="requires the tesseract binary and a sample invoice image",
)


def test_run_ocr_returns_text_and_words():
    result = run_ocr(SAMPLE)
    assert isinstance(result, OcrResult)
    assert result.words, "expected OCR to find words"
    # Anchor tokens present on every invoice in this fixed template.
    upper = result.text.upper()
    assert "INVOICE" in upper
    assert "SELLER" in upper
    assert "TOTAL" in upper


def test_ocr_words_have_sane_boxes():
    result = run_ocr(SAMPLE)
    word = result.words[0]
    assert word.width > 0 and word.height > 0
    assert 0 <= word.confidence <= 100
