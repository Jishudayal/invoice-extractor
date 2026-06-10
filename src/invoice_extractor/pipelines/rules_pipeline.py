"""Pipeline B — deterministic rules over OCR output.

Extracts fields by exploiting the fixed invoice template: a header regex for the
single invoice number and date, and **word-box geometry** for the two-column
Seller/Client block (left column = seller, right column = client). Using
coordinates rather than text order is what makes the Seller/Client split robust,
since OCR emits the columns in an unreliable order.

Values are returned exactly as read (raw); normalisation happens in the
comparison layer.
"""

from __future__ import annotations

import re
from pathlib import Path

from invoice_extractor import pipelines
from invoice_extractor.models import InvoiceFields, PipelineResult
from invoice_extractor.normalize import find_amount_strings, normalize_text
from invoice_extractor.ocr import OcrResult, OcrWord, run_ocr

# x-coordinate dividing the left (seller) and right (client) columns on this
# 1654px-wide template. Seller content sits well left of it, client well right.
COLUMN_X = 600

# Words within this many pixels of each other vertically belong to one row.
_ROW_TOLERANCE = 14

_INVOICE_NO_RE = re.compile(r"invoice\s*no[:.]?\s*([0-9]{4,})", re.IGNORECASE)
_DATE_RE = re.compile(r"\d{1,2}/\d{1,2}/\d{4}")
_TAX_ID_RE = re.compile(r"\d{3}-\d{2}-\d{4}")


def _cluster_rows(words: list[OcrWord]) -> list[list[OcrWord]]:
    """Group words into visual rows (sorted top-to-bottom, each sorted left-to-right)."""
    rows: list[list[OcrWord]] = []
    for word in sorted(words, key=lambda w: (w.top, w.left)):
        if rows and word.top - rows[-1][0].top <= _ROW_TOLERANCE:
            rows[-1].append(word)
        else:
            rows.append([word])
    return [sorted(row, key=lambda w: w.left) for row in rows]


def _join_column(row: list[OcrWord], *, left: bool) -> str | None:
    """Join the words of a row that fall in the left (or right) column."""
    parts = [w.text for w in row if (w.left < COLUMN_X) == left]
    return normalize_text(" ".join(parts))


def _extract_party_names(rows: list[list[OcrWord]]) -> tuple[str | None, str | None]:
    """Seller and client names: the row immediately below the 'Seller:'/'Client:' row."""
    for index, row in enumerate(rows[:-1]):
        if any(w.text.lower().startswith("seller") for w in row):
            name_row = rows[index + 1]
            return _join_column(name_row, left=True), _join_column(name_row, left=False)
    return None, None


def _extract_tax_ids(words: list[OcrWord]) -> tuple[str | None, str | None]:
    """Seller and client tax ids, disambiguated by column (first match wins)."""
    seller = client = None
    for word in words:
        if not _TAX_ID_RE.fullmatch(word.text):
            continue
        if word.left < COLUMN_X:
            seller = seller or word.text
        else:
            client = client or word.text
    return seller, client


def _extract_summary_totals(
    rows: list[list[OcrWord]],
) -> tuple[str | None, str | None, str | None]:
    """Net / VAT / Gross from the bold SUMMARY 'Total' row.

    Anchors on the ``Total`` token (which distinguishes the totals row from the
    per-rate row above it), then reads the three amounts on that row left-to-right
    -> (net worth, VAT, gross worth). Returns raw substrings; the caller stores
    them as-read.
    """
    for row in rows:
        if not any(w.text.strip().lower() == "total" for w in row):
            continue
        row_text = " ".join(w.text for w in row)
        amounts = find_amount_strings(row_text)
        if len(amounts) == 3:
            return amounts[0], amounts[1], amounts[2]
    return None, None, None


def extract_fields(ocr: OcrResult) -> InvoiceFields:
    """Apply the full rule set to one OCR result."""
    rows = _cluster_rows(ocr.words)
    seller_name, client_name = _extract_party_names(rows)
    seller_tax_id, client_tax_id = _extract_tax_ids(ocr.words)
    net_worth, vat, gross_worth = _extract_summary_totals(rows)

    invoice_no = _INVOICE_NO_RE.search(ocr.text)
    date = _DATE_RE.search(ocr.text)

    return InvoiceFields(
        seller_name=seller_name,
        seller_tax_id=seller_tax_id,
        client_name=client_name,
        client_tax_id=client_tax_id,
        invoice_number=invoice_no.group(1) if invoice_no else None,
        invoice_date=date.group(0) if date else None,
        net_worth=net_worth,
        vat=vat,
        gross_worth=gross_worth,
    )


class RulesPipeline:
    """OCR an image, then extract fields with deterministic rules."""

    name = "rules"

    def __init__(self, tesseract_cmd: str | None = None) -> None:
        self.tesseract_cmd = tesseract_cmd

    def extract(self, image_path: Path) -> PipelineResult:
        try:
            ocr = run_ocr(image_path, tesseract_cmd=self.tesseract_cmd)
            fields = extract_fields(ocr)
            return PipelineResult(file_name=image_path.name, pipeline=self.name, fields=fields)
        except Exception as exc:
            return PipelineResult(file_name=image_path.name, pipeline=self.name, error=str(exc))


pipelines.register("rules", lambda settings: RulesPipeline(settings.tesseract_cmd))
