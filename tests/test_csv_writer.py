import csv
import shutil
from pathlib import Path

import pytest

from invoice_extractor.csv_writer import OUTPUT_COLUMNS, validation_flags, write_output_csv
from invoice_extractor.models import InvoiceFields, PipelineResult

_RECONCILING = InvoiceFields(
    seller_name="Ochoa-Scott",
    seller_tax_id="921-82-1053",
    client_name="Green LLC",
    client_tax_id="965-99-1263",
    invoice_number="94138597",
    invoice_date="02/05/2018",
    net_worth="1 612,50",
    vat="161,25",
    gross_worth="1 773,75",
)


def _result(fields: InvoiceFields, *, error: str | None = None) -> PipelineResult:
    return PipelineResult(file_name="batch1-0331.jpg", pipeline="rules", fields=fields, error=error)


def test_clean_result_has_no_flags():
    assert validation_flags(_result(_RECONCILING)) == ""


def test_missing_fields_are_flagged():
    fields = _RECONCILING.model_copy(update={"vat": None})
    flags = validation_flags(_result(fields))
    assert "missing=vat" in flags


def test_non_reconciling_totals_are_flagged():
    fields = _RECONCILING.model_copy(update={"gross_worth": "9 999,99"})
    assert validation_flags(_result(fields)) == "totals_mismatch"


def test_extraction_error_is_flagged():
    assert validation_flags(_result(InvoiceFields(), error="boom")) == "extraction_error"


def test_write_output_csv_header_and_rows(tmp_path):
    path = tmp_path / "output.csv"
    write_output_csv([_result(_RECONCILING)], path)

    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    assert list(rows[0].keys()) == OUTPUT_COLUMNS
    assert rows[0]["invoice_number"] == "94138597"
    assert rows[0]["gross_worth"] == "1 773,75"
    assert rows[0]["source_strategy"] == "rules"
    assert rows[0]["validation_flags"] == ""


def _locate(name: str) -> Path | None:
    for base in (Path("data/batch1_1"), Path("batch1_1")):
        candidate = base / name
        if candidate.exists():
            return candidate
    return None


@pytest.mark.skipif(shutil.which("tesseract") is None, reason="requires the tesseract binary")
def test_cli_writes_output_csv_end_to_end(tmp_path):
    src = _locate("batch1-0331.jpg")
    if src is None:
        pytest.skip("sample image not available")
    shutil.copy(src, tmp_path / "batch1-0331.jpg")

    from invoice_extractor.cli import main

    out_dir = tmp_path / "deliverables"
    exit_code = main(["--input-dir", str(tmp_path), "--output-dir", str(out_dir), "--offline"])

    assert exit_code == 0
    output_csv = out_dir / "output.csv"
    assert output_csv.exists()
    with output_csv.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 1
    assert rows[0]["invoice_number"] == "94138597"
