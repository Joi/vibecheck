"""Web UI routes for vibecheck."""

import os
import time
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.templating import Jinja2Templates

from .database import ArticlesDB, CommunitiesDB, EvaluationsDB, LinksDB, ToolsDB

# Simple in-memory cache with TTL
_cache: dict = {}
_cache_ttl = 300  # 5 minutes

def get_cached(key: str, fetch_fn, ttl: int = _cache_ttl):
    """Get value from cache or fetch and cache it."""
    now = time.time()
    if key in _cache:
        value, expires = _cache[key]
        if now < expires:
            return value
    value = fetch_fn()
    _cache[key] = (value, now + ttl)
    return value

router = APIRouter()

# Templates directory - handle both local dev and Vercel deployment
def find_templates_dir() -> Path:
    """Find templates directory in various possible locations."""
    candidates = [
        Path(__file__).parent / "templates",  # Local dev
        Path("src/vibecheck/templates"),  # Vercel relative
        Path(os.getcwd()) / "src" / "vibecheck" / "templates",  # Vercel cwd
        Path("/var/task/src/vibecheck/templates"),  # AWS Lambda style
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    # Return first candidate even if not found (will error later with clear message)
    return candidates[0]

templates_dir = find_templates_dir()
templates = None  # Lazy load to avoid startup errors

def format_date(value, fmt="%b %d"):
    """Format a date string or datetime object."""
    if value is None:
        return ""
    if isinstance(value, str):
        # Parse ISO format string
        try:
            from datetime import datetime
            # Handle ISO format with or without microseconds
            if "." in value:
                dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            else:
                dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return dt.strftime(fmt)
        except (ValueError, AttributeError):
            return value[:10] if len(value) >= 10 else value
    # Assume it's a datetime object
    try:
        return value.strftime(fmt)
    except AttributeError:
        return str(value)

def get_templates():
    """Lazy load templates to provide better error messages."""
    global templates
    if templates is None:
        if not templates_dir.exists():
            raise RuntimeError(f"Templates directory not found. Tried: {templates_dir}")
        templates = Jinja2Templates(directory=str(templates_dir))
        # Add custom filters
        templates.env.filters["format_date"] = format_date
    return templates


def get_tools_db() -> ToolsDB:
    return ToolsDB()


def get_communities_db() -> CommunitiesDB:
    return CommunitiesDB()


def get_articles_db() -> ArticlesDB:
    return ArticlesDB()


def get_evaluations_db() -> EvaluationsDB:
    return EvaluationsDB()


def get_links_db() -> LinksDB:
    return LinksDB()


@router.get("/", response_class=HTMLResponse)
async def home(
    request: Request,
    page: int = Query(1, ge=1),
    format: Optional[str] = Query(None),
    tools_db: ToolsDB = Depends(get_tools_db),
    communities_db: CommunitiesDB = Depends(get_communities_db),
    articles_db: ArticlesDB = Depends(get_articles_db),
):
    """Homepage with tools list. Use ?format=md for markdown."""
    try:
        per_page = 24 if format != "md" else 50
        result = tools_db.list_tools(page=page, per_page=per_page, sort_by="created_at", sort_order="desc")
        
        # Markdown format for agents
        if format == "md":
            tools = result.get("tools", [])
            md = "# Vibecheck - AI Tools Directory\n\n"
            md += f"**{result.get('total', 0)} tools** curated for AI practitioners\n\n"
            md += "## Tools\n\n"
            for tool in tools:
                md += f"### [{tool['name']}](/tools/{tool['slug']})\n"
                if tool.get('description'):
                    md += f"{tool['description'][:200]}\n"
                if tool.get('url'):
                    md += f"- URL: {tool['url']}\n"
                if tool.get('github_url'):
                    md += f"- GitHub: {tool['github_url']}\n"
                md += "\n"
            md += "\n---\n"
            md += "Use `/docs?format=md` for API documentation.\n"
            return Response(content=md, media_type="text/markdown; charset=utf-8")
        
        # Get communities for all tools in ONE query (not N+1)
        tools = result.get("tools", [])
        tool_ids = [t["id"] for t in tools]
        communities_by_tool = communities_db.get_communities_for_tools_batch(tool_ids)
        
        # Add communities to each tool
        for tool in tools:
            tool_communities = communities_by_tool.get(tool["id"], [])
            tool["communities"] = [c["name"] for c in tool_communities]
        
        # Cache communities list and article count (don't change often)
        communities = get_cached("communities_list", communities_db.list_communities)
        total_articles = get_cached(
            "articles_total",
            lambda: articles_db.list_articles(page=1, per_page=1).get("total", 0)
        )
        
        return get_templates().TemplateResponse("index.html", {
            "request": request,
            "active_page": "tools",
            "tools": tools,
            "total_tools": result.get("total", 0),
            "total_articles": total_articles,
            "communities": communities,
            "page": page,
            "has_more": page * per_page < result.get("total", 0),
        })
    except Exception as e:
        import traceback
        return JSONResponse({
            "error": str(e),
            "traceback": traceback.format_exc()
        }, status_code=500)


@router.get("/tools", response_class=HTMLResponse)
async def tools_list(
    request: Request,
    page: int = Query(1, ge=1),
    category: Optional[str] = None,
    tools_db: ToolsDB = Depends(get_tools_db),
    communities_db: CommunitiesDB = Depends(get_communities_db),
    articles_db: ArticlesDB = Depends(get_articles_db),
):
    """Tools listing page."""
    per_page = 24
    result = tools_db.list_tools(page=page, per_page=per_page, category=category, sort_by="created_at", sort_order="desc")
    
    # Get communities for all tools in ONE query (not N+1)
    tools = result.get("tools", [])
    tool_ids = [t["id"] for t in tools]
    communities_by_tool = communities_db.get_communities_for_tools_batch(tool_ids)
    
    for tool in tools:
        tool_communities = communities_by_tool.get(tool["id"], [])
        tool["communities"] = [c["name"] for c in tool_communities]
    
    # Cache communities list and article count
    communities = get_cached("communities_list", communities_db.list_communities)
    total_articles = get_cached(
        "articles_total",
        lambda: articles_db.list_articles(page=1, per_page=1).get("total", 0)
    )
    
    return get_templates().TemplateResponse("index.html", {
        "request": request,
        "active_page": "tools",
        "tools": tools,
        "total_tools": result.get("total", 0),
        "total_articles": total_articles,
        "communities": communities,
        "page": page,
        "has_more": page * per_page < result.get("total", 0),
    })


@router.get("/tools/{slug}", response_class=HTMLResponse)
async def tool_detail(
    request: Request,
    slug: str,
    format: Optional[str] = Query(None),
    tools_db: ToolsDB = Depends(get_tools_db),
    communities_db: CommunitiesDB = Depends(get_communities_db),
    evaluations_db: EvaluationsDB = Depends(get_evaluations_db),
    links_db: LinksDB = Depends(get_links_db),
):
    """Tool detail page. Use ?format=md for markdown."""
    try:
        tool = tools_db.get_tool(slug)
        if not tool:
            raise HTTPException(status_code=404, detail="Tool not found")
        
        # Get related data (with error handling)
        evaluations = evaluations_db.get_evaluations_for_tool(tool["id"])
        links = links_db.get_links_for_tool(tool["id"])
        
        try:
            communities = communities_db.get_communities_for_tool(tool["id"])
        except Exception:
            communities = []
        
        try:
            mentions = links_db.get_tool_mentions(tool["id"])
        except Exception:
            mentions = []
        
        # Extract community info
        community_list = []
        for c in communities:
            if c.get("communities"):
                community_list.append({
                    "slug": c["communities"]["slug"],
                    "name": c["communities"]["name"],
                })
        
        # Markdown format for agents
        if format == "md":
            md = f"# {tool['name']}\n\n"
            if tool.get('description'):
                md += f"{tool['description']}\n\n"
            if tool.get('url'):
                md += f"**URL:** {tool['url']}\n"
            if tool.get('github_url'):
                md += f"**GitHub:** {tool['github_url']}\n"
            if tool.get('github_stars'):
                md += f"**Stars:** {tool['github_stars']}\n"
            md += "\n"
            
            if evaluations:
                md += "## Evaluations\n\n"
                for ev in evaluations:
                    md += f"- **Verdict:** {ev.get('verdict', 'N/A')}\n"
                    md += f"- **Works:** {'Yes' if ev.get('works') else 'No'}\n"
                    md += f"- **Maintained:** {'Yes' if ev.get('actively_maintained') else 'No'}\n"
                    if ev.get('notes'):
                        md += f"- **Notes:** {ev['notes']}\n"
                    md += "\n"
            
            if links:
                md += "## Links\n\n"
                for link in links:
                    md += f"- [{link.get('title', link['url'])}]({link['url']})\n"
                md += "\n"
            
            return Response(content=md, media_type="text/markdown; charset=utf-8")
        
        return get_templates().TemplateResponse("tool.html", {
            "request": request,
            "active_page": "tools",
            "tool": tool,
            "evaluations": evaluations,
            "links": links,
            "communities": community_list,
            "mentions": mentions,
        })
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        return JSONResponse({
            "error": str(e),
            "traceback": traceback.format_exc()
        }, status_code=500)


@router.get("/articles", response_class=HTMLResponse)
async def articles_list(
    request: Request,
    page: int = Query(1, ge=1),
    format: Optional[str] = Query(None),
    articles_db: ArticlesDB = Depends(get_articles_db),
):
    """Articles listing page. Use ?format=md for markdown."""
    per_page = 20 if format != "md" else 50
    result = articles_db.list_articles(page=page, per_page=per_page)
    articles = result.get("articles", [])
    
    # Markdown format for agents
    if format == "md":
        md = "# Vibecheck - Articles\n\n"
        md += f"**{result.get('total', 0)} articles** on vibe coding and AI tools\n\n"
        for article in articles:
            md += f"## [{article['title']}]({article['url']})\n"
            if article.get('summary'):
                md += f"{article['summary'][:300]}\n"
            if article.get('community_slug'):
                md += f"- Community: {article['community_slug']}\n"
            md += "\n"
        md += "\n---\n"
        md += "Use `/docs?format=md` for API documentation.\n"
        return Response(content=md, media_type="text/markdown; charset=utf-8")
    
    return get_templates().TemplateResponse("articles.html", {
        "request": request,
        "active_page": "articles",
        "articles": articles,
        "total_articles": result.get("total", 0),
        "page": page,
        "has_more": page * per_page < result.get("total", 0),
    })


@router.get("/bookmarks", response_class=HTMLResponse)
async def bookmarks_page(request: Request):
    """Bookmarks page - items are stored in localStorage and rendered client-side."""
    return get_templates().TemplateResponse("bookmarks.html", {
        "request": request,
        "active_page": "bookmarks",
    })


@router.get("/discover", response_class=HTMLResponse)
async def discover_page(
    request: Request,
    mode: str = Query("mixed", regex="^(tools|articles|mixed)$"),
    tools_db: ToolsDB = Depends(get_tools_db),
    articles_db: ArticlesDB = Depends(get_articles_db),
):
    """Tinder-like swipe interface for discovering tools and articles."""
    items = []
    
    if mode in ("tools", "mixed"):
        # Get random tools (order by random-ish - using created_at for now)
        tools_result = tools_db.list_tools(page=1, per_page=30, sort_by="created_at")
        for tool in tools_result.get("tools", []):
            items.append({
                "type": "tool",
                "slug": tool["slug"],
                "name": tool.get("name", tool["slug"]),
                "description": tool.get("description", ""),
                "categories": tool.get("categories", []),
                "github_stars": tool.get("github_stars"),
                "upvotes": tool.get("upvotes", 0),
                "url": f"/tools/{tool['slug']}",
            })
    
    if mode in ("articles", "mixed"):
        articles_result = articles_db.list_articles(page=1, per_page=30)
        for article in articles_result.get("articles", []):
            items.append({
                "type": "article",
                "slug": article["slug"],
                "title": article.get("title", "Untitled"),
                "summary": article.get("summary", ""),
                "tags": article.get("tags", []),
                "community_slug": article.get("community_slug"),
                "upvotes": article.get("upvotes", 0),
                "url": article.get("url", f"/articles/{article['slug']}"),
            })
    
    # Shuffle items for variety
    import random
    random.shuffle(items)
    
    return get_templates().TemplateResponse("discover.html", {
        "request": request,
        "active_page": "discover",
        "items": items,
        "mode": mode,
    })


@router.get("/communities", response_class=HTMLResponse)
async def communities_list(
    request: Request,
    communities_db: CommunitiesDB = Depends(get_communities_db),
):
    """Communities listing page."""
    communities = communities_db.list_communities()
    
    return get_templates().TemplateResponse("communities.html", {
        "request": request,
        "active_page": "communities",
        "communities": communities,
    })


@router.get("/communities/{slug}", response_class=HTMLResponse)
async def community_detail(
    request: Request,
    slug: str,
    communities_db: CommunitiesDB = Depends(get_communities_db),
):
    """Community detail page."""
    try:
        community = communities_db.get_community(slug)
        if not community:
            raise HTTPException(status_code=404, detail="Community not found")
        
        # Get tools for this community
        tool_communities = communities_db.get_tools_for_community(community["slug"])
        
        # Extract tool info from the join result
        tools = []
        for tc in tool_communities:
            if tc.get("tools"):
                tool = tc["tools"]
                tool["first_mentioned"] = tc.get("first_mentioned")
                tools.append(tool)
        
        return get_templates().TemplateResponse("community.html", {
            "request": request,
            "active_page": "communities",
            "community": community,
            "tools": tools,
        })
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        return JSONResponse({
            "error": str(e),
            "traceback": traceback.format_exc()
        }, status_code=500)



# ============== Documentation ==============

@router.get("/docs", response_class=HTMLResponse)
async def docs_page(
    request: Request,
    format: Optional[str] = Query(None),
):
    """API documentation page. Use ?format=md for markdown."""
    if format == "md":
        return Response(
            content=DOCS_MARKDOWN,
            media_type="text/markdown; charset=utf-8",
        )
    
    return get_templates().TemplateResponse("docs.html", {
        "request": request,
        "active_page": "docs",
    })


DOCS_MARKDOWN = """# Vibecheck API Documentation

REST API for AI tools intelligence.

## For AI Agents

Add `?format=md` to any page URL to get markdown instead of HTML:
- `/docs?format=md` - This documentation
- `/?format=md` - Tools list
- `/articles?format=md` - Articles list  
- `/tools/{slug}?format=md` - Tool details

## Base URL

```
https://vibecheck.ito.com/api/v1
```

All API endpoints return JSON. CORS is enabled for all origins.

## Tools

### GET /tools
List all tools with pagination.

**Query Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| page | int | Page number (default: 1) |
| per_page | int | Items per page (default: 20, max: 100) |
| category | string | Filter by category slug |
| sort_by | string | Sort field: created_at, name, github_stars |
| sort_order | string | asc or desc |

### GET /tools/{slug}
Get tool details including evaluations and links.

### POST /tools
Create a new tool.

```json
{
  "name": "Tool Name",
  "url": "https://example.com",
  "github_url": "https://github.com/org/repo",
  "description": "Tool description",
  "categories": ["ide", "agent"]
}
```

### PATCH /tools/{slug}
Update an existing tool.

## Articles

### GET /articles
List articles with pagination.

**Query Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| page | int | Page number (default: 1) |
| per_page | int | Items per page (default: 20) |
| community | string | Filter by community slug |

### GET /articles/{slug}
Get article details.

### POST /articles
Create a new article.

```json
{
  "url": "https://example.com/article",
  "title": "Article Title",
  "summary": "Brief description",
  "community_slug": "agi",
  "tags": ["vibe-coding", "agents"]
}
```

## Search

### GET /search
Search tools and articles.

**Query Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| q | string | Search query (required) |
| type | string | Filter: tools, articles, or all |
| limit | int | Max results (default: 20) |

## Communities

### GET /communities
List all communities.

### GET /communities/{slug}
Get community details with tool count.

## Evaluations

### POST /tools/{slug}/evaluations
Add or update an evaluation.

```json
{
  "works": true,
  "actively_maintained": true,
  "verdict": "solid",
  "security_notes": "No concerns",
  "notes": "Works great"
}
```

**Verdict Values:**
- `essential` - Daily driver, highly recommended
- `solid` - Works well, good choice
- `situational` - Right for specific use cases
- `caution` - Works but has issues
- `avoid` - Broken or dangerous

## OpenAPI

- [/api/docs](/api/docs) - Swagger UI
- [/api/redoc](/api/redoc) - ReDoc
- [/api/openapi.json](/api/openapi.json) - OpenAPI spec
"""
