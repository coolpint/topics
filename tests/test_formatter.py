import unittest
from datetime import datetime, timezone

from topic_pitcher.formatter import format_digest
from topic_pitcher.models import EvidenceItem, TopicDefinition, TopicDigest
from topic_pitcher.ranking import representative_evidence


NOW = datetime(2026, 3, 11, 0, 0, tzinfo=timezone.utc)


class FormatterTests(unittest.TestCase):
    def test_trend_support_does_not_replace_case_headline(self):
        topic = TopicDefinition(
            slug="oil_inflation",
            label="유가 급등과 인플레이션 재점화",
            news_queries=[],
            keywords=["유가", "휘발유값"],
            why_now="",
            reader_fit="",
            article_focus="유가 일반론보다 주유소 가격처럼 바로 체감되는 지점으로 시작해야 한다.",
            reporting_points="주유소 가격표와 운임·유류할증료 중 어디가 먼저 움직였는지 붙이면 된다.",
        )
        digest = TopicDigest(
            topic=topic,
            total_score=10.0,
            social_score=2.0,
            media_score=3.0,
            evidence=[
                EvidenceItem(
                    source="naver_datalab",
                    source_type="trend",
                    title="네이버 검색어 상승: 국제유가 / 휘발유값",
                    url="https://datalab.naver.com",
                    published_at=NOW,
                    publisher="Naver DataLab",
                    metrics={"ratio": 82.0, "delta": 13.0},
                    snippet="유가 급등",
                    audience_region="KR",
                ),
                EvidenceItem(
                    source="google_news_kr",
                    source_type="news",
                    title="주유소 휘발유값 들썩…국제유가 상승 여파 본격화",
                    url="https://example.com/oil",
                    published_at=NOW,
                    publisher="한국경제",
                    metrics={"mentions": 1},
                    snippet="주유소 휘발유값 들썩 국제유가 상승 여파 본격화",
                    audience_region="KR",
                ),
            ],
        )

        message = format_digest([digest], NOW, [])
        self.assertIn("한국경제 | 주유소 휘발유값 들썩", message)
        self.assertNotIn("1. Naver DataLab | 네이버 검색어 상승", message)
        self.assertIn("기사화 포인트: 유가 일반론보다 주유소 가격처럼 바로 체감되는 지점으로 시작해야 한다.", message)
        self.assertIn("발전시키는 법: 주유소 가격표와 운임·유류할증료 중 어디가 먼저 움직였는지 붙이면 된다.", message)
        self.assertIn("실제 기사 메모:", message)
        self.assertIn("기사 근거 링크:", message)
        self.assertIn("- 현장 장면 | 한국경제 | 주유소 휘발유값 들썩…국제유가 상승 여파 본격화 | https://example.com/oil", message)
        self.assertNotIn("검색지수", message)

    def test_representative_evidence_prefers_trusted_publisher(self):
        topic = TopicDefinition(
            slug="trade_tariffs",
            label="관세·무역 리쇼어링과 비용 압박",
            news_queries=[],
            keywords=["관세", "무역"],
            why_now="",
            reader_fit="",
        )
        digest = TopicDigest(
            topic=topic,
            evidence=[
                EvidenceItem(
                    source="google_news",
                    source_type="news",
                    title="Supreme Court blow drives tariff pivot",
                    url="https://example.com/meyka",
                    published_at=NOW,
                    publisher="Meyka",
                    metrics={"mentions": 1},
                    snippet="tariff pivot",
                ),
                EvidenceItem(
                    source="google_news",
                    source_type="news",
                    title="Tariff ruling forces exporters to rethink pricing",
                    url="https://example.com/reuters",
                    published_at=NOW,
                    publisher="Reuters",
                    metrics={"mentions": 1},
                    snippet="tariff ruling exporters pricing",
                ),
            ],
        )

        self.assertEqual(representative_evidence(digest).publisher, "Reuters")

    def test_empty_digest_includes_notice_and_explanation(self):
        message = format_digest(
            [],
            NOW,
            ["reddit: HTTP Error 403: Blocked"],
            notices=["최근 30일 중복 회피 규칙에 걸린 주제만 남아, 이번 발송은 상위 중복 후보를 다시 포함했습니다."],
        )
        self.assertIn("최근 30일 중복 회피 규칙에 걸린 주제만 남아", message)
        self.assertIn("이번 실행에서는 기사화 가능한 신규 토픽을 충분히 확보하지 못했습니다.", message)
        self.assertIn("수집 경고:", message)

    def test_digest_omits_signal_explanations_and_uses_story_links(self):
        topic = TopicDefinition(
            slug="public_service_bottlenecks",
            label="공항·공공서비스 병목과 예산 압박",
            news_queries=[],
            keywords=["airport", "shutdown", "tsa"],
            why_now="",
            reader_fit="",
            article_focus="공항 팁이 아니라 셧다운과 인력 차질이 허브공항 병목으로 드러나는 장면으로 써야 한다.",
            reporting_points="대기시간, 인력, 여행 성수기 영향이 연결되는지 확인하면 된다.",
        )
        digest = TopicDigest(
            topic=topic,
            total_score=20.0,
            social_score=5.0,
            media_score=7.0,
            evidence=[
                EvidenceItem(
                    source="google_news",
                    source_type="news",
                    title="Atlanta airport wait times climbed in the last week amid shutdown - AJC.com",
                    url="https://example.com/ajc",
                    published_at=NOW,
                    publisher="AJC.com",
                    metrics={"mentions": 1},
                    snippet="airport wait times amid shutdown",
                ),
                EvidenceItem(
                    source="google_news",
                    source_type="news",
                    title="TSA Delays Snarl Spring Break Travel Amid DHS Shutdown - thetraveler.org",
                    url="https://example.com/traveler",
                    published_at=NOW,
                    publisher="thetraveler.org",
                    metrics={"mentions": 1},
                    snippet="spring break travel shutdown",
                ),
                EvidenceItem(
                    source="google_news",
                    source_type="news",
                    title="Airport workers miss pay as US government shutdown hits one month - Iraqi News",
                    url="https://example.com/iraqinews",
                    published_at=NOW,
                    publisher="Iraqi News",
                    metrics={"mentions": 1},
                    snippet="airport workers miss pay shutdown",
                ),
                EvidenceItem(
                    source="naver_blog",
                    source_type="social",
                    title="청주 공항 예약 방법 및 면세점 환전 주차 국제선 국내선 식당",
                    url="https://blog.naver.com/example",
                    published_at=NOW,
                    publisher="네이버 블로그",
                    metrics={"total": 7113},
                    snippet="청주 공항 팁",
                    audience_region="KR",
                ),
            ],
        )

        message = format_digest([digest], NOW, [])
        self.assertIn("실제 기사 메모:", message)
        self.assertIn("기사 근거 링크:", message)
        self.assertIn("AJC.com", message)
        self.assertIn("thetraveler.org", message)
        self.assertIn("Iraqi News", message)
        self.assertNotIn("한국 독자 신호", message)
        self.assertNotIn("반응 신호", message)
        self.assertNotIn("큰 그림", message)
        self.assertNotIn("경제 독자 관점", message)
        self.assertNotIn("네이버 블로그", message)


if __name__ == "__main__":
    unittest.main()
