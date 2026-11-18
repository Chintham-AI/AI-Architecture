"""Exercise 1 - Read a CSV of expenses, total them by category and save the result as JSON.

Two implementations on purpose:
- summarise_rows(): plain Python (csv module, dict, loops). Learn the fundamentals.
- summarise_with_pandas(): the same result with pandas. What you'd use for big data.
The tests check that both give identical answers.

Architect notes:
- Money uses Decimal, never float: 0.1 + 0.2 != 0.3 in float. Token-cost maths in later
  stages has the same problem.
- Bad rows are *reported*, not silently dropped and not fatal. Real-world data (and LLM
  output!) is messy; decide explicitly what to do with each failure.
"""

import argparse
import csv
import json
import logging
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from pathlib import Path

import pandas as pd

from stage0.log import setup_logging

log = logging.getLogger(__name__)

CENT = Decimal("0.01")


@dataclass
class Summary:
    """Result of summarising expenses. A dataclass groups related data with type hints."""

    totals: dict[str, str]  # category -> amount as string (JSON has no Decimal type)
    grand_total: str
    row_count: int
    rejected: list[dict] = field(default_factory=list)

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2)


def normalise_category(raw: str | None) -> str:
    """'  travel ' -> 'Travel'. Empty -> raise ValueError so the caller can reject the row."""
    cleaned = (raw or "").strip()
    if not cleaned:
        raise ValueError("missing category")
    return cleaned.title()


def parse_amount(raw: str | None) -> Decimal:
    try:
        amount = Decimal((raw or "").strip())
    except InvalidOperation as exc:
        # `from exc` keeps the original error attached (exception chaining) for debugging.
        raise ValueError(f"invalid amount {raw!r}") from exc
    if amount < 0:
        raise ValueError(f"negative amount {amount}")
    return amount


def summarise_rows(rows: Iterable[dict[str, str]]) -> Summary:
    """Total amounts by category using only the standard library."""
    totals: dict[str, Decimal] = defaultdict(Decimal)
    rejected: list[dict] = []
    count = 0

    # start=2 because line 1 of the CSV is the header
    for line_no, row in enumerate(rows, start=2):
        try:
            category = normalise_category(row.get("category"))
            amount = parse_amount(row.get("amount"))
        except ValueError as exc:
            log.warning("Skipping line %d: %s", line_no, exc)
            rejected.append({"line": line_no, "reason": str(exc), "row": row})
            continue
        totals[category] += amount
        count += 1

    grand = sum(totals.values(), Decimal(0))
    return Summary(
        totals={k: str(v.quantize(CENT, ROUND_HALF_UP)) for k, v in sorted(totals.items())},
        grand_total=str(grand.quantize(CENT, ROUND_HALF_UP)),
        row_count=count,
        rejected=rejected,
    )


def summarise_csv(path: Path) -> Summary:
    # newline="" is what the csv docs require; utf-8-sig also strips an Excel BOM if present.
    with path.open(newline="", encoding="utf-8-sig") as f:
        return summarise_rows(csv.DictReader(f))


def summarise_with_pandas(path: Path) -> dict[str, str]:
    """Same totals with pandas: vectorised, concise, scales to millions of rows."""
    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    df["category"] = df["category"].str.strip().str.title()
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce")  # 'abc' -> NaN
    valid = df[(df["category"] != "") & df["amount"].notna() & (df["amount"] >= 0)]
    # Convert via str to avoid float noise, then round like the Decimal version.
    grouped = valid.groupby("category")["amount"].apply(
        lambda s: sum((Decimal(str(x)) for x in s), Decimal(0))
    )
    return {k: str(v.quantize(CENT, ROUND_HALF_UP)) for k, v in sorted(grouped.items())}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Total expenses by category.")
    parser.add_argument("csv_path", type=Path)
    parser.add_argument("-o", "--output", type=Path, help="Write JSON here (default: stdout)")
    args = parser.parse_args(argv)
    setup_logging()

    if not args.csv_path.exists():
        log.error("File not found: %s", args.csv_path)
        return 1

    summary = summarise_csv(args.csv_path)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)  # don't crash on a new folder
        args.output.write_text(summary.to_json(), encoding="utf-8")
        log.info("Wrote %s (%d rows, %d rejected)", args.output, summary.row_count,
                 len(summary.rejected))
    else:
        print(summary.to_json())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
