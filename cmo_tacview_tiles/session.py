"""HTTP session helpers: polite User-Agent, retries, timeouts."""

from __future__ import annotations

import threading
from typing import Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .constants import DEFAULT_RETRIES, DEFAULT_TIMEOUT, USER_AGENT

_THREAD_LOCAL = threading.local()


def build_session(
    retries: int = DEFAULT_RETRIES,
    timeout: float = DEFAULT_TIMEOUT,
    user_agent: str = USER_AGENT,
) -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": user_agent,
            "Accept": "image/webp,image/*,*/*;q=0.8",
        }
    )
    session.request_timeout = timeout  # type: ignore[attr-defined]
    retry_kwargs = dict(
        total=max(0, retries),
        connect=max(0, retries),
        read=max(0, retries),
        backoff_factor=0.8,
        status_forcelist=(429, 500, 502, 503, 504),
        raise_on_status=False,
    )
    try:
        retry = Retry(allowed_methods=frozenset({"HEAD", "GET"}), **retry_kwargs)
    except TypeError:  # urllib3 < 1.26
        retry = Retry(method_whitelist=frozenset({"HEAD", "GET"}), **retry_kwargs)
    adapter = HTTPAdapter(max_retries=retry, pool_connections=8, pool_maxsize=8)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def thread_session(
    retries: int = DEFAULT_RETRIES,
    timeout: float = DEFAULT_TIMEOUT,
    user_agent: str = USER_AGENT,
) -> requests.Session:
    """Return a per-thread session (requests.Session is not thread-safe)."""
    key = (retries, timeout, user_agent)
    session: Optional[requests.Session] = getattr(_THREAD_LOCAL, "session", None)
    if session is None or getattr(_THREAD_LOCAL, "key", None) != key:
        session = build_session(retries=retries, timeout=timeout, user_agent=user_agent)
        _THREAD_LOCAL.session = session
        _THREAD_LOCAL.key = key
    return session


def request_timeout(session: requests.Session, fallback: float = DEFAULT_TIMEOUT) -> float:
    return float(getattr(session, "request_timeout", fallback))
