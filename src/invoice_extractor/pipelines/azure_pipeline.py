"""Pipeline C — Azure Document Intelligence ``prebuilt-invoice`` (optional).

A genuinely different paradigm from the OCR-based pipelines: a layout-aware
cloud model that returns invoice fields directly. Off by default; runs only when
Azure DI is configured and not ``--offline``. Like every pipeline it never raises
and records latency/cost.

``azure-ai-documentintelligence`` is imported lazily (only when the analyzer is
built), so the keyless path never needs the dependency.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from invoice_extractor import pipelines
from invoice_extractor.config import Settings
from invoice_extractor.models import InvoiceFields, PipelineResult

# Our field name -> Azure prebuilt-invoice field name.
FIELD_MAP = {
    "seller_name": "VendorName",
    "seller_tax_id": "VendorTaxId",
    "client_name": "CustomerName",
    "client_tax_id": "CustomerTaxId",
    "invoice_number": "InvoiceId",
    "invoice_date": "InvoiceDate",
    "net_worth": "SubTotal",
    "vat": "TotalTax",
    "gross_worth": "InvoiceTotal",
}


def _field_content(fields: Any, azure_name: str) -> str | None:
    """The raw recognised text for one Azure field, or None if absent."""
    field = fields.get(azure_name) if fields else None
    if field is None:
        return None
    return getattr(field, "content", None) or None


def to_invoice_fields(document: Any) -> InvoiceFields:
    """Map an Azure analysed invoice document to our :class:`InvoiceFields`.

    Uses each field's recognised ``content`` (raw as-printed text); the comparison
    layer normalises it like any other pipeline's output.
    """
    fields = getattr(document, "fields", None) or {}
    return InvoiceFields(
        **{ours: _field_content(fields, azure) for ours, azure in FIELD_MAP.items()}
    )


class AzureInvoicePipeline:
    name = "azure"

    def __init__(self, analyze: Callable[[Path], Any], *, cost_per_doc: float = 0.0) -> None:
        self._analyze = analyze
        self._cost_per_doc = cost_per_doc

    def extract(self, image_path: Path) -> PipelineResult:
        start = time.monotonic()
        try:
            document = self._analyze(image_path)
            fields = to_invoice_fields(document)
            latency_ms = (time.monotonic() - start) * 1000.0
            return PipelineResult(
                file_name=image_path.name,
                pipeline=self.name,
                fields=fields,
                latency_ms=round(latency_ms, 1),
                cost_usd=round(self._cost_per_doc, 6),
            )
        except Exception as exc:
            latency_ms = (time.monotonic() - start) * 1000.0
            return PipelineResult(
                file_name=image_path.name,
                pipeline=self.name,
                latency_ms=round(latency_ms, 1),
                error=str(exc),
            )


def make_azure_analyze(settings: Settings) -> Callable[[Path], Any]:
    """Build the Azure DI analyze function, or raise if DI is not configured."""
    if not settings.azure_di_enabled:
        raise RuntimeError("Azure Document Intelligence is not configured; set AZURE_DI_* in .env.")

    from azure.ai.documentintelligence import DocumentIntelligenceClient  # lazy
    from azure.core.credentials import AzureKeyCredential

    client = DocumentIntelligenceClient(
        endpoint=settings.azure_di_endpoint,
        credential=AzureKeyCredential(settings.azure_di_key),
    )

    def analyze(image_path: Path) -> Any:
        poller = client.begin_analyze_document(
            "prebuilt-invoice",
            image_path.read_bytes(),
            content_type="application/octet-stream",
        )
        documents = poller.result().documents or []
        if not documents:
            raise RuntimeError("Azure DI returned no invoice documents")
        return documents[0]

    return analyze


def _build(settings: Settings) -> AzureInvoicePipeline:
    return AzureInvoicePipeline(
        make_azure_analyze(settings),
        cost_per_doc=settings.azure_di_cost_per_doc,
    )


pipelines.register("azure", _build)
