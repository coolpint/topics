import os
from dataclasses import dataclass
from pathlib import Path
from typing import Tuple


DEFAULT_REDDIT_SUBREDDITS = (
    "Economics",
    "investing",
    "stocks",
    "StockMarket",
    "RealEstate",
    "technology",
    "Futurology",
)

DEFAULT_MASTODON_BASE_URLS = (
    "https://mastodon.social",
)


def load_dotenv(dotenv_path: str = ".env") -> None:
    path = Path(dotenv_path)
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key or key in os.environ:
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        os.environ[key] = value


@dataclass(frozen=True)
class AppConfig:
    telegram_bot_token: str
    telegram_chat_id: str
    youtube_api_key: str
    naver_client_id: str
    naver_client_secret: str
    bluesky_base_url: str
    bluesky_limit: int
    mastodon_base_urls: Tuple[str, ...]
    mastodon_limit: int
    reddit_subreddits: Tuple[str, ...]
    lookback_hours: int
    google_news_hl: str
    google_news_gl: str
    google_news_ceid: str
    google_news_kr_hl: str
    google_news_kr_gl: str
    google_news_kr_ceid: str
    youtube_region_code: str
    youtube_language: str

    @classmethod
    def from_env(cls) -> "AppConfig":
        load_dotenv()
        subreddits_raw = os.getenv("REDDIT_SUBREDDITS", ",".join(DEFAULT_REDDIT_SUBREDDITS))
        subreddits = tuple(
            item.strip()
            for item in subreddits_raw.split(",")
            if item.strip()
        )
        mastodon_base_urls_raw = os.getenv("MASTODON_BASE_URLS", ",".join(DEFAULT_MASTODON_BASE_URLS))
        mastodon_base_urls = tuple(
            item.strip().rstrip("/")
            for item in mastodon_base_urls_raw.split(",")
            if item.strip()
        )
        return cls(
            telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN", "").strip(),
            telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID", "").strip(),
            youtube_api_key=os.getenv("YOUTUBE_API_KEY", "").strip(),
            naver_client_id=os.getenv("NAVER_CLIENT_ID", "").strip(),
            naver_client_secret=os.getenv("NAVER_CLIENT_SECRET", "").strip(),
            bluesky_base_url=os.getenv("BLUESKY_BASE_URL", "https://public.api.bsky.app").strip().rstrip("/"),
            bluesky_limit=int(os.getenv("BLUESKY_LIMIT", "5")),
            mastodon_base_urls=mastodon_base_urls or DEFAULT_MASTODON_BASE_URLS,
            mastodon_limit=int(os.getenv("MASTODON_LIMIT", "10")),
            reddit_subreddits=subreddits or DEFAULT_REDDIT_SUBREDDITS,
            lookback_hours=int(os.getenv("TOPIC_LOOKBACK_HOURS", "48")),
            google_news_hl=os.getenv("GOOGLE_NEWS_HL", "en-US"),
            google_news_gl=os.getenv("GOOGLE_NEWS_GL", "US"),
            google_news_ceid=os.getenv("GOOGLE_NEWS_CEID", "US:en"),
            google_news_kr_hl=os.getenv("GOOGLE_NEWS_KR_HL", "ko"),
            google_news_kr_gl=os.getenv("GOOGLE_NEWS_KR_GL", "KR"),
            google_news_kr_ceid=os.getenv("GOOGLE_NEWS_KR_CEID", "KR:ko"),
            youtube_region_code=os.getenv("YOUTUBE_REGION_CODE", "KR"),
            youtube_language=os.getenv("YOUTUBE_LANGUAGE", "ko"),
        )
