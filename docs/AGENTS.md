# vibecheck for AI Agents

This guide is for AI agents, bots, and LLMs interacting with vibecheck.

## Quick Reference

**Base URL**: `https://vibecheck.ito.com`
**API Prefix**: `/api/v1`
**Format**: JSON
**Auth**: None required (currently)

## What vibecheck Does

vibecheck tracks AI coding tools discussed in practitioner communities. Use it to:

1. **Find tools** - Search by name, category, or description
2. **Check vibes** - See if tools work, are maintained, community verdicts
3. **Track buzz** - When/where tools are mentioned
4. **Add intel** - Contribute tool info and evaluations

## Essential Endpoints

### Search (most useful)

```
GET /api/v1/search?q={query}&limit=10
```

Returns tools matching the query with relevance scores.

### List tools by category

```
GET /api/v1/tools?category={category-slug}
```

Categories: `coding-assistant`, `agent-framework`, `cli`, `editor`, `mcp-server`, `library`, `app`, `infrastructure`, `orchestration`, `research`, `paper`

### Get tool details

```
GET /api/v1/tools/{slug}
```

Returns full tool info including evaluations, links, GitHub stats.

### Recent mentions

```
GET /api/v1/communities/{community}/mentions?limit=20
```

Communities: `agi`, `henkaku`, `dg`

## MCP Integration

If you're Claude or another MCP-compatible assistant, vibecheck provides an MCP server with these tools:

| Tool | Description |
|------|-------------|
| `vibecheck_search` | Search for tools |
| `vibecheck_get` | Get tool details |
| `vibecheck_list` | List tools with filters |
| `vibecheck_add` | Add a new tool |
| `vibecheck_mention` | Record a mention |
| `vibecheck_categories` | List categories |
| `vibecheck_communities` | List communities |
| `vibecheck_recent` | Recent mentions |

## Adding Data

### Add a tool

```
POST /api/v1/tools
Content-Type: application/json

{
  "slug": "tool-name",
  "name": "Tool Name",
  "github_url": "https://github.com/org/repo",
  "categories": ["coding-assistant"],
  "description": "Brief description"
}
```

### Record a mention

```
POST /api/v1/ingest
Content-Type: application/json

{
  "tool_name": "Tool Name",
  "community": "agi",
  "context_snippet": "Sanitized context of mention",
  "sentiment": "positive",
  "source": "your-agent-name"
}
```

Sentiment values: `positive`, `negative`, `neutral`, `question`

## Best Practices

1. **Use search first** - Don't list all tools; search with specific queries
2. **Check before adding** - Search for existing tool before creating duplicate
3. **Provide context** - When recording mentions, include sanitized context
4. **Attribute source** - Set `source` field to identify your agent
5. **Respect rate limits** - Don't hammer the API

## Response Format

All responses are JSON. Errors return:

```json
{
  "detail": "Error message"
}
```

With appropriate HTTP status codes (400, 404, 500).

## Alternative Access

- **llms.txt**: `https://vibecheck.ito.com/llms.txt` - This document in plain text
- **API docs**: `https://vibecheck.ito.com/api/docs` - Interactive OpenAPI docs
- **Raw markdown**: `https://vibecheck.ito.com/docs/AGENTS.md`

## Contact

Built by Joi Ito. Source: https://github.com/Joi/vibecheck
