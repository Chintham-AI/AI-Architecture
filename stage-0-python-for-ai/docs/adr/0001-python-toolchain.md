# ADR-0001: Python toolchain for AI back-ends (uv + httpx + Pydantic + FastAPI)

- **Status:** Accepted
- **Date:** 2026-11-18
- **Stage:** 0

## Context

Every later stage (LLM apps, RAG, agents, evals) needs a Python back-end that calls slow, rate-limited remote APIs, validates untrusted structured data and exposes HTTP endpoints. We need a default stack that a team can repeat for every project.

## Decision

| Concern | Choice | Rejected alternatives |
|---|---|---|
| Env + packages | **uv** with `pyproject.toml` + `uv.lock` | pip + venv + requirements.txt (slower, no lockfile by default), Poetry (slower, extra tool) |
| HTTP client | **httpx** | requests: no async support and no built-in mock transport |
| Data contracts | **Pydantic v2** | dataclasses (no validation), marshmallow (less ecosystem use in AI SDKs) |
| Web framework | **FastAPI** | Flask (no built-in validation or OpenAPI), Django (too heavy for an API-only service) |
| Retries | Hand-written for learning; **tenacity / SDK retries** in production | none |
| Tests | **pytest** + `httpx.MockTransport` + FastAPI dependency overrides | live-network tests (slow, flaky, cost money once LLMs are involved) |

## Consequences

- **+ Portability:** none of this is tied to a cloud vendor. The same service runs on Azure Container Apps, AWS Fargate or Cloud Run (Stage 7).
- **+ Quality:** Pydantic schemas work as validation *and* as LLM structured-output schemas, so there is one source of truth.
- **+ Maintainability:** the lockfile gives reproducible installs in CI.
- **− Trade-off (speed vs control):** hand-rolled retries teach the mechanics but are code we must maintain. Switch to a library before production.
- **− Trade-off (cost vs reliability):** retries raise reliability but multiply calls. With LLMs, each retry costs tokens, so cap attempts and honour `Retry-After`.

Dimensions traded (from *The architect's lens*): **Reliability**, **Maintainability**, **Portability**.
