import json

import pytest

from stage0.invoice import Invoice, validate_invoice


def load(path):
    return [{k: v for k, v in d.items() if not k.startswith("_")}
            for d in json.loads(path.read_text(encoding="utf-8"))]


def test_good_invoices_are_valid(data_dir):
    for data in load(data_dir / "invoices_good.json"):
        invoice, errors = validate_invoice(data)
        assert errors == [] and invoice is not None


def test_normalisation(data_dir):
    invoice, _ = validate_invoice(load(data_dir / "invoices_good.json")[1])
    assert invoice.invoice_number == "INV-0099"  # whitespace stripped
    assert invoice.currency == "INR"  # upper-cased


@pytest.mark.parametrize(
    ("index", "expected_fragment"),
    [
        (0, "does not match line items"),
        (1, "invoice_number: String should match pattern"),
        (1, "issue_date: Input should be a valid date"),
        (1, "currency: Input should be"),
        (1, "line_items.0.quantity: Input should be greater than 0"),
        (2, "line_items: List should have at least 1 item"),
        (2, "confidence: Extra inputs are not permitted"),
        (3, "due_date cannot be before issue_date"),
    ],
)
def test_bad_invoices_report_clear_errors(data_dir, index, expected_fragment):
    invoice, errors = validate_invoice(load(data_dir / "invoices_bad.json")[index])
    assert invoice is None
    assert any(expected_fragment in e for e in errors), errors


def test_json_schema_is_ready_for_llm_structured_output():
    schema = Invoice.model_json_schema()
    assert schema["additionalProperties"] is False
    assert {"invoice_number", "line_items", "total"} <= set(schema["required"])
