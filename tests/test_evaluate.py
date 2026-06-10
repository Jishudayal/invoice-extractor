import csv

from invoice_extractor.evaluate import evaluate, load_gold, write_accuracy_report
from invoice_extractor.models import InvoiceFields, PipelineResult
from invoice_extractor.reconcile import reconcile_batch

# One gold invoice with all nine fields (money totals reconcile).
_GOLD = {
    "a.jpg": {
        "file_name": "a.jpg",
        "seller_name": "Ochoa-Scott",
        "seller_tax_id": "921-82-1053",
        "client_name": "Green LLC",
        "client_tax_id": "965-99-1263",
        "invoice_number": "94138597",
        "invoice_date": "02/05/2018",
        "net_worth": "1 612,50",
        "vat": "161,25",
        "gross_worth": "1 773,75",
    }
}


def _fields(**overrides) -> InvoiceFields:
    base = dict(
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
    base.update(overrides)
    return InvoiceFields(**base)


def test_perfect_pipeline_scores_100():
    results = [PipelineResult(file_name="a.jpg", pipeline="rules", fields=_fields())]
    report = evaluate(results, reconcile_batch(results), _GOLD)
    assert report.overall["rules"] == 100.0
    assert report.per_field["seller_name"]["rules"] == 100.0


def test_wrong_field_lowers_accuracy_and_normalisation_is_applied():
    results = [
        # rules perfect; llm has a wrong client_name and a $-prefixed gross (still
        # correct once normalised).
        PipelineResult(file_name="a.jpg", pipeline="rules", fields=_fields()),
        PipelineResult(
            file_name="a.jpg",
            pipeline="llm",
            fields=_fields(client_name="Wrong Co", gross_worth="$1773,75"),
        ),
    ]
    report = evaluate(results, reconcile_batch(results), _GOLD)

    assert report.sources == ["llm", "rules", "final"]
    assert report.overall["rules"] == 100.0
    assert report.per_field["client_name"]["llm"] == 0.0  # genuinely wrong
    assert report.per_field["gross_worth"]["llm"] == 100.0  # $ prefix normalised away
    # 1 of 9 fields wrong for llm.
    assert report.overall["llm"] == round(100.0 * 8 / 9, 1)


def test_load_and_write_round_trip(tmp_path):
    gold_path = tmp_path / "gold.csv"
    with gold_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(_GOLD["a.jpg"].keys()))
        writer.writeheader()
        writer.writerow(_GOLD["a.jpg"])

    loaded = load_gold(gold_path)
    assert loaded["a.jpg"]["invoice_number"] == "94138597"

    results = [PipelineResult(file_name="a.jpg", pipeline="rules", fields=_fields())]
    report = evaluate(results, reconcile_batch(results), loaded)
    out = tmp_path / "accuracy.csv"
    write_accuracy_report(report, out)

    with out.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.reader(handle))
    assert rows[0] == ["field", "rules", "final"]
    assert rows[-1][0] == "OVERALL"
