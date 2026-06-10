"""Score the pipelines against the gold set and write deliverables/accuracy.csv.

Runs the configured pipelines over only the gold-labelled invoices, reconciles,
and reports true accuracy on the gold subset (per field and overall) for each
pipeline and the final output.

Usage:
    python scripts/evaluate.py            # uses gold/gold_labels.csv + data/batch1_1
"""

from __future__ import annotations

import logging
import shutil
import sys
import tempfile
from pathlib import Path

from invoice_extractor import runner
from invoice_extractor.compare import FIELD_NAMES
from invoice_extractor.config import load_settings
from invoice_extractor.evaluate import evaluate, load_gold, write_accuracy_report
from invoice_extractor.reconcile import reconcile_batch

GOLD_PATH = Path("gold/gold_labels.csv")
IMAGES_DIR = Path("data/batch1_1")
OUTPUT_PATH = Path("deliverables/accuracy.csv")


def _print_summary(report) -> None:
    width = max(len(f) for f in FIELD_NAMES)
    header = "field".ljust(width) + "  " + "  ".join(f"{s:>7}" for s in report.sources)
    print("\nTrue accuracy on the gold subset (%) — not A-vs-B agreement:")
    print(header)
    for field in FIELD_NAMES:
        row = "  ".join(f"{report.per_field[field][s]:>7}" for s in report.sources)
        print(field.ljust(width) + "  " + row)
    overall = "  ".join(f"{report.overall[s]:>7}" for s in report.sources)
    print("OVERALL".ljust(width) + "  " + overall)


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")

    if not GOLD_PATH.exists():
        print(f"gold labels not found: {GOLD_PATH}", file=sys.stderr)
        return 1
    gold = load_gold(GOLD_PATH)
    settings = load_settings()

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        for file_name in gold:
            source = IMAGES_DIR / file_name
            if not source.exists():
                print(f"missing image: {source}", file=sys.stderr)
                print("run: python scripts/download_invoices.py", file=sys.stderr)
                return 1
            shutil.copy(source, tmp_dir / file_name)
        results = runner.run(tmp_dir, offline=False, settings=settings)

    if not results:
        return 1

    reconciled = reconcile_batch(results)
    report = evaluate(results, reconciled, gold)
    write_accuracy_report(report, OUTPUT_PATH)
    _print_summary(report)
    print(f"\nwrote {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
