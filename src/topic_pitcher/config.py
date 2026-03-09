import os
from dataclasses import dataclass
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


@dataclass(frozen=True)
class AppConfig:
    telegram_bot_token: str
    telegram_chat_id: str
    youtube_api_key: str
    naver_client_id: str
    naver_client_secret: str
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
        subreddits_raw = os.getenv("REDDIT_SUBREDDITS", ",".join(DEFAULT_REDDIT_SUBREDDITS))
        subreddits = tuple(
            item.strip()
            for item in subreddits_raw.split(",")
            if item.strip()
        )
        return cls(
            telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN", "").strip(),
            telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID", "").strip(),
            youtube_api_key=os.getenv("YOUTUBE_API_KEY", "").strip(),
            naver_client_id=os.getenv("NAVER_CLIENT_ID", "").strip(),
            naver_client_secret=os.getenv("NAVER_CLIENT_SECRET", "").strip(),
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
