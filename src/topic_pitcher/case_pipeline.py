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
PRIMARY_ARTICLE_SOURCES = {"google_news", "google_news_kr"}
DISCOVERY_SOURCES = {"google_news", "google_news_kr", "mastodon"}
GENERIC_NOTE_MARKERS = (
    "enjoy the videos and music you love",
    "upload original content",
    "share it all with friends",
    "watch the video",
    "comprehensive up-to-date news coverage",
)
MACRO_SENSITIVE_FRAMES = {"jobs", "housing", "china", "trade", "ai_power", "oil"}
FRAME_TAKEAWAYS = {
    "airport": "이 사안의 핵심은 예산·인력 문제가 공항 현장의 대기줄과 여행 소비 불편으로 전가된다는 점이다.",
    "oil": "핵심은 지정학 이슈가 추상적인 유가 전망이 아니라 운임·주유소 가격·생활물가 압박으로 내려온다는 데 있다.",
    "housing": "핵심은 금리 방향보다 먼저 실수요자와 매도자의 행동이 바뀌고 있다는 점이다.",
    "ai_power": "핵심은 AI 투자 경쟁의 병목이 모델이 아니라 전력망과 설비 계약이라는 점이다.",
    "jobs": "핵심은 지표 한 줄이 아니라 그 해석 변화가 대출금리와 자산가격 판단까지 건드린다는 점이다.",
    "defense": "핵심은 방산 호황이 주문 규모보다 생산능력과 납기 관리에서 승부가 난다는 점이다.",
    "pet": "핵심은 취향 소비처럼 보이는 지출이 실제로는 새 서비스 산업을 키우고 있다는 점이다.",
    "trade": "핵심은 정책 변화가 결국 기업의 가격·재고·조달 전략을 바꾸는 비용 이슈라는 점이다.",
    "nuclear": "핵심은 폐로 현장 노동과 기술 문제가 원전 비용과 지역 산업 문제로 이어진다는 점이다.",
    "china": "핵심은 중국 수요 회복을 거시지표가 아니라 현장 산업 수요와 물동량으로 읽어야 한다는 점이다.",
    "generic": "핵심은 현장에서 벌어진 변화가 비용, 수요, 투자 판단으로 번지는 경로를 보여주는 데 있다.",
}
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
        "cost",
        "costs",
        "exports",
        "homebuying",
        "mortgage",
        "market",
        "rates",
        "stocks",
        "spring break",
        "surcharge",
        "운임",
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
    if item.source in DISCOVERY_SOURCES:
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


def _case_hint(anchor: EvidenceItem, cluster_terms: Set[str]) -> str:
    location = _location_hint(anchor)
    if location:
        return location
    for term in sorted(cluster_terms, key=lambda value: (-len(value), value)):
        if len(term) < 4:
            continue
        if term in GENERIC_ECON_TERMS or term in CASE_STOPWORDS:
            continue
        return term
    return ""


def _clean_note_text(text: str) -> str:
    cleaned = " ".join((text or "").split()).strip()
    if not cleaned:
        return ""
    lowered = cleaned.lower()
    if any(marker in lowered for marker in GENERIC_NOTE_MARKERS):
        return ""
    return cleaned.rstrip()


def _support_note(item: EvidenceItem, context: Optional[ArticleContext]) -> str:
    for candidate in (
        context.summary if context else "",
        item.snippet,
        _clean_title(item),
    ):
        cleaned = _clean_note_text(candidate)
        if cleaned:
            return cleaned
    return _clean_title(item)


def _is_reportable_article(item: EvidenceItem) -> bool:
    return item.source in PRIMARY_ARTICLE_SOURCES and _publisher_quality(item) >= 0.75


def _support_text(support: Optional[CaseSupport]) -> str:
    if not support:
        return ""
    return _clean_note_text(support.note or support.item.snippet or _clean_title(support.item))


def _render_point(label: str, text: str) -> str:
    cleaned = _clean_note_text(text)
    if not cleaned:
        return ""
    return "{}: {}".format(label, cleaned.rstrip("."))


def _frame_headline(frame: str, anchor: EvidenceItem, cluster_terms: Set[str]) -> str:
    hint = _case_hint(anchor, cluster_terms)
    if frame == "airport":
        return "{} 공항 대기줄이 길어진 이유, 셧다운이 여행 성수기를 덮쳤다".format(hint or "허브")
    if frame == "oil":
        return "{} 공급 차질이 기름값을 다시 흔드는 이유".format(hint or "원유 수송로")
    if frame == "housing":
        return "{} 사례로 본 금리 변곡점 이후 주택 실수요 변화".format(hint or "최근 시장")
    if frame == "ai_power":
        return "{} 사례로 본 AI 전력 병목".format(hint or "데이터센터 투자")
    if frame == "jobs":
        return "{}를 앞두고 물가와 고용이 충돌했다".format(hint or "Fed 회의")
    if frame == "defense":
        return "{} 사례로 본 K-방산 호황의 병목".format(hint or "방산 수출")
    if frame == "pet":
        return "{} 사례로 본 반려동물 프리미엄 소비".format(hint or "펫케어")
    if frame == "trade":
        return "{} 변수 하나가 기업 비용을 바꿨다".format(hint or "관세")
    if frame == "nuclear":
        return "{} 폐로 현장이 보여준 원전 경제".format(hint or "후쿠시마")
    if frame == "china":
        return "{} 사례로 읽는 중국 수요의 온도차".format(hint or "수출 현장")
    return _clean_title(anchor)


def _frame_summary(frame: str, supports: Dict[str, CaseSupport], anchor: EvidenceItem) -> str:
    location = _location_hint(anchor) or "현장"
    if frame == "airport":
        return (
            "{} 공항 대기시간 급증은 단순한 여행 팁이 아니라 연방 예산 차질이 여행 소비 현장에 닿는 장면이다. "
            "셧다운 여파로 흔들린 TSA 운영이 성수기 수요와 겹치면서 혼잡과 서비스 부담이 커졌고, "
            "결국 공항 병목이 승객 불편과 운영 비용 문제로 번졌다는 흐름이 선명하다."
        ).format(location)
    if frame == "oil":
        return (
            "{} 공급 차질은 추상적인 유가 전망이 아니라 실제 운임과 주유소 가격 압박으로 이어질 수 있는 사례다. "
            "전쟁·해상 리스크와 수송 우회 비용이 겹치면서, 에너지 이슈가 생활물가와 기업 비용 문제로 내려오는 경로가 드러난다."
        ).format(location)
    if frame == "housing":
        return (
            "이 사례는 금리 방향이 바뀌는 순간 실제 주택 매수자와 매도자의 판단이 어떻게 달라지는지 보여준다. "
            "대출금리, 재고, 매도자 기대가 함께 움직이면서 시장 회복의 속도가 갈리는 장면으로 읽을 수 있다."
        )
    if frame == "ai_power":
        return (
            "AI 투자 붐의 진짜 병목이 모델 경쟁이 아니라 전력망과 설비 계약이라는 점을 보여주는 사례다. "
            "데이터센터 증설이 전기요금, 변압기, 전력 계약 문제와 부딪히며 투자 속도와 비용 구조를 동시에 흔든다."
        )
    if frame == "jobs":
        return (
            "이번 사례는 Fed 회의를 앞두고 물가와 고용 지표가 엇갈릴 때 시장이 왜 방향을 잃는지 보여준다. "
            "문제는 숫자 자체보다 해석의 변화가 대출금리와 자산가격 판단으로 바로 번진다는 점이다."
        )
    if frame == "defense":
        return (
            "이 사례는 K-방산 호황의 핵심 병목이 수주 숫자보다 생산능력과 납기 관리에 있다는 점을 보여준다. "
            "주문 확대가 곧바로 실적으로 이어지지 않고, 공장 증설과 협력사 조달 부담이 함께 커지는 구조가 드러난다."
        )
    if frame == "pet":
        return (
            "이 사례는 반려동물 소비가 단순한 사치가 아니라 고가 서비스 산업으로 커지고 있음을 보여준다. "
            "가계의 취향 지출이 미용, 돌봄, 보험 같은 세분 시장을 키우는 흐름으로 읽을 수 있다."
        )
    if frame == "trade":
        return (
            "이 사례는 관세나 법원 변수 같은 정책 변화가 실제 기업 비용과 재고 전략을 어떻게 바꾸는지 보여준다. "
            "무역 뉴스가 추상적인 정책 논쟁이 아니라 가격과 조달 문제라는 점이 드러난다."
        )
    if frame == "nuclear":
        return (
            "이 사례는 폐로 현장 노동과 기술 문제가 원전 비용과 지역경제 문제로 이어지는 장면을 보여준다. "
            "에너지 정책이 결국 사람과 작업 현장의 비용으로 나타난다는 점이 선명하다."
        )
    if frame == "china":
        return (
            "이 사례는 중국 경기 회복을 거시 숫자보다 현장 수요와 물동량으로 읽어야 한다는 점을 보여준다. "
            "내수와 수출의 온도차가 산업별 수혜와 리스크를 다르게 만든다는 흐름이 잡힌다."
        )
    scene = _support_text(supports.get("scene"))
    cause = _support_text(supports.get("cause"))
    impact = _support_text(supports.get("impact"))
    parts = [part for part in (scene, cause, impact) if part]
    if not parts:
        parts.append(_clean_title(anchor))
    parts.append(FRAME_TAKEAWAYS.get(frame, FRAME_TAKEAWAYS["generic"]))
    return " ".join(part.rstrip(".") + "." for part in parts)


def _plan_points(frame: str, supports: Dict[str, CaseSupport], anchor: EvidenceItem) -> List[str]:
    location = _location_hint(anchor) or "현장"
    points: List[str] = []
    if frame == "airport":
        points.append("현장: {} 공항에서 보안검색 대기시간이 최근 실제로 길어졌다는 보도가 나왔다".format(location))
        points.append("배경: 셧다운 여파로 TSA 운영 차질이 여행 성수기 수요와 겹쳤다")
        points.append("파급: 승객 불편뿐 아니라 공항 운영 부담과 여행 소비 차질이 함께 커지고 있다")
        return points
    if frame == "oil":
        points.append("현장: {} 관련 공급 차질이 유가 전망이 아니라 실제 운임과 정제 비용 문제로 번지고 있다".format(location))
        points.append("배경: 전쟁·해상 리스크와 우회 운송 비용이 공급망을 흔들고 있다")
        points.append("파급: 결국 주유소 가격과 생활물가 압박으로 연결될 수 있다")
        return points
    if frame == "housing":
        points.append("현장: 금리 방향 변화에 따라 주택 실수요자의 매수·대기 판단이 갈리고 있다")
        points.append("배경: 대출금리뿐 아니라 재고와 매도자 기대가 함께 움직이고 있다")
        points.append("파급: 거래량 회복과 가격 반등의 속도가 지역별로 달라질 수 있다")
        return points
    if frame == "ai_power":
        points.append("현장: 데이터센터 증설이 전력망, 변압기, 전력 계약 문제와 부딪히고 있다")
        points.append("배경: AI 투자 속도를 전력 인프라가 따라가지 못하고 있다")
        points.append("파급: 기업 CAPEX와 전기요금 전가 부담이 동시에 커진다")
        return points
    if frame == "jobs":
        points.append("현장: Fed 회의를 앞두고 물가와 고용 지표가 엇갈리며 시장 해석이 갈리고 있다")
        points.append("배경: 고용 둔화 우려와 물가 상방 압력이 동시에 남아 있다")
        points.append("파급: 주식·채권뿐 아니라 모기지와 대출금리 판단에도 바로 연결된다")
        return points
    if frame == "defense":
        points.append("현장: 방산 주문 확대가 실제 공장 증설과 납기 관리 문제로 이어지고 있다")
        points.append("배경: 완성품 수주보다 협력사 부품 조달과 생산능력 확보가 더 큰 병목으로 떠오른다")
        points.append("파급: 수출 호황이 곧바로 실적으로 이어지지 않고 CAPEX 부담과 납기 리스크를 키운다")
        return points
    if frame == "pet":
        points.append("현장: 반려동물 관련 고가 서비스 소비가 빠르게 커지고 있다")
        points.append("배경: 미용·돌봄·보험처럼 세분화된 서비스 시장이 붙고 있다")
        points.append("파급: 취향 지출이 하나의 생활서비스 산업으로 굳어지고 있다")
        return points
    if frame == "trade":
        points.append("현장: 정책·법원 변수 하나가 기업 가격과 재고 전략을 흔들고 있다")
        points.append("배경: 관세와 조달 비용 변화가 공급망 운영 방식까지 바꾸고 있다")
        points.append("파급: 수출 기업과 소비자 가격에 동시에 영향을 줄 수 있다")
        return points
    if frame == "nuclear":
        points.append("현장: 폐로 작업 현장 인력과 기술 문제가 계속 드러나고 있다")
        points.append("배경: 작업 난도와 장기 비용 부담이 예상보다 크다")
        points.append("파급: 원전 경제성과 지역 산업 문제를 함께 다시 보게 만든다")
        return points
    if frame == "china":
        points.append("현장: 중국 수요 회복이 일부 산업과 물동량에서만 먼저 나타난다")
        points.append("배경: 내수와 수출의 회복 속도가 다르게 움직이고 있다")
        points.append("파급: 한국 기업별 수혜와 리스크가 더 선명하게 갈릴 수 있다")
        return points
    for role_name, label in (("scene", "현장"), ("cause", "배경"), ("impact", "파급")):
        point = _render_point(label, _support_text(supports.get(role_name)))
        if point:
            points.append(point)
    if not points:
        points.append("근거: {}".format(_clean_title(anchor)))
    points.append("쟁점: {}".format(FRAME_TAKEAWAYS.get(frame, FRAME_TAKEAWAYS["generic"]).rstrip(".")))
    return points[:4]


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
    reportable_articles = [item for item in cluster.items if _is_reportable_article(item)]
    if not reportable_articles:
        return None
    ranked_articles = sorted(reportable_articles, key=lambda value: _item_score(value, now), reverse=True)
    scene_candidates = [
        item
        for item in ranked_articles
        if _role(item) == "scene"
    ]
    scene_candidates.sort(key=lambda value: _anchor_score(value, now), reverse=True)
    anchor = scene_candidates[0] if scene_candidates else next(
        (item for item in ranked_articles),
        ranked_articles[0],
    )
    if len(reportable_articles) == 1 and _publisher_quality(anchor) < 1.2:
        return None
    supports: List[CaseSupport] = []
    article_cluster = _CaseCluster(
        anchor=anchor,
        items=reportable_articles,
        terms=set(cluster.terms),
        topic_hints=set(cluster.topic_hints),
    )
    for role_name, item in _choose_supports(article_cluster, now):
        context = None
        if context_fetcher and item.source in PRIMARY_ARTICLE_SOURCES:
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
    if "scene" not in support_map:
        return None
    if role_count < 2:
        return None
    if frame in MACRO_SENSITIVE_FRAMES and _specificity_score(anchor) < 0.9:
        return None
    if len(reportable_articles) == 1 and role_count <= 1 and _specificity_score(anchor) < 1.1:
        return None
    cluster_score = (
        _item_score(anchor, now) * 1.8
        + len(reportable_articles) * 0.75
        + len({item.publisher for item in cluster.items}) * 0.25
        + sum(1 for item in reportable_articles if _publisher_quality(item) > 1.0) * 0.9
        + len(supports) * 0.75
    )
    social_support = sum(_item_score(item, now) for item in cluster.items if _is_social(item))
    cluster_score += min(social_support, 10.0) * 0.08
    headline = _frame_headline(frame, anchor, cluster.terms)
    return CasePitch(
        slug=_slug_from_terms(anchor, cluster.terms),
        headline=headline,
        summary=_frame_summary(frame, support_map, anchor),
        angle=FRAME_TAKEAWAYS.get(frame, FRAME_TAKEAWAYS["generic"]),
        score=cluster_score,
        evidence=reportable_articles,
        supports=supports,
        terms=set(cluster.terms),
        plan_points=_plan_points(frame, support_map, anchor),
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
