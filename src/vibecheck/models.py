"""Pydantic models for vibecheck API."""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, HttpUrl


class Verdict(str, Enum):
    """Tool evaluation verdicts."""

    ESSENTIAL = "essential"  # 🔥 Daily driver, highly recommended
    SOLID = "solid"  # ✅ Works well, good choice
    SITUATIONAL = "situational"  # 🤷 Right for specific use cases
    CAUTION = "caution"  # ⚠️ Works but has significant issues
    AVOID = "avoid"  # 💀 Broken, abandoned, or dangerous


class LinkType(str, Enum):
    """Types of external links."""

    BLOG = "blog"
    VIDEO = "video"
    DISCUSSION = "discussion"
    DOCS = "docs"
    TUTORIAL = "tutorial"
    REVIEW = "review"
    OTHER = "other"


class Sentiment(str, Enum):
    """Sentiment of tool mentions."""

    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"
    QUESTION = "question"


# ============== Request Models ==============


class ToolCreate(BaseModel):
    """Create a new tool."""

    slug: str = Field(..., pattern=r"^[a-z0-9-]+$", min_length=2, max_length=100)
    name: str = Field(..., min_length=1, max_length=200)
    url: Optional[HttpUrl] = None
    github_url: Optional[HttpUrl] = None
    categories: list[str] = Field(default_factory=list)
    communities: list[str] = Field(default_factory=list)  # ["agi", "henkaku", "dg"]
    description: Optional[str] = None


class ToolUpdate(BaseModel):
    """Update an existing tool."""

    name: Optional[str] = None
    url: Optional[HttpUrl] = None
    github_url: Optional[HttpUrl] = None
    categories: Optional[list[str]] = None
    description: Optional[str] = None


class EvaluationCreate(BaseModel):
    """Submit an evaluation for a tool."""

    works: Optional[bool] = None
    actively_maintained: Optional[bool] = None
    verdict: Optional[Verdict] = None
    security_notes: Optional[str] = None
    notes: Optional[str] = None
    communities: list[str] = Field(default_factory=list)


class LinkCreate(BaseModel):
    """Add an external link to a tool."""

    url: HttpUrl
    title: Optional[str] = None
    link_type: LinkType = LinkType.OTHER
    snippet: Optional[str] = Field(None, max_length=500)


# ============== Response Models ==============


class UserResponse(BaseModel):
    """Public user info for attribution."""

    id: str
    github_username: Optional[str] = None
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None


class EvaluationResponse(BaseModel):
    """Evaluation with evaluator info."""

    id: str
    works: Optional[bool] = None
    actively_maintained: Optional[bool] = None
    verdict: Optional[Verdict] = None
    security_notes: Optional[str] = None
    notes: Optional[str] = None
    communities: list[str] = []
    evaluator: Optional[UserResponse] = None
    created_at: datetime
    updated_at: datetime


class LinkResponse(BaseModel):
    """External link response."""

    id: str
    url: str
    title: Optional[str] = None
    link_type: LinkType
    snippet: Optional[str] = None
    submitted_by: Optional[UserResponse] = None
    created_at: datetime


class CommunityResponse(BaseModel):
    """Community where tools are discussed."""

    slug: str
    name: str
    description: Optional[str] = None
    tool_count: int = 0


class ToolCommunityResponse(BaseModel):
    """Tool's presence in a community."""

    community: CommunityResponse
    first_mentioned: Optional[datetime] = None
    mention_count: int = 0
    sentiment_summary: Optional[str] = None


class ToolResponse(BaseModel):
    """Tool with all related data."""

    id: str
    slug: str
    name: str
    url: Optional[str] = None
    github_url: Optional[str] = None
    categories: list[str] = []
    description: Optional[str] = None

    # GitHub stats
    github_stars: Optional[int] = None
    github_last_commit: Optional[datetime] = None
    github_open_issues: Optional[int] = None
    github_license: Optional[str] = None

    # Communities where this tool is discussed
    communities: list[str] = []  # Just slugs for list view

    # Metadata
    first_seen: datetime
    source: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class ToolDetailResponse(ToolResponse):
    """Tool with evaluations and links."""

    evaluations: list[EvaluationResponse] = []
    links: list[LinkResponse] = []
    community_details: list[ToolCommunityResponse] = []  # Full community info
    mention_count: int = 0

    # Aggregated evaluation stats
    avg_verdict: Optional[str] = None
    works_count: int = 0
    works_total: int = 0


class ToolListResponse(BaseModel):
    """Paginated list of tools."""

    tools: list[ToolResponse]
    total: int
    page: int
    per_page: int
    has_more: bool


class CategoryResponse(BaseModel):
    """Category info."""

    slug: str
    name: str
    description: Optional[str] = None
    tool_count: int = 0


class SearchResult(BaseModel):
    """Search result with relevance."""

    tool: ToolResponse
    relevance: float = 1.0
    matched_fields: list[str] = []


class SearchResponse(BaseModel):
    """Search results."""

    results: list[SearchResult]
    query: str
    total: int


# ============== Import Models ==============


class ImportSource(str, Enum):
    """Types of import sources."""

    SLACK = "slack"
    WHATSAPP = "whatsapp"
    DISCORD = "discord"
    AWESOME_LIST = "awesome-list"
    MANUAL = "manual"


class ToolMention(BaseModel):
    """A sanitized mention of a tool from an import."""

    tool_name: str
    tool_url: Optional[str] = None
    context_snippet: Optional[str] = None  # Sanitized
    sentiment: Optional[Sentiment] = None
    mention_date: Optional[datetime] = None
    community: Optional[str] = None  # Community slug where mentioned


class ImportBatchCreate(BaseModel):
    """Create an import batch."""

    source_type: ImportSource
    source_name: Optional[str] = None
    mentions: list[ToolMention] = []


class ImportBatchResponse(BaseModel):
    """Import batch result."""

    id: str
    source_type: ImportSource
    source_name: Optional[str] = None
    tool_count: int
    created_at: datetime
    tools_created: list[str] = []  # slugs of new tools
    tools_updated: list[str] = []  # slugs of existing tools with new mentions
