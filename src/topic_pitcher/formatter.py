from datetime import datetime, timedelta, timezone
from typing import Iterable, List

from .models import CasePitch


KST = timezone(timedelta(hours=9))
ROLE_LABELS = {
    "scene": "현장",
    "cause": "배경",
    "impact": "파급",
    "fact": "근거",
}


def _trim(text: str, limit: int = 180) -> str:
    text = " ".join((text or "").split()).strip()
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip(" ,.;:") + "..."


def format_digest(
    digests: Iterable[CasePitch],
    generated_at: datetime,
    errors: List[str],
    notices: List[str] = None,
) -> str:
    digest_list = list(digests)
    lines = []
    lines.append("[경제 발제] {}".format(generated_at.astimezone(KST).strftime("%Y-%m-%d %H:%M KST")))
    lines.append("")
    for notice in notices or []:
        lines.append(notice)
    if notices:
        lines.append("")
    for index, digest in enumerate(digest_list, start=1):
        lines.append("{}. {}".format(index, digest.headline))
        lines.append("발제: {}".format(_trim(digest.summary, 320)))
        if digest.plan_points:
            lines.append("기사 구성:")
            for point in digest.plan_points[:4]:
                lines.append("- {}".format(_trim(point, 140)))
        lines.append("근거 기사:")
        for support in digest.supports[:3]:
            lines.append(
                "- {} | {} | {} | {}".format(
                    ROLE_LABELS.get(support.role, "근거"),
                    support.item.publisher or support.item.source,
                    _trim(support.note or support.item.title, 200),
                    support.resolved_url or support.item.url,
                )
            )
        lines.append("")
    if not digest_list:
        lines.append("이번 실행에서는 기사화 가능한 신규 사례를 충분히 확보하지 못했습니다.")
        lines.append("")
    if errors:
        lines.append("수집 경고:")
        for error in errors:
            lines.append("- {}".format(error))
    return "\n".join(lines).strip()
