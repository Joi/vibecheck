"""Web UI routes for vibecheck."""

import os
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from .database import ArticlesDB, CommunitiesDB, EvaluationsDB, LinksDB, ToolsDB

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
    tools_db: ToolsDB = Depends(get_tools_db),
    communities_db: CommunitiesDB = Depends(get_communities_db),
    articles_db: ArticlesDB = Depends(get_articles_db),
):
    """Homepage with tools list."""
    try:
        per_page = 24
        result = tools_db.list_tools(page=page, per_page=per_page, sort_by="created_at", sort_order="desc")
        
        # Get communities for all tools in ONE query (not N+1)
        tools = result.get("tools", [])
        tool_ids = [t["id"] for t in tools]
        communities_by_tool = communities_db.get_communities_for_tools_batch(tool_ids)
        
        # Add communities to each tool
        for tool in tools:
            tool_communities = communities_by_tool.get(tool["id"], [])
            tool["communities"] = [c["name"] for c in tool_communities]
        
        communities = communities_db.list_communities()
        
        # Get article count
        articles_result = articles_db.list_articles(page=1, per_page=1)
        total_articles = articles_result.get("total", 0)
        
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
    
    communities = communities_db.list_communities()
    articles_result = articles_db.list_articles(page=1, per_page=1)
    
    return get_templates().TemplateResponse("index.html", {
        "request": request,
        "active_page": "tools",
        "tools": tools,
        "total_tools": result.get("total", 0),
        "total_articles": articles_result.get("total", 0),
        "communities": communities,
        "page": page,
        "has_more": page * per_page < result.get("total", 0),
    })


@router.get("/tools/{slug}", response_class=HTMLResponse)
async def tool_detail(
    request: Request,
    slug: str,
    tools_db: ToolsDB = Depends(get_tools_db),
    communities_db: CommunitiesDB = Depends(get_communities_db),
    evaluations_db: EvaluationsDB = Depends(get_evaluations_db),
    links_db: LinksDB = Depends(get_links_db),
):
    """Tool detail page."""
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
    articles_db: ArticlesDB = Depends(get_articles_db),
):
    """Articles listing page."""
    per_page = 20
    result = articles_db.list_articles(page=page, per_page=per_page)
    
    return get_templates().TemplateResponse("articles.html", {
        "request": request,
        "active_page": "articles",
        "articles": result.get("articles", []),
        "page": page,
        "has_more": page * per_page < result.get("total", 0),
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


