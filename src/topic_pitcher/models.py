from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Set


@dataclass(frozen=True)
class TopicDefinition:
    slug: str
    label: str
    news_queries: List[str]
    keywords: List[str]
    why_now: str
    reader_fit: str
    youtube_query: str = ""
    korea_queries: List[str] = field(default_factory=list)
    korea_relevance: float = 1.0
    story_bias: float = 1.0
    article_focus: str = ""
    reporting_points: str = ""


@dataclass
class EvidenceItem:
    source: str
    source_type: str
    title: str
    url: str
    published_at: datetime
    publisher: str = ""
    topic_hint: str = ""
    metrics: Dict[str, float] = field(default_factory=dict)
    snippet: str = ""
    audience_region: str = "global"


@dataclass
class TopicDigest:
    topic: TopicDefinition
    total_score: float = 0.0
    social_score: float = 0.0
    media_score: float = 0.0
    evidence: List[EvidenceItem] = field(default_factory=list)
    unique_sources: Set[str] = field(default_factory=set)
    unique_publishers: Set[str] = field(default_factory=set)
    matched_keywords: Set[str] = field(default_factory=set)


@dataclass
class CaseSupport:
    role: str
    item: EvidenceItem
    note: str = ""
    resolved_url: str = ""


@dataclass
class CasePitch:
    slug: str
    headline: str
    summary: str
    angle: str
    score: float = 0.0
    evidence: List[EvidenceItem] = field(default_factory=list)
    supports: List[CaseSupport] = field(default_factory=list)
    terms: Set[str] = field(default_factory=set)
    plan_points: List[str] = field(default_factory=list)
