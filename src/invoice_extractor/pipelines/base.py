"""The contract every extraction pipeline implements."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from invoice_extractor.models import PipelineResult


@runtime_checkable
class ExtractionPipeline(Protocol):
    """Turns one invoice image into a :class:`PipelineResult`.

    Implementations must not raise for a single bad image — capture the failure
    in ``PipelineResult.error`` and return a result so the batch keeps going.
    """

    name: str

    def extract(self, image_path: Path) -> PipelineResult: ...
