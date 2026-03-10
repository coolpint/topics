import unittest
from datetime import datetime, timezone

from topic_pitcher.models import EvidenceItem, TopicDefinition
from topic_pitcher.history import select_fresh_topics
from topic_pitcher.ranking import looks_economic, rank_topics
from topic_pitcher.taxonomy import TOPIC_DEFINITIONS


NOW = datetime(2026, 3, 9, 0, 0, tzinfo=timezone.utc)


def make_item(source, title, metrics, source_type="social", publisher="test"):
    return EvidenceItem(
        source=source,
        source_type=source_type,
        title=title,
        url="https://example.com/{}".format(title.replace(" ", "-")),
        published_at=NOW,
        publisher=publisher,
        metrics=metrics,
        snippet=title,
    )


class RankingTests(unittest.TestCase):
    def test_filters_non_economic_noise(self):
        item = make_item("reddit", "Oscars celebrity fashion recap", {"score": 100, "comments": 20})
        self.assertFalse(looks_economic(item))

    def test_recognizes_korean_economic_keywords(self):
        item = make_item("google_news_kr", "국제유가 급등에 한국 수입물가 압박", {"mentions": 1}, source_type="news")
        self.assertTrue(looks_economic(item))

    def test_cross_source_topic_ranking_prefers_macro_signal(self):
        items = [
            make_item(
                "reddit",
                "US jobs report shows payroll losses and higher unemployment as Fed rate cut bets shift",
                {"score": 800, "comments": 160},
                publisher="r/Economics",
            ),
            make_item(
                "google_news",
                "US jobs report weakens as investors debate next Fed move",
                {"mentions": 1},
                source_type="news",
                publisher="AP",
            ),
            make_item(
                "reddit",
                "AI data center electricity demand jumps as utilities brace for higher load",
                {"score": 150, "comments": 30},
                publisher="r/Futurology",
            ),
        ]
        ranked = rank_topics(items, TOPIC_DEFINITIONS, now=NOW, top_n=2)
        self.assertEqual(ranked[0].topic.slug, "us_jobs_fed")
        self.assertGreater(ranked[0].total_score, ranked[1].total_score)

    def test_korean_signal_boosts_korea_relevant_topic(self):
        topic = TopicDefinition(
            slug="oil_inflation",
            label="유가 급등과 인플레이션 재점화",
            news_queries=[],
            keywords=["유가", "국제유가", "인플레이션"],
            why_now="",
            reader_fit="",
            korea_queries=["국제유가 물가 환율"],
            korea_relevance=1.25,
        )
        items = [
            EvidenceItem(
                source="google_news_kr",
                source_type="news",
                title="국제유가 상승에 한국 소비자물가 우려 확대",
                url="https://example.com/kr-oil",
                published_at=NOW,
                publisher="한국경제",
                topic_hint="oil_inflation",
                metrics={"mentions": 1},
                snippet="국제유가 상승 한국 소비자물가 우려 확대",
                audience_region="KR",
            )
        ]
        ranked = rank_topics(items, [topic], now=NOW, top_n=1)
        self.assertEqual(ranked[0].topic.slug, "oil_inflation")
        self.assertGreater(ranked[0].total_score, 3.0)

    def test_recent_topic_history_filters_similar_slug(self):
        topic = TopicDefinition(
            slug="premium_pet_spending",
            label="반려동물 프리미엄 소비와 펫서비스 산업",
            news_queries=[],
            keywords=["반려동물", "미용", "펫서비스"],
            why_now="",
            reader_fit="",
            korea_queries=["반려동물 미용 프리미엄 소비"],
            korea_relevance=1.2,
            story_bias=1.3,
        )
        digest = rank_topics(
            [
                EvidenceItem(
                    source="google_news_kr",
                    source_type="news",
                    title="반려동물 미용 프리미엄 소비가 커지며 펫서비스 산업 확대",
                    url="https://example.com/pet",
                    published_at=NOW,
                    publisher="한국경제",
                    topic_hint="premium_pet_spending",
                    metrics={"mentions": 1},
                    snippet="반려동물 미용 프리미엄 소비 펫서비스 산업 확대",
                    audience_region="KR",
                )
            ],
            [topic],
            now=NOW,
            top_n=1,
        )
        fresh, skipped = select_fresh_topics(
            digest,
            [
                {
                    "sent_at": NOW.isoformat(),
                    "slug": "premium_pet_spending",
                    "label": "반려동물 프리미엄 소비와 펫서비스 산업",
                    "terms": ["반려동물", "미용", "펫서비스"],
                }
            ],
            NOW,
            limit=1,
        )
        self.assertEqual(fresh, [])
        self.assertEqual(skipped, ["반려동물 프리미엄 소비와 펫서비스 산업"])


if __name__ == "__main__":
    unittest.main()
