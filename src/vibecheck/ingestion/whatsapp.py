"""WhatsApp chat log ingester."""

import re
from datetime import datetime
from typing import Optional

from .base import BaseIngester, ExtractedArticle, ExtractedTool, IngestionResult


class WhatsAppIngester(BaseIngester):
    """
    Ingest tools from WhatsApp chat exports.

    Supports the standard WhatsApp export format:
    [MM/DD/YY, HH:MM:SS AM/PM] Name: Message
    or
    MM/DD/YY, HH:MM - Name: Message
    """

    SOURCE_TYPE = "whatsapp"

    # WhatsApp message patterns
    # Pattern 1: [MM/DD/YY, HH:MM:SS AM/PM] Name: Message
    PATTERN_1 = re.compile(
        r"^\[(\d{1,2}/\d{1,2}/\d{2,4}),?\s+(\d{1,2}:\d{2}(?::\d{2})?\s*[AP]?M?)\]\s*([^:]+):\s*(.+)",
        re.IGNORECASE,
    )

    # Pattern 2: MM/DD/YY, HH:MM - Name: Message
    PATTERN_2 = re.compile(
        r"^(\d{1,2}/\d{1,2}/\d{2,4}),?\s+(\d{1,2}:\d{2})\s*-\s*([^:]+):\s*(.+)",
    )

    # Pattern 3: DD/MM/YYYY, HH:MM - Name: Message (European format)
    PATTERN_3 = re.compile(
        r"^(\d{1,2}/\d{1,2}/\d{4}),?\s+(\d{1,2}:\d{2})\s*-\s*([^:]+):\s*(.+)",
    )

    # Pattern 4: [YYYY/MM/DD, HH:MM:SS] Name: Message (ISO-like format)
    PATTERN_4 = re.compile(
        r"^\[(\d{4}/\d{1,2}/\d{1,2}),?\s+(\d{1,2}:\d{2}(?::\d{2})?)\]\s*([^:]+):\s*(.+)",
    )

    def parse(self, content: str, source_name: Optional[str] = None) -> IngestionResult:
        """
        Parse WhatsApp export and extract tool mentions.

        Args:
            content: WhatsApp chat export text
            source_name: Group name (optional)

        Returns:
            IngestionResult with extracted tools
        """
        lines = content.strip().split("\n")
        messages = []
        current_message = None
        errors = []

        for line in lines:
            parsed = self._parse_line(line)

            if parsed:
                # New message
                if current_message:
                    messages.append(current_message)
                current_message = parsed
            elif current_message:
                # Continuation of previous message
                current_message["text"] += "\n" + line

        if current_message:
            messages.append(current_message)

        tools_found = []
        articles_found = []
        seen_urls = set()  # Deduplicate URLs

        for msg in messages:
            try:
                text = msg["text"]
                urls = self.extract_urls(text)
                
                # Extract articles from "other" URLs (non-tool URLs)
                for url in urls["other"]:
                    # Skip duplicates and common non-article URLs
                    if url in seen_urls:
                        continue
                    if any(skip in url.lower() for skip in [
                        "youtube.com/watch", "youtu.be", "twitter.com", "x.com",
                        "instagram.com", "facebook.com", "tiktok.com", "linkedin.com/posts",
                        "whatsapp.com", "t.me", "discord.gg", "meet.google.com", "zoom.us"
                    ]):
                        continue
                    
                    seen_urls.add(url)
                    raw_snippet = f"{msg.get('sender', 'Unknown')}: {text}" if msg.get("sender") else text
                    snippet = self.sanitize_snippet(raw_snippet)
                    
                    articles_found.append(ExtractedArticle(
                        url=url,
                        title=None,  # Will be fetched later
                        context_snippet=snippet,
                        mention_date=msg.get("datetime"),
                        source_community=source_name,
                    ))
                
                # Extract tools (existing logic)
                if not self.is_tool_related(text):
                    continue

                extracted = self._extract_tools_from_message(
                    text=text,
                    mention_date=msg.get("datetime"),
                    sender=msg.get("sender"),
                )
                tools_found.extend(extracted)

            except Exception as e:
                errors.append(f"Error parsing message: {e}")

        return IngestionResult(
            source_type=self.SOURCE_TYPE,
            source_name=source_name,
            message_count=len(messages),
            tools_found=tools_found,
            articles_found=articles_found,
            errors=errors,
        )

    def _parse_line(self, line: str) -> Optional[dict]:
        """Try to parse a line as a WhatsApp message header."""
        for pattern in [self.PATTERN_1, self.PATTERN_2, self.PATTERN_3, self.PATTERN_4]:
            match = pattern.match(line)
            if match:
                date_str, time_str, sender, text = match.groups()

                # Try to parse datetime
                dt = self._parse_datetime(date_str, time_str)

                # Sanitize sender name
                sender = self._sanitize_sender(sender)

                return {
                    "datetime": dt,
                    "sender": sender,
                    "text": text.strip(),
                }

        return None

    def _parse_datetime(self, date_str: str, time_str: str) -> Optional[datetime]:
        """Parse date and time strings into datetime."""
        # Normalize time string
        time_str = time_str.strip().upper()

        # Try common formats
        formats = [
            "%m/%d/%y %I:%M:%S %p",
            "%m/%d/%y %I:%M %p",
            "%m/%d/%y %H:%M:%S",
            "%m/%d/%y %H:%M",
            "%m/%d/%Y %I:%M:%S %p",
            "%m/%d/%Y %I:%M %p",
            "%m/%d/%Y %H:%M:%S",
            "%m/%d/%Y %H:%M",
            "%d/%m/%y %H:%M",
            "%d/%m/%Y %H:%M",
            # ISO-like formats (YYYY/MM/DD)
            "%Y/%m/%d %H:%M:%S",
            "%Y/%m/%d %H:%M",
        ]

        combined = f"{date_str} {time_str}"

        for fmt in formats:
            try:
                return datetime.strptime(combined, fmt)
            except ValueError:
                continue

        return None

    def _sanitize_sender(self, sender: str) -> str:
        """Sanitize sender name for privacy."""
        if not self.sanitize:
            return sender.strip()

        # For privacy, we anonymize to just initials or "[user]"
        sender = sender.strip()

        # If it looks like a phone number, fully redact
        if re.match(r"^\+?\d[\d\s-]+$", sender):
            return "[user]"

        # Otherwise, use first initial only
        if sender:
            return f"{sender[0]}."

        return "[user]"

    def _extract_tools_from_message(
        self,
        text: str,
        mention_date: Optional[datetime],
        sender: Optional[str],
    ) -> list[ExtractedTool]:
        """Extract tool mentions from a single message."""
        tools = []
        urls = self.extract_urls(text)
        sentiment = self.detect_sentiment(text)

        # Build sanitized snippet (include anonymized sender context)
        raw_snippet = f"{sender}: {text}" if sender else text
        snippet = self.sanitize_snippet(raw_snippet)

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
