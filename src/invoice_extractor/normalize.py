"""Pure normalisation helpers shared by every pipeline and the comparison layer.

These turn raw, as-printed field values into canonical forms so two pipelines can
be compared on *meaning* rather than incidental formatting:

- money  -> ``Decimal``           (European spacing/commas, plus OCR ``$``-spacing)
- date   -> ISO ``YYYY-MM-DD``    (source invoices print ``MM/DD/YYYY``)
- tax id -> canonical ``###-##-####``
- text   -> trimmed, single-spaced

``find_amounts`` locates every money amount in a block of OCR text (reassembling
groups the OCR split on the thousands space).

Every function is total and side-effect free: empty or unparseable input returns
``None`` (or ``[]``) rather than raising, so one bad field never breaks a batch.
"""

from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal, InvalidOperation


def normalize_text(value: str | None) -> str | None:
    """Trim and collapse internal whitespace; empty becomes ``None``."""
    if value is None:
        return None
    collapsed = " ".join(value.split())
    return collapsed or None


def parse_money(value: str | None) -> Decimal | None:
    """Parse an as-printed amount into a :class:`Decimal`.

    Handles this dataset's European formatting (space thousands separators, comma
    decimal) and OCR artefacts such as a missing space after ``$`` — e.g.
    ``"$ 1 612,50"``, ``"$1129,39"`` and ``"5 587,91"`` all parse correctly. Also
    tolerates the inverse US grouping (``"1,612.50"``) for robustness.
    """
    if value is None:
        return None
    # Keep only digits, separators and a leading sign. This drops the currency
    # symbol, the space thousands separators, and any stray OCR characters.
    text = re.sub(r"[^\d.,+-]", "", value)
    if not text:
        return None

    sign = "-" if text[0] == "-" else ""
    text = text.lstrip("+-")

    if "," in text and "." in text:
        # The rightmost separator is the decimal point; the other groups thousands.
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif "," in text:
        # These invoices group thousands with spaces, so a lone comma is always
        # the decimal separator (a lone dot is already a decimal point — left as-is).
        text = text.replace(",", ".")

    try:
        return Decimal(sign + text)
    except InvalidOperation:
        return None


# A money amount: a leading digit, then digit/space groups (space = thousands
# separator, regular or non-breaking), then a comma/dot decimal with two digits.
_AMOUNT_RE = re.compile(r"\d[\d  ]*[.,]\d{2}")


def find_amount_strings(text: str | None) -> list[str]:
    """Raw money substrings found in OCR text, in reading order.

    OCR often splits a space-grouped amount across word tokens
    (``"1 612,50"`` -> ``["1", "612,50"]``). Matching at the *text* level — where
    the spaces survive — reassembles each amount. Returns the matched substrings
    as-is (callers that want numbers use :func:`find_amounts`).
    """
    if not text:
        return []
    return _AMOUNT_RE.findall(text)


def find_amounts(text: str | None) -> list[Decimal]:
    """Find and parse every money amount in a block of OCR text, in reading order.

    Selecting *which* amounts are the SUMMARY totals is the pipelines' job; this
    only locates and parses them.
    """
    amounts: list[Decimal] = []
    for token in find_amount_strings(text):
        parsed = parse_money(token)
        if parsed is not None:
            amounts.append(parsed)
    return amounts


def parse_date(value: str | None) -> str | None:
    """Parse a printed ``MM/DD/YYYY`` date into ISO ``YYYY-MM-DD``.

    Separators and surrounding spaces are normalised first, so ``"02/05/2018"``,
    ``"02 / 05 / 2018"`` and ``"02.05.2018"`` all parse.
    """
    if value is None:
        return None
    cleaned = re.sub(r"\s*[/.\-]\s*", "/", value.strip())
    for fmt in ("%m/%d/%Y", "%m/%d/%y"):
        try:
            return datetime.strptime(cleaned, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def parse_tax_id(value: str | None) -> str | None:
    """Normalise a tax id to canonical ``###-##-####`` (exactly nine digits)."""
    if value is None:
        return None
    digits = re.sub(r"\D", "", value)
    if len(digits) != 9:
        return None
    return f"{digits[:3]}-{digits[3:5]}-{digits[5:]}"
