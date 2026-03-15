import unittest
from datetime import datetime, timezone

from topic_pitcher.formatter import format_digest
from topic_pitcher.models import CasePitch, CaseSupport, EvidenceItem


NOW = datetime(2026, 3, 11, 0, 0, tzinfo=timezone.utc)


class FormatterTests(unittest.TestCase):
    def test_case_digest_focuses_on_article_ready_lines(self):
        anchor = EvidenceItem(
            source="google_news",
            source_type="news",
            title="Atlanta airport wait times climbed in the last week amid shutdown - AJC.com",
            url="https://example.com/ajc",
            published_at=NOW,
            publisher="AJC.com",
            metrics={"mentions": 1},
            snippet="Atlanta airport wait times climbed in the last week amid shutdown",
        )
        cause = EvidenceItem(
            source="google_news",
            source_type="news",
            title="TSA Delays Snarl Spring Break Travel Amid DHS Shutdown - thetraveler.org",
            url="https://example.com/traveler",
            published_at=NOW,
            publisher="thetraveler.org",
            metrics={"mentions": 1},
            snippet="TSA delays snarl spring break travel amid DHS shutdown",
        )
        impact = EvidenceItem(
            source="google_news",
            source_type="news",
            title="Airport workers miss pay as US government shutdown hits one month - Iraqi News",
            url="https://example.com/workers",
            published_at=NOW,
            publisher="Iraqi News",
            metrics={"mentions": 1},
            snippet="Airport workers miss pay as US government shutdown hits one month",
        )
        digest = CasePitch(
            slug="atlanta-airport-shutdown",
            headline="Atlanta airport wait times climbed in the last week amid shutdown",
            summary="애틀랜타 공항 대기시간 상승이 현장으로 잡혔다. 셧다운과 TSA 운영 차질이 배경으로 붙는다. 여행 성수기 수요와 겹치며 공항 병목이 소비자 불편으로 번지는 그림이다.",
            angle="셧다운이 공항 혼잡과 여행 소비 차질로 번지는 구조",
            score=10.0,
            evidence=[anchor, cause, impact],
            supports=[
                CaseSupport(role="scene", item=anchor, note="애틀랜타 공항 대기시간이 지난주 들어 더 길어졌다는 현장 기사다."),
                CaseSupport(role="cause", item=cause, note="DHS 셧다운으로 TSA 지연이 여행 성수기와 충돌했다는 배경 기사다."),
                CaseSupport(role="impact", item=impact, note="공항 노동자 급여 차질이 장기화되며 운영 부담이 커졌다는 파급 기사다."),
            ],
            terms={"atlanta", "airport", "shutdown", "tsa"},
        )

        message = format_digest([digest], NOW, [])
        self.assertIn("기사 한 줄:", message)
        self.assertIn("기사 초점:", message)
        self.assertIn("근거:", message)
        self.assertIn("- 현장 | AJC.com | 애틀랜타 공항 대기시간이 지난주 들어 더 길어졌다는 현장 기사다. | https://example.com/ajc", message)
        self.assertNotIn("왜 뽑았나", message)
        self.assertNotIn("발전시키는 법", message)
        self.assertNotIn("한국 독자 신호", message)
        self.assertNotIn("반응 신호", message)

    def test_empty_digest_still_reports_errors(self):
        message = format_digest([], NOW, ["reddit: HTTP Error 403: Blocked"], notices=["최근 30일 안에 다룬 유사 사례 4건은 제외했습니다."])
        self.assertIn("최근 30일 안에 다룬 유사 사례 4건은 제외했습니다.", message)
        self.assertIn("이번 실행에서는 기사화 가능한 신규 사례를 충분히 확보하지 못했습니다.", message)
        self.assertIn("수집 경고:", message)


if __name__ == "__main__":
    unittest.main()
