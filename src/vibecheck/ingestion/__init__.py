"""Ingestion interfaces for importing tools from various sources."""

from .base import BaseIngester, IngestionResult
from .slack import SlackIngester
from .whatsapp import WhatsAppIngester

__all__ = ["BaseIngester", "IngestionResult", "SlackIngester", "WhatsAppIngester"]
