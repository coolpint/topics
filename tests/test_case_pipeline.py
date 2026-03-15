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
        self.assertIn("Atlanta airport wait times", pitches[0].headline)
        self.assertIn("공항", pitches[0].summary)
        self.assertEqual([support.role for support in pitches[0].supports[:3]], ["scene", "cause", "impact"])

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
                "U.S. allows temporary purchases of Russian oil already at sea to stabilize energy markets - AP",
                "AP",
                topic_hint="oil_inflation",
            ),
            make_item(
                "reddit",
                "More bad news for oil. Thermal anomalies on Kharg Island's oil terminal contradict claims infrastructure wasn't targeted.",
                "r/stocks",
                metrics={"score": 700, "comments": 250},
                source_type="social",
                topic_hint="oil_inflation",
            ),
        ]
        pitches = build_case_pitches(items, now=NOW, top_n=3, context_fetcher=None)
        self.assertGreaterEqual(len(pitches), 1)
        self.assertIn("Kharg", pitches[0].headline)
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


if __name__ == "__main__":
    unittest.main()
