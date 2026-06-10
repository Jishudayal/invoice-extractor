"""Pipeline A wiring, tested with a fake LLM client (no Azure, no creds).

The image still needs OCR, so the pipeline tests guard-skip without tesseract.
The live Azure path is verified separately via scripts/smoke_llm.py.
"""

import shutil
from pathlib import Path

import pytest

from invoice_extractor.config import Settings
from invoice_extractor.llm import SYSTEM_PROMPT, LLMExtraction, make_llm_client
from invoice_extractor.models import InvoiceFields
from invoice_extractor.pipelines.llm_pipeline import LLMPipeline


class _FakeClient:
    def __init__(self, extraction: LLMExtraction | None = None, error: Exception | None = None):
        self._extraction = extraction
        self._error = error

    def extract(self, ocr_text: str) -> LLMExtraction:
        if self._error is not None:
            raise self._error
        assert self._extraction is not None
        return self._extraction


def _locate(name: str) -> Path | None:
    for base in (Path("data/batch1_1"), Path("batch1_1")):
        candidate = base / name
        if candidate.exists():
            return candidate
    return None


def test_system_prompt_covers_the_key_rules():
    assert "two-column" in SYSTEM_PROMPT
    assert "SUMMARY" in SYSTEM_PROMPT


def test_make_llm_client_requires_credentials():
    # _env_file=None ignores any local .env so this is deterministic.
    with pytest.raises(RuntimeError, match="Azure OpenAI is not configured"):
        make_llm_client(Settings(_env_file=None))


@pytest.mark.skipif(shutil.which("tesseract") is None, reason="requires the tesseract binary")
def test_pipeline_maps_extraction_and_records_cost(tmp_path):
    src = _locate("batch1-0331.jpg")
    if src is None:
        pytest.skip("sample image not available")
    shutil.copy(src, tmp_path / "img.jpg")

    client = _FakeClient(
        LLMExtraction(
            fields=InvoiceFields(invoice_number="94138597"),
            input_tokens=1000,
            output_tokens=100,
        )
    )
    pipeline = LLMPipeline(client, input_cost_per_1k=0.0025, output_cost_per_1k=0.01)
    result = pipeline.extract(tmp_path / "img.jpg")

    assert result.pipeline == "llm"
    assert result.error is None
    assert result.fields.invoice_number == "94138597"
    assert result.latency_ms is not None
    assert result.cost_usd == round(1000 / 1000 * 0.0025 + 100 / 1000 * 0.01, 6)


@pytest.mark.skipif(shutil.which("tesseract") is None, reason="requires the tesseract binary")
def test_pipeline_never_raises_on_client_error(tmp_path):
    src = _locate("batch1-0331.jpg")
    if src is None:
        pytest.skip("sample image not available")
    shutil.copy(src, tmp_path / "img.jpg")

    pipeline = LLMPipeline(_FakeClient(error=RuntimeError("boom")))
    result = pipeline.extract(tmp_path / "img.jpg")

    assert result.error == "boom"
    assert result.fields.invoice_number is None
