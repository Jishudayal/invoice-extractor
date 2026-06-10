"""Batch extraction: run the selected pipeline(s) over a folder of images.

Each image is processed independently — a failure on one image is captured in its
:class:`PipelineResult` (pipelines never raise) and logged, so the batch always
runs to completion. Returns every result for downstream CSV writing.
"""

from __future__ import annotations

import logging
from pathlib import Path

from invoice_extractor import pipelines
from invoice_extractor.config import Settings
from invoice_extractor.models import PipelineResult

logger = logging.getLogger(__name__)

_IMAGE_GLOBS = ("*.jpg", "*.jpeg", "*.png")


def _discover_images(input_dir: Path) -> list[Path]:
    found = [p for glob in _IMAGE_GLOBS for p in input_dir.glob(glob)]
    return sorted(found)


def _select_pipeline_names(*, offline: bool, settings: Settings) -> list[str]:
    """Pipelines to run for this invocation.

    Phase 2 ships only the keyless rules pipeline. Cloud pipelines (Azure OpenAI,
    Azure Document Intelligence) are added in later phases and will be gated on
    credentials and the ``offline`` flag here.
    """
    return ["rules"]


def run(input_dir: Path, *, offline: bool, settings: Settings) -> list[PipelineResult]:
    """OCR + extract every image in ``input_dir`` with the selected pipeline(s)."""
    pipelines.load_builtin_pipelines()

    images = _discover_images(input_dir)
    if not images:
        logger.warning("no images found in %s", input_dir)
        return []

    names = _select_pipeline_names(offline=offline, settings=settings)
    built = {name: pipelines.build(name, settings) for name in names}
    logger.info("processing %d image(s) with pipeline(s): %s", len(images), ", ".join(names))

    results: list[PipelineResult] = []
    passed = failed = 0
    for image in images:
        for name, pipeline in built.items():
            result = pipeline.extract(image)
            results.append(result)
            if result.error:
                failed += 1
                logger.warning("FAIL  %-20s [%s] %s", image.name, name, result.error)
            else:
                filled = sum(1 for value in result.fields.model_dump().values() if value)
                passed += 1
                logger.info("PASS  %-20s [%s] %d/9 fields", image.name, name, filled)

    logger.info("done: %d passed, %d failed", passed, failed)
    return results
