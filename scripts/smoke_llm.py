"""One-shot smoke test for Pipeline A (Azure OpenAI).

Builds the LLM pipeline from your ``.env`` and runs it over a single invoice,
printing the extracted fields, latency, and estimated cost. Use this to confirm
the live Azure structured-output path before running the full batch.

Usage:
    pip install -e ".[llm]"
    # set AZURE_OPENAI_* in .env, then:
    python scripts/smoke_llm.py [path/to/invoice.jpg]
"""

from __future__ import annotations

import sys
from pathlib import Path

from invoice_extractor import pipelines
from invoice_extractor.config import load_settings

DEFAULT_IMAGE = Path("data/batch1_1/batch1-0331.jpg")


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    image = Path(argv[0]) if argv else DEFAULT_IMAGE
    if not image.exists():
        print(f"image not found: {image} (pass a path, or download the dataset)", file=sys.stderr)
        return 1

    settings = load_settings()
    if not settings.llm_enabled:
        print("Azure OpenAI not configured; set AZURE_OPENAI_* in .env.", file=sys.stderr)
        return 1

    pipelines.load_builtin_pipelines()
    pipeline = pipelines.build("llm", settings)
    result = pipeline.extract(image)

    if result.error:
        print(f"FAILED: {result.error}", file=sys.stderr)
        return 1

    print(f"file: {result.file_name}")
    print(f"latency_ms: {result.latency_ms}   cost_usd: {result.cost_usd}")
    for name, value in result.fields.model_dump().items():
        print(f"  {name:15} = {value!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
