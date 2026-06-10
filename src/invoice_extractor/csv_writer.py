"""Write reconciled records to ``output.csv`` — the final per-invoice fields.

One row per invoice: the nine fields, how the values were chosen
(``source_strategy``), and ``validation_flags``. The values and flags are decided
in :mod:`invoice_extractor.reconcile`; this module only serialises them.
"""

from __future__ import annotations

import csv
from pathlib import Path

from invoice_extractor.models import ReconciledInvoice

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


def _row(record: ReconciledInvoice) -> dict[str, str]:
    fields = record.fields
    return {
        "file_name": record.file_name,
        "seller_name": fields.seller_name or "",
        "seller_tax_id": fields.seller_tax_id or "",
        "client_name": fields.client_name or "",
        "client_tax_id": fields.client_tax_id or "",
        "invoice_number": fields.invoice_number or "",
        "invoice_date": fields.invoice_date or "",
        "net_worth": fields.net_worth or "",
        "vat": fields.vat or "",
        "gross_worth": fields.gross_worth or "",
        "source_strategy": record.source_strategy,
        "validation_flags": record.validation_flags,
    }


def write_output_csv(records: list[ReconciledInvoice], path: Path) -> None:
    """Write reconciled records to ``path`` (creating parent directories)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        for record in records:
            writer.writerow(_row(record))
