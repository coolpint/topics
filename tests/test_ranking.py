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

    def test_concrete_story_outranks_broader_macro_topic(self):
        items = [
            make_item(
                "reddit",
                "TSA lines stretch through airport terminal as budget fight freezes hiring",
                {"score": 220, "comments": 70},
                publisher="r/news",
            ),
            make_item(
                "google_news",
                "Airport security wait times lengthen as staffing shortage hits checkpoints",
                {"mentions": 1},
                source_type="news",
                publisher="WSJ",
            ),
            make_item(
                "reddit",
                "Oil prices surge again as inflation fears return",
                {"score": 1000, "comments": 220},
                publisher="r/Economics",
            ),
            make_item(
                "google_news",
                "Crude jumps and markets brace for fresh inflation pressure",
                {"mentions": 1},
                source_type="news",
                publisher="Reuters",
            ),
        ]
        ranked = rank_topics(items, TOPIC_DEFINITIONS, now=NOW, top_n=2)
        self.assertEqual(ranked[0].topic.slug, "public_service_bottlenecks")
        self.assertTrue(all(digest.topic.slug != "oil_inflation" for digest in ranked))

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
                title="국제유가 상승에 주유소 휘발유값 들썩, 한국 소비자물가 우려 확대",
                url="https://example.com/kr-oil",
                published_at=NOW,
                publisher="한국경제",
                topic_hint="oil_inflation",
                metrics={"mentions": 1},
                snippet="국제유가 상승 주유소 휘발유값 한국 소비자물가 우려 확대",
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

    def test_generic_title_with_relevant_body_does_not_match(self):
        topic = TopicDefinition(
            slug="ai_power_capex",
            label="AI 데이터센터 전력·설비투자 경쟁",
            news_queries=[],
            keywords=["ai", "data center", "전력"],
            why_now="",
            reader_fit="",
        )
        ranked = rank_topics(
            [
                EvidenceItem(
                    source="reddit",
                    source_type="social",
                    title="What are you buying during this downturn?",
                    url="https://example.com/post",
                    published_at=NOW,
                    publisher="r/stocks",
                    metrics={"score": 200, "comments": 80},
                    snippet="What are you buying during this downturn? AI data center electricity play discussion",
                )
            ],
            [topic],
            now=NOW,
            top_n=1,
        )
        self.assertEqual(ranked, [])

    def test_topic_hint_does_not_override_macro_only_title(self):
        ranked = rank_topics(
            [
                EvidenceItem(
                    source="google_news",
                    source_type="news",
                    title="Oil prices rise as inflation worries grow",
                    url="https://example.com/oil",
                    published_at=NOW,
                    publisher="Reuters",
                    topic_hint="oil_inflation",
                    metrics={"mentions": 1},
                    snippet="Oil prices rise as inflation worries grow",
                )
            ],
            TOPIC_DEFINITIONS,
            now=NOW,
            top_n=5,
        )
        self.assertTrue(all(digest.topic.slug != "oil_inflation" for digest in ranked))

    def test_duplicate_topic_keywords_do_not_create_false_match(self):
        ranked = rank_topics(
            [
                EvidenceItem(
                    source="hacker_news",
                    source_type="social",
                    title="Launch HN: Faster AI Inference on Apple Silicon",
                    url="https://example.com/hn",
                    published_at=NOW,
                    publisher="news.ycombinator.com",
                    metrics={"score": 180, "comments": 60},
                    snippet="Launch HN: Faster AI Inference on Apple Silicon",
                )
            ],
            TOPIC_DEFINITIONS,
            now=NOW,
            top_n=5,
        )
        self.assertTrue(all(digest.topic.slug != "ai_power_capex" for digest in ranked))

    def test_bluesky_signal_can_support_concrete_topic(self):
        ranked = rank_topics(
            [
                EvidenceItem(
                    source="bluesky",
                    source_type="social",
                    title="Atlanta travelers say TSA lines stretched past the terminal during shutdown",
                    url="https://bsky.app/profile/example/post/1",
                    published_at=NOW,
                    publisher="Travel Watch",
                    metrics={"likes": 80, "reposts": 20, "replies": 14, "quotes": 5},
                    snippet="Atlanta travelers say TSA lines stretched past the terminal during shutdown",
                ),
                EvidenceItem(
                    source="google_news",
                    source_type="news",
                    title="Airport security wait times lengthen as staffing shortage hits checkpoints",
                    url="https://example.com/wsj",
                    published_at=NOW,
                    publisher="WSJ",
                    metrics={"mentions": 1},
                    snippet="Airport security wait times lengthen as staffing shortage hits checkpoints",
                ),
            ],
            TOPIC_DEFINITIONS,
            now=NOW,
            top_n=2,
        )
        self.assertEqual(ranked[0].topic.slug, "public_service_bottlenecks")


if __name__ == "__main__":
    unittest.main()
