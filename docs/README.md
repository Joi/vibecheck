# vibecheck

AI Tools Intelligence - Community-curated tracking of AI coding tools.

## What is vibecheck?

vibecheck tracks AI tools discussed in practitioner communities (AGI, Henkaku, Digital Garage). It answers:

- **What tools exist?** - Searchable catalog with categories
- **Do they work?** - Community evaluations and verdicts
- **Who's using them?** - Mention tracking with timestamps
- **Is it maintained?** - GitHub stats, last commit, open issues

## Quick Start

### Search for tools

```bash
curl https://vibecheck.ito.com/api/v1/search?q=cursor
```

### List all tools

```bash
curl https://vibecheck.ito.com/api/v1/tools
```

### Get tool details

```bash
curl https://vibecheck.ito.com/api/v1/tools/cursor
```

### Add a tool

```bash
curl -X POST https://vibecheck.ito.com/api/v1/tools \
  -H "Content-Type: application/json" \
  -d '{
    "slug": "cursor",
    "name": "Cursor",
    "github_url": "https://github.com/getcursor/cursor",
    "categories": ["coding-assistant", "editor"],
    "description": "AI-first code editor"
  }'
```

## API Reference

See [API.md](./API.md) for complete endpoint documentation.

## For AI Agents

See [AGENTS.md](./AGENTS.md) for bot-specific integration guide.

## MCP Server

vibecheck provides an MCP server for Claude and other AI assistants:

```json
{
  "mcpServers": {
    "vibecheck": {
      "command": "uvx",
      "args": ["vibecheck-mcp"],
      "env": {
        "SUPABASE_URL": "https://pycvrvounfzlrwjdmuij.supabase.co",
        "SUPABASE_ANON_KEY": "your-anon-key"
      }
    }
  }
}
```

## Communities

| Slug | Name | Description |
|------|------|-------------|
| `agi` | AGI | AGI community discussions |
| `henkaku` | Henkaku | Henkaku community |
| `dg` | DG | Digital Garage community |

## Categories

| Slug | Name |
|------|------|
| `agent-framework` | Agent Frameworks |
| `coding-assistant` | Coding Assistants |
| `cli` | CLI Tools |
| `editor` | Editors & IDEs |
| `mcp-server` | MCP Servers |
| `library` | Libraries |
| `app` | Applications |
| `infrastructure` | Infrastructure |
| `orchestration` | Orchestration |
| `research` | Research Tools |
| `paper` | Papers |

## Links

- **Website**: https://vibecheck.ito.com
- **API Docs**: https://vibecheck.ito.com/api/docs
- **GitHub**: https://github.com/Joi/vibecheck
