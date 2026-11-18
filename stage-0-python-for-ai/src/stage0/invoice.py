"""Exercise 3 - A Pydantic model for an invoice; validate good and bad sample data.

Why this is the most important Stage 0 exercise for AI work:
In Stage 2 you'll ask an LLM to "extract the invoice as JSON". The model will *usually*
comply - and sometimes return a string where a number should be, a missing field, or a
total that doesn't add up. Pydantic is the contract between the fuzzy model and your
strict code:
  - field types + constraints  -> catches shape errors
  - validators                 -> catches business-rule errors (total != sum of lines)
  - model_json_schema()        -> the SAME schema you hand to the LLM as "structured output"
Validation errors can even be fed back to the model to self-correct (Stage 2/4 pattern).
"""

import argparse
import json
import logging
from datetime import date
from decimal import Decimal
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    computed_field,
    field_validator,
    model_validator,
)

from stage0.log import setup_logging

log = logging.getLogger(__name__)

Money = Annotated[Decimal, Field(ge=0, max_digits=12, decimal_places=2)]


class Currency(StrEnum):
    USD = "USD"
    EUR = "EUR"
    GBP = "GBP"
    INR = "INR"
    SGD = "SGD"


class LineItem(BaseModel):
    description: str = Field(min_length=1, max_length=200)
    quantity: Annotated[Decimal, Field(gt=0)]
    unit_price: Money

    @computed_field  # included in .model_dump() / JSON output
    @property
    def amount(self) -> Decimal:
        return (self.quantity * self.unit_price).quantize(Decimal("0.01"))


class Invoice(BaseModel):
    # extra="forbid": unknown fields are an error, not silently ignored. Strict contracts
    # catch LLM hallucinated fields and API drift early.
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    invoice_number: str = Field(pattern=r"^INV-\d{4,}$", examples=["INV-20431"])
    supplier: str = Field(min_length=2)
    issue_date: date
    due_date: date
    currency: Currency
    line_items: list[LineItem] = Field(min_length=1)
    tax: Money = Decimal("0")
    total: Money

    @field_validator("currency", mode="before")
    @classmethod
    def upper_currency(cls, v: object) -> object:
        # 'usd' -> 'USD'. mode="before" runs on raw input, before type conversion.
        return v.upper() if isinstance(v, str) else v

    @model_validator(mode="after")
    def check_business_rules(self) -> Self:
        # Cross-field rules can only run once every field is parsed.
        if self.due_date < self.issue_date:
            raise ValueError("due_date cannot be before issue_date")
        expected = sum((li.amount for li in self.line_items), Decimal(0)) + self.tax
        if abs(expected - self.total) > Decimal("0.01"):
            raise ValueError(f"total {self.total} does not match line items + tax = {expected}")
        return self


def validate_invoice(data: dict) -> tuple[Invoice | None, list[str]]:
    """Return (invoice, []) on success or (None, [human-readable errors])."""
    try:
        return Invoice.model_validate(data), []
    except ValidationError as exc:
        errors = [
            f"{'.'.join(str(p) for p in err['loc']) or '<invoice>'}: {err['msg']}"
            for err in exc.errors()
        ]
        return None, errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate invoice JSON files.")
    parser.add_argument("files", nargs="*", type=Path,
                        default=[Path("data/invoices_good.json"), Path("data/invoices_bad.json")])
    parser.add_argument("--schema", action="store_true", help="Print the JSON Schema and exit")
    args = parser.parse_args(argv)
    setup_logging()

    if args.schema:
        print(json.dumps(Invoice.model_json_schema(), indent=2))
        return 0

    failures = 0
    for path in args.files:
        print(f"\n=== {path} ===")
        for i, data in enumerate(json.loads(path.read_text(encoding="utf-8"))):
            label = data.get("_label", f"#{i}")
            data = {k: v for k, v in data.items() if not k.startswith("_")}
            invoice, errors = validate_invoice(data)
            if invoice:
                print(f"  VALID   {label}: {invoice.invoice_number} {invoice.currency} "
                      f"{invoice.total}")
            else:
                failures += 1
                print(f"  INVALID {label}:")
                for e in errors:
                    print(f"            - {e}")
    print(f"\n{failures} invalid invoice(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
