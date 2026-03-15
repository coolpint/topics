import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Set, Tuple


STOPWORDS = {
    "the",
    "and",
    "for",
    "with",
    "from",
    "that",
    "this",
    "into",
    "amid",
    "over",
    "after",
    "under",
    "will",
    "have",
    "more",
    "than",
    "your",
    "what",
    "when",
    "where",
    "why",
    "how",
    "시장",
    "경제",
    "기사",
    "발제",
    "주제",
    "한국",
    "미국",
}


def _normalize_token(token: str) -> str:
    return token.strip().lower()


def _extract_terms(text: str) -> Set[str]:
    cleaned = []
    for raw in text.replace("/", " ").replace("-", " ").split():
        token = _normalize_token(raw)
        if not token or token in STOPWORDS:
            continue
        if len(token) >= 3 or any("\uac00" <= ch <= "\ud7a3" for ch in token):
            cleaned.append(token)
    return set(cleaned)


def _pitch_slug(pitch: Any) -> str:
    if hasattr(pitch, "slug"):
        return getattr(pitch, "slug")
    topic = getattr(pitch, "topic", None)
    if topic is not None and hasattr(topic, "slug"):
        return topic.slug
    return ""


def _pitch_label(pitch: Any) -> str:
    if hasattr(pitch, "headline"):
        return getattr(pitch, "headline")
    topic = getattr(pitch, "topic", None)
    if topic is not None and hasattr(topic, "label"):
        return topic.label
    return ""


def _pitch_terms(pitch: Any) -> Set[str]:
    terms = set()
    if hasattr(pitch, "terms"):
        terms.update({term for term in getattr(pitch, "terms") if isinstance(term, str)})
    if hasattr(pitch, "headline"):
        terms.update(_extract_terms(getattr(pitch, "headline")))
    if hasattr(pitch, "summary"):
        terms.update(_extract_terms(getattr(pitch, "summary")))
    topic = getattr(pitch, "topic", None)
    if topic is not None:
        terms.update(_extract_terms(getattr(topic, "label", "")))
        terms.update(_extract_terms(" ".join(sorted(getattr(pitch, "matched_keywords", set())))))
    for item in getattr(pitch, "evidence", [])[:2]:
        terms.update(_extract_terms(getattr(item, "title", "")))
    return terms


def load_history(history_path: str) -> List[Dict[str, object]]:
    path = Path(history_path)
    if not path.exists():
        return []
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        return []
    return raw


def select_fresh_topics(
    digests: Iterable[Any],
    history: List[Dict[str, object]],
    now: datetime,
    limit: int,
    window_days: int = 30,
) -> Tuple[List[Any], List[str], bool]:
    ranked_digests = list(digests)
    fresh: List[Any] = []
    skipped: List[str] = []
    used_recent_fallback = False
    cutoff = now - timedelta(days=window_days)
    recent_entries = []
    for entry in history:
        sent_at = entry.get("sent_at")
        if not isinstance(sent_at, str):
            continue
        try:
            parsed = datetime.fromisoformat(sent_at)
        except ValueError:
            continue
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        if parsed >= cutoff:
            recent_entries.append(entry)
    for digest in ranked_digests:
        terms = _pitch_terms(digest)
        duplicate = False
        for entry in recent_entries:
            if entry.get("slug") == _pitch_slug(digest):
                duplicate = True
                break
            old_terms = set(entry.get("terms", []))
            if len(terms & old_terms) >= 4:
                duplicate = True
                break
        if duplicate:
            skipped.append(_pitch_label(digest))
            continue
        fresh.append(digest)
        if len(fresh) >= limit:
            break
    if not fresh and ranked_digests:
        fresh = ranked_digests[:limit]
        used_recent_fallback = True
    return fresh, skipped, used_recent_fallback


def save_history(history_path: str, digests: Iterable[Any], now: datetime, keep_days: int = 90) -> None:
    path = Path(history_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    history = load_history(history_path)
    cutoff = now - timedelta(days=keep_days)
    compact_history = []
    for entry in history:
        sent_at = entry.get("sent_at")
        if not isinstance(sent_at, str):
            continue
        try:
            parsed = datetime.fromisoformat(sent_at)
        except ValueError:
            continue
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        if parsed >= cutoff:
            compact_history.append(entry)
    for digest in digests:
        compact_history.append(
            {
                "sent_at": now.isoformat(),
                "slug": _pitch_slug(digest),
                "label": _pitch_label(digest),
                "top_title": getattr(digest.evidence[0], "title", "") if getattr(digest, "evidence", []) else "",
                "terms": sorted(_pitch_terms(digest)),
            }
        )
    path.write_text(
        json.dumps(compact_history, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
