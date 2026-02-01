# vibecheck Architecture

## Overview

vibecheck is a tool intelligence platform with three main layers:

```
┌─────────────────────────────────────────────────────────────┐
│                      Web UI (Future)                        │
│                   vibecheck.ito.com                         │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      REST API Layer                         │
│                    FastAPI + Pydantic                       │
│                                                             │
│  /api/v1/tools      - CRUD for tools                       │
│  /api/v1/search     - Search tools                         │
│  /api/v1/bot/*      - Bot-optimized endpoints              │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                     Database Layer                          │
│                    Supabase (Postgres)                      │
│                                                             │
│  - Row Level Security for public read / auth write          │
│  - Realtime subscriptions (future)                          │
│  - Edge functions for GitHub stats refresh                  │
└─────────────────────────────────────────────────────────────┘
```

## Components

### API Layer (`src/vibecheck/api.py`)

FastAPI application with:
- Public read access (no auth required)
- Authenticated write access (GitHub OAuth)
- Bot-friendly endpoints with flat responses
- CORS enabled for cross-origin access

### Database Layer (`src/vibecheck/database.py`)

Supabase client wrappers:
- `ToolsDB` - Tool CRUD and search
- `EvaluationsDB` - User evaluations
- `LinksDB` - External links
- `CategoriesDB` - Category management

### Ingestion Layer (`src/vibecheck/ingestion/`)

Chat log parsers for importing tool mentions:
- `SlackIngester` - Slack JSON export and copy-paste
- `WhatsAppIngester` - WhatsApp chat export

All ingesters:
- Extract GitHub/npm/PyPI URLs
- Detect sentiment (positive/negative/neutral/question)
- Sanitize personal information
- Categorize tools automatically

### Models (`src/vibecheck/models.py`)

Pydantic models for:
- Request validation
- Response serialization
- Type safety throughout

## Data Flow

### Tool Submission

```
User/Bot → POST /tools → Validation → Database → Response
                            │
                            └── GitHub URL? → Queue for stats refresh
```

### Tool Discovery

```
GET /tools?category=agent-framework
         ↓
    Query Database
         ↓
    Filter & Sort
         ↓
    Paginate
         ↓
    Return JSON
```

### Chat Import

```
Export File → Ingester.parse()
                  │
                  ├── Parse messages
                  ├── Filter tool-related
                  ├── Extract URLs
                  ├── Detect sentiment
                  ├── Sanitize snippets
                  └── Return ExtractedTools[]
                           │
                           ▼
                  POST /tools (batch)
                  POST /tools/{slug}/mentions
```

## Database Schema

See `supabase/migrations/` for full schema.

### Core Tables

| Table | Purpose |
|-------|---------|
| `tools` | Tool catalog with metadata |
| `evaluations` | User verdicts (one per user per tool) |
| `links` | External resources |
| `users` | GitHub-authenticated users |
| `categories` | Tool categories |
| `import_batches` | Bulk import tracking |
| `tool_mentions` | Sanitized discussion context |

### Row Level Security

- **Read**: Public (no auth required)
- **Insert**: Authenticated users
- **Update**: Own records only (evaluations)
- **Admin**: Full access via service role

## Authentication

GitHub OAuth flow:
1. User clicks "Sign in with GitHub"
2. Redirect to GitHub OAuth
3. Callback with code
4. Exchange for access token
5. Fetch user info
6. Create/update user record
7. Return JWT for API access

## Security Considerations

### Data Privacy

- Chat imports are sanitized (emails, phone numbers, names removed)
- Users control their own evaluations
- No raw chat logs stored (only sanitized snippets)

### API Security

- Rate limiting (TODO)
- Input validation via Pydantic
- SQL injection prevention via Supabase client
- CORS configured for known origins (production)

## Future: Federation

The architecture is designed for future federation:

```
┌──────────────────┐    ┌──────────────────┐
│ vibecheck.ito.com│◄──►│ alice.tools      │
│  (Joi's instance)│    │  (Alice's fork)  │
└────────┬─────────┘    └────────┬─────────┘
         │                       │
         └───────────┬───────────┘
                     │
              ┌──────▼──────┐
              │  Shared     │
              │  Protocol   │
              │             │
              │  - Tool IDs │
              │  - Reviews  │
              │  - Links    │
              └─────────────┘
```

Federation design principles:
- Each instance is independent (can run without peers)
- Shared data format for tools and reviews
- Pull-based sync (no push requirements)
- Trust levels (full, tools-only, harvest)
- No database required for lightweight participants

See `docs/FEDERATION.md` (future) for protocol spec.

## Deployment

### Recommended Stack

- **API**: Fly.io or Railway (easy Python deployment)
- **Database**: Supabase (managed Postgres + auth)
- **Domain**: vibecheck.ito.com (Cloudflare DNS)

### Environment Variables

```bash
# Supabase
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_ANON_KEY=eyJ...
SUPABASE_SERVICE_ROLE_KEY=eyJ...

# GitHub OAuth
GITHUB_CLIENT_ID=xxx
GITHUB_CLIENT_SECRET=xxx
GITHUB_TOKEN=xxx  # For API calls

# App
APP_URL=https://vibecheck.ito.com
DEBUG=false
```

## Performance Considerations

### Database

- Indexes on `slug`, `categories`, `github_stars`
- GIN index on `categories` for array queries
- Connection pooling via Supabase

### API

- Pagination (default 50, max 100)
- Selective field loading
- Caching headers (future)

### Search

- Currently: ILIKE queries (simple)
- Future: Full-text search via Postgres `tsvector`
