"""Write extraction results to ``output.csv`` — the final per-invoice fields.

One row per result: the nine fields, the pipeline that produced them
(``source_strategy``), and ``validation_flags`` summarising obvious problems
(missing fields, totals that don't reconcile, extraction errors). In Phase 2 the
rows come straight from the rules pipeline; from Phase 3 they'll be the
reconciled output of multiple pipelines.
"""

from __future__ import annotations

import csv
from pathlib import Path

from invoice_extractor.models import PipelineResult
from invoice_extractor.normalize import parse_money

OUTPUT_COLUMNS = [
    "file_name",
    "seller_name",
    "seller_tax_id",
    "client_name",
    "client_tax_id",
    "invoice_number",
    "invoice_date",
    "net_worth",
    "vat",
    "gross_worth",
    "source_strategy",
    "validation_flags",
]


def validation_flags(result: PipelineResult) -> str:
    """Summarise obvious problems with a result as a ``;``-separated flag string.

    Empty string means "no problems detected". This is a deliberately light
    sanity layer; richer cross-pipeline validation arrives in Phase 3.
    """
    if result.error:
        return "extraction_error"

    fields = result.fields
    flags: list[str] = []

    missing = [name for name, value in fields.model_dump().items() if not value]
    if missing:
        flags.append("missing=" + ",".join(missing))

    net = parse_money(fields.net_worth)
    vat = parse_money(fields.vat)
    gross = parse_money(fields.gross_worth)
    if None not in (net, vat, gross):
        if net + vat != gross:
            flags.append("totals_mismatch")
    elif all((fields.net_worth, fields.vat, fields.gross_worth)):
        flags.append("totals_unparsed")

    return ";".join(flags)


def _row(result: PipelineResult) -> dict[str, str]:
    fields = result.fields
    return {
        "file_name": result.file_name,
        "seller_name": fields.seller_name or "",
        "seller_tax_id": fields.seller_tax_id or "",
        "client_name": fields.client_name or "",
        "client_tax_id": fields.client_tax_id or "",
        "invoice_number": fields.invoice_number or "",
        "invoice_date": fields.invoice_date or "",
        "net_worth": fields.net_worth or "",
        "vat": fields.vat or "",
        "gross_worth": fields.gross_worth or "",
        "source_strategy": result.pipeline,
        "validation_flags": validation_flags(result),
    }


def write_output_csv(results: list[PipelineResult], path: Path) -> None:
    """Write results to ``path`` (creating parent directories)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        for result in results:
            writer.writerow(_row(result))
