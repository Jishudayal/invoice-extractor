"""Comparison engine: compare two pipelines field-by-field on normalised meaning.

Produces the rows for ``comparison_report.csv`` (per file, per field: each
pipeline's raw and normalised value, whether they match, a severity, and a note)
and the per-field roll-up for ``summary.csv``.

Matching is on *normalised* values, so incidental formatting differences (OCR
spacing, date format, tax-id punctuation) do not count as disagreements — only
genuine differences in meaning do.
"""

from __future__ import annotations

import csv
from decimal import Decimal
from pathlib import Path

from pydantic import BaseModel

from invoice_extractor.models import InvoiceFields, PipelineResult
from invoice_extractor.normalize import normalize_text, parse_date, parse_money, parse_tax_id

# The two pipelines compared (A vs B). Azure Document Intelligence (Phase 4) is
# handled separately rather than crammed into this pairwise report.
PIPELINE_A = "llm"
PIPELINE_B = "rules"

FIELD_NAMES = list(InvoiceFields.model_fields)

# Ordered tuple, not a set: reconciliation iterates these for the money block, so
# the order is part of the contract (left-to-right: net, VAT, gross).
MONEY_FIELDS = ("net_worth", "vat", "gross_worth")
_TAX_ID_FIELDS = {"seller_tax_id", "client_tax_id"}
_DATE_FIELDS = {"invoice_date"}
_NAME_FIELDS = {"seller_name", "client_name"}


def normalize_field(field: str, value: str | None) -> Decimal | str | None:
    """Canonicalise one field's raw value for comparison and reconciliation."""
    if field in MONEY_FIELDS:
        return parse_money(value)
    if field in _DATE_FIELDS:
        return parse_date(value)
    if field in _TAX_ID_FIELDS:
        return parse_tax_id(value)
    return normalize_text(value)


def _render(value: Decimal | str | None) -> str:
    return "" if value is None else str(value)


def _mismatch_severity(field: str) -> str:
    # Names carry more OCR/format variance than IDs and money, so a name
    # disagreement is lower severity than a money or ID disagreement.
    return "medium" if field in _NAME_FIELDS else "high"


class ComparisonRow(BaseModel):
    file_name: str
    field: str
    value_a: str
    value_b: str
    normalized_a: str
    normalized_b: str
    match: bool
    severity: str
    notes: str


class SummaryRow(BaseModel):
    field: str
    total: int
    matches: int
    mismatches: int
    match_rate: float


def _compare_field(
    file_name: str,
    field: str,
    raw_a: str | None,
    raw_b: str | None,
    pipeline_a: str,
    pipeline_b: str,
) -> ComparisonRow:
    norm_a = normalize_field(field, raw_a)
    norm_b = normalize_field(field, raw_b)
    # A match is a *confirmed* agreement on a value: both pipelines must have
    # produced one. "Both missing" is therefore not a match — otherwise two
    # pipelines that both fail to find a field would inflate the match rate.
    match = norm_a is not None and norm_a == norm_b

    if norm_a is None and norm_b is None:
        notes = "both_missing"
    elif norm_a is None:
        notes = f"{pipeline_a}_missing"
    elif norm_b is None:
        notes = f"{pipeline_b}_missing"
    elif match and (raw_a or "") != (raw_b or ""):
        notes = "formatting_only"
    else:
        notes = ""

    return ComparisonRow(
        file_name=file_name,
        field=field,
        value_a=raw_a or "",
        value_b=raw_b or "",
        normalized_a=_render(norm_a),
        normalized_b=_render(norm_b),
        match=match,
        severity="" if match else _mismatch_severity(field),
        notes=notes,
    )


def compare_results(
    results: list[PipelineResult],
    pipeline_a: str = PIPELINE_A,
    pipeline_b: str = PIPELINE_B,
) -> list[ComparisonRow]:
    """Build comparison rows (one per file per field) for two pipelines."""
    by_file: dict[str, dict[str, InvoiceFields]] = {}
    for result in results:
        per_pipeline = by_file.setdefault(result.file_name, {})
        if result.pipeline in per_pipeline:
            raise ValueError(
                f"duplicate result for {result.file_name!r} from pipeline {result.pipeline!r}"
            )
        per_pipeline[result.pipeline] = result.fields

    rows: list[ComparisonRow] = []
    for file_name in sorted(by_file):
        per_pipeline = by_file[file_name]
        fields_a = per_pipeline.get(pipeline_a) or InvoiceFields()
        fields_b = per_pipeline.get(pipeline_b) or InvoiceFields()
        for field in FIELD_NAMES:
            rows.append(
                _compare_field(
                    file_name,
                    field,
                    getattr(fields_a, field),
                    getattr(fields_b, field),
                    pipeline_a,
                    pipeline_b,
                )
            )
    return rows


def summarize(rows: list[ComparisonRow]) -> list[SummaryRow]:
    """Per-field match counts and rates across all files."""
    counts = {field: [0, 0] for field in FIELD_NAMES}  # field -> [total, matches]
    for row in rows:
        counts[row.field][0] += 1
        if row.match:
            counts[row.field][1] += 1

    summary: list[SummaryRow] = []
    for field in FIELD_NAMES:
        total, matches = counts[field]
        rate = round(100.0 * matches / total, 1) if total else 0.0
        summary.append(
            SummaryRow(
                field=field,
                total=total,
                matches=matches,
                mismatches=total - matches,
                match_rate=rate,
            )
        )
    return summary


def write_comparison_report(
    rows: list[ComparisonRow],
    path: Path,
    pipeline_a: str = PIPELINE_A,
    pipeline_b: str = PIPELINE_B,
) -> None:
    header = [
        "file_name",
        "field",
        f"{pipeline_a}_value",
        f"{pipeline_b}_value",
        f"{pipeline_a}_normalized",
        f"{pipeline_b}_normalized",
        "match",
        "severity",
        "notes",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        for row in rows:
            writer.writerow(
                [
                    row.file_name,
                    row.field,
                    row.value_a,
                    row.value_b,
                    row.normalized_a,
                    row.normalized_b,
                    row.match,
                    row.severity,
                    row.notes,
                ]
            )


def write_summary(summary: list[SummaryRow], path: Path) -> None:
    fieldnames = ["field", "total", "matches", "mismatches", "match_rate"]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in summary:
            writer.writerow(row.model_dump())
