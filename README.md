# vibecheck 🎯

> AI tools intelligence — curated evaluations with API access for humans and agents

**vibecheck.ito.com** (coming soon)

## What is this?

A curated database of AI coding tools with structured evaluations, community context, and an API-first design. Think "OpenReview meets Product Hunt" for AI developer tools.

### Why?

- **Discovery**: Find tools your peers actually use
- **Evaluation**: Structured verdicts, not just hype
- **Context**: See what people are saying in communities
- **API-first**: Query from your agents and bots

## Status

🚧 **Early development** — Core infrastructure in place, awaiting Supabase connection

## Features

### Structured Evaluations

Every tool gets evaluated on:
- **Works?** — Does it actually function as advertised?
- **Actively maintained?** — Recent commits, responsive maintainers?
- **Security notes** — Any concerns to be aware of?
- **Verdict** — Overall recommendation

| Verdict | Meaning |
|---------|---------|
| 🔥 essential | Daily driver, highly recommended |
| ✅ solid | Works well, good choice |
| 🤷 situational | Right tool for specific use cases |
| ⚠️ caution | Works but has significant issues |
| 💀 avoid | Broken, abandoned, or dangerous |

### Community Context

Import tool mentions from:
- Slack channels (export or copy-paste)
- WhatsApp groups (export)
- Discord (coming soon)
- Awesome lists (harvesting)

All imports are **sanitized** to remove personal information while preserving useful context.

### Bot-Friendly API

Designed for agent integration:
```bash
# Get tool info
curl https://vibecheck.ito.com/api/v1/bot/tool/cursor

# Get recommendations
curl "https://vibecheck.ito.com/api/v1/bot/recommend?use_case=code+review"
```

## Quick Start

### Prerequisites

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) (recommended) or pip
- Supabase account (for full functionality)

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

### Local Development (No Supabase)

For testing the ingestion pipeline without a database:

```python
from vibecheck.ingestion import SlackIngester

ingester = SlackIngester(sanitize=True)
result = ingester.parse(open("slack-export.txt").read(), source_name="#ai-tools")

for tool in result.tools_found:
    print(f"{tool.name}: {tool.sentiment} - {tool.context_snippet}")
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

### Evaluations

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/tools/{slug}/evaluations` | Add/update your evaluation |

### Links

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/tools/{slug}/links` | Add external link (blog, video, etc.) |

### Search & Discovery

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/search?q=` | Search tools |
| GET | `/categories` | List categories with counts |

### Bot Endpoints

Simplified responses for agent consumption:

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/bot/tool/{slug}` | Flat tool summary with metrics |
| GET | `/bot/recommend?use_case=` | Get recommendations for a use case |

## Data Model

```
Tool
├── slug, name, url, github_url
├── categories[]
├── description
├── GitHub stats (stars, last_commit, auto-refreshed)
└── source_context (where we found it)

Evaluation
├── works: bool
├── actively_maintained: bool
├── verdict: essential | solid | situational | caution | avoid
├── security_notes
├── notes
└── communities[] (e.g., #digitalgarage, #ai-tools)

Link
├── url, title
├── type: blog | video | discussion | docs | tutorial | review
└── snippet (pull quote)
```

## Ingestion

### Slack Import

```python
from vibecheck.ingestion import SlackIngester

# From JSON export
ingester = SlackIngester()
result = ingester.parse(open("channel-export.json").read())

# From copy-pasted text
result = ingester.parse("""
alice  2:30 PM
Check out https://github.com/anthropics/claude-code - been using it all week

bob  2:35 PM
Nice! How does it compare to cursor?
""")
```

### WhatsApp Import

```python
from vibecheck.ingestion import WhatsAppIngester

ingester = WhatsAppIngester()
result = ingester.parse(open("WhatsApp Chat - AI Tools.txt").read())

# All personal info is automatically sanitized
for tool in result.tools_found:
    print(tool.context_snippet)  # Names replaced with initials
```

## Project Structure

```
vibecheck/
├── src/vibecheck/
│   ├── api.py           # FastAPI application
│   ├── config.py        # Settings management
│   ├── database.py      # Supabase client
│   ├── models.py        # Pydantic models
│   └── ingestion/       # Chat log parsers
│       ├── base.py      # Base ingester
│       ├── slack.py     # Slack export parser
│       └── whatsapp.py  # WhatsApp export parser
├── supabase/
│   └── migrations/      # Database schema
├── docs/                # Documentation
├── tests/               # Test suite
└── scripts/             # Utility scripts
```

## Roadmap

### Phase 1: Core (Current)
- [x] Database schema
- [x] REST API
- [x] Slack/WhatsApp ingestion
- [ ] Supabase connection
- [ ] GitHub OAuth
- [ ] Basic web UI

### Phase 2: Growth
- [ ] GitHub stats auto-refresh
- [ ] Discord ingestion
- [ ] Awesome list harvesting
- [ ] Search improvements (full-text)

### Phase 3: Federation
- [ ] Federation protocol spec
- [ ] Peer discovery
- [ ] Cross-instance review aggregation
- [ ] Self-hosted instances

## Issue Tracking

We use [beads](https://github.com/obra/beads) as the primary issue tracker (stored in `.beads/`).

GitHub Issues are enabled for external contributors, but the beads database is the source of truth.

```bash
# View open issues
bd list

# See what's ready to work on
bd ready
```

## Contributing

Contributions welcome! See [CONTRIBUTING.md](docs/CONTRIBUTING.md) for guidelines.

### Quick Contribution Guide

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
