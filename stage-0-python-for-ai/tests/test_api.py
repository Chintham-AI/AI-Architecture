import httpx
import pytest
from fastapi.testclient import TestClient

from stage0.api import app, get_fx_client

client = TestClient(app)

GOOD_INVOICE = {
    "invoice_number": "INV-1234",
    "supplier": "Acme",
    "issue_date": "2026-11-01",
    "due_date": "2026-11-30",
    "currency": "USD",
    "line_items": [{"description": "Tokens", "quantity": 2, "unit_price": "5.00"}],
    "total": "10.00",
}


@pytest.fixture
def fake_fx():
    """Override the FX dependency with a mock transport; restore afterwards."""

    def install(handler):
        def _client():
            with httpx.Client(transport=httpx.MockTransport(handler),
                              base_url="https://fx.test") as c:
                yield c

        app.dependency_overrides[get_fx_client] = _client

    yield install
    app.dependency_overrides.clear()


def test_health():
    r = client.get("/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"


def test_expense_summary_upload(data_dir):
    with (data_dir / "expenses.csv").open("rb") as f:
        r = client.post("/expenses/summary", files={"file": ("expenses.csv", f, "text/csv")})
    assert r.status_code == 200
    body = r.json()
    assert body["grand_total"] == "1701.24"
    assert len(body["rejected"]) == 2


def test_expense_summary_rejects_wrong_columns():
    r = client.post("/expenses/summary",
                    files={"file": ("x.csv", b"name,age\nbob,3\n", "text/csv")})
    assert r.status_code == 400
    assert "columns" in r.json()["detail"]


def test_expense_summary_rejects_non_utf8():
    r = client.post("/expenses/summary", files={"file": ("x.csv", b"\xff\xfe\x00bad", "text/csv")})
    assert r.status_code == 400


def test_invoice_validate_ok():
    r = client.post("/invoices/validate", json=GOOD_INVOICE)
    assert r.status_code == 200 and r.json()["valid"] is True


def test_invoice_validate_bad_total_is_422():
    r = client.post("/invoices/validate", json={**GOOD_INVOICE, "total": "99.00"})
    assert r.status_code == 422
    assert "does not match" in r.text


def test_fx_rates_success(fake_fx):
    fake_fx(lambda req: httpx.Response(200, json={"rates": {"EUR": 0.91, "INR": 93.48}}))
    r = client.get("/fx/rates", params={"base": "usd", "symbols": "eur,inr"})
    assert r.status_code == 200
    assert r.json() == {"EUR": "0.91", "INR": "93.48"}


def test_fx_upstream_failure_maps_to_502(fake_fx):
    fake_fx(lambda req: httpx.Response(404, text="not found"))
    r = client.get("/fx/rates")
    assert r.status_code == 502


def test_fx_rejects_bad_symbols():
    r = client.get("/fx/rates", params={"symbols": "EURO"})
    assert r.status_code == 422
