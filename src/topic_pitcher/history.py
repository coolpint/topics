import json
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Set, Tuple

from .models import TopicDigest


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


def _digest_terms(digest: TopicDigest) -> Set[str]:
    terms = set()
    terms.update(_extract_terms(digest.topic.label))
    terms.update(_extract_terms(" ".join(sorted(digest.matched_keywords))))
    for item in digest.evidence[:2]:
        terms.update(_extract_terms(item.title))
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
    digests: Iterable[TopicDigest],
    history: List[Dict[str, object]],
    now: datetime,
    limit: int,
    window_days: int = 30,
) -> Tuple[List[TopicDigest], List[str], bool]:
    ranked_digests = list(digests)
    fresh: List[TopicDigest] = []
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
        terms = _digest_terms(digest)
        duplicate = False
        for entry in recent_entries:
            if entry.get("slug") == digest.topic.slug:
                duplicate = True
                break
            old_terms = set(entry.get("terms", []))
            if len(terms & old_terms) >= 4:
                duplicate = True
                break
        if duplicate:
            skipped.append(digest.topic.label)
            continue
        fresh.append(digest)
        if len(fresh) >= limit:
            break
    if not fresh and ranked_digests:
        fresh = ranked_digests[:limit]
        used_recent_fallback = True
    return fresh, skipped, used_recent_fallback


def save_history(history_path: str, digests: Iterable[TopicDigest], now: datetime, keep_days: int = 90) -> None:
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
                "slug": digest.topic.slug,
                "label": digest.topic.label,
                "top_title": digest.evidence[0].title if digest.evidence else "",
                "terms": sorted(_digest_terms(digest)),
            }
        )
    path.write_text(
        json.dumps(compact_history, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
