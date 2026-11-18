"""Shared logging setup.

Why logging instead of print?
- Levels (DEBUG/INFO/WARNING/ERROR) let you turn noise up or down without code changes.
- Each line carries a timestamp and the module name, so you can trace what happened.
- In production, handlers ship logs to a collector (Azure Monitor, CloudWatch, Langfuse...)
  without touching business code. In Stage 5 this grows into OpenTelemetry tracing.
"""

import logging
import os

_FORMAT = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"


def setup_logging(level: str | None = None) -> None:
    """Configure the root logger once. Level comes from the arg, then LOG_LEVEL env var."""
    level = (level or os.getenv("LOG_LEVEL", "INFO")).upper()
    logging.basicConfig(level=level, format=_FORMAT)
    # Third-party libraries are chatty at DEBUG; keep them at WARNING.
    for noisy in ("httpx", "httpcore"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
