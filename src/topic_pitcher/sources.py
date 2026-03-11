import json
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from typing import Iterable, List, Sequence, Tuple
from urllib.parse import quote_plus, urlparse

from .config import AppConfig
from .http import fetch_json, fetch_text
from .models import EvidenceItem, TopicDefinition


class SourceError(RuntimeError):
    pass


TRUSTED_KR_PUBLISHER_TOKENS = (
    "연합뉴스",
    "한국경제",
    "매일경제",
    "서울경제",
    "헤럴드경제",
    "아시아경제",
    "머니투데이",
    "이데일리",
    "조선비즈",
    "뉴스핌",
    "뉴시스",
    "파이낸셜뉴스",
    "전자신문",
    "ebn",
    "mk.co.kr",
    "hankyung",
    "sedaily",
    "chosunbiz",
    "newsis",
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _within_lookback(published_at: datetime, lookback_hours: int, now: datetime) -> bool:
    return published_at >= now - timedelta(hours=lookback_hours)


def _parse_reddit_time(epoch_seconds: float) -> datetime:
    return datetime.fromtimestamp(epoch_seconds, tz=timezone.utc)


def _parse_datetime(value: str) -> datetime:
    parsed = parsedate_to_datetime(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _domain_from_url(url: str) -> str:
    return urlparse(url).netloc.lower()


def _item_text(title: str, snippet: str) -> str:
    return (title + " " + snippet).strip()


def _is_trusted_kr_publisher(publisher: str) -> bool:
    lowered = publisher.lower()
    return any(token.lower() in lowered for token in TRUSTED_KR_PUBLISHER_TOKENS)


class RedditSource:
    name = "reddit"

    def __init__(self, subreddits: Sequence[str], lookback_hours: int):
        self.subreddits = list(subreddits)
        self.lookback_hours = lookback_hours

    def collect(self, now: datetime) -> List[EvidenceItem]:
        items: List[EvidenceItem] = []
        for subreddit in self.subreddits:
            payload = fetch_json(
                "https://api.reddit.com/r/{}/top".format(subreddit),
                params={"limit": 25, "t": "day", "raw_json": 1},
                headers={"Accept": "application/json"},
            )
            children = payload.get("data", {}).get("children", [])
            for child in children:
                data = child.get("data", {})
                if data.get("over_18"):
                    continue
                published_at = _parse_reddit_time(float(data.get("created_utc", 0)))
                if not _within_lookback(published_at, self.lookback_hours, now):
                    continue
                items.append(
                    EvidenceItem(
                        source=self.name,
                        source_type="social",
                        title=data.get("title", "").strip(),
                        url="https://www.reddit.com" + data.get("permalink", ""),
                        published_at=published_at,
                        publisher="r/{}".format(data.get("subreddit", subreddit)),
                        metrics={
                            "score": float(data.get("score", 0)),
                            "comments": float(data.get("num_comments", 0)),
                        },
                        snippet=_item_text(data.get("title", ""), data.get("selftext", "")),
                    )
                )
        return items


class HackerNewsSource:
    name = "hacker_news"

    def __init__(self, lookback_hours: int, limit: int = 25):
        self.lookback_hours = lookback_hours
        self.limit = limit

    def collect(self, now: datetime) -> List[EvidenceItem]:
        story_ids = fetch_json("https://hacker-news.firebaseio.com/v0/topstories.json")
        items: List[EvidenceItem] = []
        for story_id in story_ids[: self.limit]:
            data = fetch_json(
                "https://hacker-news.firebaseio.com/v0/item/{}.json".format(story_id)
            )
            if not isinstance(data, dict):
                continue
            if data.get("type") != "story":
                continue
            published_at = datetime.fromtimestamp(float(data.get("time", 0)), tz=timezone.utc)
            if not _within_lookback(published_at, self.lookback_hours, now):
                continue
            url = data.get("url") or "https://news.ycombinator.com/item?id={}".format(story_id)
            items.append(
                EvidenceItem(
                    source=self.name,
                    source_type="social",
                    title=data.get("title", "").strip(),
                    url=url,
                    published_at=published_at,
                    publisher=_domain_from_url(url) or "news.ycombinator.com",
                    metrics={
                        "score": float(data.get("score", 0)),
                        "comments": float(data.get("descendants", 0)),
                    },
                    snippet=_item_text(data.get("title", ""), data.get("text", "")),
                )
            )
        return items


class GoogleNewsSource:
    name = "google_news"

    def __init__(
        self,
        lookback_hours: int,
        topic_definitions: Sequence[TopicDefinition],
        *,
        source_name: str,
        hl: str,
        gl: str,
        ceid: str,
        query_attr: str,
        audience_region: str,
    ):
        self.lookback_hours = lookback_hours
        self.topic_definitions = list(topic_definitions)
        self.source_name = source_name
        self.hl = hl
        self.gl = gl
        self.ceid = ceid
        self.query_attr = query_attr
        self.audience_region = audience_region

    def _query_feed(self, query: str) -> str:
        from urllib.parse import urlencode

        params = urlencode(
            {
                "q": "{} when:{}h".format(query, self.lookback_hours),
                "hl": self.hl,
                "gl": self.gl,
                "ceid": self.ceid,
            }
        )
        return "https://news.google.com/rss/search?" + params

    def collect(self, now: datetime) -> List[EvidenceItem]:
        seen = set()
        items: List[EvidenceItem] = []
        for topic in self.topic_definitions:
            for query in getattr(topic, self.query_attr):
                xml_text = fetch_text(self._query_feed(query))
                root = ET.fromstring(xml_text)
                channel = root.find("channel")
                if channel is None:
                    continue
                for item in channel.findall("item"):
                    title = (item.findtext("title") or "").strip()
                    link = (item.findtext("link") or "").strip()
                    pub_date = (item.findtext("pubDate") or "").strip()
                    if not title or not link or not pub_date:
                        continue
                    dedupe_key = (title, link)
                    if dedupe_key in seen:
                        continue
                    seen.add(dedupe_key)
                    published_at = _parse_datetime(pub_date)
                    if not _within_lookback(published_at, self.lookback_hours, now):
                        continue
                    source_tag = item.find("source")
                    publisher = ""
                    if source_tag is not None and source_tag.text:
                        publisher = source_tag.text.strip()
                    if self.audience_region == "KR" and not _is_trusted_kr_publisher(publisher):
                        continue
                    items.append(
                        EvidenceItem(
                            source=self.source_name,
                            source_type="news",
                            title=title,
                            url=link,
                            published_at=published_at,
                            publisher=publisher or _domain_from_url(link),
                            topic_hint=topic.slug,
                            metrics={"mentions": 1.0},
                            snippet=title,
                            audience_region=self.audience_region,
                        )
                    )
        return items


class NaverNewsSearchSource:
    name = "naver_news"

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        topic_definitions: Sequence[TopicDefinition],
        lookback_hours: int,
    ):
        self.client_id = client_id
        self.client_secret = client_secret
        self.topic_definitions = list(topic_definitions)
        self.lookback_hours = lookback_hours

    def collect(self, now: datetime) -> List[EvidenceItem]:
        if not self.client_id or not self.client_secret:
            return []
        items: List[EvidenceItem] = []
        for topic in self.topic_definitions:
            for query in topic.korea_queries:
                payload = fetch_json(
                    "https://openapi.naver.com/v1/search/news.json",
                    params={
                        "query": query,
                        "display": 10,
                        "sort": "date",
                    },
                    headers={
                        "X-Naver-Client-Id": self.client_id,
                        "X-Naver-Client-Secret": self.client_secret,
                    },
                )
                total = float(payload.get("total", 0))
                if total <= 0:
                    continue
                preview_titles = []
                for result in payload.get("items", [])[:3]:
                    raw_title = unescape(result.get("title", ""))
                    cleaned = (
                        raw_title.replace("<b>", "")
                        .replace("</b>", "")
                        .strip()
                    )
                    if cleaned:
                        preview_titles.append(cleaned)
                items.append(
                    EvidenceItem(
                        source=self.name,
                        source_type="trend",
                        title="네이버 뉴스 검색량: {}".format(query),
                        url="https://search.naver.com/search.naver?where=news&query={}".format(
                            quote_plus(query)
                        ),
                        published_at=now,
                        publisher="Naver News Search",
                        topic_hint=topic.slug,
                        metrics={"total": total},
                        snippet="{} {}".format(query, " | ".join(preview_titles)).strip(),
                        audience_region="KR",
                    )
                )
        return items


class YouTubeSource:
    name = "youtube"

    def __init__(self, lookback_hours: int, topic_definitions: Sequence[TopicDefinition], api_key: str, region_code: str, language: str):
        self.lookback_hours = lookback_hours
        self.topic_definitions = [topic for topic in topic_definitions if topic.youtube_query]
        self.api_key = api_key
        self.region_code = region_code
        self.language = language

    def _published_after(self, now: datetime) -> str:
        window = now - timedelta(hours=self.lookback_hours)
        return window.replace(microsecond=0).isoformat().replace("+00:00", "Z")

    def _search(self, query: str, now: datetime) -> Iterable[Tuple[str, dict]]:
        payload = fetch_json(
            "https://www.googleapis.com/youtube/v3/search",
            params={
                "part": "snippet",
                "type": "video",
                "order": "viewCount",
                "maxResults": 5,
                "publishedAfter": self._published_after(now),
                "regionCode": self.region_code,
                "relevanceLanguage": self.language,
                "q": query,
                "key": self.api_key,
            },
        )
        for item in payload.get("items", []):
            video_id = item.get("id", {}).get("videoId")
            if video_id:
                yield video_id, item

    def _video_details(self, video_ids: Sequence[str]) -> dict:
        if not video_ids:
            return {}
        payload = fetch_json(
            "https://www.googleapis.com/youtube/v3/videos",
            params={
                "part": "snippet,statistics",
                "id": ",".join(video_ids),
                "key": self.api_key,
            },
        )
        return {
            item.get("id"): item
            for item in payload.get("items", [])
            if item.get("id")
        }

    def collect(self, now: datetime) -> List[EvidenceItem]:
        items: List[EvidenceItem] = []
        for topic in self.topic_definitions:
            search_hits = list(self._search(topic.youtube_query, now))
            details = self._video_details([video_id for video_id, _ in search_hits])
            for video_id, search_item in search_hits:
                detail = details.get(video_id, {})
                snippet = detail.get("snippet") or search_item.get("snippet", {})
                stats = detail.get("statistics", {})
                published_at_raw = snippet.get("publishedAt")
                if not published_at_raw:
                    continue
                published_at = datetime.fromisoformat(
                    published_at_raw.replace("Z", "+00:00")
                ).astimezone(timezone.utc)
                if not _within_lookback(published_at, self.lookback_hours, now):
                    continue
                items.append(
                    EvidenceItem(
                        source=self.name,
                        source_type="video",
                        title=snippet.get("title", "").strip(),
                        url="https://www.youtube.com/watch?v={}".format(video_id),
                        published_at=published_at,
                        publisher=snippet.get("channelTitle", "YouTube"),
                        topic_hint=topic.slug,
                        metrics={
                            "views": float(stats.get("viewCount", 0)),
                            "likes": float(stats.get("likeCount", 0)),
                            "comments": float(stats.get("commentCount", 0)),
                        },
                        snippet=_item_text(snippet.get("title", ""), snippet.get("description", "")),
                    )
                )
        return items


def collect_all_sources(config: AppConfig, topic_definitions: Sequence[TopicDefinition]) -> Tuple[List[EvidenceItem], List[str]]:
    now = _utc_now()
    sources = [
        RedditSource(config.reddit_subreddits, config.lookback_hours),
        HackerNewsSource(config.lookback_hours),
        GoogleNewsSource(
            config.lookback_hours,
            topic_definitions,
            source_name="google_news",
            hl=config.google_news_hl,
            gl=config.google_news_gl,
            ceid=config.google_news_ceid,
            query_attr="news_queries",
            audience_region="global",
        ),
        GoogleNewsSource(
            config.lookback_hours,
            topic_definitions,
            source_name="google_news_kr",
            hl=config.google_news_kr_hl,
            gl=config.google_news_kr_gl,
            ceid=config.google_news_kr_ceid,
            query_attr="korea_queries",
            audience_region="KR",
        ),
        NaverNewsSearchSource(
            config.naver_client_id,
            config.naver_client_secret,
            topic_definitions,
            config.lookback_hours,
        ),
    ]
    if config.youtube_api_key:
        sources.append(
            YouTubeSource(
                config.lookback_hours,
                topic_definitions,
                config.youtube_api_key,
                config.youtube_region_code,
                config.youtube_language,
            )
        )
    items: List[EvidenceItem] = []
    errors: List[str] = []
    for source in sources:
        try:
            items.extend(source.collect(now))
        except Exception as exc:  # pragma: no cover - network failure path
            errors.append("{}: {}".format(source.name, exc))
    return items, errors
