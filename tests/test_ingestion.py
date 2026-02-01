"""Tests for ingestion interfaces."""

import pytest

from vibecheck.ingestion import SlackIngester, WhatsAppIngester
from vibecheck.ingestion.base import BaseIngester


class TestBaseIngester:
    """Tests for base ingester functionality."""

    def test_extract_github_urls(self):
        """Should extract GitHub URLs from text."""
        ingester = SlackIngester()
        text = "Check out https://github.com/anthropics/claude-code and https://github.com/cursor-ai/cursor"
        urls = ingester.extract_urls(text)
        
        assert len(urls["github"]) == 2
        assert "https://github.com/anthropics/claude-code" in urls["github"]
        assert "https://github.com/cursor-ai/cursor" in urls["github"]

    def test_extract_npm_urls(self):
        """Should extract npm URLs from text."""
        ingester = SlackIngester()
        text = "Install from https://npmjs.com/package/langchain"
        urls = ingester.extract_urls(text)
        
        assert len(urls["npm"]) == 1
        assert "https://npmjs.com/package/langchain" in urls["npm"]

    def test_extract_pypi_urls(self):
        """Should extract PyPI URLs from text."""
        ingester = SlackIngester()
        text = "pip install from https://pypi.org/project/anthropic"
        urls = ingester.extract_urls(text)
        
        assert len(urls["pypi"]) == 1
        assert "https://pypi.org/project/anthropic" in urls["pypi"]

    def test_detect_positive_sentiment(self):
        """Should detect positive sentiment."""
        ingester = SlackIngester()
        assert ingester.detect_sentiment("I love this tool, it's amazing!") == "positive"
        assert ingester.detect_sentiment("This is excellent, highly recommend") == "positive"

    def test_detect_negative_sentiment(self):
        """Should detect negative sentiment."""
        ingester = SlackIngester()
        assert ingester.detect_sentiment("This tool is broken and buggy") == "negative"
        assert ingester.detect_sentiment("Avoid this, it doesn't work") == "negative"

    def test_detect_question_sentiment(self):
        """Should detect questions."""
        ingester = SlackIngester()
        assert ingester.detect_sentiment("Has anyone tried this tool?") == "question"
        assert ingester.detect_sentiment("What do you think about cursor?") == "question"

    def test_detect_neutral_sentiment(self):
        """Should default to neutral for ambiguous text."""
        ingester = SlackIngester()
        assert ingester.detect_sentiment("I used this tool today") == "neutral"

    def test_sanitize_snippet_removes_email(self):
        """Should remove email addresses from snippets."""
        ingester = SlackIngester(sanitize=True)
        text = "Contact me at john@example.com for more info"
        sanitized = ingester.sanitize_snippet(text)
        
        assert "john@example.com" not in sanitized
        assert "[email]" in sanitized

    def test_sanitize_snippet_removes_mentions(self):
        """Should anonymize @mentions."""
        ingester = SlackIngester(sanitize=True)
        text = "Thanks @johndoe for sharing this!"
        sanitized = ingester.sanitize_snippet(text)
        
        assert "@johndoe" not in sanitized
        assert "@[user]" in sanitized

    def test_sanitize_snippet_truncates(self):
        """Should truncate long snippets."""
        ingester = SlackIngester(sanitize=True)
        text = "x" * 500
        sanitized = ingester.sanitize_snippet(text, max_length=100)
        
        assert len(sanitized) <= 100
        assert sanitized.endswith("...")

    def test_extract_tool_name_from_github(self):
        """Should extract repo name from GitHub URL."""
        ingester = SlackIngester()
        url = "https://github.com/anthropics/claude-code"
        name = ingester.extract_tool_name_from_url(url)
        
        assert name == "claude-code"

    def test_extract_tool_name_from_npm(self):
        """Should extract package name from npm URL."""
        ingester = SlackIngester()
        url = "https://npmjs.com/package/langchain"
        name = ingester.extract_tool_name_from_url(url)
        
        assert name == "langchain"

    def test_is_tool_related(self):
        """Should identify tool-related messages."""
        ingester = SlackIngester()
        
        assert ingester.is_tool_related("Check out this awesome tool")
        assert ingester.is_tool_related("I recommend using this library")
        assert ingester.is_tool_related("https://github.com/owner/repo")
        assert not ingester.is_tool_related("Nice weather today")


class TestSlackIngester:
    """Tests for Slack ingestion."""

    def test_parse_text_with_github_link(self):
        """Should extract tools from plain text with GitHub links."""
        ingester = SlackIngester()
        text = """
alice  2:30 PM
Check out https://github.com/anthropics/claude-code - been using it all week

bob  2:35 PM
Nice! How does it compare to cursor?
"""
        result = ingester.parse(text, source_name="#ai-tools")
        
        assert result.source_type == "slack"
        assert result.source_name == "#ai-tools"
        assert len(result.tools_found) == 1
        assert result.tools_found[0].name == "claude-code"
        assert result.tools_found[0].github_url == "https://github.com/anthropics/claude-code"

    def test_parse_sanitizes_snippets(self):
        """Should sanitize personal info in snippets."""
        ingester = SlackIngester(sanitize=True)
        text = """
john  3:00 PM
@alice check out https://github.com/cursor-ai/cursor - email me at john@test.com
"""
        result = ingester.parse(text)
        
        assert len(result.tools_found) == 1
        snippet = result.tools_found[0].context_snippet
        assert "@alice" not in snippet
        assert "john@test.com" not in snippet


class TestWhatsAppIngester:
    """Tests for WhatsApp ingestion."""

    def test_parse_standard_format(self):
        """Should parse standard WhatsApp export format."""
        ingester = WhatsAppIngester()
        text = """[1/15/26, 2:30:45 PM] John: Check out https://github.com/langchain-ai/langchain
[1/15/26, 2:31:00 PM] Alice: Thanks for sharing!"""
        
        result = ingester.parse(text, source_name="AI Tools Group")
        
        assert result.source_type == "whatsapp"
        assert result.source_name == "AI Tools Group"
        assert len(result.tools_found) == 1
        assert result.tools_found[0].name == "langchain"

    def test_parse_alternative_format(self):
        """Should parse alternative WhatsApp format."""
        ingester = WhatsAppIngester()
        text = """1/15/26, 14:30 - John: Try https://github.com/anthropics/anthropic-sdk-python
1/15/26, 14:31 - Alice: Will do!"""
        
        result = ingester.parse(text)
        
        assert len(result.tools_found) == 1
        assert result.tools_found[0].name == "anthropic-sdk-python"

    def test_sanitizes_sender_names(self):
        """Should anonymize sender names."""
        ingester = WhatsAppIngester(sanitize=True)
        text = """[1/15/26, 2:30:00 PM] John Smith: https://github.com/owner/repo is great"""
        
        result = ingester.parse(text)
        
        assert len(result.tools_found) == 1
        snippet = result.tools_found[0].context_snippet
        # Should only have first initial
        assert "John Smith" not in snippet

    def test_sanitizes_phone_numbers(self):
        """Should redact phone number senders."""
        ingester = WhatsAppIngester(sanitize=True)
        text = """[1/15/26, 2:30:00 PM] +1 555-123-4567: https://github.com/owner/repo"""
        
        result = ingester.parse(text)
        
        assert len(result.tools_found) == 1
        snippet = result.tools_found[0].context_snippet
        assert "+1 555-123-4567" not in snippet
        assert "[user]" in snippet
