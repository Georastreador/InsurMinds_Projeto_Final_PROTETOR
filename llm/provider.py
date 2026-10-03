"""Single place where the OpenAI client is created.

v1.2 created `OpenAI(api_key=...)` in five adapters with SDK defaults. Here timeout and
retries are explicit and configurable. The SDK retries connection errors, 408, 409, 429
and 5xx with exponential backoff and jitter, so a transient rate limit no longer
fails the run.
"""
from __future__ import annotations

import os
from typing import Any, Optional

DEFAULT_MODEL = "gpt-5.6-luna"
DEFAULT_TIMEOUT_S = 300.0
DEFAULT_MAX_RETRIES = 4

# Exceptions the Harness treats as transient even after the SDK retries (one more A3 attempt).
TRANSIENT_ERRORS = {"APITimeoutError", "APIConnectionError", "RateLimitError", "InternalServerError"}


def model_name(model: Optional[str] = None) -> str:
    return model or os.getenv("OPENAI_MODEL", DEFAULT_MODEL)


def make_openai_client(api_key: Optional[str] = None) -> Any:
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError("OpenAI SDK not installed. Run: pip install -r requirements.txt") from exc
    key = api_key or os.getenv("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("OPENAI_API_KEY is not configured.")
    return OpenAI(api_key=key,
                  timeout=float(os.getenv("OPENAI_TIMEOUT_S", DEFAULT_TIMEOUT_S)),
                  max_retries=int(os.getenv("OPENAI_MAX_RETRIES", DEFAULT_MAX_RETRIES)))


def is_transient(exc: BaseException) -> bool:
    return type(exc).__name__ in TRANSIENT_ERRORS
