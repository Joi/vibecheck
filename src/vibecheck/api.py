"""FastAPI application for vibecheck."""

from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .web import router as web_router
from .admin import router as admin_router
from .database import ArticlesDB, CategoriesDB, CommunitiesDB, EvaluationsDB, LinksDB, ToolsDB, get_admin_client
from .models import (
    ArticleCreate,
    ArticleListResponse,
    ArticleResponse,
    CategoryResponse,
    CommunityResponse,
    EvaluationCreate,
    EvaluationResponse,
    LinkCreate,
    LinkResponse,
    SearchResponse,
    SearchResult,
    ToolCommunityResponse,
    ToolCreate,
    ToolDetailResponse,
    ToolListResponse,
    ToolMentionResponse,
    ToolResponse,
    ToolUpdate,
    WebhookBatchIngest,
    WebhookResponse,
    WebhookToolMention,
)

settings = get_settings()

app = FastAPI(
    title="vibecheck",
    description="AI tools intelligence - curated evaluations with API access",
    version="0.1.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

# CORS - allow all origins for API access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Web UI routes (must be before API routes to avoid conflicts)
app.include_router(web_router)

# Admin routes
app.include_router(admin_router)


# ============== Dependencies ==============


def get_tools_db() -> ToolsDB:
    return ToolsDB()


def get_evaluations_db() -> EvaluationsDB:
    return EvaluationsDB()


def get_links_db() -> LinksDB:
    return LinksDB()


def get_categories_db() -> CategoriesDB:
    return CategoriesDB()


def get_communities_db() -> CommunitiesDB:
    return CommunitiesDB()


# ============== Health ==============


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok", "service": "vibecheck"}


@app.get("/")
async def root():
    """Root endpoint with API info."""
    return {
        "name": "vibecheck",
        "version": "0.1.0",
        "description": "AI tools intelligence API",
        "docs": f"{settings.app_url}/api/docs",
        "endpoints": {
            "tools": f"{settings.api_prefix}/tools",
            "categories": f"{settings.api_prefix}/categories",
            "search": f"{settings.api_prefix}/search",
        },
    }


# ============== Tools ==============


@app.get(f"{settings.api_prefix}/tools", response_model=ToolListResponse)
async def list_tools(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    category: Optional[str] = None,
    sort_by: str = Query("github_stars", regex="^(github_stars|name|created_at|updated_at)$"),
    sort_order: str = Query("desc", regex="^(asc|desc)$"),
    db: ToolsDB = Depends(get_tools_db),
):
    """List all tools with pagination and filtering."""
    result = db.list_tools(
        page=page,
        per_page=per_page,
        category=category,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    return ToolListResponse(
        tools=[ToolResponse(**t) for t in result["tools"]],
        total=result["total"],
        page=result["page"],
        per_page=result["per_page"],
        has_more=(result["page"] * result["per_page"]) < result["total"],
    )


@app.get(f"{settings.api_prefix}/tools/{{slug}}", response_model=ToolDetailResponse)
async def get_tool(slug: str, db: ToolsDB = Depends(get_tools_db)):
    """Get a tool by slug with all evaluations and links."""
    tool = db.get_tool(slug)
    if not tool:
        raise HTTPException(status_code=404, detail=f"Tool '{slug}' not found")

    # Transform nested user data
    evaluations = []
    for e in tool.get("evaluations", []):
        user_data = e.pop("users", None)
        if user_data:
            e["evaluator"] = user_data
        evaluations.append(EvaluationResponse(**e))

    links = []
    for link in tool.get("links", []):
        user_data = link.pop("users", None)
        if user_data:
            link["submitted_by"] = user_data
        links.append(LinkResponse(**link))

    # Calculate aggregate stats
    works_evals = [e for e in evaluations if e.works is not None]
    works_count = sum(1 for e in works_evals if e.works)

    verdicts = [e.verdict for e in evaluations if e.verdict]
    avg_verdict = max(set(verdicts), key=verdicts.count) if verdicts else None

    return ToolDetailResponse(
        **{k: v for k, v in tool.items() if k not in ("evaluations", "links")},
        evaluations=evaluations,
        links=links,
        mention_count=tool.get("mention_count", 0),
        avg_verdict=avg_verdict.value if avg_verdict else None,
        works_count=works_count,
        works_total=len(works_evals),
    )


@app.post(f"{settings.api_prefix}/tools", response_model=ToolResponse, status_code=201)
async def create_tool(
    tool: ToolCreate,
    db: ToolsDB = Depends(get_tools_db),
):
    """Create a new tool. Requires authentication."""
    # TODO: Add authentication
    try:
        result = db.create_tool(tool.model_dump(exclude_none=True))
        # Add empty communities list (not stored in tools table, fetched from tool_communities)
        result["communities"] = []
        return ToolResponse(**result)
    except Exception as e:
        if "duplicate key" in str(e).lower():
            raise HTTPException(status_code=409, detail=f"Tool '{tool.slug}' already exists")
        raise HTTPException(status_code=500, detail=str(e))


@app.patch(f"{settings.api_prefix}/tools/{{slug}}", response_model=ToolResponse)
async def update_tool(
    slug: str,
    updates: ToolUpdate,
):
    """Update a tool. Uses admin client to bypass RLS."""
    # Use admin client for updates (bypasses RLS)
    admin_db = ToolsDB(client=get_admin_client())
    result = admin_db.update_tool(slug, updates.model_dump(exclude_none=True))
    if not result:
        raise HTTPException(status_code=404, detail=f"Tool '{slug}' not found")
    # Add empty communities list for response model
    result["communities"] = []
    return ToolResponse(**result)


# ============== Evaluations ==============


@app.post(
    f"{settings.api_prefix}/tools/{{slug}}/evaluations",
    response_model=EvaluationResponse,
    status_code=201,
)
async def create_evaluation(
    slug: str,
    evaluation: EvaluationCreate,
    tools_db: ToolsDB = Depends(get_tools_db),
    evals_db: EvaluationsDB = Depends(get_evaluations_db),
):
    """Add or update an evaluation for a tool. Requires authentication."""
    # Get tool first
    tool = tools_db.get_tool(slug)
    if not tool:
        raise HTTPException(status_code=404, detail=f"Tool '{slug}' not found")

    # TODO: Get user_id from authentication
    user_id = None  # Placeholder

    result = evals_db.create_evaluation(
        tool_id=tool["id"],
        user_id=user_id,
        data=evaluation.model_dump(exclude_none=True),
    )
    return EvaluationResponse(**result)


# ============== Links ==============


@app.post(
    f"{settings.api_prefix}/tools/{{slug}}/links",
    response_model=LinkResponse,
    status_code=201,
)
async def create_link(
    slug: str,
    link: LinkCreate,
    tools_db: ToolsDB = Depends(get_tools_db),
    links_db: LinksDB = Depends(get_links_db),
):
    """Add an external link to a tool. Requires authentication."""
    # Get tool first
    tool = tools_db.get_tool(slug)
    if not tool:
        raise HTTPException(status_code=404, detail=f"Tool '{slug}' not found")

    # TODO: Get user_id from authentication
    user_id = None  # Placeholder

    try:
        result = links_db.create_link(
            tool_id=tool["id"],
            user_id=user_id,
            data=link.model_dump(exclude_none=True, mode="json"),
        )
        return LinkResponse(**result)
    except Exception as e:
        if "duplicate key" in str(e).lower():
            raise HTTPException(status_code=409, detail="This link already exists for this tool")
        raise HTTPException(status_code=500, detail=str(e))


# ============== Categories ==============


@app.get(f"{settings.api_prefix}/categories", response_model=list[CategoryResponse])
async def list_categories(db: CategoriesDB = Depends(get_categories_db)):
    """List all categories with tool counts."""
    categories = db.list_categories()
    return [CategoryResponse(**c) for c in categories]


# ============== Search ==============


@app.get(f"{settings.api_prefix}/search", response_model=SearchResponse)
async def search_tools(
    q: str = Query(..., min_length=1, max_length=100),
    limit: int = Query(20, ge=1, le=100),
    db: ToolsDB = Depends(get_tools_db),
):
    """Search tools by name, description, or slug."""
    results = db.search_tools(q, limit=limit)
    return SearchResponse(
        results=[
            SearchResult(
                tool=ToolResponse(**t),
                relevance=1.0,  # TODO: Implement relevance scoring
                matched_fields=["name", "description", "slug"],
            )
            for t in results
        ],
        query=q,
        total=len(results),
    )


# ============== Bot-friendly endpoints ==============


@app.get(f"{settings.api_prefix}/bot/tool/{{slug}}")
async def bot_get_tool(slug: str, db: ToolsDB = Depends(get_tools_db)):
    """
    Simplified tool info optimized for bot/agent consumption.
    Returns a flat structure with key metrics.
    """
    tool = db.get_tool(slug)
    if not tool:
        raise HTTPException(status_code=404, detail=f"Tool '{slug}' not found")

    evaluations = tool.get("evaluations", [])
    verdicts = [e.get("verdict") for e in evaluations if e.get("verdict")]
    works_votes = [e.get("works") for e in evaluations if e.get("works") is not None]

    return {
        "slug": tool["slug"],
        "name": tool["name"],
        "url": tool.get("url"),
        "github_url": tool.get("github_url"),
        "categories": tool.get("categories", []),
        "description": tool.get("description"),
        # GitHub stats
        "github_stars": tool.get("github_stars"),
        "github_last_commit": tool.get("github_last_commit"),
        "actively_maintained": tool.get("github_last_commit") is not None,
        # Evaluation summary
        "evaluation_count": len(evaluations),
        "works_yes": sum(1 for w in works_votes if w),
        "works_no": sum(1 for w in works_votes if not w),
        "top_verdict": max(set(verdicts), key=verdicts.count) if verdicts else None,
        "verdict_counts": {v: verdicts.count(v) for v in set(verdicts)} if verdicts else {},
        # Links
        "link_count": len(tool.get("links", [])),
        "mention_count": tool.get("mention_count", 0),
    }


@app.get(f"{settings.api_prefix}/bot/recommend")
async def bot_recommend(
    use_case: str = Query(..., description="What you want to do (e.g., 'code review', 'agent framework')"),
    limit: int = Query(5, ge=1, le=20),
    db: ToolsDB = Depends(get_tools_db),
):
    """
    Get tool recommendations for a use case.
    Bot-friendly endpoint for agents to find tools.
    """
    # Simple keyword matching for now
    results = db.search_tools(use_case, limit=limit * 2)

    # Filter to only tools with positive evaluations
    recommended = []
    for tool in results:
        tool_detail = db.get_tool(tool["slug"])
        if not tool_detail:
            continue

        evaluations = tool_detail.get("evaluations", [])
        verdicts = [e.get("verdict") for e in evaluations if e.get("verdict")]

        # Prefer tools with "essential" or "solid" verdicts
        good_verdicts = [v for v in verdicts if v in ("essential", "solid")]
        if good_verdicts or not verdicts:  # Include tools with no evaluations yet
            recommended.append(
                {
                    "slug": tool["slug"],
                    "name": tool["name"],
                    "description": tool.get("description"),
                    "github_stars": tool.get("github_stars"),
                    "verdict_summary": max(set(verdicts), key=verdicts.count) if verdicts else "unreviewed",
                    "evaluation_count": len(evaluations),
                }
            )

        if len(recommended) >= limit:
            break

    return {
        "use_case": use_case,
        "recommendations": recommended,
        "count": len(recommended),
    }


# ============== Communities ==============


@app.get(f"{settings.api_prefix}/communities", response_model=list[CommunityResponse])
async def list_communities(db: CommunitiesDB = Depends(get_communities_db)):
    """List all communities with tool counts."""
    communities = db.list_communities()
    return [CommunityResponse(**c) for c in communities]


@app.get(f"{settings.api_prefix}/communities/{{slug}}")
async def get_community(
    slug: str,
    db: CommunitiesDB = Depends(get_communities_db),
):
    """Get a community with its tools."""
    community = db.get_community(slug)
    if not community:
        raise HTTPException(status_code=404, detail=f"Community '{slug}' not found")

    tools = db.get_tools_for_community(slug)

    return {
        "community": CommunityResponse(**community),
        "tools": [
            {
                "tool": t.get("tools", {}),
                "first_mentioned": t.get("first_mentioned"),
                "mention_count": t.get("mention_count", 0),
                "sentiment_summary": t.get("sentiment_summary"),
            }
            for t in tools
        ],
        "tool_count": len(tools),
    }


@app.get(f"{settings.api_prefix}/communities/{{slug}}/tools")
async def get_community_tools(
    slug: str,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    db: CommunitiesDB = Depends(get_communities_db),
):
    """Get tools discussed in a community."""
    community = db.get_community(slug)
    if not community:
        raise HTTPException(status_code=404, detail=f"Community '{slug}' not found")

    tools = db.get_tools_for_community(slug)

    # Paginate
    start = (page - 1) * per_page
    end = start + per_page
    paginated = tools[start:end]

    return {
        "community": slug,
        "tools": [
            {
                "slug": t.get("tools", {}).get("slug"),
                "name": t.get("tools", {}).get("name"),
                "github_url": t.get("tools", {}).get("github_url"),
                "mention_count": t.get("mention_count", 0),
                "sentiment_summary": t.get("sentiment_summary"),
            }
            for t in paginated
        ],
        "total": len(tools),
        "page": page,
        "per_page": per_page,
        "has_more": end < len(tools),
    }


# ============== Mention History ==============


@app.get(f"{settings.api_prefix}/mentions", response_model=list[ToolMentionResponse])
async def get_mentions(
    tool: Optional[str] = Query(None, description="Filter by tool slug"),
    community: Optional[str] = Query(None, description="Filter by community slug"),
    limit: int = Query(50, ge=1, le=200),
    db: CommunitiesDB = Depends(get_communities_db),
):
    """
    Get mention history with timestamps.
    
    Each mention records when a tool was discussed in a community.
    """
    mentions = db.get_mention_history(
        tool_slug=tool,
        community_slug=community,
        limit=limit,
    )
    return [ToolMentionResponse(**m) for m in mentions]


@app.get(f"{settings.api_prefix}/tools/{{slug}}/mentions")
async def get_tool_mentions(
    slug: str,
    community: Optional[str] = Query(None, description="Filter by community"),
    limit: int = Query(50, ge=1, le=200),
    tools_db: ToolsDB = Depends(get_tools_db),
    communities_db: CommunitiesDB = Depends(get_communities_db),
):
    """Get all mentions of a specific tool with timestamps."""
    tool = tools_db.get_tool(slug)
    if not tool:
        raise HTTPException(status_code=404, detail=f"Tool '{slug}' not found")

    mentions = communities_db.get_mention_history(
        tool_slug=slug,
        community_slug=community,
        limit=limit,
    )

    return {
        "tool": slug,
        "mentions": mentions,
        "total": len(mentions),
    }


@app.get(f"{settings.api_prefix}/communities/{{slug}}/mentions")
async def get_community_mentions(
    slug: str,
    limit: int = Query(50, ge=1, le=200),
    db: CommunitiesDB = Depends(get_communities_db),
):
    """Get recent tool mentions in a community with timestamps."""
    community = db.get_community(slug)
    if not community:
        raise HTTPException(status_code=404, detail=f"Community '{slug}' not found")

    mentions = db.get_mention_history(
        community_slug=slug,
        limit=limit,
    )

    return {
        "community": slug,
        "mentions": mentions,
        "total": len(mentions),
    }


# ============== Webhooks / Integration ==============


@app.post(f"{settings.api_prefix}/ingest", response_model=WebhookResponse)
async def ingest_tool_mention(
    mention: WebhookToolMention,
    tools_db: ToolsDB = Depends(get_tools_db),
    communities_db: CommunitiesDB = Depends(get_communities_db),
):
    """
    Ingest a single tool mention from external system (ai-wiki, etc.).
    
    If tool doesn't exist, creates it. Records the mention with timestamp.
    """
    errors = []
    created = 0
    updated = 0
    
    # Find or create tool
    tool = None
    if mention.tool_slug:
        tool = tools_db.get_tool(mention.tool_slug)
    
    if not tool:
        # Try to find by name (fuzzy match could be added later)
        # For now, create new tool
        slug = mention.tool_slug or mention.tool_name.lower().replace(" ", "-").replace("_", "-")
        slug = "".join(c for c in slug if c.isalnum() or c == "-")
        
        try:
            tool = tools_db.create_tool({
                "slug": slug,
                "name": mention.tool_name,
                "url": mention.tool_url,
                "github_url": mention.github_url,
                "source": mention.source,
            })
            created = 1
        except Exception as e:
            # Tool might already exist with different slug
            errors.append(f"Failed to create tool: {str(e)}")
            return WebhookResponse(received=1, created=0, updated=0, skipped=1, errors=errors)
    
    # Record the mention
    try:
        communities_db.record_mention(
            tool_id=tool["id"],
            community_slug=mention.community,
            mentioned_at=mention.mentioned_at.isoformat() if mention.mentioned_at else None,
            context_snippet=mention.context_snippet,
            sentiment=mention.sentiment.value if mention.sentiment else None,
        )
        updated = 1
    except Exception as e:
        errors.append(f"Failed to record mention: {str(e)}")
    
    return WebhookResponse(
        received=1,
        created=created,
        updated=updated,
        skipped=0,
        errors=errors,
    )


@app.post(f"{settings.api_prefix}/ingest/batch", response_model=WebhookResponse)
async def ingest_batch(
    batch: WebhookBatchIngest,
    tools_db: ToolsDB = Depends(get_tools_db),
    communities_db: CommunitiesDB = Depends(get_communities_db),
):
    """
    Batch ingest multiple tool mentions.
    
    Useful for importing from chat exports or syncing from ai-wiki.
    """
    total_created = 0
    total_updated = 0
    total_skipped = 0
    all_errors = []
    
    for mention in batch.mentions:
        # Find or create tool
        tool = None
        if mention.tool_slug:
            tool = tools_db.get_tool(mention.tool_slug)
        
        if not tool:
            slug = mention.tool_slug or mention.tool_name.lower().replace(" ", "-").replace("_", "-")
            slug = "".join(c for c in slug if c.isalnum() or c == "-")
            
            existing = tools_db.get_tool(slug)
            if existing:
                tool = existing
            else:
                try:
                    tool = tools_db.create_tool({
                        "slug": slug,
                        "name": mention.tool_name,
                        "url": mention.tool_url,
                        "github_url": mention.github_url,
                        "source": batch.source or mention.source,
                    })
                    total_created += 1
                except Exception as e:
                    all_errors.append(f"Tool '{mention.tool_name}': {str(e)}")
                    total_skipped += 1
                    continue
        
        # Record mention
        try:
            communities_db.record_mention(
                tool_id=tool["id"],
                community_slug=mention.community,
                mentioned_at=mention.mentioned_at.isoformat() if mention.mentioned_at else None,
                context_snippet=mention.context_snippet,
                sentiment=mention.sentiment.value if mention.sentiment else None,
            )
            total_updated += 1
        except Exception as e:
            all_errors.append(f"Mention for '{mention.tool_name}': {str(e)}")
    
    return WebhookResponse(
        received=len(batch.mentions),
        created=total_created,
        updated=total_updated,
        skipped=total_skipped,
        errors=all_errors[:10],  # Limit error messages
    )


# ============== Articles ==============


def get_articles_db():
    return ArticlesDB()


@app.get(f"{settings.api_prefix}/articles", response_model=ArticleListResponse)
async def list_articles(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    community: Optional[str] = None,
    tag: Optional[str] = None,
    articles_db: ArticlesDB = Depends(get_articles_db),
):
    """List articles about vibe coding, AI tools, and related topics."""
    result = articles_db.list_articles(
        page=page,
        per_page=per_page,
        community=community,
        tag=tag,
    )
    return ArticleListResponse(**result)


@app.get(f"{settings.api_prefix}/articles/recent")
async def recent_articles(
    limit: int = Query(10, ge=1, le=50),
    community: Optional[str] = None,
    articles_db: ArticlesDB = Depends(get_articles_db),
):
    """Get most recently discovered articles."""
    articles = articles_db.get_recent_articles(limit=limit, community=community)
    return {"articles": articles, "total": len(articles)}


@app.get(f"{settings.api_prefix}/articles/search")
async def search_articles(
    q: str = Query(..., min_length=1),
    limit: int = Query(20, ge=1, le=100),
    articles_db: ArticlesDB = Depends(get_articles_db),
):
    """Search articles by title or summary."""
    results = articles_db.search_articles(query=q, limit=limit)
    return {"results": results, "query": q, "total": len(results)}


@app.get(f"{settings.api_prefix}/articles/{{slug}}", response_model=ArticleResponse)
async def get_article(
    slug: str,
    articles_db: ArticlesDB = Depends(get_articles_db),
):
    """Get article details by slug."""
    article = articles_db.get_article(slug)
    if not article:
        raise HTTPException(status_code=404, detail=f"Article '{slug}' not found")
    return ArticleResponse(**article)


@app.post(f"{settings.api_prefix}/articles", response_model=ArticleResponse)
async def create_article(
    article: ArticleCreate,
):
    """Add a new article about vibe coding / AI tools."""
    # Use admin client to bypass RLS (needed for upsert/update operations)
    admin_db = ArticlesDB(client=get_admin_client())
    
    data = article.model_dump(exclude_none=True)
    data["url"] = str(data["url"])  # Convert HttpUrl to string
    
    result = admin_db.create_article(data)
    return ArticleResponse(**result)


@app.patch(f"{settings.api_prefix}/articles/{{slug}}")
async def update_article(
    slug: str,
    title: Optional[str] = None,
    summary: Optional[str] = None,
    tags: Optional[list[str]] = None,
):
    """Update an article's metadata (title, summary, tags)."""
    admin_db = ArticlesDB(client=get_admin_client())
    
    # Build update data
    update_data = {}
    if title is not None:
        update_data["title"] = title
    if summary is not None:
        update_data["summary"] = summary
    if tags is not None:
        update_data["tags"] = tags
    
    if not update_data:
        raise HTTPException(status_code=400, detail="No update fields provided")
    
    result = admin_db.update_article(slug, update_data)
    if not result:
        raise HTTPException(status_code=404, detail=f"Article '{slug}' not found")
    
    return ArticleResponse(**result)


@app.post(f"{settings.api_prefix}/articles/{{slug}}/upvote")
async def upvote_article(
    slug: str,
    articles_db: ArticlesDB = Depends(get_articles_db),
):
    """Upvote an article."""
    try:
        article = articles_db.upvote_article(slug)
        return {"slug": slug, "upvotes": article.get("upvotes", 0)}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
