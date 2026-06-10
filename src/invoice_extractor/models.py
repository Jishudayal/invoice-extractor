"""Core data models shared across every extraction pipeline.

``InvoiceFields`` is the single source of truth for the nine required fields: it
defines the LLM structured-output schema, the shape every rules/Azure pipeline
returns, and the columns written to CSV. ``PipelineResult`` wraps those fields
with per-image metadata (which pipeline produced them, timing, cost, errors).
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class InvoiceFields(BaseModel):
    """The nine fields extracted from a single invoice.

    Values are stored exactly as extracted (raw strings); numeric normalisation
    of the money fields happens in a later step, so the spine stays simple and
    every pipeline reports what it actually saw. ``None`` means "not found".

    The field descriptions double as guidance for the LLM pipeline's structured
    output, which is why they encode domain rules (e.g. money comes from the
    SUMMARY total row, not the line items).
    """

    seller_name: str | None = Field(
        default=None, description="Seller / vendor company name."
    )
    seller_tax_id: str | None = Field(
        default=None, description="Seller Tax Id, format ###-##-####."
    )
    client_name: str | None = Field(
        default=None, description="Client / buyer company name."
    )
    client_tax_id: str | None = Field(
        default=None, description="Client Tax Id, format ###-##-####."
    )
    invoice_number: str | None = Field(
        default=None, description="Invoice number (digits after 'Invoice no:')."
    )
    invoice_date: str | None = Field(
        default=None, description="Date of issue, as printed (MM/DD/YYYY)."
    )
    net_worth: str | None = Field(
        default=None, description="Total net worth from the SUMMARY total row, as printed."
    )
    vat: str | None = Field(
        default=None, description="Total VAT amount from the SUMMARY total row, as printed."
    )
    gross_worth: str | None = Field(
        default=None, description="Total gross worth from the SUMMARY total row, as printed."
    )


class PipelineResult(BaseModel):
    """The outcome of running one pipeline over one invoice image.

    A pipeline must not raise for a single bad image: it captures the failure in
    ``error`` and still returns a result so the batch keeps going.
    """

    file_name: str
    pipeline: str
    fields: InvoiceFields = Field(default_factory=InvoiceFields)
    latency_ms: float | None = None
    cost_usd: float | None = None
    error: str | None = None


class ReconciledInvoice(BaseModel):
    """The final, reconciled fields for one invoice — a row of ``output.csv``.

    ``source_strategy`` records how the values were chosen (a single pipeline's
    name, ``agreement`` when pipelines concurred, or ``reconciled`` when policy
    resolved a disagreement); ``validation_flags`` summarises any problems.
    """

    file_name: str
    fields: InvoiceFields = Field(default_factory=InvoiceFields)
    source_strategy: str
    validation_flags: str = ""
