"""Command-line entry point: extract invoice fields over a folder of images.

Runs the configured pipelines (rules always; the LLM pipeline when Azure OpenAI
is configured and not ``--offline``), then writes the deliverables: ``output.csv``
(final reconciled fields) plus, when at least two pipelines ran, the
``comparison_report.csv`` and ``summary.csv`` cross-validation reports.
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from invoice_extractor import runner
from invoice_extractor.compare import (
    compare_results,
    summarize,
    write_comparison_report,
    write_summary,
)
from invoice_extractor.config import load_settings
from invoice_extractor.csv_writer import write_output_csv
from invoice_extractor.reconcile import reconcile_batch

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
    parser.add_argument(
        "--include-azure",
        action="store_true",
        help="Also run the optional Azure Document Intelligence pipeline (requires AZURE_DI_*).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")

    settings = load_settings()
    results = runner.run(
        args.input_dir,
        offline=args.offline,
        settings=settings,
        include_azure=args.include_azure,
    )

    if not results:
        return 1

    records = reconcile_batch(results)
    write_output_csv(records, args.output_dir / "output.csv")
    logger.info("wrote %d row(s) to %s", len(records), args.output_dir / "output.csv")

    present = {result.pipeline for result in results}

    # Cross-validation reports are only meaningful when two pipelines ran.
    if len(present) >= 2:
        comparison = compare_results(results)
        write_comparison_report(comparison, args.output_dir / "comparison_report.csv")
        write_summary(summarize(comparison), args.output_dir / "summary.csv")
        logger.info("wrote comparison_report.csv and summary.csv to %s", args.output_dir)

    # A pipeline that was requested but never produced results (e.g. misconfigured
    # Azure) is a failure — don't let a green exit hide a missing comparison.
    requested = runner.select_pipeline_names(
        offline=args.offline, settings=settings, include_azure=args.include_azure
    )
    missing = [name for name in requested if name not in present]
    if missing:
        logger.error("requested pipeline(s) did not run: %s", ", ".join(missing))

    failed = sum(1 for result in results if result.error)
    return 1 if (failed or missing) else 0


if __name__ == "__main__":
    raise SystemExit(main())
