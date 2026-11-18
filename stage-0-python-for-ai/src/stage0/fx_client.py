"""Exercise 2 - Call a free public REST API, handle timeouts and errors, retry with backoff.

API: Frankfurter (https://frankfurter.dev) - free currency exchange rates, no key needed.

Why this matters for AI: every model API (OpenAI, Anthropic, Gemini, Foundry, Bedrock)
- times out on long generations,
- returns 429 Too Many Requests when you exceed tokens/requests per minute,
- returns 5xx / 529 "overloaded" during peaks.
The pattern below - classify the error, retry only what is retryable, back off
exponentially with jitter, honour Retry-After, give up after N attempts - is exactly what
you will need in Stage 2 and what an AI gateway does for you in Stage 7.

In production you'd usually reach for `tenacity` or the SDK's built-in retries; writing it
once by hand is how you learn what those knobs mean.
"""

import argparse
import logging
import os
import random
import time
from collections.abc import Callable
from decimal import Decimal

import httpx
from dotenv import load_dotenv

from stage0.log import setup_logging

log = logging.getLogger(__name__)

# Status codes worth retrying. 4xx (except 408/429) means *our* request is wrong:
# retrying a 400 or 401 just burns money and time.
RETRYABLE_STATUS = {408, 429, 500, 502, 503, 504, 529}


class ApiError(Exception):
    """Raised when the API call ultimately fails. Carries status code for callers."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


def backoff_delay(attempt: int, base: float, cap: float) -> float:
    """Exponential backoff with 'full jitter': random(0, min(cap, base * 2^attempt)).

    Jitter matters: if 1,000 clients all fail at once and all retry after exactly 2s,
    they hammer the server again at exactly the same moment (thundering herd).
    """
    return random.uniform(0, min(cap, base * (2**attempt)))


def retry_after_seconds(response: httpx.Response) -> float | None:
    """Servers often tell you how long to wait on 429/503. Respect it."""
    value = response.headers.get("Retry-After")
    if value is None:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        return None  # HTTP-date format: ignore for simplicity


def request_with_retry(
    client: httpx.Client,
    method: str,
    url: str,
    *,
    max_attempts: int = 4,
    base_delay: float = 0.5,
    max_delay: float = 8.0,
    sleep: Callable[[float], None] = time.sleep,  # injectable so tests don't really sleep
    **kwargs,
) -> httpx.Response:
    """Send a request, retrying transient failures. Returns the successful response."""
    last_error: str = ""
    for attempt in range(max_attempts):
        try:
            response = client.request(method, url, **kwargs)
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            # Timeouts, DNS failures, connection resets: transient, retry.
            last_error = f"{type(exc).__name__}: {exc}"
            delay = backoff_delay(attempt, base_delay, max_delay)
        else:
            if response.is_success:
                return response
            if response.status_code not in RETRYABLE_STATUS:
                # Permanent failure: fail fast with a clear message.
                raise ApiError(
                    f"{method} {url} failed with {response.status_code}: {response.text[:200]}",
                    status_code=response.status_code,
                )
            last_error = f"HTTP {response.status_code}"
            delay = retry_after_seconds(response) or backoff_delay(attempt, base_delay, max_delay)

        if attempt < max_attempts - 1:
            log.warning("Attempt %d/%d failed (%s); retrying in %.2fs",
                        attempt + 1, max_attempts, last_error, delay)
            sleep(delay)

    raise ApiError(f"{method} {url} failed after {max_attempts} attempts: {last_error}")


def build_client() -> httpx.Client:
    """Config comes from environment variables (loaded from .env), never hard-coded.

    This API needs no key, but the pattern is identical for OPENAI_API_KEY etc.
    Even better (Stage 2+): keyless auth via managed identity / IAM role.
    """
    load_dotenv()
    base_url = os.getenv("FX_API_BASE_URL", "https://api.frankfurter.dev/v1")
    timeout = float(os.getenv("FX_API_TIMEOUT_SECONDS", "5"))
    headers = {"User-Agent": "stage0-learning-client/0.1"}
    if api_key := os.getenv("FX_API_KEY"):  # unused by Frankfurter; shows the pattern
        headers["Authorization"] = f"Bearer {api_key}"
    # Separate connect vs read timeouts: connect should be quick; reads can take longer.
    return httpx.Client(base_url=base_url, timeout=httpx.Timeout(timeout, connect=3.0),
                        headers=headers)


def get_rates(client: httpx.Client, base: str, symbols: list[str]) -> dict[str, Decimal]:
    response = request_with_retry(
        client, "GET", "/latest", params={"base": base.upper(), "symbols": ",".join(symbols)}
    )
    try:
        payload = response.json()
        # parse_float=Decimal would be stricter; str() round-trip is fine here.
        return {k: Decimal(str(v)) for k, v in payload["rates"].items()}
    except (ValueError, KeyError) as exc:
        # The server said 200 but sent something unexpected: still an error for us.
        raise ApiError(f"Unexpected response body: {response.text[:200]}") from exc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Get FX rates with retries.")
    parser.add_argument("--base", default="USD")
    parser.add_argument("--symbols", default="EUR,INR,GBP")
    args = parser.parse_args(argv)
    setup_logging()

    with build_client() as client:  # `with` guarantees connections are closed
        try:
            rates = get_rates(client, args.base, args.symbols.split(","))
        except ApiError as exc:
            log.error("Could not fetch rates: %s", exc)
            return 1
    for code, rate in rates.items():
        print(f"1 {args.base} = {rate} {code}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
