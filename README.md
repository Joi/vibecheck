# vibecheck

> AI tools intelligence — curated evaluations with API access for humans and agents

**vibecheck.ito.com** (coming soon)

## What is this?

A curated database of AI coding tools with structured evaluations, community context, and an API-first design for agent access.

### Features

- **Structured evaluations**: Does it work? Actively maintained? Security concerns?
- **Community context**: Discussion snippets, links to posts/reviews
- **API-first**: Query and contribute via REST API
- **Bot-friendly**: Designed for agent integration
- **Open methodology**: Contribute to how we evaluate tools

## Status

🚧 **Early development** — Setting up infrastructure

## Quick Start

```bash
# Clone
git clone https://github.com/joi/vibecheck.git
cd vibecheck

# Install dependencies
uv sync

# Run locally
uv run uvicorn vibecheck.api:app --reload
```

## API

Base URL: `https://vibecheck.ito.com/api/v1/` (coming soon)

### Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/tools` | List all tools |
| GET | `/tools/{slug}` | Get tool details + evaluations |
| POST | `/tools` | Submit a new tool |
| POST | `/tools/{slug}/evaluations` | Add evaluation |
| POST | `/tools/{slug}/links` | Add external link |
| GET | `/categories` | List categories |
| GET | `/search?q=` | Search tools |

### Authentication

GitHub OAuth for submissions. Read access is public.

## Data Model

```
Tool
├── name, slug, url, github_url
├── categories[]
├── github_stars, last_commit (auto-updated)
└── source_context (where we found it)

Evaluation
├── works: bool
├── actively_maintained: bool
├── verdict: essential | solid | situational | caution | avoid
├── security_notes
├── notes
└── communities[] (tags like #digitalgarage)

Link
├── url, title, type
└── snippet (pull quote)
```

## Verdicts

| Verdict | Meaning |
|---------|---------|
| 🔥 essential | Daily driver, highly recommended |
| ✅ solid | Works well, good choice |
| 🤷 situational | Right tool for specific use cases |
| ⚠️ caution | Works but has significant issues |
| 💀 avoid | Broken, abandoned, or dangerous |

## Contributing

See [CONTRIBUTING.md](docs/CONTRIBUTING.md) for guidelines.

### Issue Tracking

We use [beads](https://github.com/obra/beads) for issue tracking. GitHub Issues are enabled for external contributors but beads is the source of truth.

## Roadmap

- [ ] Core API + Supabase schema
- [ ] Web UI (basic dashboard)
- [ ] Channel ingestion (Slack, WhatsApp, Discord)
- [ ] GitHub stats auto-refresh
- [ ] Federation protocol (share reviews across instances)

## License

MIT

## Author

[Joi Ito](https://joi.ito.com) — with contributions from the community
