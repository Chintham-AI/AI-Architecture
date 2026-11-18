"""Exercise 2+ (async basics) - fetch many rates at the same time with async/await.

Why: an agent that calls 5 tools, or a RAG pipeline that embeds 1,000 chunks, spends most
of its time *waiting on the network*. Sequentially that's sum(latencies); concurrently it's
roughly max(latencies). Run `uv run fx-async` and compare the two timings it prints.

Key ideas:
- `async def` defines a coroutine; `await` pauses it until the I/O is done, letting the
  event loop run other coroutines meanwhile.
- `asyncio.gather` runs many coroutines concurrently.
- `asyncio.Semaphore` caps concurrency - essential with rate-limited AI APIs, or you
  turn your speed-up into a wall of 429s.
- `finally` always runs: here it records timing whether the call succeeded or not.
"""

import asyncio
import logging
import time
from decimal import Decimal

import httpx

from stage0.fx_client import RETRYABLE_STATUS, ApiError, backoff_delay
from stage0.log import setup_logging

log = logging.getLogger(__name__)

BASE_URL = "https://api.frankfurter.dev/v1"


async def get_rate_async(
    client: httpx.AsyncClient,
    sem: asyncio.Semaphore,
    base: str,
    target: str,
    max_attempts: int = 3,
) -> tuple[str, Decimal]:
    async with sem:  # at most N requests in flight
        for attempt in range(max_attempts):
            started = time.perf_counter()
            try:
                r = await client.get("/latest", params={"base": base, "symbols": target})
                if r.is_success:
                    return f"{base}->{target}", Decimal(str(r.json()["rates"][target]))
                if r.status_code not in RETRYABLE_STATUS:
                    raise ApiError(f"{base}->{target}: HTTP {r.status_code}", r.status_code)
                reason = f"HTTP {r.status_code}"
            except httpx.TransportError as exc:
                reason = type(exc).__name__
            finally:
                log.debug("%s->%s attempt %d took %.3fs", base, target, attempt + 1,
                          time.perf_counter() - started)
            if attempt < max_attempts - 1:
                await asyncio.sleep(backoff_delay(attempt, 0.5, 4.0))  # never time.sleep here!
        raise ApiError(f"{base}->{target} failed after {max_attempts} attempts: {reason}")


PAIRS = [("USD", "EUR"), ("USD", "INR"), ("EUR", "GBP"), ("GBP", "JPY"), ("INR", "SGD"),
         ("AUD", "USD")]


async def fetch_all(concurrency: int = 4) -> dict[str, Decimal]:
    sem = asyncio.Semaphore(concurrency)
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=5.0) as client:
        # return_exceptions=True: one failure doesn't cancel the rest; we inspect each.
        results = await asyncio.gather(
            *(get_rate_async(client, sem, b, t) for b, t in PAIRS), return_exceptions=True
        )
    rates: dict[str, Decimal] = {}
    for res in results:
        if isinstance(res, BaseException):
            log.error("Failed: %s", res)
        else:
            rates[res[0]] = res[1]
    return rates


async def fetch_sequential() -> dict[str, Decimal]:
    return await fetch_all(concurrency=1)  # same code, concurrency of one


def main() -> int:
    setup_logging()
    t0 = time.perf_counter()
    asyncio.run(fetch_sequential())
    seq = time.perf_counter() - t0

    t0 = time.perf_counter()
    rates = asyncio.run(fetch_all(concurrency=6))
    conc = time.perf_counter() - t0

    for pair, rate in rates.items():
        print(f"{pair:>9}: {rate}")
    print(f"\nsequential: {seq:.2f}s   concurrent: {conc:.2f}s   speed-up: {seq / conc:.1f}x")
    return 0 if len(rates) == len(PAIRS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
