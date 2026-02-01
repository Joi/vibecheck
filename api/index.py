"""Vercel serverless entry point for vibecheck API."""

import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from vibecheck.api import app

# Vercel expects a handler named 'app' or 'handler'
# FastAPI apps work directly with Vercel's Python runtime
