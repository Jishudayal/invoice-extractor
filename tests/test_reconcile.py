from invoice_extractor.models import InvoiceFields, PipelineResult
from invoice_extractor.reconcile import reconcile_batch, reconcile_file


def _result(pipeline, *, error=None, **fields):
    return PipelineResult(
        file_name="f.jpg",
        pipeline=pipeline,
        fields=InvoiceFields(**fields),
        error=error,
    )


# Money values that reconcile (net + vat == gross).
_NET, _VAT, _GROSS = "1 612,50", "161,25", "1 773,75"


def _by_pipeline(*results):
    return {r.pipeline: r for r in results}


def test_single_pipeline_passes_through():
    record = reconcile_file("f.jpg", _by_pipeline(_result("rules", invoice_number="123")))
    assert record.source_strategy == "rules"
    assert record.fields.invoice_number == "123"


def test_full_agreement_marks_source_agreement():
    common = dict(invoice_number="123", net_worth=_NET, vat=_VAT, gross_worth=_GROSS)
    record = reconcile_file(
        "f.jpg", _by_pipeline(_result("rules", **common), _result("llm", **common))
    )
    assert record.source_strategy == "agreement"
    assert "disagree" not in record.validation_flags


def test_non_money_disagreement_prefers_rules_and_flags():
    record = reconcile_file(
        "f.jpg",
        _by_pipeline(
            _result("rules", seller_name="Ochoa-Scott"),
            _result("llm", seller_name="Ochoa Scott Inc"),
        ),
    )
    assert record.fields.seller_name == "Ochoa-Scott"  # rules wins
    assert record.source_strategy == "reconciled"
    assert "disagree=seller_name" in record.validation_flags


def test_money_disagreement_prefers_the_reconciling_pipeline():
    # rules totals reconcile; llm's do not -> money taken from rules.
    record = reconcile_file(
        "f.jpg",
        _by_pipeline(
            _result("rules", net_worth=_NET, vat=_VAT, gross_worth=_GROSS),
            _result("llm", net_worth="1 612,50", vat="161,25", gross_worth="9 999,99"),
        ),
    )
    assert record.fields.gross_worth == _GROSS
    assert "money_from=rules" in record.validation_flags


def test_money_unresolved_when_neither_reconciles():
    record = reconcile_file(
        "f.jpg",
        _by_pipeline(
            _result("rules", net_worth="100,00", vat="10,00", gross_worth="999,99"),
            _result("llm", net_worth="200,00", vat="20,00", gross_worth="888,88"),
        ),
    )
    assert "totals_unresolved" in record.validation_flags


def test_errored_pipeline_is_dropped_and_noted():
    record = reconcile_file(
        "f.jpg",
        _by_pipeline(
            _result("rules", invoice_number="123"),
            _result("llm", error="boom"),
        ),
    )
    # Falls back to the single working pipeline; the failure is recorded.
    assert record.source_strategy == "rules"
    assert "llm_error" in record.validation_flags
    assert record.fields.invoice_number == "123"


def test_reconcile_batch_one_record_per_file_sorted():
    def res(file_name, number):
        return PipelineResult(
            file_name=file_name, pipeline="rules", fields=InvoiceFields(invoice_number=number)
        )

    records = reconcile_batch([res("b.jpg", "2"), res("a.jpg", "1")])
    assert [r.file_name for r in records] == ["a.jpg", "b.jpg"]
