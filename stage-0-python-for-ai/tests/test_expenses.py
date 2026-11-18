import json
from decimal import Decimal

import pytest

from stage0.expenses import (
    main,
    normalise_category,
    parse_amount,
    summarise_csv,
    summarise_rows,
    summarise_with_pandas,
)


def test_totals_by_category(data_dir):
    s = summarise_csv(data_dir / "expenses.csv")
    assert s.totals == {
        "Meals": "128.00",
        "Software": "324.35",
        "Training": "213.99",
        "Travel": "1034.90",  # 'travel ' row merged into 'Travel'
    }
    assert s.grand_total == "1701.24"
    assert s.row_count == 10


def test_bad_rows_are_reported_not_fatal(data_dir):
    s = summarise_csv(data_dir / "expenses.csv")
    reasons = {r["line"]: r["reason"] for r in s.rejected}
    assert reasons == {10: "invalid amount 'abc'", 11: "missing category"}


def test_pandas_matches_plain_python(data_dir):
    assert summarise_with_pandas(data_dir / "expenses.csv") == summarise_csv(
        data_dir / "expenses.csv"
    ).totals


def test_decimal_avoids_float_errors():
    rows = [{"category": "x", "amount": "0.1"}, {"category": "x", "amount": "0.2"}]
    assert summarise_rows(rows).totals == {"X": "0.30"}  # float would give 0.30000000000000004


@pytest.mark.parametrize("raw", ["", "abc", "-1", None])
def test_parse_amount_rejects_bad_values(raw):
    with pytest.raises(ValueError):
        parse_amount(raw)


def test_parse_amount_accepts_whitespace():
    assert parse_amount(" 12.30 ") == Decimal("12.30")


def test_normalise_category():
    assert normalise_category("  travel ") == "Travel"
    with pytest.raises(ValueError):
        normalise_category("   ")


def test_cli_writes_json(data_dir, tmp_path):
    out = tmp_path / "new_folder" / "summary.json"  # regression: folder doesn't exist yet
    assert main([str(data_dir / "expenses.csv"), "-o", str(out)]) == 0
    assert json.loads(out.read_text())["grand_total"] == "1701.24"


def test_cli_missing_file_returns_error(tmp_path):
    assert main([str(tmp_path / "nope.csv")]) == 1
