"""Accuracy evaluation against the hand-labelled gold set.

Scores each pipeline **and** the final reconciled output against
``gold/gold_labels.csv`` — i.e. *true accuracy on the gold subset*. This is a
different (and stronger) signal than the A-vs-B *agreement* in ``summary.csv``:
two pipelines can agree and both be wrong, so accuracy is measured against
independently hand-labelled truth. Comparison is on normalised values.
"""

from __future__ import annotations

import csv
from pathlib import Path

from pydantic import BaseModel

from invoice_extractor.compare import FIELD_NAMES, normalize_field
from invoice_extractor.models import InvoiceFields, PipelineResult, ReconciledInvoice

FINAL = "final"


class EvaluationReport(BaseModel):
    sources: list[str]  # e.g. ["llm", "rules", "final"]
    per_field: dict[str, dict[str, float]]  # field -> source -> accuracy %
    overall: dict[str, float]  # source -> accuracy %


def load_gold(path: Path) -> dict[str, dict[str, str]]:
    """Load the gold labels keyed by file name."""
    with path.open(newline="", encoding="utf-8") as handle:
        return {row["file_name"]: row for row in csv.DictReader(handle)}


def _score(
    gold: dict[str, dict[str, str]],
    extracted: dict[str, InvoiceFields],
) -> tuple[dict[str, float], float]:
    """Per-field and overall accuracy of one source's extractions against gold."""
    per_field: dict[str, float] = {}
    total_correct = total = 0
    for field in FIELD_NAMES:
        correct = count = 0
        for file_name, gold_row in gold.items():
            fields = extracted.get(file_name)
            expected = normalize_field(field, gold_row[field])
            actual = normalize_field(field, getattr(fields, field)) if fields else None
            count += 1
            if actual == expected:
                correct += 1
        per_field[field] = round(100.0 * correct / count, 1) if count else 0.0
        total_correct += correct
        total += count
    overall = round(100.0 * total_correct / total, 1) if total else 0.0
    return per_field, overall


def evaluate(
    results: list[PipelineResult],
    reconciled: list[ReconciledInvoice],
    gold: dict[str, dict[str, str]],
) -> EvaluationReport:
    """Score every pipeline and the final reconciled output against gold."""
    by_source: dict[str, dict[str, InvoiceFields]] = {}
    for result in results:
        by_source.setdefault(result.pipeline, {})[result.file_name] = result.fields
    by_source[FINAL] = {record.file_name: record.fields for record in reconciled}

    sources = sorted(name for name in by_source if name != FINAL) + [FINAL]
    per_field: dict[str, dict[str, float]] = {field: {} for field in FIELD_NAMES}
    overall: dict[str, float] = {}
    for source in sources:
        field_acc, overall_acc = _score(gold, by_source[source])
        for field in FIELD_NAMES:
            per_field[field][source] = field_acc[field]
        overall[source] = overall_acc

    return EvaluationReport(sources=sources, per_field=per_field, overall=overall)


def write_accuracy_report(report: EvaluationReport, path: Path) -> None:
    """Write the accuracy report: one row per field plus an OVERALL row."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["field", *report.sources])
        for field in FIELD_NAMES:
            writer.writerow([field, *(report.per_field[field][s] for s in report.sources)])
        writer.writerow(["OVERALL", *(report.overall[s] for s in report.sources)])
