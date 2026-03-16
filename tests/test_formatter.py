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
            headline="애틀랜타 공항 대기줄이 길어진 이유, 셧다운이 여행 성수기를 덮쳤다",
            summary="애틀랜타 공항 대기시간 급증은 단순한 여행 팁이 아니라 연방 예산 차질이 여행 소비 현장에 닿는 장면이다. 셧다운 여파로 흔들린 TSA 운영이 성수기 수요와 겹치면서 혼잡과 서비스 부담이 커졌고, 결국 공항 병목이 승객 불편과 운영 비용 문제로 번졌다는 흐름이 선명하다.",
            angle="이 사안의 핵심은 예산·인력 문제가 공항 현장의 대기줄과 여행 소비 불편으로 전가된다는 점이다.",
            score=10.0,
            evidence=[anchor, cause, impact],
            supports=[
                CaseSupport(role="scene", item=anchor, note="애틀랜타 공항 대기시간이 지난주 들어 더 길어졌다는 현장 기사다."),
                CaseSupport(role="cause", item=cause, note="DHS 셧다운으로 TSA 지연이 여행 성수기와 충돌했다는 배경 기사다."),
                CaseSupport(role="impact", item=impact, note="공항 노동자 급여 차질이 장기화되며 운영 부담이 커졌다는 파급 기사다."),
            ],
            terms={"atlanta", "airport", "shutdown", "tsa"},
            plan_points=[
                "현장: 애틀랜타 공항에서 보안검색 대기시간이 최근 실제로 길어졌다는 보도가 나왔다",
                "배경: 셧다운 여파로 TSA 운영 차질이 여행 성수기 수요와 겹쳤다",
                "파급: 승객 불편뿐 아니라 공항 운영 부담과 여행 소비 차질이 함께 커지고 있다",
            ],
        )

        message = format_digest([digest], NOW, [])
        self.assertIn("[경제 발제]", message)
        self.assertIn("발제:", message)
        self.assertIn("기사 구성:", message)
        self.assertIn("근거 기사:", message)
        self.assertIn("- 현장: 애틀랜타 공항에서 보안검색 대기시간이 최근 실제로 길어졌다는 보도가 나왔다", message)
        self.assertIn("- 현장 | AJC.com | 애틀랜타 공항 대기시간이 지난주 들어 더 길어졌다는 현장 기사다. | https://example.com/ajc", message)
        self.assertNotIn("기사 한 줄", message)
        self.assertNotIn("기사 초점", message)
        self.assertNotIn("한국 독자 신호", message)
        self.assertNotIn("반응 신호", message)

    def test_empty_digest_still_reports_errors(self):
        message = format_digest([], NOW, ["reddit: HTTP Error 403: Blocked"], notices=["최근 30일 안에 다룬 유사 사례 4건은 제외했습니다."])
        self.assertIn("최근 30일 안에 다룬 유사 사례 4건은 제외했습니다.", message)
        self.assertIn("이번 실행에서는 기사화 가능한 신규 사례를 충분히 확보하지 못했습니다.", message)
        self.assertIn("수집 경고:", message)


if __name__ == "__main__":
    unittest.main()
