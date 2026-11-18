# Stage 0 · Python for AI

> Goal: write, run and debug the small Python programs every later stage uses.
> Roadmap steps: **Theory → Why and what → Hands-on → Checkpoint**

## 1. Theory, mapped to code in this folder

| Concept | Where to see it working |
|---|---|
| Variables, dicts, lists, loops, functions | [expenses.py](src/stage0/expenses.py) `summarise_rows` |
| Files, CSV, JSON | [expenses.py](src/stage0/expenses.py), [data/](data/) |
| Exceptions: `try/except/else/finally`, custom errors, `raise ... from` | [fx_client.py](src/stage0/fx_client.py), [fx_async.py](src/stage0/fx_async.py) |
| Retries with exponential backoff + jitter, `Retry-After` | [fx_client.py](src/stage0/fx_client.py) `request_with_retry` |
| Classes, dataclasses, type hints | `Summary` in [expenses.py](src/stage0/expenses.py), `ApiError` in [fx_client.py](src/stage0/fx_client.py) |
| Pydantic models, validators, JSON Schema | [invoice.py](src/stage0/invoice.py) |
| Packages + virtual envs with `uv` | [pyproject.toml](pyproject.toml), `uv.lock` |
| `async` / `await`, `gather`, `Semaphore` | [fx_async.py](src/stage0/fx_async.py) |
| HTTP, headers, status codes, secrets from env vars | [fx_client.py](src/stage0/fx_client.py) `build_client`, [.env.example](.env.example) |
| `logging` instead of `print` | [log.py](src/stage0/log.py) |
| pytest, fixtures, parametrize, mocking HTTP | [tests/](tests/) |
| FastAPI, dependency injection, error mapping | [api.py](src/stage0/api.py) |

## 2. Why it matters for an AI architect

Every SDK, framework and eval tool later in the path is Python. Three habits from this stage carry straight into AI work:

1. **Assume the network fails.** Model APIs time out, rate-limit (429) and overload (5xx/529). Classify errors, retry only the transient ones, back off with jitter, and give up cleanly.
2. **Never trust the shape of data.** LLM output is "usually right". Pydantic models are the contract, and `Invoice.model_json_schema()` is the same schema you'll pass to a model as *structured output* in Stage 2.
3. **Test without the network.** `httpx.MockTransport` and FastAPI dependency overrides let you test every failure path quickly. Later stages use the same idea to mock LLM calls.

## 3. Hands-on

```bash
cd stage-0-python-for-ai
uv sync                              # creates .venv and installs locked deps
cp .env.example .env                 # optional: config lives in env vars, never in code

uv run expenses data/expenses.csv -o output/summary.json   # Ex1
uv run fx --base USD --symbols EUR,INR,GBP                  # Ex2 (live API, with retries)
uv run fx-async                                             # Ex2+ sequential vs concurrent timing
uv run invoices                                             # Ex3 good + bad invoices
uv run invoices --schema                                    # Ex3 JSON Schema for LLM structured output
uv run uvicorn stage0.api:app --reload                      # Ex4 then open http://127.0.0.1:8000/docs

uv run pytest                        # 44 tests, no network needed
uv run ruff check .                  # lint
```

> VS Code: run `Python: Select Interpreter` and choose `stage-0-python-for-ai/.venv` so imports resolve.

| # | Roadmap exercise | Result |
|---|---|---|
| 1 | CSV of expenses → totals by category → JSON | Stdlib and pandas versions agree. Bad rows are reported, not fatal. `Decimal` used for money. |
| 2 | Public REST API, timeouts, errors, retry with backoff | Frankfurter FX API. Retries 408/429/5xx/timeouts, fails fast on other 4xx, honours `Retry-After`. Async version ran **7.3× faster** (1.98 s → 0.27 s). |
| 3 | Pydantic invoice, good and bad samples | Type, pattern, enum, range, extra-field and cross-field business rules (total = lines + tax, due ≥ issue). |
| 4 | FastAPI endpoint + pytest | `/expenses/summary` (CSV upload), `/invoices/validate`, `/fx/rates` (upstream failure → 502), `/health`. 44 tests. |

Architecture: [C4 context](docs/c4-context.md) · [ADR-0001](docs/adr/0001-python-toolchain.md)

### Lessons from running it

- `expenses -o output/summary.json` crashed the first time because `output/` didn't exist. Fixed with `mkdir(parents=True)` and the test now writes into a new folder. This is why you run code for real and don't stop at the unit tests.
- Pydantic `mode="after"` validators **only run once all field validations pass**. Bad invoice #3 has a due-date error that is not reported until its field errors are fixed. If you feed validation errors back to an LLM for self-correction, expect more than one round.

## 4. Your turn: drills to do without looking at the code

These are what make the first checkpoint box honest. Put each one in `practice/` and commit it.

- [ ] **D1.** Write `word_freq.py`: read any `.txt` file and print the 10 most common words (lower-case, no punctuation). Use only `dict` and loops first, then redo it with `collections.Counter`.
- [ ] **D2.** Add a `--month 2026-11` filter to `expenses.py` and a test for it.
- [ ] **D3.** Replace the hand-written retry loop with [`tenacity`](https://tenacity.readthedocs.io) in a copy of `fx_client.py`. Which version is easier to read? Which is easier to test?
- [ ] **D4.** Add a `vendor_tax_id` field to `Invoice` that must match a pattern, but only when `currency == "INR"` (hint: `model_validator`).
- [ ] **D5.** Add `POST /fx/convert` (`amount`, `from`, `to`) to the API, with a request model and two tests (success, upstream 503 → 502).
- [ ] **D6.** Explain in 5 lines in `notes/`: why full jitter? What breaks if every client retries after exactly 2 s?

## 5. Checkpoint

- [ ] I can write a script with functions, loops and dictionaries without copying from examples (*do D1, D2*)
- [x] My code handles API errors and retries instead of crashing (*fx_client + 6 retry tests*)
- [x] I can create a virtual environment and install packages for a new project (*uv init / add / sync*)
- [x] I have a small FastAPI service with tests in GitHub (*api.py + test_api.py, once pushed*)

Tick the first box yourself after the drills. That is the gate to Stage 1.

## Resources

[Python tutorial: errors](https://docs.python.org/3/tutorial/errors.html) · [Automate the Boring Stuff](https://automatetheboringstuff.com/) · [Real Python](https://realpython.com/) · [Pydantic](https://docs.pydantic.dev/) · [FastAPI tutorial](https://fastapi.tiangolo.com/tutorial/) · [pytest](https://docs.pytest.org/) · [uv](https://docs.astral.sh/uv/) · [HTTPX](https://www.python-httpx.org/) · [AWS: Exponential backoff and jitter](https://aws.amazon.com/blogs/architecture/exponential-backoff-and-jitter/)
