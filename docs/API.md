# vibecheck API Reference

Base URL: `https://vibecheck.ito.com`

## Authentication

Currently no authentication required. Rate limiting may apply.

---

## Tools

### List Tools

```
GET /api/v1/tools
```

Query parameters:
- `category` (string) - Filter by category slug
- `page` (int) - Page number (default: 1)
- `per_page` (int) - Results per page (default: 50, max: 100)

Response:
```json
{
  "tools": [...],
  "total": 42,
  "page": 1,
  "per_page": 50,
  "has_more": false
}
```

### Get Tool

```
GET /api/v1/tools/{slug}
```

Response:
```json
{
  "id": "uuid",
  "slug": "cursor",
  "name": "Cursor",
  "url": "https://cursor.com",
  "github_url": "https://github.com/getcursor/cursor",
  "description": "AI-first code editor",
  "categories": ["coding-assistant", "editor"],
  "github_stars": 12345,
  "github_last_commit": "2026-01-30T12:00:00Z",
  "evaluations": [...],
  "links": [...]
}
```

### Create Tool

```
POST /api/v1/tools
```

Body:
```json
{
  "slug": "cursor",
  "name": "Cursor",
  "url": "https://cursor.com",
  "github_url": "https://github.com/getcursor/cursor",
  "categories": ["coding-assistant", "editor"],
  "communities": ["agi", "henkaku"],
  "description": "AI-first code editor"
}
```

### Update Tool

```
PATCH /api/v1/tools/{slug}
```

Body: Same as create, all fields optional.

---

## Search

### Search Tools

```
GET /api/v1/search
```

Query parameters:
- `q` (string, required) - Search query
- `category` (string) - Filter by category
- `limit` (int) - Max results (default: 20)

Response:
```json
{
  "results": [
    {
      "slug": "cursor",
      "name": "Cursor",
      "description": "...",
      "score": 0.95
    }
  ],
  "query": "cursor",
  "total": 1
}
```

---

## Categories

### List Categories

```
GET /api/v1/categories
```

Response:
```json
[
  {
    "slug": "coding-assistant",
    "name": "Coding Assistants",
    "description": "AI pair programming tools",
    "tool_count": 15
  }
]
```

---

## Communities

### List Communities

```
GET /api/v1/communities
```

Response:
```json
[
  {
    "slug": "agi",
    "name": "AGI",
    "description": "AGI community discussions",
    "tool_count": 25
  }
]
```

### Get Community Tools

```
GET /api/v1/communities/{slug}/tools
```

### Get Community Mentions

```
GET /api/v1/communities/{slug}/mentions
```

Query parameters:
- `limit` (int) - Max results (default: 50)

---

## Evaluations

### Add Evaluation

```
POST /api/v1/tools/{slug}/evaluations
```

Body:
```json
{
  "works": true,
  "actively_maintained": true,
  "verdict": "solid",
  "notes": "Great tool, works well with Claude",
  "security_notes": "No concerns",
  "communities": ["agi"]
}
```

Verdict values: `essential`, `solid`, `situational`, `caution`, `avoid`

---

## Links

### Add Link

```
POST /api/v1/tools/{slug}/links
```

Body:
```json
{
  "url": "https://example.com/review",
  "title": "My review of Cursor",
  "link_type": "review",
  "snippet": "Brief excerpt..."
}
```

Link types: `blog`, `video`, `discussion`, `docs`, `tutorial`, `review`, `other`

---

## Mentions

### Get Tool Mentions

```
GET /api/v1/tools/{slug}/mentions
```

Response:
```json
{
  "tool": "cursor",
  "mentions": [
    {
      "community": "agi",
      "mentioned_at": "2026-02-01T14:30:00Z",
      "context_snippet": "Really impressed with...",
      "sentiment": "positive"
    }
  ],
  "total": 5
}
```

---

## Webhooks / Ingest

### Ingest Single Mention

```
POST /api/v1/ingest
```

For external systems (ai-wiki, etc.) to push tool mentions.

Body:
```json
{
  "tool_name": "Cursor",
  "tool_slug": "cursor",
  "tool_url": "https://cursor.com",
  "github_url": "https://github.com/getcursor/cursor",
  "community": "agi",
  "mentioned_at": "2026-02-01T14:30:00Z",
  "context_snippet": "Really impressed with the tab completion",
  "sentiment": "positive",
  "source": "ai-wiki",
  "source_doc_url": "https://ai-wiki.example.com/docs/cursor"
}
```

Response:
```json
{
  "received": 1,
  "created": 1,
  "updated": 1,
  "skipped": 0,
  "errors": []
}
```

### Batch Ingest

```
POST /api/v1/ingest/batch
```

Body:
```json
{
  "mentions": [...],
  "source": "slack-import",
  "deduplicate": true
}
```

---

## Health

### Health Check

```
GET /health
```

Response:
```json
{
  "status": "ok",
  "service": "vibecheck"
}
```
