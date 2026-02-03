"""Admin routes for vibecheck."""

import hashlib
import hmac
import os
import secrets
import time
from functools import wraps
from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from .database import ArticlesDB, CommunitiesDB, ToolsDB, get_supabase_client
from .web import find_templates_dir, get_templates

router = APIRouter(prefix="/admin")

# Session configuration
SESSION_COOKIE = "vibecheck_admin_session"
SESSION_MAX_AGE = 86400 * 7  # 7 days
SECRET_KEY = os.environ.get("ADMIN_SECRET_KEY", "dev-secret-change-in-prod")


def get_admin_password() -> str:
    """Get admin password from environment."""
    return os.environ.get("ADMIN_PASSWORD", "")


def create_session_token(timestamp: int) -> str:
    """Create a signed session token."""
    message = f"admin:{timestamp}"
    signature = hmac.new(
        SECRET_KEY.encode(), message.encode(), hashlib.sha256
    ).hexdigest()[:32]
    return f"{timestamp}:{signature}"


def verify_session_token(token: str) -> bool:
    """Verify a session token is valid and not expired."""
    try:
        parts = token.split(":")
        if len(parts) != 2:
            return False
        timestamp, signature = int(parts[0]), parts[1]
        
        # Check expiration
        if time.time() - timestamp > SESSION_MAX_AGE:
            return False
        
        # Verify signature
        expected = create_session_token(timestamp).split(":")[1]
        return hmac.compare_digest(signature, expected)
    except Exception:
        return False


def is_authenticated(request: Request) -> bool:
    """Check if request has valid admin session."""
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return False
    return verify_session_token(token)


def require_auth(request: Request):
    """Dependency that requires authentication."""
    if not is_authenticated(request):
        raise HTTPException(status_code=401, detail="Not authenticated")
    return True


# Database dependencies
def get_tools_db() -> ToolsDB:
    return ToolsDB()

def get_articles_db() -> ArticlesDB:
    return ArticlesDB()

def get_communities_db() -> CommunitiesDB:
    return CommunitiesDB()


# Auth routes
@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, error: Optional[str] = None):
    """Show login page."""
    if is_authenticated(request):
        return RedirectResponse("/admin", status_code=302)
    
    return get_templates().TemplateResponse("admin/login.html", {
        "request": request,
        "error": error,
    })


@router.post("/login")
async def login(request: Request, password: str = Form(...)):
    """Process login."""
    admin_password = get_admin_password()
    
    if not admin_password:
        return RedirectResponse("/admin/login?error=Admin+not+configured", status_code=302)
    
    if not hmac.compare_digest(password, admin_password):
        return RedirectResponse("/admin/login?error=Invalid+password", status_code=302)
    
    # Create session
    token = create_session_token(int(time.time()))
    response = RedirectResponse("/admin", status_code=302)
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=SESSION_MAX_AGE,
        httponly=True,
        secure=True,
        samesite="lax",
    )
    return response


@router.get("/logout")
async def logout():
    """Log out admin."""
    response = RedirectResponse("/admin/login", status_code=302)
    response.delete_cookie(SESSION_COOKIE)
    return response


# Admin dashboard
@router.get("", response_class=HTMLResponse)
async def admin_dashboard(
    request: Request,
    tools_db: ToolsDB = Depends(get_tools_db),
    articles_db: ArticlesDB = Depends(get_articles_db),
):
    """Admin dashboard."""
    if not is_authenticated(request):
        return RedirectResponse("/admin/login", status_code=302)
    
    tools_result = tools_db.list_tools(page=1, per_page=1)
    articles_result = articles_db.list_articles(page=1, per_page=1)
    
    return get_templates().TemplateResponse("admin/dashboard.html", {
        "request": request,
        "total_tools": tools_result.get("total", 0),
        "total_articles": articles_result.get("total", 0),
    })


# Tools CRUD
@router.get("/tools", response_class=HTMLResponse)
async def admin_tools_list(
    request: Request,
    page: int = Query(1, ge=1),
    search: Optional[str] = None,
    tools_db: ToolsDB = Depends(get_tools_db),
):
    """List tools for admin."""
    if not is_authenticated(request):
        return RedirectResponse("/admin/login", status_code=302)
    
    per_page = 50
    result = tools_db.list_tools(page=page, per_page=per_page, sort_by="name", sort_order="asc")
    
    tools = result.get("tools", [])
    if search:
        search_lower = search.lower()
        tools = [t for t in tools if search_lower in t.get("name", "").lower() 
                 or search_lower in t.get("description", "").lower()]
    
    return get_templates().TemplateResponse("admin/tools_list.html", {
        "request": request,
        "tools": tools,
        "total": result.get("total", 0),
        "page": page,
        "per_page": per_page,
        "search": search or "",
    })


@router.get("/tools/new", response_class=HTMLResponse)
async def admin_tool_new(request: Request):
    """New tool form."""
    if not is_authenticated(request):
        return RedirectResponse("/admin/login", status_code=302)
    
    return get_templates().TemplateResponse("admin/tool_edit.html", {
        "request": request,
        "tool": None,
        "is_new": True,
    })


@router.get("/tools/{slug}/edit", response_class=HTMLResponse)
async def admin_tool_edit(
    request: Request,
    slug: str,
    tools_db: ToolsDB = Depends(get_tools_db),
):
    """Edit tool form."""
    if not is_authenticated(request):
        return RedirectResponse("/admin/login", status_code=302)
    
    tool = tools_db.get_tool(slug)
    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found")
    
    return get_templates().TemplateResponse("admin/tool_edit.html", {
        "request": request,
        "tool": tool,
        "is_new": False,
    })


@router.post("/tools/save")
async def admin_tool_save(
    request: Request,
    tools_db: ToolsDB = Depends(get_tools_db),
):
    """Save tool (create or update)."""
    if not is_authenticated(request):
        return RedirectResponse("/admin/login", status_code=302)
    
    form = await request.form()
    tool_id = form.get("id")
    
    data = {
        "name": form.get("name"),
        "slug": form.get("slug"),
        "description": form.get("description"),
        "url": form.get("url") or None,
        "github_url": form.get("github_url") or None,
        "categories": [c.strip() for c in (form.get("categories") or "").split(",") if c.strip()],
    }
    
    client = get_supabase_client()
    
    if tool_id:
        # Update existing
        client.table("tools").update(data).eq("id", tool_id).execute()
    else:
        # Create new
        client.table("tools").insert(data).execute()
    
    return RedirectResponse("/admin/tools", status_code=302)


@router.post("/tools/{slug}/delete")
async def admin_tool_delete(
    request: Request,
    slug: str,
    tools_db: ToolsDB = Depends(get_tools_db),
):
    """Delete a tool."""
    if not is_authenticated(request):
        return RedirectResponse("/admin/login", status_code=302)
    
    tool = tools_db.get_tool(slug)
    if tool:
        client = get_supabase_client()
        client.table("tools").delete().eq("id", tool["id"]).execute()
    
    return RedirectResponse("/admin/tools", status_code=302)


# Articles CRUD
@router.get("/articles", response_class=HTMLResponse)
async def admin_articles_list(
    request: Request,
    page: int = Query(1, ge=1),
    search: Optional[str] = None,
    articles_db: ArticlesDB = Depends(get_articles_db),
):
    """List articles for admin."""
    if not is_authenticated(request):
        return RedirectResponse("/admin/login", status_code=302)
    
    per_page = 50
    result = articles_db.list_articles(page=page, per_page=per_page)
    
    articles = result.get("articles", [])
    if search:
        search_lower = search.lower()
        articles = [a for a in articles if search_lower in a.get("title", "").lower() 
                   or search_lower in a.get("url", "").lower()]
    
    return get_templates().TemplateResponse("admin/articles_list.html", {
        "request": request,
        "articles": articles,
        "total": result.get("total", 0),
        "page": page,
        "per_page": per_page,
        "search": search or "",
    })


@router.get("/articles/new", response_class=HTMLResponse)
async def admin_article_new(request: Request):
    """New article form."""
    if not is_authenticated(request):
        return RedirectResponse("/admin/login", status_code=302)
    
    return get_templates().TemplateResponse("admin/article_edit.html", {
        "request": request,
        "article": None,
        "is_new": True,
    })


@router.get("/articles/{slug}/edit", response_class=HTMLResponse)
async def admin_article_edit(
    request: Request,
    slug: str,
    articles_db: ArticlesDB = Depends(get_articles_db),
):
    """Edit article form."""
    if not is_authenticated(request):
        return RedirectResponse("/admin/login", status_code=302)
    
    article = articles_db.get_article(slug)
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    
    return get_templates().TemplateResponse("admin/article_edit.html", {
        "request": request,
        "article": article,
        "is_new": False,
    })


@router.post("/articles/save")
async def admin_article_save(
    request: Request,
    articles_db: ArticlesDB = Depends(get_articles_db),
):
    """Save article (create or update)."""
    if not is_authenticated(request):
        return RedirectResponse("/admin/login", status_code=302)
    
    form = await request.form()
    article_id = form.get("id")
    
    import re
    title = form.get("title", "")
    slug = form.get("slug") or title.lower()
    slug = re.sub(r'[^a-z0-9]+', '-', slug).strip('-')[:100]
    
    data = {
        "title": title,
        "slug": slug,
        "url": form.get("url"),
        "author": form.get("author") or None,
        "summary": form.get("summary") or None,
        "source": form.get("source") or None,
        "tags": [t.strip() for t in (form.get("tags") or "").split(",") if t.strip()],
    }
    
    client = get_supabase_client()
    
    if article_id:
        # Update existing
        client.table("articles").update(data).eq("id", article_id).execute()
    else:
        # Create new - add unique suffix to slug
        import hashlib
        url_hash = hashlib.md5(data["url"].encode()).hexdigest()[:6]
        data["slug"] = f"{slug}-{url_hash}"
        client.table("articles").insert(data).execute()
    
    return RedirectResponse("/admin/articles", status_code=302)


@router.post("/articles/{slug}/delete")
async def admin_article_delete(
    request: Request,
    slug: str,
    articles_db: ArticlesDB = Depends(get_articles_db),
):
    """Delete an article."""
    if not is_authenticated(request):
        return RedirectResponse("/admin/login", status_code=302)
    
    article = articles_db.get_article(slug)
    if article:
        client = get_supabase_client()
        client.table("articles").delete().eq("id", article["id"]).execute()
    
    return RedirectResponse("/admin/articles", status_code=302)


@router.get("/debug-env")
async def debug_env():
    """Debug endpoint to check env vars (remove in production)."""
    pw = os.environ.get("ADMIN_PASSWORD", "NOT_SET")
    return {
        "password_set": pw != "NOT_SET" and pw != "",
        "password_length": len(pw) if pw else 0,
        "first_char": pw[0] if pw else None,
    }
