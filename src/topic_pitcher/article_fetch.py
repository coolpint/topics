import re
from dataclasses import dataclass
from html import unescape
from typing import Optional
from urllib.request import Request, urlopen

from .http import USER_AGENT


META_PATTERNS = (
    re.compile(
        r'<meta[^>]+(?:property|name)=["\'](?:og:description|description|twitter:description)["\'][^>]+content=["\'](.*?)["\']',
        re.IGNORECASE | re.DOTALL,
    ),
    re.compile(
        r'<meta[^>]+content=["\'](.*?)["\'][^>]+(?:property|name)=["\'](?:og:description|description|twitter:description)["\']',
        re.IGNORECASE | re.DOTALL,
    ),
)
PARAGRAPH_PATTERN = re.compile(r"<p\b[^>]*>(.*?)</p>", re.IGNORECASE | re.DOTALL)
TAG_PATTERN = re.compile(r"<[^>]+>")
WHITESPACE_PATTERN = re.compile(r"\s+")
NOISE_MARKERS = (
    "subscribe",
    "newsletter",
    "cookie",
    "advertisement",
    "advertising",
    "terms of use",
    "privacy policy",
)
GENERIC_SUMMARIES = (
    "comprehensive up-to-date news coverage, aggregated from sources all over the world by google news",
)


@dataclass(frozen=True)
class ArticleContext:
    summary: str = ""
    final_url: str = ""


def _clean_html_text(value: str) -> str:
    text = unescape(TAG_PATTERN.sub(" ", value or ""))
    return WHITESPACE_PATTERN.sub(" ", text).strip()


def _meta_description(html: str) -> str:
    for pattern in META_PATTERNS:
        match = pattern.search(html)
        if match:
            text = _clean_html_text(match.group(1))
            if len(text) >= 40:
                return text
    return ""


def _paragraph_summary(html: str) -> str:
    for match in PARAGRAPH_PATTERN.finditer(html):
        text = _clean_html_text(match.group(1))
        if len(text) < 60:
            continue
        lowered = text.lower()
        if any(marker in lowered for marker in NOISE_MARKERS):
            continue
        return text
    return ""


def _shorten(text: str, limit: int = 220) -> str:
    text = WHITESPACE_PATTERN.sub(" ", text).strip()
    if len(text) <= limit:
        return text
    shortened = text[: limit - 3].rstrip(" ,.;:") + "..."
    return shortened


def fetch_article_context(url: str, timeout: int = 8) -> ArticleContext:
    request = Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
    )
    with urlopen(request, timeout=timeout) as response:
        html = response.read().decode("utf-8", errors="replace")
        final_url = response.geturl()
    summary = _meta_description(html) or _paragraph_summary(html)
    normalized_summary = WHITESPACE_PATTERN.sub(" ", summary).strip().lower()
    if any(marker in normalized_summary for marker in GENERIC_SUMMARIES):
        summary = ""
    if "news.google.com" in final_url and not summary:
        return ArticleContext(summary="", final_url=url)
    return ArticleContext(summary=_shorten(summary), final_url=final_url)
