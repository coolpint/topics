import argparse
import json
from datetime import datetime, timezone
from typing import List

from .config import AppConfig
from .formatter import format_digest
from .history import load_history, save_history, select_fresh_topics
from .ranking import rank_topics
from .sources import collect_all_sources
from .taxonomy import TOPIC_DEFINITIONS
from .telegram import send_message


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Rank economic news topics from public social and news signals."
    )
    parser.add_argument(
        "--send-telegram",
        action="store_true",
        help="Send the ranked digest to Telegram using TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID.",
    )
    parser.add_argument(
        "--max-topics",
        type=int,
        default=5,
        help="How many topics to keep in the final ranking.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print a JSON payload instead of the Telegram-friendly text digest.",
    )
    parser.add_argument(
        "--history-path",
        default="data/topic_history.json",
        help="Path to the persisted topic history used to avoid repeating recent topics.",
    )
    return parser


def _serialize(digests) -> List[dict]:
    payload = []
    for digest in digests:
        payload.append(
            {
                "slug": digest.topic.slug,
                "label": digest.topic.label,
                "total_score": round(digest.total_score, 3),
                "social_score": round(digest.social_score, 3),
                "media_score": round(digest.media_score, 3),
                "evidence": [
                    {
                        "source": item.source,
                        "publisher": item.publisher,
                        "title": item.title,
                        "url": item.url,
                        "published_at": item.published_at.isoformat(),
                        "metrics": item.metrics,
                    }
                    for item in digest.evidence[:5]
                ],
            }
        )
    return payload


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    config = AppConfig.from_env()
    items, errors = collect_all_sources(config, TOPIC_DEFINITIONS)
    now = datetime.now(timezone.utc)
    history = load_history(args.history_path)
    ranked_digests = rank_topics(items, TOPIC_DEFINITIONS, now=now, top_n=len(TOPIC_DEFINITIONS))
    digests, skipped_recent, used_recent_fallback = select_fresh_topics(
        ranked_digests,
        history,
        now,
        limit=args.max_topics,
    )
    notices = []
    if used_recent_fallback:
        notices.append(
            "최근 30일 중복 회피 규칙에 걸린 주제만 남아, 이번 발송은 상위 중복 후보를 다시 포함했습니다."
        )
    elif skipped_recent:
        notices.append(
            "최근 30일 안에 다룬 유사 주제 {}건은 제외했습니다.".format(len(skipped_recent))
        )
    if args.json:
        print(
            json.dumps(
                {
                    "generated_at": now.isoformat(),
                    "topics": _serialize(digests),
                    "skipped_recent": skipped_recent,
                    "used_recent_fallback": used_recent_fallback,
                    "errors": errors,
                },
                indent=2,
            )
        )
        return 0
    message = format_digest(digests, now, errors, notices=notices)
    print(message)
    if args.send_telegram:
        send_message(config.telegram_bot_token, config.telegram_chat_id, message)
        save_history(args.history_path, digests, now)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
