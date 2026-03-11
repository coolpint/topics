import json
import os
from typing import Any, Dict, Optional
from urllib.parse import urlencode
from urllib.request import Request, urlopen


USER_AGENT = os.getenv(
    "TOPIC_USER_AGENT",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 topic-pitcher/0.1",
)


def build_url(base: str, params: Optional[Dict[str, Any]] = None) -> str:
    if not params:
        return base
    return base + "?" + urlencode(params, doseq=True)


def fetch_text(
    url: str,
    *,
    params: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
    data: Optional[bytes] = None,
    method: Optional[str] = None,
    timeout: int = 20,
) -> str:
    merged_headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json, application/xml, text/xml, text/plain;q=0.8, */*;q=0.7",
    }
    if headers:
        merged_headers.update(headers)
    request = Request(
        build_url(url, params),
        headers=merged_headers,
        data=data,
        method=method,
    )
    with urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="replace")


def fetch_json(
    url: str,
    *,
    params: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
    data: Optional[bytes] = None,
    method: Optional[str] = None,
    timeout: int = 20,
) -> Any:
    return json.loads(
        fetch_text(
            url,
            params=params,
            headers=headers,
            data=data,
            method=method,
            timeout=timeout,
        )
    )
