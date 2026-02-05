# vibecheck

> AI tools intelligence — curated evaluations with API access for humans and agents

**Live at [vibecheck.ito.com](https://vibecheck.ito.com)**

## What is this?

A curated database of AI coding tools and articles with structured evaluations, community context, and an API-first design. Think "OpenReview meets Product Hunt" for AI developer tools.

### Why?

- **Discovery**: Find tools your peers actually use
- **Evaluation**: Structured verdicts, not just hype
- **Context**: See what people are saying in communities
- **Articles**: Curated reading on vibe coding and AI development
- **API-first**: Query from your agents and bots

## Features

### Tools Database

Every tool gets evaluated on:
- **Works?** — Does it actually function as advertised?
- **Actively maintained?** — Recent commits, responsive maintainers?
- **Security notes** — Any concerns to be aware of?
- **Verdict** — Overall recommendation

| Verdict | Meaning |
|---------|---------|
| essential | Daily driver, highly recommended |
| solid | Works well, good choice |
| situational | Right tool for specific use cases |
| caution | Works but has significant issues |
| avoid | Broken, abandoned, or dangerous |

### Articles

Curated articles about vibe coding, AI tools, and developer workflows. Articles are imported from community discussions with real titles and descriptions fetched from source URLs.

### Community Import

Import tool mentions and articles from:
- **WhatsApp groups** — Export and import with automatic metadata fetching
- **Slack channels** — Export or copy-paste
- Discord (coming soon)

All imports are **sanitized** to remove personal information while preserving useful context.

### Admin Interface

Manage tools, articles, and communities at `/admin` (requires login).

## Quick Start

### Prerequisites

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) (recommended) or pip
- Supabase account

### Installation

```bash
# Clone
git clone https://github.com/joi/vibecheck.git
cd vibecheck

# Install dependencies
uv sync

# Copy environment template
cp .env.example .env
# Edit .env with your Supabase credentials

# Run database migrations
supabase db push

# Start the API server
uv run uvicorn vibecheck.api:app --reload
```

## API Reference

Base URL: `https://vibecheck.ito.com/api/v1/`

### Tools

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/tools` | List all tools (paginated) |
| GET | `/tools/{slug}` | Get tool with evaluations & links |
| POST | `/tools` | Add a new tool |
| PATCH | `/tools/{slug}` | Update tool info |

### Articles

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/articles` | List all articles (paginated) |
| GET | `/articles/{slug}` | Get article details |
| POST | `/articles` | Add a new article |

### Search & Discovery

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/search?q=` | Search tools and articles |
| GET | `/categories` | List categories with counts |
| GET | `/communities` | List communities |

## WhatsApp Import

Import tools and articles from WhatsApp group exports:

```bash
# Import with automatic metadata fetching (recommended)
uv run python scripts/ingest_whatsapp.py chat-export.zip --community agi

# Incremental import (skip already-imported content)
uv run python scripts/ingest_whatsapp.py chat-export.zip --community agi --auto-since

# Dry run to preview what will be imported
uv run python scripts/ingest_whatsapp.py chat-export.zip --community agi --dry-run

# Skip URL fetching (faster, but uses generated titles)
uv run python scripts/ingest_whatsapp.py chat-export.zip --community agi --no-fetch
```

The import script:
- Extracts GitHub URLs as tools
- Extracts article URLs (blogs, docs, etc.)
- Fetches real titles and descriptions from URLs
- Deduplicates against existing database content
- Supports incremental imports with `--auto-since`

## Project Structure

```
vibecheck/
├── src/vibecheck/
│   ├── api.py           # FastAPI application
│   ├── admin.py         # Admin interface
│   ├── config.py        # Settings management
│   ├── database.py      # Supabase client
│   └── models.py        # Pydantic models
├── scripts/
│   └── ingest_whatsapp.py  # WhatsApp import script
├── supabase/
│   └── migrations/      # Database schema
└── tests/               # Test suite
```

## Deployment

Deployed on Vercel with Supabase backend:

- **Frontend/API**: Vercel (auto-deploys from main)
- **Database**: Supabase (PostgreSQL)
- **Domain**: vibecheck.ito.com

## Issue Tracking

We use [beads](https://github.com/obra/beads) as the primary issue tracker (stored in `.beads/`).

```bash
# View open issues
bd list

# See what's ready to work on
bd ready
```

## Contributing

Contributions welcome!

1. Fork the repo
2. Create a feature branch
3. Make your changes
4. Run tests: `uv run pytest`
5. Submit a PR

## License

MIT

## Author

[Joi Ito](https://joi.ito.com)

Built with help from the AI tools community.
