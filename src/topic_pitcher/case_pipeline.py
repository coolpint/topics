import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Set, Tuple

from .article_fetch import ArticleContext
from .models import CasePitch, CaseSupport, EvidenceItem
from .ranking import (
    TREND_ONLY_SOURCES,
    _is_social,
    _passes_minimum_signal,
    _publisher_quality,
    _source_score,
    _specificity_score,
    looks_economic,
)


TOKEN_PATTERN = re.compile(r"[A-Za-z][A-Za-z0-9&'.-]{1,}|[가-힣]{2,}|\d+(?:,\d+)?%?")
PROPER_PHRASE_PATTERN = re.compile(
    r"\b(?:[A-Z][a-z]+|[A-Z]{2,})(?:\s+(?:[A-Z][a-z]+|[A-Z]{2,})){0,2}\b"
)
CASE_STOPWORDS = {
    "about",
    "after",
    "again",
    "amid",
    "analysis",
    "ahead",
    "between",
    "behind",
    "below",
    "breaking",
    "clash",
    "company",
    "economy",
    "economic",
    "facing",
    "first",
    "from",
    "global",
    "higher",
    "inside",
    "latest",
    "lower",
    "market",
    "markets",
    "more",
    "news",
    "report",
    "shares",
    "show",
    "shows",
    "still",
    "today",
    "week",
    "weeks",
    "with",
    "year",
    "years",
    "경제",
    "기사",
    "뉴스",
    "시장",
    "발제",
    "화제",
    "한국",
    "미국",
}
GENERIC_ECON_TERMS = {
    "economy",
    "economic",
    "inflation",
    "jobs",
    "payroll",
    "market",
    "markets",
    "rates",
    "growth",
    "gdp",
    "trade",
    "tariff",
    "tariffs",
    "consumer",
    "consumers",
    "housing",
    "mortgage",
    "mortgages",
    "oil",
    "energy",
    "prices",
    "price",
    "전력",
    "경제",
    "고용",
    "금리",
    "물가",
    "성장",
    "성장률",
    "수출",
    "유가",
    "인플레이션",
    "주택",
    "중국",
    "환율",
}
ARTICLE_EXCLUDED_SOURCES = {"naver_blog", "naver_cafe", "naver_news", "naver_datalab"}
NEWSLIKE_SOURCES = {"google_news", "google_news_kr", "youtube", "mastodon"}
ROLE_TERMS = {
    "scene": {
        "wait",
        "delay",
        "lines",
        "line",
        "queue",
        "queueing",
        "climbed",
        "surge",
        "soared",
        "rose",
        "rises",
        "jumped",
        "miss pay",
        "buyers",
        "worker",
        "workers",
        "terminal",
        "airport",
        "factory",
        "plant",
        "주유소",
        "대기",
        "급등",
        "상승",
        "작업",
        "공항",
        "공장",
    },
    "cause": {
        "shutdown",
        "budget",
        "staffing",
        "hiring",
        "tariff",
        "court",
        "fed",
        "cut",
        "cuts",
        "investment",
        "dhs",
        "tsa",
        "power",
        "grid",
        "lawsuit",
        "셧다운",
        "예산",
        "인력",
        "관세",
        "연준",
        "투자",
        "전력망",
    },
    "impact": {
        "travel",
        "business",
        "consumer",
        "consumers",
        "exports",
        "homebuying",
        "mortgage",
        "market",
        "stocks",
        "spring break",
        "surcharge",
        "travelers",
        "여행",
        "소비자",
        "수출",
        "주택",
        "물류",
        "시장",
    },
}
FRAME_RULES = (
    ("airport", {"airport", "tsa", "terminal", "travel", "wait", "shutdown", "security", "공항", "보안검색"}),
    ("oil", {"kharg", "hormuz", "oil", "crude", "refinery", "gasoline", "terminal", "유가", "주유소", "정유"}),
    ("housing", {"mortgage", "homebuying", "homebuyer", "housing", "realtor", "builder", "주택", "모기지", "분양"}),
    ("ai_power", {"data center", "ai", "grid", "electricity", "utility", "nuclear", "transformer", "데이터센터", "전력", "변압기"}),
    ("jobs", {"payroll", "jobs", "unemployment", "fed", "labor", "wages", "고용", "실업률", "연준"}),
    ("defense", {"defense", "missile", "munitions", "shipyard", "artillery", "방산", "미사일", "수주", "공장"}),
    ("pet", {"pet", "grooming", "spa", "daycare", "반려동물", "펫", "미용"}),
    ("trade", {"tariff", "trade", "court", "shipping", "exports", "관세", "무역", "수출"}),
    ("nuclear", {"fukushima", "decommissioning", "cleanup", "worker", "폐로", "후쿠시마", "원전", "작업자"}),
    ("china", {"china", "exports", "property", "consumption", "중국", "내수", "부동산"}),
)
GENERIC_TITLE_MARKERS = (
    "주간",
    "전망",
    "브리핑",
    "리포트",
    "레이더",
    "나우",
    "column",
    "columns",
    "analysis",
    "outlook",
    "what to know",
    "weekly",
)


@dataclass
class _CaseCluster:
    anchor: EvidenceItem
    items: List[EvidenceItem] = field(default_factory=list)
    terms: Set[str] = field(default_factory=set)
    topic_hints: Set[str] = field(default_factory=set)


def _normalize(text: str) -> str:
    lowered = text.lower()
    lowered = re.sub(r"[^0-9a-z가-힣%/&+\- ]+", " ", lowered)
    return re.sub(r"\s+", " ", lowered).strip()


def _clean_title(item: EvidenceItem) -> str:
    title = re.sub(r"\s+", " ", item.title).strip()
    publisher = (item.publisher or "").strip()
    if publisher:
        for suffix in (" - {}".format(publisher), " | {}".format(publisher)):
            if title.endswith(suffix):
                title = title[: -len(suffix)].rstrip()
    return title


def _extract_terms(item: EvidenceItem) -> Set[str]:
    text = "{} {}".format(item.title, item.snippet or "")
    normalized = _normalize(text)
    terms: Set[str] = set()
    publisher_terms = {
        _normalize(token)
        for token in TOKEN_PATTERN.findall(item.publisher or "")
        if _normalize(token)
    }
    for match in PROPER_PHRASE_PATTERN.findall(item.title):
        phrase = _normalize(match)
        if phrase and phrase not in CASE_STOPWORDS and phrase not in publisher_terms:
            terms.add(phrase)
    for raw in TOKEN_PATTERN.findall(text):
        token = _normalize(raw)
        if not token or token in CASE_STOPWORDS or token in GENERIC_ECON_TERMS or token in publisher_terms:
            continue
        if len(token) < 3 and not raw.isupper():
            continue
        terms.add(token)
    return terms


def _item_score(item: EvidenceItem, now: datetime) -> float:
    score = _source_score(item, now)
    score += max(_specificity_score(item), 0.0) * 2.2
    score += max(_publisher_quality(item) - 1.0, 0.0) * 2.0
    score += min(len(_extract_terms(item)), 6) * 0.18
    if item.source in NEWSLIKE_SOURCES:
        score += 0.7
    if item.source in ARTICLE_EXCLUDED_SOURCES:
        score *= 0.45
    return score


def _anchor_score(item: EvidenceItem, now: datetime) -> float:
    score = _item_score(item, now)
    location = _location_hint(item)
    haystack = _normalize(item.title)
    if location:
        score += 0.9
    if any(token in haystack for token in ("wait", "delay", "queue", "line", "climbed", "rose", "surge", "대기", "급등", "상승")):
        score += 0.7
    if any(token in haystack for token in ("worker", "workers", "miss pay", "임금", "급여")):
        score -= 0.35
    return score


def _role(item: EvidenceItem) -> str:
    haystack = _normalize("{} {}".format(item.title, item.snippet or ""))
    if any(phrase in haystack for phrase in ("miss pay", "homebuying", "surcharge")):
        return "impact"
    scores = {}
    for role_name, terms in ROLE_TERMS.items():
        hits = sum(1 for term in terms if term in haystack)
        scores[role_name] = hits
    if not any(scores.values()):
        return "fact"
    return max(scores, key=scores.get)


def _cluster_similarity(item: EvidenceItem, terms: Set[str], cluster: _CaseCluster) -> float:
    shared = terms & cluster.terms
    if not shared:
        return 0.0
    phrase_bonus = sum(1.0 for term in shared if " " in term)
    overlap_ratio = len(shared) / max(min(len(terms), len(cluster.terms)), 1)
    topic_hint_bonus = 0.85 if item.topic_hint and item.topic_hint in cluster.topic_hints else 0.0
    return len(shared) * 1.15 + phrase_bonus + overlap_ratio + topic_hint_bonus


def _is_viable_item(item: EvidenceItem) -> bool:
    if not looks_economic(item):
        return False
    if _is_social(item) and not _passes_minimum_signal(item):
        return False
    if item.source in TREND_ONLY_SOURCES:
        return False
    if item.source in ARTICLE_EXCLUDED_SOURCES and item.source != "youtube":
        return False
    if item.source in {"google_news", "google_news_kr"} and _publisher_quality(item) < 0.75:
        return False
    normalized_title = _normalize(item.title)
    if any(marker in normalized_title for marker in GENERIC_TITLE_MARKERS) and _specificity_score(item) < 1.05:
        return False
    terms = _extract_terms(item)
    if len(terms) >= 2:
        return True
    return _specificity_score(item) > 0.35


def _choose_supports(cluster: _CaseCluster, now: datetime) -> List[Tuple[str, EvidenceItem]]:
    selected: List[Tuple[str, EvidenceItem]] = []
    used_urls = set()
    used_publishers = set()
    for role_name in ("scene", "cause", "impact"):
        candidates = [
            item
            for item in cluster.items
            if _role(item) == role_name and item.url not in used_urls
        ]
        if not candidates:
            continue
        candidates.sort(key=lambda item: _item_score(item, now), reverse=True)
        chosen = next(
            (
                item
                for item in candidates
                if (item.publisher or item.source) not in used_publishers
            ),
            candidates[0],
        )
        selected.append((role_name, chosen))
        used_urls.add(chosen.url)
        used_publishers.add(chosen.publisher or chosen.source)
    if not selected:
        ranked = sorted(cluster.items, key=lambda item: _item_score(item, now), reverse=True)
        for item in ranked[:3]:
            selected.append(("fact", item))
    return selected[:3]


def _detect_frame(cluster: _CaseCluster) -> str:
    haystack_terms = set(cluster.terms)
    title_text = _normalize(" ".join(item.title for item in cluster.items[:4]))
    best_frame = "generic"
    best_score = 0
    for frame, hints in FRAME_RULES:
        score = sum(1 for hint in hints if hint in haystack_terms or hint in title_text)
        if score > best_score:
            best_frame = frame
            best_score = score
    return best_frame


def _location_hint(item: EvidenceItem) -> str:
    for match in PROPER_PHRASE_PATTERN.findall(item.title):
        phrase = match.strip()
        if phrase.upper() == phrase and len(phrase) <= 4:
            continue
        return phrase
    for token in re.findall(r"[A-Z][a-z]+", item.title):
        if token.lower() in {"today", "march", "federal"}:
            continue
        return token
    return ""


def _support_note(item: EvidenceItem, context: Optional[ArticleContext]) -> str:
    if context and context.summary:
        return context.summary
    return _clean_title(item)


def _frame_summary(frame: str, supports: Dict[str, CaseSupport], anchor: EvidenceItem) -> str:
    location = _location_hint(anchor)
    if frame == "airport":
        parts = [
            "{} 공항 대기시간 상승이 현장으로 잡혔다.".format(location or "허브"),
            "셧다운과 TSA 운영 차질이 배경으로 붙는다." if "cause" in supports else "",
            "여행 성수기 수요와 겹치며 공항 병목이 소비자 불편으로 번지는 그림이다." if "impact" in supports else "",
        ]
        return " ".join(part for part in parts if part)
    if frame == "oil":
        parts = [
            "{} 관련 공급 차질이 먼저 잡혔다.".format(location or "원유 터미널"),
            "전쟁·해상 리스크가 배경으로 붙고," if "cause" in supports else "",
            "유가와 물류비, 인플레이션 기대를 함께 흔드는 사안이다." if "impact" in supports else "유가와 물류비를 함께 흔드는 사안이다.",
        ]
        return " ".join(part for part in parts if part)
    if frame == "housing":
        return "모기지 금리 변화가 실수요자 의사결정과 주택시장 회복 기대를 동시에 흔드는 사례다."
    if frame == "ai_power":
        return "데이터센터 전력 수요가 전력망 투자와 비용 전가 문제로 번지는 장면이 잡혔다."
    if frame == "jobs":
        return "고용지표 변화가 금리 경로와 소비·주택시장 기대를 동시에 흔드는 사례다."
    if frame == "defense":
        return "방산 주문이 공장 증설, 납기, 협력사 공급망 문제로 이어지는 장면이 모였다."
    if frame == "pet":
        return "반려동물 소비가 취향 지출이 아니라 서비스 산업 확대 사례로 잡혔다."
    if frame == "trade":
        return "정책·법원 변수 하나가 가격, 재고, 수출 전략으로 번지는 사례다."
    if frame == "nuclear":
        return "폐로 현장 인력 문제가 원전 비용과 지역 산업 문제로 이어지는 장면이다."
    if frame == "china":
        return "중국 수요·수출 변화가 내수 회복보다 산업·해운 파급으로 읽히는 사례다."
    role_labels = {
        "scene": "현장 장면",
        "cause": "원인",
        "impact": "파급",
    }
    joined = ", ".join(
        "{} '{}'".format(role_labels.get(role, "근거"), _clean_title(support.item))
        for role, support in supports.items()
    )
    return "{}가 같은 사건의 다른 단면을 보여준다.".format(joined or _clean_title(anchor))


def _frame_angle(frame: str) -> str:
    if frame == "airport":
        return "셧다운이 공항 혼잡과 여행 소비 차질로 번지는 구조"
    if frame == "oil":
        return "특정 공급 차질이 유가와 생활물가 압박으로 이어지는 구조"
    if frame == "housing":
        return "금리 변곡점이 실수요자·매도자 판단을 바꾸는 구조"
    if frame == "ai_power":
        return "AI 투자 붐이 전력비와 설비투자 부담으로 전가되는 구조"
    if frame == "jobs":
        return "고용 둔화가 금리 기대와 가계 체감 변수로 번지는 구조"
    if frame == "defense":
        return "수주 확대가 공장·협력사·납기 병목으로 이어지는 구조"
    if frame == "pet":
        return "취향 소비가 서비스 신산업으로 커지는 구조"
    if frame == "trade":
        return "정책 변화가 기업 가격·재고 전략으로 내려오는 구조"
    if frame == "nuclear":
        return "폐로 현장 노동이 에너지 비용과 지역경제 문제로 이어지는 구조"
    if frame == "china":
        return "중국 내수·수출 변화가 한국 산업 수요로 이어지는 구조"
    return "현장과 원인, 파급이 한 사건으로 묶이는 구조"


def _slug_from_terms(anchor: EvidenceItem, terms: Set[str]) -> str:
    parts = []
    for term in sorted(terms, key=lambda value: (-len(value), value)):
        cleaned = re.sub(r"[^0-9a-z가-힣]+", "-", term).strip("-")
        if cleaned and cleaned not in parts:
            parts.append(cleaned[:24])
        if len(parts) == 4:
            break
    if not parts:
        parts.append(re.sub(r"[^0-9a-z가-힣]+", "-", _normalize(anchor.title)).strip("-")[:48] or "case")
    return "-".join(parts)[:96]


def _cluster_to_pitch(
    cluster: _CaseCluster,
    now: datetime,
    context_fetcher: Optional[Callable[[str], ArticleContext]],
) -> Optional[CasePitch]:
    article_items = [item for item in cluster.items if item.source not in ARTICLE_EXCLUDED_SOURCES]
    newslike_count = sum(1 for item in article_items if item.source in NEWSLIKE_SOURCES)
    if not article_items or newslike_count == 0:
        return None
    ranked_articles = sorted(article_items, key=lambda value: _item_score(value, now), reverse=True)
    scene_candidates = [
        item
        for item in ranked_articles
        if item.source in NEWSLIKE_SOURCES and _role(item) == "scene"
    ]
    scene_candidates.sort(key=lambda value: _anchor_score(value, now), reverse=True)
    anchor = scene_candidates[0] if scene_candidates else next(
        (
            item
            for item in ranked_articles
            if item.source in NEWSLIKE_SOURCES
        ),
        ranked_articles[0],
    )
    supports: List[CaseSupport] = []
    for role_name, item in _choose_supports(cluster, now):
        context = None
        if context_fetcher and item.source in NEWSLIKE_SOURCES:
            try:
                context = context_fetcher(item.url)
            except Exception:
                context = None
        supports.append(
            CaseSupport(
                role=role_name,
                item=item,
                note=_support_note(item, context),
                resolved_url=context.final_url if context and context.final_url else item.url,
            )
        )
    support_map = {support.role: support for support in supports}
    frame = _detect_frame(cluster)
    role_count = len(set(support.role for support in supports))
    if len(cluster.items) == 1 and role_count <= 1 and _specificity_score(anchor) < 1.1:
        return None
    cluster_score = (
        _item_score(anchor, now) * 1.8
        + len(article_items) * 0.55
        + len({item.publisher for item in cluster.items}) * 0.25
        + sum(1 for item in article_items if _publisher_quality(item) > 1.0) * 0.9
        + len(supports) * 0.75
    )
    social_support = sum(_item_score(item, now) for item in cluster.items if _is_social(item))
    cluster_score += min(social_support, 12.0) * 0.18
    if "scene" not in support_map:
        cluster_score *= 0.82
    if role_count == 1:
        cluster_score *= 0.58
    elif role_count == 2:
        cluster_score *= 0.82
    headline = _clean_title(anchor)
    return CasePitch(
        slug=_slug_from_terms(anchor, cluster.terms),
        headline=headline,
        summary=_frame_summary(frame, support_map, anchor),
        angle=_frame_angle(frame),
        score=cluster_score,
        evidence=article_items,
        supports=supports,
        terms=set(cluster.terms),
    )


def build_case_pitches(
    items: Iterable[EvidenceItem],
    *,
    now: Optional[datetime] = None,
    top_n: int = 5,
    context_fetcher: Optional[Callable[[str], ArticleContext]] = None,
) -> List[CasePitch]:
    if now is None:
        now = datetime.now(timezone.utc)
    candidates: List[Tuple[EvidenceItem, Set[str]]] = []
    for item in items:
        if not _is_viable_item(item):
            continue
        terms = _extract_terms(item)
        if not terms:
            continue
        candidates.append((item, terms))
    candidates.sort(key=lambda pair: _item_score(pair[0], now), reverse=True)
    clusters: List[_CaseCluster] = []
    for item, terms in candidates:
        best_cluster = None
        best_score = 0.0
        for cluster in clusters:
            similarity = _cluster_similarity(item, terms, cluster)
            if similarity > best_score:
                best_cluster = cluster
                best_score = similarity
        if best_cluster and best_score >= 1.95:
            best_cluster.items.append(item)
            best_cluster.terms.update(terms)
            if item.topic_hint:
                best_cluster.topic_hints.add(item.topic_hint)
            continue
        clusters.append(
            _CaseCluster(
                anchor=item,
                items=[item],
                terms=set(terms),
                topic_hints={item.topic_hint} if item.topic_hint else set(),
            )
        )
    pitches: List[CasePitch] = []
    for cluster in clusters:
        pitch = _cluster_to_pitch(cluster, now, context_fetcher)
        if pitch is None:
            continue
        pitches.append(pitch)
    pitches.sort(key=lambda pitch: pitch.score, reverse=True)
    return pitches[:top_n]
