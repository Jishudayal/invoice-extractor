"""Command-line entry point: extract invoice fields over a folder of images.

Phase 2 runs the keyless rules pipeline and reports per-image status. Writing the
CSV deliverables is added in Step 2.4; cloud pipelines arrive in later phases.
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from invoice_extractor import runner
from invoice_extractor.config import load_settings
from invoice_extractor.csv_writer import write_output_csv

logger = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="invoice-extract",
        description="Extract key fields from invoice images using independent pipelines.",
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=Path("data/batch1_1"),
        help="Directory of invoice images to process (default: data/batch1_1).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("deliverables"),
        help="Where to write the CSV outputs (default: deliverables).",
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Run only credential-free pipelines (skip Azure OpenAI and Azure DI).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")

    settings = load_settings()
    results = runner.run(args.input_dir, offline=args.offline, settings=settings)

    if not results:
        return 1

    output_path = args.output_dir / "output.csv"
    write_output_csv(results, output_path)
    logger.info("wrote %d row(s) to %s", len(results), output_path)

    failed = sum(1 for result in results if result.error)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
