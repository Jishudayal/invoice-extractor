"""Pipeline registry.

Pipelines register a factory under a name; the runner builds them on demand with
the current :class:`Settings`. Factories (not instances) keep credential-needing
pipelines from being constructed until they are actually used. Deliberately a
plain dict, not a plugin framework.
"""

from __future__ import annotations

from collections.abc import Callable

from invoice_extractor.config import Settings
from invoice_extractor.pipelines.base import ExtractionPipeline

PipelineFactory = Callable[[Settings], ExtractionPipeline]

_FACTORIES: dict[str, PipelineFactory] = {}


def register(name: str, factory: PipelineFactory) -> None:
    """Register a pipeline factory under ``name``."""
    if name in _FACTORIES:
        raise ValueError(f"Pipeline already registered: {name!r}")
    _FACTORIES[name] = factory


def build(name: str, settings: Settings) -> ExtractionPipeline:
    """Build a registered pipeline with the given settings."""
    try:
        factory = _FACTORIES[name]
    except KeyError:
        raise KeyError(f"Unknown pipeline: {name!r}. Available: {available()}") from None
    return factory(settings)


def available() -> list[str]:
    """Names of all registered pipelines, sorted."""
    return sorted(_FACTORIES)


def load_builtin_pipelines() -> None:
    """Import the built-in pipeline modules so they self-register.

    Imported lazily here (not at package import) to avoid a circular import: each
    pipeline module imports this package to call :func:`register`. Safe to call
    repeatedly — module imports are cached, so registration runs only once.
    """
    from invoice_extractor.pipelines import (  # noqa: F401
        azure_pipeline,
        llm_pipeline,
        rules_pipeline,
    )


__all__ = [
    "ExtractionPipeline",
    "PipelineFactory",
    "register",
    "build",
    "available",
    "load_builtin_pipelines",
]
