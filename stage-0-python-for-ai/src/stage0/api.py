"""Exercise 4 - Wrap the expense script (and friends) in a small FastAPI service.

Run:   uv run uvicorn stage0.api:app --reload
Docs:  http://127.0.0.1:8000/docs   (interactive Swagger UI, generated from the type hints)

What to notice:
- Request/response bodies are Pydantic models -> automatic validation (422 on bad input)
  and an OpenAPI spec for free. AI back-ends in later stages look exactly like this.
- The FX client is injected with Depends(), so tests can swap in a fake without network.
- Upstream failures are translated to 502 Bad Gateway: callers learn *whose* fault it was.
"""

import csv
import io
import logging
from collections.abc import Iterator
from dataclasses import asdict
from decimal import Decimal
from typing import Annotated

import httpx
from fastapi import Depends, FastAPI, HTTPException, Query, UploadFile, status
from pydantic import BaseModel

from stage0 import __version__
from stage0.expenses import summarise_rows
from stage0.fx_client import ApiError, build_client, get_rates
from stage0.invoice import Invoice
from stage0.log import setup_logging

setup_logging()
log = logging.getLogger(__name__)

MAX_UPLOAD_BYTES = 1_000_000

app = FastAPI(title="Stage 0 - Python for AI", version=__version__)


class SummaryOut(BaseModel):
    totals: dict[str, str]
    grand_total: str
    row_count: int
    rejected: list[dict]


class InvoiceCheck(BaseModel):
    valid: bool
    invoice_number: str
    computed_total: Decimal


def get_fx_client() -> Iterator[httpx.Client]:
    """Dependency: one client per request, always closed afterwards."""
    with build_client() as client:
        yield client


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__}


@app.post("/expenses/summary", response_model=SummaryOut)
async def expenses_summary(file: UploadFile) -> SummaryOut:
    raw = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "CSV larger than 1 MB")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "File must be UTF-8 CSV") from exc

    reader = csv.DictReader(io.StringIO(text))
    required = {"category", "amount"}
    if not reader.fieldnames or not required.issubset(reader.fieldnames):
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            f"CSV must have columns: {sorted(required)}")
    summary = summarise_rows(reader)
    log.info("Summarised %s: %d rows, %d rejected", file.filename, summary.row_count,
             len(summary.rejected))
    return SummaryOut(**asdict(summary))


@app.post("/invoices/validate", response_model=InvoiceCheck)
def validate_invoice(invoice: Invoice) -> InvoiceCheck:
    # If we get here, FastAPI + Pydantic already validated everything; bad input got a 422.
    return InvoiceCheck(valid=True, invoice_number=invoice.invoice_number,
                        computed_total=invoice.total)


@app.get("/fx/rates")
def fx_rates(
    client: Annotated[httpx.Client, Depends(get_fx_client)],
    base: Annotated[str, Query(min_length=3, max_length=3)] = "USD",
    symbols: Annotated[str, Query(pattern=r"^[A-Za-z]{3}(,[A-Za-z]{3})*$")] = "EUR,INR",
) -> dict[str, Decimal]:
    try:
        return get_rates(client, base, symbols.upper().split(","))
    except ApiError as exc:
        log.error("FX upstream failure: %s", exc)
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Upstream FX service failed") from exc
