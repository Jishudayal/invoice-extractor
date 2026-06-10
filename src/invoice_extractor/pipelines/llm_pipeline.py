"""Pipeline A — OCR text + LLM structured extraction.

OCR the image (shared front-end), hand the text to an :class:`LLMClient`, and
record latency and (token-based) cost on the result. Like every pipeline it never
raises: a failure is captured in ``PipelineResult.error`` so the batch continues.
"""

from __future__ import annotations

import time
from pathlib import Path

from invoice_extractor import pipelines
from invoice_extractor.config import Settings
from invoice_extractor.llm import LLMClient, make_llm_client
from invoice_extractor.models import PipelineResult
from invoice_extractor.ocr import run_ocr


class LLMPipeline:
    name = "llm"

    def __init__(
        self,
        client: LLMClient,
        *,
        tesseract_cmd: str | None = None,
        input_cost_per_1k: float = 0.0,
        output_cost_per_1k: float = 0.0,
    ) -> None:
        self._client = client
        self._tesseract_cmd = tesseract_cmd
        self._input_cost_per_1k = input_cost_per_1k
        self._output_cost_per_1k = output_cost_per_1k

    def extract(self, image_path: Path) -> PipelineResult:
        start = time.monotonic()
        try:
            ocr = run_ocr(image_path, tesseract_cmd=self._tesseract_cmd)
            extraction = self._client.extract(ocr.text)
            latency_ms = (time.monotonic() - start) * 1000.0
            cost = (
                extraction.input_tokens / 1000.0 * self._input_cost_per_1k
                + extraction.output_tokens / 1000.0 * self._output_cost_per_1k
            )
            return PipelineResult(
                file_name=image_path.name,
                pipeline=self.name,
                fields=extraction.fields,
                latency_ms=round(latency_ms, 1),
                cost_usd=round(cost, 6),
            )
        except Exception as exc:
            latency_ms = (time.monotonic() - start) * 1000.0
            return PipelineResult(
                file_name=image_path.name,
                pipeline=self.name,
                latency_ms=round(latency_ms, 1),
                error=str(exc),
            )


def _build(settings: Settings) -> LLMPipeline:
    return LLMPipeline(
        make_llm_client(settings),
        tesseract_cmd=settings.tesseract_cmd,
        input_cost_per_1k=settings.llm_input_cost_per_1k,
        output_cost_per_1k=settings.llm_output_cost_per_1k,
    )


pipelines.register("llm", _build)
