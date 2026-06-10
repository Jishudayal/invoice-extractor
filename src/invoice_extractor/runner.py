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


def select_pipeline_names(
    *, offline: bool, settings: Settings, include_azure: bool = False
) -> list[str]:
    """Pipelines to run for this invocation.

    The rules pipeline (B) is keyless and always runs. The LLM pipeline (A) runs
    when Azure OpenAI is configured and we are not offline. The Azure Document
    Intelligence pipeline (C) is opt-in: it runs only when ``include_azure`` is
    set *and* it is configured *and* we are not offline.
    """
    names = ["rules"]
    if offline:
        return names
    if settings.llm_enabled:
        names.append("llm")
    if include_azure and settings.azure_di_enabled:
        names.append("azure")
    return names


def _build_pipelines(names: list[str], settings: Settings) -> dict:
    """Build the selected pipelines, skipping (with a warning) any that can't build."""
    built = {}
    for name in names:
        try:
            built[name] = pipelines.build(name, settings)
        except Exception as exc:
            logger.warning("skipping pipeline %s: %s", name, exc)
    return built


def _log_pipeline_summary(results: list[PipelineResult]) -> None:
    for name in sorted({result.pipeline for result in results}):
        rows = [r for r in results if r.pipeline == name]
        failed = sum(1 for r in rows if r.error)
        latencies = [r.latency_ms for r in rows if r.latency_ms is not None]
        avg_latency = sum(latencies) / len(latencies) if latencies else 0.0
        cost = sum(r.cost_usd for r in rows if r.cost_usd is not None)
        logger.info(
            "pipeline %-6s: %d processed, %d failed, avg %.0f ms, cost $%.4f",
            name,
            len(rows),
            failed,
            avg_latency,
            cost,
        )


def run(
    input_dir: Path, *, offline: bool, settings: Settings, include_azure: bool = False
) -> list[PipelineResult]:
    """OCR + extract every image in ``input_dir`` with the selected pipeline(s)."""
    pipelines.load_builtin_pipelines()

    images = _discover_images(input_dir)
    if not images:
        logger.warning("no images found in %s", input_dir)
        return []

    names = select_pipeline_names(offline=offline, settings=settings, include_azure=include_azure)
    built = _build_pipelines(names, settings)
    if not built:
        logger.error("no pipelines available to run")
        return []
    logger.info("processing %d image(s) with pipeline(s): %s", len(images), ", ".join(built))

    results: list[PipelineResult] = []
    for image in images:
        for name, pipeline in built.items():
            try:
                result = pipeline.extract(image)
            except Exception as exc:
                # Pipelines are designed not to raise; this guarantees per-image
                # isolation even if one has a bug.
                result = PipelineResult(file_name=image.name, pipeline=name, error=str(exc))
            results.append(result)
            if result.error:
                logger.warning("FAIL  %-20s [%s] %s", image.name, name, result.error)
            else:
                filled = sum(1 for value in result.fields.model_dump().values() if value)
                logger.info("PASS  %-20s [%s] %d/9 fields", image.name, name, filled)

    _log_pipeline_summary(results)
    return results
