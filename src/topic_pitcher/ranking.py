import math
import re
from datetime import datetime, timezone
from typing import Dict, Iterable, List
from urllib.parse import urlparse

from .models import EvidenceItem, TopicDefinition, TopicDigest
from .taxonomy import ANTI_KEYWORDS, GLOBAL_ECON_KEYWORDS

MICRO_SIGNAL_TERMS = [
    "pet",
    "groom",
    "airport",
    "security",
    "queue",
    "terminal",
    "worker",
    "factory",
    "plant",
    "store",
    "shop",
    "salon",
    "service",
    "subscription",
    "defense",
    "munition",
    "shipyard",
    "order backlog",
    "contract",
    "transformer",
    "substation",
    "utility bill",
    "utility",
    "utilities",
    "server",
    "rack",
    "decommissioning",
    "fukushima",
    "gas station",
    "gas price",
    "fuel surcharge",
    "tanker",
    "refinery",
    "airline",
    "trucker",
    "homebuyer",
    "realtor",
    "builder",
    "tenant",
    "landlord",
    "coupon",
    "mall",
    "restaurant",
    "developer",
    "delivery rider",
    "반려동물",
    "미용",
    "공항",
    "보안검색",
    "대기열",
    "터미널",
    "작업자",
    "현장",
    "공장",
    "방산",
    "수주",
    "수주잔고",
    "변압기",
    "변전소",
    "전기요금",
    "서버",
    "폐로",
    "주유소",
    "휘발유값",
    "유조선",
    "정유",
    "항공사",
    "운임",
    "주택구매자",
    "세입자",
    "집주인",
    "분양",
    "상가",
    "식당",
    "개발업체",
]

MACRO_ONLY_TERMS = [
    "economy",
    "inflation",
    "growth",
    "gdp",
    "fed",
    "jobs",
    "market",
    "rates",
    "경제",
    "물가",
    "성장률",
    "연준",
    "고용",
    "증시",
    "금리",
]

CONCRETE_ROLE_TERMS = [
    "worker",
    "operator",
    "driver",
    "customer",
    "founder",
    "investor",
    "traveler",
    "passenger",
    "commuter",
    "homebuyer",
    "renter",
    "tenant",
    "landlord",
    "worker",
    "owner",
    "작업자",
    "직원",
    "소비자",
    "청년",
    "승객",
    "투자자",
    "사장",
    "입주민",
]

COMPANY_OR_PLACE_TERMS = [
    "inc",
    "corp",
    "group",
    "bank",
    "energy",
    "airlines",
    "airport",
    "tsa",
    "terminal",
    "plant",
    "factory",
    "refinery",
    "shipyard",
    "mall",
    "restaurant",
    "station",
    "campus",
    "terminal",
    "공항",
    "터미널",
    "공장",
    "정유",
    "조선소",
    "상가",
    "식당",
    "발전소",
]

CONCRETE_NUMBER_PATTERN = re.compile(
    r"(\$|€|£|¥|원|달러|만원|억원|조원|%|\b\d{1,3}(?:,\d{3})+\b|\b\d+\b\s?(?:year-old|세|명|개|배|시간|억|만|million|billion))",
    re.IGNORECASE,
)


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
    title_haystack = _normalize(item.title)
    matches: List[TopicDefinition] = []
    for topic in topic_definitions:
        keyword_hits = {keyword for keyword in topic.keywords if _contains_term(haystack, keyword)}
        title_hits = {keyword for keyword in topic.keywords if _contains_term(title_haystack, keyword)}
        topic_hint_match = item.topic_hint and item.topic_hint == topic.slug
        if not title_hits:
            continue
        if not topic_hint_match and len(keyword_hits) < 2:
            continue
        if item.source != "naver_news" and _specificity_score(item) <= 0:
            continue
        if len(keyword_hits) >= 2 or topic_hint_match:
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


def _specificity_score(item: EvidenceItem) -> float:
    haystack = _normalize(item.title)
    micro_hits = sum(1 for term in MICRO_SIGNAL_TERMS if _contains_term(haystack, term))
    macro_hits = sum(1 for term in MACRO_ONLY_TERMS if _contains_term(haystack, term))
    numeric_bonus = 0.4 if CONCRETE_NUMBER_PATTERN.search(item.title) else 0.0
    person_bonus = 0.25 if any(
        _contains_term(haystack, term)
        for term in CONCRETE_ROLE_TERMS + ["groom"]
    ) else 0.0
    entity_bonus = 0.2 if any(_contains_term(haystack, term) for term in COMPANY_OR_PLACE_TERMS) else 0.0
    base_score = micro_hits * 0.28 + numeric_bonus + person_bonus + entity_bonus
    proper_noun_bonus = 0.15 if base_score > 0 and re.search(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b", item.title) else 0.0
    penalty = 0.35 if macro_hits >= 2 and micro_hits == 0 and numeric_bonus == 0 and person_bonus == 0 else 0.0
    return min(2.2, base_score + proper_noun_bonus) - penalty


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


def _evidence_priority(item: EvidenceItem, now: datetime) -> float:
    return _source_score(item, now) * max(0.85, 1.0 + 0.06 * _specificity_score(item))


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

    ranked: List[TopicDigest] = []
    for digest in digests.values():
        if not digest.evidence:
            continue
        digest.evidence.sort(key=lambda item: _evidence_priority(item, now), reverse=True)
        core_evidence = digest.evidence[:3]
        supporting_evidence = digest.evidence[3:7]
        digest.social_score = sum(
            _evidence_priority(item, now) for item in core_evidence if _is_social(item)
        ) + 0.35 * sum(
            _evidence_priority(item, now) for item in supporting_evidence if _is_social(item)
        )
        digest.media_score = sum(
            _evidence_priority(item, now) for item in core_evidence if not _is_social(item)
        ) + 0.35 * sum(
            _evidence_priority(item, now) for item in supporting_evidence if not _is_social(item)
        )
        digest.total_score = digest.social_score + digest.media_score
        breadth_bonus = 0.55 * len(digest.unique_sources) + 0.2 * len(digest.unique_publishers)
        bridge_bonus = 1.0 if digest.social_score > 0 and digest.media_score > 0 else 0.0
        keyword_bonus = min(len(digest.matched_keywords), 4) * 0.25
        korean_signal_bonus = 1.0 if any(_is_korean_signal(item) for item in digest.evidence) else 0.0
        anchor_strength = max((_specificity_score(item) for item in digest.evidence), default=0.0)
        concrete_evidence_count = sum(1 for item in digest.evidence if _specificity_score(item) > 0.2)
        anchor_bonus = max(anchor_strength, 0.0) * 0.6 + min(concrete_evidence_count, 3) * 0.18
        digest.total_score += breadth_bonus + bridge_bonus + keyword_bonus + korean_signal_bonus + anchor_bonus
        if anchor_strength <= 0:
            digest.total_score *= 0.22
        digest.total_score *= digest.topic.korea_relevance * digest.topic.story_bias
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
    if digest.evidence:
        top_item = digest.evidence[0]
        lines.append(
            "대표 사례: {}의 '{}'.".format(
                top_item.publisher or top_item.source,
                top_item.title,
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
    lines.append("큰 그림: {}".format(digest.topic.why_now))
    lines.append("경제 독자 관점: {}".format(digest.topic.reader_fit))
    return lines
