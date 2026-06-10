from decimal import Decimal

from invoice_extractor.normalize import (
    find_amount_strings,
    find_amounts,
    normalize_text,
    parse_date,
    parse_money,
    parse_tax_id,
)


def test_parse_money_european_and_ocr_spacing():
    assert parse_money("$ 1 612,50") == Decimal("1612.50")
    assert parse_money("$1129,39") == Decimal("1129.39")  # OCR dropped the space after $
    assert parse_money("$5 587,91") == Decimal("5587.91")
    assert parse_money("84 944,82") == Decimal("84944.82")
    assert parse_money("161,25") == Decimal("161.25")
    assert parse_money("1 773,75") == Decimal("1773.75")


def test_parse_money_edge_formats():
    assert parse_money("1.612,50") == Decimal("1612.50")  # dot thousands separator
    assert parse_money("1,612.50") == Decimal("1612.50")  # US grouping (robustness)
    assert parse_money("1580") == Decimal("1580")
    assert parse_money(None) is None
    assert parse_money("") is None
    assert parse_money("n/a") is None


def test_parse_money_is_permissive_about_surrounding_text():
    # Intentional: the rules pipeline anchors the SUMMARY total before parsing,
    # so leading labels and symbols are stripped rather than rejected.
    assert parse_money("Total: $ 1 612,50") == Decimal("1612.50")


def test_parse_money_lone_comma_is_decimal_for_this_dataset():
    # These invoices group thousands with spaces, never commas, so a lone comma
    # is always the decimal separator.
    assert parse_money("1 234,00") == Decimal("1234.00")
    assert parse_money("395,00") == Decimal("395.00")


def test_summary_totals_reconcile():
    net = parse_money("1 612,50")
    vat = parse_money("161,25")
    gross = parse_money("1 773,75")
    assert net is not None and vat is not None and gross is not None
    assert net + vat == gross


def test_find_amount_strings_returns_raw_substrings():
    # The rules pipeline stores these raw, so the contract is worth pinning.
    assert find_amount_strings("$1 612,50 $ 161,25") == ["1 612,50", "161,25"]
    assert find_amount_strings("Total") == []
    assert find_amount_strings(None) == []


def test_find_amounts_reassembles_space_split_money():
    # OCR preserves the thousands space in the line text, so the amount survives.
    assert find_amounts("$1 612,50 $ 161,25") == [Decimal("1612.50"), Decimal("161.25")]
    assert find_amounts("$1773,75") == [Decimal("1773.75")]
    assert find_amounts("Total") == []
    assert find_amounts(None) == []


def test_parse_date_to_iso():
    assert parse_date("02/05/2018") == "2018-02-05"
    assert parse_date("10/04/2020") == "2020-10-04"
    assert parse_date("02 / 05 / 2018") == "2018-02-05"
    assert parse_date("02.05.2018") == "2018-02-05"
    assert parse_date("not a date") is None
    assert parse_date(None) is None


def test_parse_tax_id_canonical():
    assert parse_tax_id("921-82-1053") == "921-82-1053"
    assert parse_tax_id("921 82 1053") == "921-82-1053"
    assert parse_tax_id("965991263") == "965-99-1263"
    assert parse_tax_id("12-34") is None
    assert parse_tax_id(None) is None


def test_normalize_text():
    assert normalize_text("  Ochoa-Scott ") == "Ochoa-Scott"
    assert normalize_text("Green   LLC") == "Green LLC"
    assert normalize_text("") is None
    assert normalize_text(None) is None
