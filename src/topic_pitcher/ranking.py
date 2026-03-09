import math
import re
from datetime import datetime, timezone
from typing import Dict, Iterable, List
from urllib.parse import urlparse

from .models import EvidenceItem, TopicDefinition, TopicDigest
from .taxonomy import ANTI_KEYWORDS, GLOBAL_ECON_KEYWORDS


def _normalize(text: str) -> str:
    lowered = text.lower()
    lowered = re.sub(r"[^0-9a-z가-힣%/\-+ ]+", " ", lowered)
    return re.sub(r"\s+", " ", lowered).strip()


def _contains_term(haystack: str, term: str) -> bool:
    normalized_term = _normalize(term)
    pattern = r"(?<![0-9a-z가-힣]){}(?![0-9a-z가-힣])".format(re.escape(normalized_term))
    return re.search(pattern, haystack) is not None


def looks_economic(item: EvidenceItem) -> bool:
    haystack = _normalize(item.snippet or item.title)
    if any(_contains_term(haystack, keyword) for keyword in ANTI_KEYWORDS):
        return False
    return any(_contains_term(haystack, keyword) for keyword in GLOBAL_ECON_KEYWORDS)


def match_topics(item: EvidenceItem, topic_definitions: Iterable[TopicDefinition]) -> List[TopicDefinition]:
    haystack = _normalize(item.snippet or item.title)
    matches: List[TopicDefinition] = []
    for topic in topic_definitions:
        if item.topic_hint and item.topic_hint == topic.slug:
            matches.append(topic)
            continue
        keyword_hits = [keyword for keyword in topic.keywords if _contains_term(haystack, keyword)]
        if len(keyword_hits) >= 2:
            matches.append(topic)
    return matches


def _freshness_decay(published_at: datetime, now: datetime) -> float:
    age_hours = max((now - published_at).total_seconds() / 3600.0, 0.0)
    return math.exp(-age_hours / 30.0)


def _source_score(item: EvidenceItem, now: datetime) -> float:
    freshness = _freshness_decay(item.published_at, now)
    if item.source == "reddit":
        raw = 1.8 * math.log1p(item.metrics.get("score", 0.0)) + 1.1 * math.log1p(
            item.metrics.get("comments", 0.0)
        )
        return 1.4 * raw * freshness
    if item.source == "hacker_news":
        raw = 1.5 * math.log1p(item.metrics.get("score", 0.0)) + 1.0 * math.log1p(
            item.metrics.get("comments", 0.0)
        )
        return 1.15 * raw * freshness
    if item.source == "youtube":
        raw = (
            1.0 * math.log1p(item.metrics.get("views", 0.0))
            + 0.8 * math.log1p(item.metrics.get("likes", 0.0))
            + 0.9 * math.log1p(item.metrics.get("comments", 0.0))
        )
        return 1.1 * raw * freshness
    if item.source == "naver_news":
        total = min(item.metrics.get("total", 0.0), 5000.0)
        return 1.35 * math.log1p(total) * freshness
    if item.source == "google_news_kr":
        return 2.45 * freshness
    return 2.0 * freshness


def _is_social(item: EvidenceItem) -> bool:
    return item.source in {"reddit", "hacker_news", "youtube"}


def _is_korean_signal(item: EvidenceItem) -> bool:
    return item.audience_region.upper() == "KR"


def _passes_minimum_signal(item: EvidenceItem) -> bool:
    if item.source == "reddit":
        return item.metrics.get("score", 0.0) >= 20.0
    if item.source == "hacker_news":
        return item.metrics.get("score", 0.0) >= 10.0
    if item.source == "youtube":
        return (
            item.metrics.get("views", 0.0) >= 1000.0
            or item.metrics.get("likes", 0.0) >= 50.0
        )
    return True


def _publisher_label(item: EvidenceItem) -> str:
    if item.publisher:
        return item.publisher
    return urlparse(item.url).netloc or item.source


def rank_topics(
    items: Iterable[EvidenceItem],
    topic_definitions: Iterable[TopicDefinition],
    now: datetime = None,
    top_n: int = 5,
) -> List[TopicDigest]:
    if now is None:
        now = datetime.now(timezone.utc)
    digests: Dict[str, TopicDigest] = {
        topic.slug: TopicDigest(topic=topic)
        for topic in topic_definitions
    }
    for item in items:
        if not looks_economic(item):
            continue
        if _is_social(item) and not _passes_minimum_signal(item):
            continue
        for topic in match_topics(item, topic_definitions):
            digest = digests[topic.slug]
            digest.evidence.append(item)
            digest.unique_sources.add(item.source)
            digest.unique_publishers.add(_publisher_label(item))
            for keyword in topic.keywords:
                if _contains_term(_normalize(item.snippet or item.title), keyword):
                    digest.matched_keywords.add(keyword)
            score = _source_score(item, now)
            if _is_social(item):
                digest.social_score += score
            else:
                digest.media_score += score
            digest.total_score += score

    ranked: List[TopicDigest] = []
    for digest in digests.values():
        if not digest.evidence:
            continue
        breadth_bonus = 0.65 * len(digest.unique_sources) + 0.25 * len(digest.unique_publishers)
        bridge_bonus = 1.1 if digest.social_score > 0 and digest.media_score > 0 else 0.0
        keyword_bonus = min(len(digest.matched_keywords), 4) * 0.25
        korean_signal_bonus = 1.0 if any(_is_korean_signal(item) for item in digest.evidence) else 0.0
        digest.total_score += breadth_bonus + bridge_bonus + keyword_bonus + korean_signal_bonus
        digest.total_score *= digest.topic.korea_relevance
        digest.evidence.sort(key=lambda item: _source_score(item, now), reverse=True)
        ranked.append(digest)
    ranked.sort(key=lambda item: item.total_score, reverse=True)
    return ranked[:top_n]


def summarize_reason(digest: TopicDigest) -> List[str]:
    evidence_count = len(digest.evidence)
    social_count = sum(1 for item in digest.evidence if _is_social(item))
    media_count = evidence_count - social_count
    top_social = next((item for item in digest.evidence if _is_social(item)), None)
    lines = []
    lines.append(
        "왜 뽑았나: {}개 증거 중 소셜 {}건, 뉴스 {}건이 겹쳤습니다.".format(
            evidence_count, social_count, media_count
        )
    )
    korean_count = sum(1 for item in digest.evidence if _is_korean_signal(item))
    if korean_count:
        lines.append("한국 독자 신호: 한국 소스 {}건이 함께 잡혔습니다.".format(korean_count))
    if top_social:
        if top_social.source == "reddit":
            lines.append(
                "반응 신호: {}에서 업보트 {:.0f}, 댓글 {:.0f}.".format(
                    top_social.publisher,
                    top_social.metrics.get("score", 0.0),
                    top_social.metrics.get("comments", 0.0),
                )
            )
        elif top_social.source == "youtube":
            lines.append(
                "반응 신호: YouTube 영상 조회수 {:.0f}, 좋아요 {:.0f}, 댓글 {:.0f}.".format(
                    top_social.metrics.get("views", 0.0),
                    top_social.metrics.get("likes", 0.0),
                    top_social.metrics.get("comments", 0.0),
                )
            )
        else:
            lines.append(
                "반응 신호: Hacker News 점수 {:.0f}, 댓글 {:.0f}.".format(
                    top_social.metrics.get("score", 0.0),
                    top_social.metrics.get("comments", 0.0),
                )
            )
    lines.append("경제 독자 관점: {}".format(digest.topic.reader_fit))
    lines.append("현재성: {}".format(digest.topic.why_now))
    return lines
