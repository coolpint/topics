from datetime import datetime, timedelta, timezone
from typing import Iterable, List

from .models import EvidenceItem, TopicDigest
from .ranking import TREND_ONLY_SOURCES, representative_evidence, summarize_reason


KST = timezone(timedelta(hours=9))


def _metric_summary(item: EvidenceItem) -> str:
    if item.source == "reddit":
        return "업보트 {:.0f} / 댓글 {:.0f}".format(
            item.metrics.get("score", 0.0),
            item.metrics.get("comments", 0.0),
        )
    if item.source == "hacker_news":
        return "점수 {:.0f} / 댓글 {:.0f}".format(
            item.metrics.get("score", 0.0),
            item.metrics.get("comments", 0.0),
        )
    if item.source == "youtube":
        return "조회수 {:.0f} / 좋아요 {:.0f} / 댓글 {:.0f}".format(
            item.metrics.get("views", 0.0),
            item.metrics.get("likes", 0.0),
            item.metrics.get("comments", 0.0),
        )
    if item.source == "bluesky":
        return "좋아요 {:.0f} / 리포스트 {:.0f} / 답글 {:.0f}".format(
            item.metrics.get("likes", 0.0),
            item.metrics.get("reposts", 0.0),
            item.metrics.get("replies", 0.0),
        )
    if item.source == "mastodon":
        return "공유 {:.0f} / 계정 {:.0f}".format(
            item.metrics.get("uses", 0.0),
            item.metrics.get("accounts", 0.0),
        )
    if item.source == "naver_blog":
        return "블로그 결과 {:.0f}".format(item.metrics.get("total", 0.0))
    if item.source == "naver_cafe":
        return "카페 결과 {:.0f}".format(item.metrics.get("total", 0.0))
    if item.source == "naver_news":
        return "검색 노출량 {:.0f}".format(item.metrics.get("total", 0.0))
    if item.source == "naver_datalab":
        return "검색지수 {:.1f} / 변화 {:+.1f}".format(
            item.metrics.get("ratio", 0.0),
            item.metrics.get("delta", 0.0),
        )
    if item.source == "google_news_kr":
        return "한국 매체 확산 신호"
    return "매체 확산 신호"


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


def format_digest(
    digests: Iterable[TopicDigest],
    generated_at: datetime,
    errors: List[str],
    max_evidence_per_topic: int = 2,
) -> str:
    lines = []
    lines.append("[경제 발제 랭킹] {}".format(generated_at.astimezone(KST).strftime("%Y-%m-%d %H:%M KST")))
    lines.append("")
    for index, digest in enumerate(digests, start=1):
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
        lines.append("근거 링크:")
        for item in _display_evidence(digest, max_evidence_per_topic):
            lines.append(
                "- {} | {} | {}".format(
                    item.publisher or item.source,
                    _metric_summary(item),
                    item.url,
                )
            )
        lines.append("")
    if errors:
        lines.append("수집 경고:")
        for error in errors:
            lines.append("- {}".format(error))
    return "\n".join(lines).strip()
