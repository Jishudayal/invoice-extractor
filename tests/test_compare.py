import csv

import pytest

from invoice_extractor.compare import (
    FIELD_NAMES,
    compare_results,
    summarize,
    write_comparison_report,
    write_summary,
)
from invoice_extractor.models import InvoiceFields, PipelineResult


def _result(file_name: str, pipeline: str, **fields) -> PipelineResult:
    return PipelineResult(file_name=file_name, pipeline=pipeline, fields=InvoiceFields(**fields))


def _row(rows, field):
    return next(r for r in rows if r.field == field)


def test_money_formatting_difference_still_matches():
    rows = compare_results(
        [
            _result("f.jpg", "llm", net_worth="1 773,75"),
            _result("f.jpg", "rules", net_worth="1773,75"),
        ]
    )
    net = _row(rows, "net_worth")
    assert net.match
    assert net.notes == "formatting_only"


def test_real_money_mismatch_is_high_severity():
    rows = compare_results(
        [
            _result("f.jpg", "llm", gross_worth="1773,75"),
            _result("f.jpg", "rules", gross_worth="9999,99"),
        ]
    )
    gross = _row(rows, "gross_worth")
    assert not gross.match
    assert gross.severity == "high"


def test_name_mismatch_is_medium_severity():
    rows = compare_results(
        [
            _result("f.jpg", "llm", seller_name="Ochoa-Scott"),
            _result("f.jpg", "rules", seller_name="Ochoa Scott Inc"),
        ]
    )
    seller = _row(rows, "seller_name")
    assert not seller.match
    assert seller.severity == "medium"


def test_missing_in_one_pipeline_is_noted():
    rows = compare_results(
        [
            _result("f.jpg", "llm"),  # vat is None
            _result("f.jpg", "rules", vat="161,25"),
        ]
    )
    vat = _row(rows, "vat")
    assert not vat.match
    assert vat.notes == "llm_missing"


def test_tax_id_punctuation_difference_still_matches():
    rows = compare_results(
        [
            _result("f.jpg", "llm", seller_tax_id="921 82 1053"),
            _result("f.jpg", "rules", seller_tax_id="921-82-1053"),
        ]
    )
    assert _row(rows, "seller_tax_id").match


def test_both_missing_is_not_a_match():
    # A field neither pipeline found is flagged, not counted as agreement.
    rows = compare_results(
        [
            _result("f.jpg", "llm", invoice_number="1"),
            _result("f.jpg", "rules", invoice_number="1"),
        ]
    )
    vat = _row(rows, "vat")  # absent from both
    assert not vat.match
    assert vat.notes == "both_missing"
    assert vat.severity == "high"


def test_duplicate_file_and_pipeline_raises():
    with pytest.raises(ValueError, match="duplicate result"):
        compare_results([_result("f.jpg", "llm"), _result("f.jpg", "llm")])


def test_summary_match_rate_math():
    rows = compare_results(
        [
            _result("f1.jpg", "llm", gross_worth="100,00"),
            _result("f1.jpg", "rules", gross_worth="100,00"),
            _result("f2.jpg", "llm", gross_worth="100,00"),
            _result("f2.jpg", "rules", gross_worth="200,00"),
        ]
    )
    gross = next(s for s in summarize(rows) if s.field == "gross_worth")
    assert (gross.total, gross.matches, gross.mismatches, gross.match_rate) == (2, 1, 1, 50.0)


def test_writers_produce_expected_headers(tmp_path):
    rows = compare_results(
        [
            _result("f.jpg", "llm", invoice_number="123"),
            _result("f.jpg", "rules", invoice_number="123"),
        ]
    )
    comparison_path = tmp_path / "comparison_report.csv"
    summary_path = tmp_path / "summary.csv"
    write_comparison_report(rows, comparison_path)
    write_summary(summarize(rows), summary_path)

    with comparison_path.open(newline="", encoding="utf-8") as handle:
        header = next(csv.reader(handle))
    assert header == [
        "file_name",
        "field",
        "llm_value",
        "rules_value",
        "llm_normalized",
        "rules_normalized",
        "match",
        "severity",
        "notes",
    ]

    with summary_path.open(newline="", encoding="utf-8") as handle:
        summary_rows = list(csv.DictReader(handle))
    assert {r["field"] for r in summary_rows} == set(FIELD_NAMES)
