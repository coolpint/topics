import unittest
from datetime import datetime, timezone

from topic_pitcher.case_pipeline import build_case_pitches
from topic_pitcher.models import EvidenceItem


NOW = datetime(2026, 3, 15, 0, 0, tzinfo=timezone.utc)


def make_item(source, title, publisher, metrics=None, snippet=None, source_type="news", topic_hint=""):
    return EvidenceItem(
        source=source,
        source_type=source_type,
        title=title,
        url="https://example.com/{}".format(abs(hash((source, title))) % 100000),
        published_at=NOW,
        publisher=publisher,
        metrics=metrics or {"mentions": 1},
        snippet=snippet or title,
        topic_hint=topic_hint,
    )


class CasePipelineTests(unittest.TestCase):
    def test_builds_case_pitch_from_specific_event_cluster(self):
        items = [
            make_item(
                "google_news",
                "Atlanta airport wait times climbed in the last week amid shutdown - AJC.com",
                "AJC.com",
                topic_hint="public_service_bottlenecks",
            ),
            make_item(
                "google_news",
                "TSA Delays Snarl Spring Break Travel Amid DHS Shutdown - thetraveler.org",
                "thetraveler.org",
                topic_hint="public_service_bottlenecks",
            ),
            make_item(
                "google_news",
                "Airport workers miss pay as US government shutdown hits one month - Iraqi News",
                "Iraqi News",
                topic_hint="public_service_bottlenecks",
            ),
            make_item(
                "reddit",
                "Atlanta travelers say TSA lines stretched past the terminal during shutdown",
                "r/news",
                metrics={"score": 320, "comments": 90},
                source_type="social",
                topic_hint="public_service_bottlenecks",
            ),
        ]
        pitches = build_case_pitches(items, now=NOW, top_n=3, context_fetcher=None)
        self.assertEqual(len(pitches), 1)
        self.assertIn("공항", pitches[0].headline)
        self.assertIn("셧다운", pitches[0].headline)
        self.assertIn("공항", pitches[0].summary)
        self.assertEqual([support.role for support in pitches[0].supports[:3]], ["scene", "cause", "impact"])
        self.assertGreaterEqual(len(pitches[0].plan_points), 3)

    def test_specific_case_outranks_generic_macro_title(self):
        items = [
            make_item(
                "google_news",
                "Oil prices rise as inflation worries grow - Reuters",
                "Reuters",
                topic_hint="oil_inflation",
            ),
            make_item(
                "google_news",
                "Kharg Island oil terminal disruption sends tanker rates higher - Reuters",
                "Reuters",
                topic_hint="oil_inflation",
            ),
            make_item(
                "google_news",
                "Insurers raise premiums on tankers near Kharg Island after terminal disruption - FT",
                "FT",
                topic_hint="oil_inflation",
            ),
            make_item(
                "google_news",
                "Asian refiners brace for costlier crude shipments from Kharg Island - Nikkei",
                "Nikkei",
                topic_hint="oil_inflation",
            ),
        ]
        pitches = build_case_pitches(items, now=NOW, top_n=3, context_fetcher=None)
        self.assertGreaterEqual(len(pitches), 1)
        self.assertIn("기름값", pitches[0].headline)
        self.assertNotEqual(pitches[0].headline, "Oil prices rise as inflation worries grow")

    def test_community_search_results_alone_do_not_force_a_pitch(self):
        items = [
            make_item(
                "google_news",
                "Atlanta airport wait times climbed in the last week amid shutdown - AJC.com",
                "AJC.com",
                topic_hint="public_service_bottlenecks",
            ),
            make_item(
                "naver_blog",
                "청주 공항 예약 방법 및 면세점 환전 주차 국제선 국내선 식당",
                "네이버 블로그",
                metrics={"total": 7113},
                source_type="community",
                topic_hint="public_service_bottlenecks",
            ),
        ]
        pitches = build_case_pitches(items, now=NOW, top_n=3, context_fetcher=None)
        self.assertEqual(len(pitches), 0)

    def test_youtube_only_case_does_not_become_pitch(self):
        items = [
            make_item(
                "youtube",
                "한국 방산이 세계 시장에서 급성장하는 3가지 이유",
                "기술왕",
                metrics={"views": 100000, "likes": 4200, "comments": 320},
                source_type="social",
                topic_hint="defense",
            ),
            make_item(
                "youtube",
                "K-Defense boom explained",
                "썰원",
                metrics={"views": 90000, "likes": 3500, "comments": 210},
                source_type="social",
                topic_hint="defense",
            ),
        ]
        pitches = build_case_pitches(items, now=NOW, top_n=3, context_fetcher=None)
        self.assertEqual(pitches, [])


if __name__ == "__main__":
    unittest.main()
