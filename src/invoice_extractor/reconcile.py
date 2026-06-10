"""Reconciliation: turn each invoice's pipeline results into one final record.

Policy (per the assessment design):

- **Agree** -> use the agreed value.
- **Disagree on money** -> prefer the pipeline whose SUMMARY totals reconcile
  (``net + vat == gross``); tie or neither -> prefer rules, and flag.
- **Disagree on any other field** -> prefer the rules pipeline (deterministic on
  this fixed template).
- A failed pipeline is dropped from the decision and noted (``<name>_error``).

The result is one :class:`ReconciledInvoice` per file — the rows of
``output.csv`` — with ``source_strategy`` and ``validation_flags`` set.
"""

from __future__ import annotations

from invoice_extractor.compare import FIELD_NAMES, MONEY_FIELDS, normalize_field
from invoice_extractor.models import InvoiceFields, PipelineResult, ReconciledInvoice
from invoice_extractor.normalize import parse_money

# Tie-break order for non-money fields and for money when both pipelines reconcile.
PIPELINE_PREFERENCE = ("rules", "llm")

NON_MONEY_FIELDS = [field for field in FIELD_NAMES if field not in MONEY_FIELDS]


def _money_reconciles(fields: InvoiceFields) -> bool:
    net = parse_money(fields.net_worth)
    vat = parse_money(fields.vat)
    gross = parse_money(fields.gross_worth)
    return None not in (net, vat, gross) and net + vat == gross


def _base_flags(fields: InvoiceFields) -> list[str]:
    """Sanity flags on the final values: missing fields and non-reconciling totals."""
    flags: list[str] = []
    missing = [name for name, value in fields.model_dump().items() if not value]
    if missing:
        flags.append("missing=" + ",".join(missing))
    net = parse_money(fields.net_worth)
    vat = parse_money(fields.vat)
    gross = parse_money(fields.gross_worth)
    if None not in (net, vat, gross):
        if net + vat != gross:
            flags.append("totals_mismatch")
    elif all((fields.net_worth, fields.vat, fields.gross_worth)):
        flags.append("totals_unparsed")
    return flags


def _ordered(names: list[str]) -> list[str]:
    preferred = [name for name in PIPELINE_PREFERENCE if name in names]
    return preferred + [name for name in names if name not in PIPELINE_PREFERENCE]


def reconcile_file(file_name: str, by_pipeline: dict[str, PipelineResult]) -> ReconciledInvoice:
    flags = [f"{name}_error" for name, result in sorted(by_pipeline.items()) if result.error]
    working = {name: result.fields for name, result in by_pipeline.items() if not result.error}
    names = _ordered(list(working))

    # No working pipeline, or exactly one: take it as-is.
    if len(names) <= 1:
        only = names[0] if names else None
        fields = working[only] if only else InvoiceFields()
        flags += _base_flags(fields)
        return ReconciledInvoice(
            file_name=file_name,
            fields=fields,
            source_strategy=only or "none",
            validation_flags="; ".join(flags),
        )

    final: dict[str, str | None] = {}
    disagreements: list[str] = []

    # Non-money fields: prefer the rules value, falling back to the next pipeline.
    for field in NON_MONEY_FIELDS:
        present = [(name, getattr(working[name], field)) for name in names]
        present = [(name, value) for name, value in present if value is not None]
        if len({normalize_field(field, value) for _, value in present}) > 1:
            disagreements.append(field)
        final[field] = present[0][1] if present else None

    # Money block: keep net/vat/gross together from one pipeline.
    money_note: str | None = None
    money_norms = {
        name: tuple(normalize_field(f, getattr(working[name], f)) for f in MONEY_FIELDS)
        for name in names
    }
    if len(set(money_norms.values())) == 1:
        chosen = names[0]
    else:
        disagreements.append("money")
        reconciling = [name for name in names if _money_reconciles(working[name])]
        if len(reconciling) == 1:
            chosen = reconciling[0]
            money_note = f"money_from={chosen}"
        elif len(reconciling) > 1:
            chosen = _ordered(reconciling)[0]
            money_note = f"money_from={chosen}"
        else:
            chosen = names[0]
            money_note = "totals_unresolved"
    for field in MONEY_FIELDS:
        final[field] = getattr(working[chosen], field)

    fields = InvoiceFields(**final)
    if disagreements:
        flags.append("disagree=" + ",".join(sorted(set(disagreements))))
    if money_note:
        flags.append(money_note)
    flags += _base_flags(fields)

    return ReconciledInvoice(
        file_name=file_name,
        fields=fields,
        source_strategy="reconciled" if disagreements else "agreement",
        validation_flags="; ".join(flags),
    )


def reconcile_batch(results: list[PipelineResult]) -> list[ReconciledInvoice]:
    """Reconcile a batch of results into one record per file (sorted by file name)."""
    by_file: dict[str, dict[str, PipelineResult]] = {}
    for result in results:
        per_pipeline = by_file.setdefault(result.file_name, {})
        if result.pipeline in per_pipeline:
            raise ValueError(
                f"duplicate result for {result.file_name!r} from pipeline {result.pipeline!r}"
            )
        per_pipeline[result.pipeline] = result
    return [reconcile_file(file_name, by_file[file_name]) for file_name in sorted(by_file)]
