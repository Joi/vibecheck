"""Slack chat log ingester."""

import json
import re
from datetime import datetime
from typing import Optional

from .base import BaseIngester, ExtractedTool, IngestionResult


class SlackIngester(BaseIngester):
    """
    Ingest tools from Slack export data.

    Supports:
    - Slack export JSON format (from workspace export)
    - Copy-pasted chat logs (plain text)
    """

    SOURCE_TYPE = "slack"

    def parse(self, content: str, source_name: Optional[str] = None) -> IngestionResult:
        """
        Parse Slack content and extract tool mentions.

        Args:
            content: Either JSON export or plain text chat log
            source_name: Channel name (optional)

        Returns:
            IngestionResult with extracted tools
        """
        # Try JSON first
        try:
            return self._parse_json(content, source_name)
        except (json.JSONDecodeError, KeyError):
            pass

        # Fall back to plain text
        return self._parse_text(content, source_name)

    def _parse_json(self, content: str, source_name: Optional[str]) -> IngestionResult:
        """Parse Slack JSON export format."""
        data = json.loads(content)
        messages = data if isinstance(data, list) else data.get("messages", [])

        tools_found = []
        errors = []

        for msg in messages:
            try:
                text = msg.get("text", "")
                if not text or not self.is_tool_related(text):
                    continue

                # Extract timestamp
                ts = msg.get("ts")
                mention_date = datetime.fromtimestamp(float(ts)) if ts else None

                # Extract tools from this message
                extracted = self._extract_tools_from_message(text, mention_date)
                tools_found.extend(extracted)

            except Exception as e:
                errors.append(f"Error parsing message: {e}")

        return IngestionResult(
            source_type=self.SOURCE_TYPE,
            source_name=source_name,
            message_count=len(messages),
            tools_found=tools_found,
            errors=errors,
        )

    def _parse_text(self, content: str, source_name: Optional[str]) -> IngestionResult:
        """Parse plain text chat log."""
        # Split by common message separators
        # Slack copy-paste often looks like:
        # username  HH:MM AM/PM
        # message text
        #
        # Or: [HH:MM] username: message

        lines = content.strip().split("\n")
        messages = []
        current_message = []

        for line in lines:
            # Check if this is a new message header
            if self._is_message_header(line):
                if current_message:
                    messages.append("\n".join(current_message))
                current_message = [line]
            else:
                current_message.append(line)

        if current_message:
            messages.append("\n".join(current_message))

        tools_found = []
        errors = []

        for msg in messages:
            try:
                if not self.is_tool_related(msg):
                    continue

                extracted = self._extract_tools_from_message(msg, None)
                tools_found.extend(extracted)

            except Exception as e:
                errors.append(f"Error parsing message: {e}")

        return IngestionResult(
            source_type=self.SOURCE_TYPE,
            source_name=source_name,
            message_count=len(messages),
            tools_found=tools_found,
            errors=errors,
        )

    def _is_message_header(self, line: str) -> bool:
        """Check if a line looks like a message header."""
        # Pattern: username  HH:MM AM/PM
        if re.match(r"^\w+\s+\d{1,2}:\d{2}\s*[AP]M", line, re.IGNORECASE):
            return True
        # Pattern: [HH:MM] username:
        if re.match(r"^\[\d{1,2}:\d{2}\]\s*\w+:", line):
            return True
        # Pattern: username (HH:MM):
        if re.match(r"^\w+\s*\(\d{1,2}:\d{2}\):", line):
            return True
        return False

    def _extract_tools_from_message(
        self, text: str, mention_date: Optional[datetime]
    ) -> list[ExtractedTool]:
        """Extract tool mentions from a single message."""
        tools = []
        urls = self.extract_urls(text)
        sentiment = self.detect_sentiment(text)
        snippet = self.sanitize_snippet(text)

        # Process GitHub URLs
        for url in urls["github"]:
            name = self.extract_tool_name_from_url(url)
            if name:
                tools.append(
                    ExtractedTool(
                        name=name,
                        url=url,
                        github_url=url,
                        context_snippet=snippet,
                        sentiment=sentiment,
                        mention_date=mention_date,
                        categories=self.categorize_tool(name, url, text),
                    )
                )

        # Process npm URLs
        for url in urls["npm"]:
            name = self.extract_tool_name_from_url(url)
            if name:
                tools.append(
                    ExtractedTool(
                        name=name,
                        url=url,
                        github_url=None,
                        context_snippet=snippet,
                        sentiment=sentiment,
                        mention_date=mention_date,
                        categories=self.categorize_tool(name, url, text),
                    )
                )

        # Process PyPI URLs
        for url in urls["pypi"]:
            name = self.extract_tool_name_from_url(url)
            if name:
                tools.append(
                    ExtractedTool(
                        name=name,
                        url=url,
                        github_url=None,
                        context_snippet=snippet,
                        sentiment=sentiment,
                        mention_date=mention_date,
                        categories=self.categorize_tool(name, url, text),
                    )
                )

        return tools
