import re
from datetime import datetime, timedelta, timezone
from typing import Iterable, List, Optional, Tuple

from .models import EvidenceItem, TopicDigest
from .ranking import TREND_ONLY_SOURCES, representative_evidence, summarize_reason


KST = timezone(timedelta(hours=9))
STORY_LINK_EXCLUDED_SOURCES = {"naver_news", "naver_datalab", "naver_blog", "naver_cafe"}
SCENE_HINTS = (
    "wait",
    "delay",
    "queue",
    "line",
    "climbed",
    "surge",
    "drop",
    "rose",
    "rises",
    "miss pay",
    "buyers",
    "workers",
    "factory",
    "airport",
    "terminal",
    "주유소",
    "대기",
    "상승",
    "급등",
    "작업",
    "현장",
    "공항",
)
CAUSE_HINTS = (
    "shutdown",
    "budget",
    "staffing",
    "hiring",
    "court",
    "tariff",
    "rate",
    "fed",
    "inflation",
    "payroll",
    "power",
    "energy",
    "supply",
    "투자",
    "셧다운",
    "예산",
    "인력",
    "관세",
    "금리",
    "연준",
    "전력",
    "공급망",
)
IMPACT_HINTS = (
    "business",
    "travel",
    "consumer",
    "market",
    "exports",
    "homebuying",
    "mortgage",
    "stocks",
    "economy",
    "spring break",
    "수요",
    "소비자",
    "수출",
    "주택",
    "여행",
    "시장",
    "경기",
)


def _display_headline(digest: TopicDigest, max_length: int = 90) -> str:
    item = representative_evidence(digest)
    if not item:
        return digest.topic.label
    publisher = (item.publisher or item.source).strip()
    headline = "{} | {}".format(publisher, item.title.strip())
    if len(headline) <= max_length:
        return headline
    return headline[: max_length - 3].rstrip() + "..."


def _display_evidence(digest: TopicDigest, max_count: int) -> List[EvidenceItem]:
    ordered: List[EvidenceItem] = []
    representative = representative_evidence(digest)
    if representative:
        ordered.append(representative)
    for item in digest.evidence:
        if item in ordered:
            continue
        if item.source in TREND_ONLY_SOURCES and ordered:
            continue
        ordered.append(item)
        if len(ordered) >= max_count:
            break
    if ordered:
        return ordered[:max_count]
    return digest.evidence[:max_count]


def _clean_title(item: EvidenceItem) -> str:
    title = re.sub(r"\s+", " ", item.title).strip()
    publisher = (item.publisher or "").strip()
    if publisher:
        for suffix in (" - {}".format(publisher), " | {}".format(publisher)):
            if title.endswith(suffix):
                title = title[: -len(suffix)].rstrip()
    return title


def _story_role(item: EvidenceItem) -> str:
    haystack = "{} {}".format(item.title, item.snippet).lower()
    scene_hits = sum(1 for term in SCENE_HINTS if term in haystack)
    cause_hits = sum(1 for term in CAUSE_HINTS if term in haystack)
    impact_hits = sum(1 for term in IMPACT_HINTS if term in haystack)
    if scene_hits >= max(cause_hits, impact_hits) and scene_hits > 0:
        return "현장 장면"
    if cause_hits >= impact_hits and cause_hits > 0:
        return "원인·배경"
    if impact_hits > 0:
        return "파급"
    return "확인 근거"


def _story_evidence(digest: TopicDigest, max_count: int = 3) -> List[Tuple[str, EvidenceItem]]:
    candidates = []
    for item in digest.evidence:
        if item.source in STORY_LINK_EXCLUDED_SOURCES:
            continue
        if item.url in {e.url for _, e in candidates}:
            continue
        candidates.append((_story_role(item), item))
    if not candidates:
        return []
    selected: List[Tuple[str, EvidenceItem]] = []
    used_publishers = set()
    for role in ("현장 장면", "원인·배경", "파급"):
        match = next(
            (
                pair
                for pair in candidates
                if pair[0] == role and (pair[1].publisher or pair[1].source) not in used_publishers
            ),
            None,
        )
        if not match:
            continue
        selected.append(match)
        used_publishers.add(match[1].publisher or match[1].source)
        if len(selected) >= max_count:
            return selected
    for pair in candidates:
        publisher = pair[1].publisher or pair[1].source
        if publisher in used_publishers:
            continue
        selected.append(pair)
        used_publishers.add(publisher)
        if len(selected) >= max_count:
            break
    return selected


def _story_memo(digest: TopicDigest) -> Optional[str]:
    story_evidence = _story_evidence(digest)
    if not story_evidence:
        return None
    fragments = []
    for role, item in story_evidence:
        fragments.append("{}은 '{}'".format(role, _clean_title(item)))
    memo = "실제 기사 메모: {}가 같이 보입니다.".format(", ".join(fragments))
    if digest.topic.article_focus:
        memo += " 기사 초점은 {} ".format(digest.topic.article_focus.rstrip("."))
    return memo.strip()


def format_digest(
    digests: Iterable[TopicDigest],
    generated_at: datetime,
    errors: List[str],
    notices: List[str] = None,
    max_evidence_per_topic: int = 2,
) -> str:
    digest_list = list(digests)
    lines = []
    lines.append("[경제 발제 랭킹] {}".format(generated_at.astimezone(KST).strftime("%Y-%m-%d %H:%M KST")))
    lines.append("")
    for notice in notices or []:
        lines.append(notice)
    if notices:
        lines.append("")
    for index, digest in enumerate(digest_list, start=1):
        lines.append("{}. {}".format(index, _display_headline(digest)))
        lines.append("이 사례로 보는 흐름: {}".format(digest.topic.label))
        lines.append(
            "점수 {:.2f} | 소셜 {:.2f} | 뉴스 {:.2f}".format(
                digest.total_score,
                digest.social_score,
                digest.media_score,
            )
        )
        for reason in summarize_reason(digest):
            lines.append(reason)
        story_memo = _story_memo(digest)
        if story_memo:
            lines.append(story_memo)
        lines.append("기사 근거 링크:")
        story_links = _story_evidence(digest, max_evidence_per_topic + 1)
        for role, item in story_links or [("확인 근거", evidence) for evidence in _display_evidence(digest, max_evidence_per_topic)]:
            lines.append(
                "- {} | {} | {} | {}".format(
                    role,
                    item.publisher or item.source,
                    _clean_title(item),
                    item.url,
                )
            )
        lines.append("")
    if not digest_list:
        lines.append("이번 실행에서는 기사화 가능한 신규 토픽을 충분히 확보하지 못했습니다.")
        lines.append("")
    if errors:
        lines.append("수집 경고:")
        for error in errors:
            lines.append("- {}".format(error))
    return "\n".join(lines).strip()
