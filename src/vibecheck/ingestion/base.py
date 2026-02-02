"""Base classes for ingestion interfaces."""

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

# Common URL patterns for tools
GITHUB_PATTERN = re.compile(r"https?://github\.com/[\w-]+/[\w.-]+")
NPM_PATTERN = re.compile(r"https?://(?:www\.)?npmjs\.com/package/[\w@/-]+")
PYPI_PATTERN = re.compile(r"https?://pypi\.org/project/[\w-]+")
GENERIC_URL_PATTERN = re.compile(r"https?://[^\s<>\"'\]]+")

# Keywords that suggest a message is about tools
TOOL_KEYWORDS = [
    "tool",
    "library",
    "framework",
    "package",
    "cli",
    "sdk",
    "api",
    "plugin",
    "extension",
    "check out",
    "try",
    "using",
    "switched to",
    "recommend",
    "awesome",
    "built with",
    "powered by",
    "integrated",
    "workflow",
    "automation",
]

# Keywords that suggest sentiment
POSITIVE_KEYWORDS = ["love", "great", "amazing", "awesome", "excellent", "recommend", "best", "solid", "works well"]
NEGATIVE_KEYWORDS = ["broken", "buggy", "avoid", "terrible", "doesn't work", "issues", "problems", "abandoned"]
QUESTION_KEYWORDS = ["anyone", "has anyone", "what do you think", "opinions on", "?"]


@dataclass
class ExtractedTool:
    """A tool extracted from a message."""

    name: str
    url: Optional[str] = None
    github_url: Optional[str] = None
    context_snippet: Optional[str] = None  # Sanitized snippet
    sentiment: Optional[str] = None  # positive, negative, neutral, question
    mention_date: Optional[datetime] = None
    categories: list[str] = field(default_factory=list)


@dataclass
class ExtractedArticle:
    """An article/link extracted from a message."""

    url: str
    title: Optional[str] = None  # Will be fetched later if not available
    context_snippet: Optional[str] = None
    mention_date: Optional[datetime] = None
    source_community: Optional[str] = None


@dataclass
class IngestionResult:
    """Result of an ingestion operation."""

    source_type: str
    source_name: Optional[str]
    message_count: int
    tools_found: list[ExtractedTool]
    articles_found: list[ExtractedArticle] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


class BaseIngester(ABC):
    """Base class for chat log ingesters."""

    def __init__(self, sanitize: bool = True):
        """
        Initialize the ingester.

        Args:
            sanitize: Whether to sanitize personal information from snippets
        """
        self.sanitize = sanitize

    @abstractmethod
    def parse(self, content: str, source_name: Optional[str] = None) -> IngestionResult:
        """
        Parse chat content and extract tool mentions.

        Args:
            content: Raw chat log content
            source_name: Optional name for the source (e.g., channel name)

        Returns:
            IngestionResult with extracted tools
        """
        pass

    def extract_urls(self, text: str) -> dict[str, list[str]]:
        """Extract URLs from text, categorized by type."""
        return {
            "github": GITHUB_PATTERN.findall(text),
            "npm": NPM_PATTERN.findall(text),
            "pypi": PYPI_PATTERN.findall(text),
            "other": [
                url
                for url in GENERIC_URL_PATTERN.findall(text)
                if not any(
                    p.match(url) for p in [GITHUB_PATTERN, NPM_PATTERN, PYPI_PATTERN]
                )
            ],
        }

    def detect_sentiment(self, text: str) -> str:
        """Detect sentiment of a message about a tool."""
        text_lower = text.lower()

        if any(kw in text_lower for kw in QUESTION_KEYWORDS):
            return "question"
        if any(kw in text_lower for kw in POSITIVE_KEYWORDS):
            return "positive"
        if any(kw in text_lower for kw in NEGATIVE_KEYWORDS):
            return "negative"
        return "neutral"

    def is_tool_related(self, text: str) -> bool:
        """Check if a message is likely about tools."""
        text_lower = text.lower()

        # Has tool-related keywords
        if any(kw in text_lower for kw in TOOL_KEYWORDS):
            return True

        # Has GitHub/npm/pypi URLs
        urls = self.extract_urls(text)
        if urls["github"] or urls["npm"] or urls["pypi"]:
            return True

        return False

    def sanitize_snippet(self, text: str, max_length: int = 300) -> str:
        """
        Sanitize a text snippet by removing personal information.

        Args:
            text: Raw text
            max_length: Maximum length of the snippet

        Returns:
            Sanitized text
        """
        if not self.sanitize:
            return text[:max_length]

        sanitized = text

        # Remove email addresses
        sanitized = re.sub(r"\b[\w.-]+@[\w.-]+\.\w+\b", "[email]", sanitized)

        # Remove phone numbers (various formats)
        sanitized = re.sub(r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b", "[phone]", sanitized)
        sanitized = re.sub(r"\+\d{1,3}[-.\s]?\d{1,14}", "[phone]", sanitized)

        # Remove @mentions (keep the mention but anonymize)
        sanitized = re.sub(r"@[\w]+", "@[user]", sanitized)

        # Remove names that look like "First Last" patterns near personal pronouns
        # This is a heuristic and may not catch everything
        sanitized = re.sub(r"\b(my|our|their)\s+([A-Z][a-z]+)\b", r"\1 [name]", sanitized)

        # Remove specific Slack user IDs
        sanitized = re.sub(r"<@U[\w]+>", "@[user]", sanitized)

        # Truncate
        if len(sanitized) > max_length:
            sanitized = sanitized[: max_length - 3] + "..."

        return sanitized.strip()

    def extract_tool_name_from_url(self, url: str) -> Optional[str]:
        """Try to extract a tool name from a URL."""
        # GitHub: https://github.com/owner/repo
        github_match = re.match(r"https?://github\.com/[\w-]+/([\w.-]+)", url)
        if github_match:
            return github_match.group(1)

        # npm: https://npmjs.com/package/name or @scope/name
        npm_match = re.match(r"https?://(?:www\.)?npmjs\.com/package/([\w@/-]+)", url)
        if npm_match:
            return npm_match.group(1)

        # PyPI: https://pypi.org/project/name
        pypi_match = re.match(r"https?://pypi\.org/project/([\w-]+)", url)
        if pypi_match:
            return pypi_match.group(1)

        return None

    def categorize_tool(self, name: str, url: Optional[str], context: str) -> list[str]:
        """Guess categories for a tool based on name and context."""
        categories = []
        text = f"{name} {url or ''} {context}".lower()

        category_keywords = {
            "agent-framework": ["agent", "agentic", "langchain", "langgraph", "autogen", "crew"],
            "editor": ["editor", "ide", "vscode", "cursor", "vim", "neovim", "emacs"],
            "cli": ["cli", "command line", "terminal", "shell"],
            "mcp-server": ["mcp", "model context protocol"],
            "coding-assistant": ["copilot", "assistant", "pair program", "code completion"],
            "code-review": ["review", "pr review", "pull request"],
            "testing": ["test", "pytest", "jest", "testing"],
            "documentation": ["docs", "documentation", "readme", "docstring"],
            "orchestration": ["orchestrat", "workflow", "pipeline"],
        }

        for category, keywords in category_keywords.items():
            if any(kw in text for kw in keywords):
                categories.append(category)

        return categories if categories else ["library"]  # Default to library
