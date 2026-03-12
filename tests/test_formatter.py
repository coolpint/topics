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


if __name__ == "__main__":
    unittest.main()
