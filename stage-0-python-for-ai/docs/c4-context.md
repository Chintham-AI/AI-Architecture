# C4 · Level 1 (System context) and Level 2 (Containers): Stage 0 service

```mermaid
C4Context
  title Stage 0 - Expense & Invoice Utility (System Context)
  Person(user, "Analyst / API client", "Uploads expense CSVs, validates invoices, checks FX rates")
  System(svc, "Stage 0 Service", "FastAPI app: expense summary, invoice validation, FX lookup")
  System_Ext(fx, "Frankfurter FX API", "Public currency exchange rates (no auth)")
  Rel(user, svc, "HTTPS / JSON, multipart CSV")
  Rel(svc, fx, "HTTPS GET /latest", "timeouts + retries w/ backoff")
```

```mermaid
flowchart LR
  subgraph svc["Stage 0 Service (one Python process)"]
    api["api.py<br/>FastAPI routes"]
    exp["expenses.py<br/>CSV → totals"]
    inv["invoice.py<br/>Pydantic contract"]
    fxc["fx_client.py<br/>retry + backoff"]
    log["log.py<br/>logging"]
  end
  user(["Client"]) -->|POST /expenses/summary| api --> exp
  user -->|POST /invoices/validate| api --> inv
  user -->|GET /fx/rates| api --> fxc -->|HTTPS| fx[("Frankfurter API")]
  fxc -. 5xx/timeout after retries .-> api -. 502 .-> user
```

**Where this goes next:** in Stage 2 the "FX API" box becomes an LLM API (same retry and timeout concerns, plus token cost), and `invoice.py` becomes the structured-output schema for an LLM invoice extractor.
