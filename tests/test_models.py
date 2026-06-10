from invoice_extractor.models import InvoiceFields, PipelineResult


def test_invoice_fields_default_to_none():
    fields = InvoiceFields()
    assert fields.seller_name is None
    assert fields.gross_worth is None


def test_pipeline_result_holds_fields_and_metadata():
    result = PipelineResult(
        file_name="batch1-0331.jpg",
        pipeline="rules",
        fields=InvoiceFields(invoice_number="94138597", gross_worth="1 773,75"),
    )
    assert result.fields.invoice_number == "94138597"
    assert result.fields.gross_worth == "1 773,75"
    assert result.error is None
