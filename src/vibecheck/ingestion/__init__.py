"""Ingestion interfaces for importing tools from various sources."""

from .base import BaseIngester, ExtractedArticle, ExtractedTool, IngestionResult
from .slack import SlackIngester
from .whatsapp import WhatsAppIngester

__all__ = [
    "BaseIngester",
    "ExtractedArticle",
    "ExtractedTool",
    "IngestionResult",
    "SlackIngester",
    "WhatsAppIngester",
]
