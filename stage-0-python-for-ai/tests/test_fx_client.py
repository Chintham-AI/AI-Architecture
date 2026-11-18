"""Test retry behaviour WITHOUT the network, using httpx.MockTransport.

Each test scripts a sequence of server behaviours and checks how the client reacts.
"""

from decimal import Decimal

import httpx
import pytest

from stage0.fx_client import ApiError, backoff_delay, get_rates, request_with_retry

OK_BODY = {"amount": 1.0, "base": "USD", "date": "2026-11-17", "rates": {"EUR": 0.91}}


def scripted_client(*steps):
    """Return (client, calls). Each step is an httpx.Response or an exception to raise."""
    calls = []
    queue = list(steps)

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        step = queue.pop(0)
        if isinstance(step, Exception):
            raise step
        return step

    client = httpx.Client(transport=httpx.MockTransport(handler), base_url="https://fx.test")
    return client, calls


class FakeSleep:
    def __init__(self):
        self.delays: list[float] = []

    def __call__(self, seconds: float) -> None:
        self.delays.append(seconds)


def test_success_first_try():
    client, calls = scripted_client(httpx.Response(200, json=OK_BODY))
    assert get_rates(client, "usd", ["EUR"]) == {"EUR": Decimal("0.91")}
    assert len(calls) == 1
    assert calls[0].url.params["base"] == "USD"


def test_retries_transient_5xx_then_succeeds():
    sleep = FakeSleep()
    client, calls = scripted_client(
        httpx.Response(503), httpx.Response(502), httpx.Response(200, json=OK_BODY)
    )
    r = request_with_retry(client, "GET", "/latest", sleep=sleep)
    assert r.status_code == 200
    assert len(calls) == 3
    assert len(sleep.delays) == 2


def test_timeout_is_retried_then_gives_up():
    sleep = FakeSleep()
    client, calls = scripted_client(*[httpx.ReadTimeout("slow")] * 3)
    with pytest.raises(ApiError, match="after 3 attempts: ReadTimeout"):
        request_with_retry(client, "GET", "/latest", max_attempts=3, sleep=sleep)
    assert len(calls) == 3
    assert len(sleep.delays) == 2  # no pointless sleep after the final attempt


def test_client_errors_fail_fast_without_retry():
    sleep = FakeSleep()
    client, calls = scripted_client(httpx.Response(400, text="bad currency"))
    with pytest.raises(ApiError) as info:
        request_with_retry(client, "GET", "/latest", sleep=sleep)
    assert info.value.status_code == 400
    assert len(calls) == 1 and sleep.delays == []


def test_honours_retry_after_header():
    sleep = FakeSleep()
    client, _ = scripted_client(
        httpx.Response(429, headers={"Retry-After": "7"}), httpx.Response(200, json=OK_BODY)
    )
    request_with_retry(client, "GET", "/latest", sleep=sleep)
    assert sleep.delays == [7.0]


def test_unexpected_body_raises_api_error():
    client, _ = scripted_client(httpx.Response(200, json={"oops": True}))
    with pytest.raises(ApiError, match="Unexpected response"):
        get_rates(client, "USD", ["EUR"])


@pytest.mark.parametrize("attempt", range(6))
def test_backoff_is_capped_and_non_negative(attempt):
    for _ in range(50):
        assert 0 <= backoff_delay(attempt, base=0.5, cap=4.0) <= min(4.0, 0.5 * 2**attempt)
