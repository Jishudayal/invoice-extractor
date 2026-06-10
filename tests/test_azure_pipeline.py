"""Pipeline C wiring + field mapping, tested with fakes (no Azure, no creds)."""

from pathlib import Path

import pytest

from invoice_extractor.config import Settings
from invoice_extractor.pipelines.azure_pipeline import (
    AzureInvoicePipeline,
    make_azure_analyze,
    to_invoice_fields,
)


class _Field:
    def __init__(self, content):
        self.content = content


class _Document:
    def __init__(self, fields):
        self.fields = fields


def test_to_invoice_fields_maps_azure_names():
    document = _Document(
        {
            "VendorName": _Field("Ochoa-Scott"),
            "VendorTaxId": _Field("921-82-1053"),
            "CustomerName": _Field("Green LLC"),
            "InvoiceId": _Field("94138597"),
            "InvoiceTotal": _Field("$1 773,75"),
            # CustomerTaxId / InvoiceDate / SubTotal / TotalTax absent -> None
        }
    )
    fields = to_invoice_fields(document)
    assert fields.seller_name == "Ochoa-Scott"
    assert fields.seller_tax_id == "921-82-1053"
    assert fields.client_name == "Green LLC"
    assert fields.invoice_number == "94138597"
    assert fields.gross_worth == "$1 773,75"
    assert fields.client_tax_id is None
    assert fields.invoice_date is None


def test_pipeline_maps_and_records_cost():
    document = _Document({"InvoiceId": _Field("94138597")})
    pipeline = AzureInvoicePipeline(lambda path: document, cost_per_doc=0.01)
    result = pipeline.extract(Path("x/batch1-0331.jpg"))
    assert result.pipeline == "azure"
    assert result.error is None
    assert result.fields.invoice_number == "94138597"
    assert result.cost_usd == 0.01


def test_pipeline_never_raises_on_analyze_error():
    def boom(_path):
        raise RuntimeError("DI down")

    result = AzureInvoicePipeline(boom).extract(Path("x/batch1-0331.jpg"))
    assert result.error == "DI down"
    assert result.fields.invoice_number is None


def test_make_azure_analyze_requires_credentials():
    with pytest.raises(RuntimeError, match="Azure Document Intelligence is not configured"):
        make_azure_analyze(Settings(_env_file=None))
