import unittest
from datetime import datetime, timezone

from topic_pitcher.formatter import format_digest
from topic_pitcher.models import EvidenceItem, TopicDefinition, TopicDigest


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


if __name__ == "__main__":
    unittest.main()
