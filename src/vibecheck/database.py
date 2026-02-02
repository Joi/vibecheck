"""Supabase database client."""

from functools import lru_cache
from typing import Optional

from supabase import Client, create_client

from .config import get_settings


@lru_cache
def get_supabase_client() -> Client:
    """Get cached Supabase client."""
    settings = get_settings()
    return create_client(settings.supabase_url, settings.supabase_anon_key)


def get_admin_client() -> Client:
    """Get Supabase client with service role (for admin operations)."""
    settings = get_settings()
    return create_client(settings.supabase_url, settings.supabase_service_role_key)


class ToolsDB:
    """Database operations for tools."""

    def __init__(self, client: Optional[Client] = None):
        self.client = client or get_supabase_client()

    def list_tools(
        self,
        page: int = 1,
        per_page: int = 50,
        category: Optional[str] = None,
        sort_by: str = "github_stars",
        sort_order: str = "desc",
    ) -> dict:
        """List tools with pagination and filtering."""
        query = self.client.table("tools").select("*", count="exact")

        if category:
            query = query.contains("categories", [category])

        # Sorting
        if sort_order == "desc":
            query = query.order(sort_by, desc=True, nullsfirst=False)
        else:
            query = query.order(sort_by, desc=False, nullsfirst=False)

        # Pagination
        offset = (page - 1) * per_page
        query = query.range(offset, offset + per_page - 1)

        result = query.execute()
        return {
            "tools": result.data,
            "total": result.count or 0,
            "page": page,
            "per_page": per_page,
        }

    def get_tool(self, slug: str) -> Optional[dict]:
        """Get a tool by slug with evaluations and links."""
        result = self.client.table("tools").select("*").eq("slug", slug).single().execute()
        if not result.data:
            return None

        tool = result.data

        # Get evaluations with evaluator info
        evals = (
            self.client.table("evaluations")
            .select("*, users(id, github_username, display_name, avatar_url)")
            .eq("tool_id", tool["id"])
            .order("created_at", desc=True)
            .execute()
        )
        tool["evaluations"] = evals.data or []

        # Get links with submitter info
        links = (
            self.client.table("links")
            .select("*, users(id, github_username, display_name, avatar_url)")
            .eq("tool_id", tool["id"])
            .order("created_at", desc=True)
            .execute()
        )
        tool["links"] = links.data or []

        # Get mention count
        mentions = (
            self.client.table("tool_mentions")
            .select("id", count="exact")
            .eq("tool_id", tool["id"])
            .execute()
        )
        tool["mention_count"] = mentions.count or 0

        return tool

    def create_tool(self, data: dict, user_id: Optional[str] = None) -> dict:
        """Create a new tool."""
        if user_id:
            data["created_by"] = user_id
        result = self.client.table("tools").insert(data).execute()
        return result.data[0]

    def update_tool(self, slug: str, data: dict) -> Optional[dict]:
        """Update a tool."""
        result = self.client.table("tools").update(data).eq("slug", slug).execute()
        return result.data[0] if result.data else None

    def search_tools(self, query: str, limit: int = 20) -> list[dict]:
        """Search tools by name, description, or slug."""
        # Simple ILIKE search - could be upgraded to full-text search
        result = (
            self.client.table("tools")
            .select("*")
            .or_(f"name.ilike.%{query}%,description.ilike.%{query}%,slug.ilike.%{query}%")
            .limit(limit)
            .execute()
        )
        return result.data or []


class EvaluationsDB:
    """Database operations for evaluations."""

    def __init__(self, client: Optional[Client] = None):
        self.client = client or get_supabase_client()

    def create_evaluation(self, tool_id: str, user_id: str, data: dict) -> dict:
        """Create or update an evaluation (upsert)."""
        data["tool_id"] = tool_id
        data["evaluator_id"] = user_id
        result = (
            self.client.table("evaluations")
            .upsert(data, on_conflict="tool_id,evaluator_id")
            .execute()
        )
        return result.data[0]

    def get_evaluations_for_tool(self, tool_id: str) -> list[dict]:
        """Get all evaluations for a tool."""
        result = (
            self.client.table("evaluations")
            .select("*, users(id, github_username, display_name, avatar_url)")
            .eq("tool_id", tool_id)
            .order("created_at", desc=True)
            .execute()
        )
        return result.data or []


class LinksDB:
    """Database operations for links."""

    def __init__(self, client: Optional[Client] = None):
        self.client = client or get_supabase_client()

    def create_link(self, tool_id: str, user_id: str, data: dict) -> dict:
        """Add a link to a tool."""
        data["tool_id"] = tool_id
        data["submitted_by"] = user_id
        result = self.client.table("links").insert(data).execute()
        return result.data[0]

    def get_links_for_tool(self, tool_id: str) -> list[dict]:
        """Get all links for a tool."""
        result = (
            self.client.table("links")
            .select("*, users(id, github_username, display_name, avatar_url)")
            .eq("tool_id", tool_id)
            .order("created_at", desc=True)
            .execute()
        )
        return result.data or []

    def get_tool_mentions(self, tool_id: str) -> list[dict]:
        """Get all mentions for a tool."""
        result = (
            self.client.table("tool_mentions")
            .select("*")
            .eq("tool_id", tool_id)
            .order("mentioned_at", desc=True)
            .limit(50)
            .execute()
        )
        return result.data or []


class CategoriesDB:
    """Database operations for categories."""

    def __init__(self, client: Optional[Client] = None):
        self.client = client or get_supabase_client()

    def list_categories(self) -> list[dict]:
        """List all categories with tool counts."""
        result = self.client.table("categories").select("*").order("name").execute()
        categories = result.data or []

        # Get tool counts per category
        for cat in categories:
            count_result = (
                self.client.table("tools")
                .select("id", count="exact")
                .contains("categories", [cat["slug"]])
                .execute()
            )
            cat["tool_count"] = count_result.count or 0

        return categories


class CommunitiesDB:
    """Database operations for communities."""

    def __init__(self, client: Optional[Client] = None):
        self.client = client or get_supabase_client()

    def list_communities(self) -> list[dict]:
        """List all communities with tool counts."""
        result = self.client.table("communities").select("*").order("name").execute()
        communities = result.data or []

        # Get tool counts per community
        for comm in communities:
            count_result = (
                self.client.table("tool_communities")
                .select("id", count="exact")
                .eq("community_id", comm["id"])
                .execute()
            )
            comm["tool_count"] = count_result.count or 0

        return communities

    def get_community(self, slug: str) -> Optional[dict]:
        """Get a community by slug."""
        result = (
            self.client.table("communities")
            .select("*")
            .eq("slug", slug)
            .single()
            .execute()
        )
        return result.data

    def get_tools_for_community(self, community_slug: str) -> list[dict]:
        """Get all tools discussed in a community."""
        # First get community ID
        community = self.get_community(community_slug)
        if not community:
            return []

        # Get tool_communities with tool info
        result = (
            self.client.table("tool_communities")
            .select("*, tools(*)")
            .eq("community_id", community["id"])
            .order("mention_count", desc=True)
            .execute()
        )
        return result.data or []

    def get_communities_for_tool(self, tool_id: str) -> list[dict]:
        """Get all communities where a tool is discussed."""
        result = (
            self.client.table("tool_communities")
            .select("*, communities(*)")
            .eq("tool_id", tool_id)
            .execute()
        )
        return result.data or []

    def get_communities_for_tools_batch(self, tool_ids: list[str]) -> dict[str, list[dict]]:
        """Get communities for multiple tools in one query.
        
        Returns a dict mapping tool_id -> list of community info.
        """
        if not tool_ids:
            return {}
        
        result = (
            self.client.table("tool_communities")
            .select("tool_id, communities(slug, name)")
            .in_("tool_id", tool_ids)
            .execute()
        )
        
        # Group by tool_id
        by_tool: dict[str, list[dict]] = {}
        for row in result.data or []:
            tid = row.get("tool_id")
            if tid not in by_tool:
                by_tool[tid] = []
            if row.get("communities"):
                by_tool[tid].append(row["communities"])
        
        return by_tool

    def add_tool_to_community(
        self,
        tool_id: str,
        community_slug: str,
        sentiment_summary: Optional[str] = None,
    ) -> dict:
        """Add or update a tool's presence in a community."""
        community = self.get_community(community_slug)
        if not community:
            raise ValueError(f"Community '{community_slug}' not found")

        # Upsert tool_communities
        data = {
            "tool_id": tool_id,
            "community_id": community["id"],
            "mention_count": 1,
        }
        if sentiment_summary:
            data["sentiment_summary"] = sentiment_summary

        result = (
            self.client.table("tool_communities")
            .upsert(data, on_conflict="tool_id,community_id")
            .execute()
        )
        return result.data[0]

    def increment_mention_count(self, tool_id: str, community_slug: str) -> None:
        """Increment mention count for a tool in a community."""
        community = self.get_community(community_slug)
        if not community:
            return

        # Get current record
        current = (
            self.client.table("tool_communities")
            .select("*")
            .eq("tool_id", tool_id)
            .eq("community_id", community["id"])
            .single()
            .execute()
        )

        if current.data:
            # Update count
            self.client.table("tool_communities").update(
                {"mention_count": current.data["mention_count"] + 1}
            ).eq("id", current.data["id"]).execute()

    def record_mention(
        self,
        tool_id: str,
        community_slug: str,
        mentioned_at: Optional[str] = None,
        context_snippet: Optional[str] = None,
        sentiment: Optional[str] = None,
    ) -> dict:
        """Record a specific mention of a tool in a community with timestamp."""
        community = self.get_community(community_slug)
        community_id = community["id"] if community else None

        data = {
            "tool_id": tool_id,
            "community_id": community_id,
            "context_snippet": context_snippet,
            "sentiment": sentiment,
        }
        if mentioned_at:
            data["mentioned_at"] = mentioned_at

        result = self.client.table("tool_mentions").insert(data).execute()

        # Also update the tool_communities aggregate
        if community_id:
            self.increment_mention_count(tool_id, community_slug)

        return result.data[0]

    def get_mention_history(
        self,
        tool_slug: Optional[str] = None,
        community_slug: Optional[str] = None,
        limit: int = 50,
    ) -> list[dict]:
        """Get mention history, optionally filtered by tool or community."""
        query = self.client.table("tool_mention_history").select("*")

        if tool_slug:
            query = query.eq("tool_slug", tool_slug)
        if community_slug:
            query = query.eq("community_slug", community_slug)

        result = query.order("mentioned_at", desc=True).limit(limit).execute()
        return result.data or []


class ArticlesDB:
    """Database operations for articles."""

    def __init__(self, client: Optional[Client] = None):
        self.client = client or get_supabase_client()

    def list_articles(
        self,
        page: int = 1,
        per_page: int = 20,
        community: Optional[str] = None,
        tag: Optional[str] = None,
    ) -> dict:
        """List articles with pagination and filtering."""
        query = self.client.table("articles").select("*", count="exact")

        if community:
            query = query.eq("community_slug", community)
        if tag:
            query = query.contains("tags", [tag])

        # Pagination
        offset = (page - 1) * per_page
        query = query.order("published_at", desc=True, nullsfirst=False)
        query = query.range(offset, offset + per_page - 1)

        result = query.execute()
        total = result.count or 0

        return {
            "articles": result.data or [],
            "total": total,
            "page": page,
            "per_page": per_page,
            "has_more": offset + per_page < total,
        }

    def get_article(self, slug: str) -> Optional[dict]:
        """Get an article by slug."""
        result = (
            self.client.table("articles")
            .select("*")
            .eq("slug", slug)
            .single()
            .execute()
        )
        return result.data

    def get_article_by_url(self, url: str) -> Optional[dict]:
        """Get an article by URL."""
        result = (
            self.client.table("articles")
            .select("*")
            .eq("url", url)
            .maybe_single()
            .execute()
        )
        return result.data

    def create_article(self, data: dict) -> dict:
        """Create a new article."""
        # Generate slug from title if not provided
        if "slug" not in data:
            import re
            slug = data["title"].lower()
            slug = re.sub(r'[^a-z0-9]+', '-', slug)
            slug = slug.strip('-')[:100]
            data["slug"] = slug

        # Check for existing by URL
        existing = self.get_article_by_url(data.get("url", ""))
        if existing:
            # Update existing instead
            return self.update_article(existing["slug"], data)

        result = self.client.table("articles").insert(data).execute()
        return result.data[0]

    def update_article(self, slug: str, data: dict) -> dict:
        """Update an existing article."""
        result = (
            self.client.table("articles")
            .update(data)
            .eq("slug", slug)
            .execute()
        )
        return result.data[0] if result.data else None

    def upvote_article(self, slug: str) -> dict:
        """Increment upvote count for an article."""
        article = self.get_article(slug)
        if not article:
            raise ValueError(f"Article '{slug}' not found")

        new_count = (article.get("upvotes") or 0) + 1
        return self.update_article(slug, {"upvotes": new_count})

    def search_articles(self, query: str, limit: int = 20) -> list[dict]:
        """Search articles by title or summary."""
        # Simple text search using ilike
        result = (
            self.client.table("articles")
            .select("*")
            .or_(f"title.ilike.%{query}%,summary.ilike.%{query}%")
            .order("published_at", desc=True)
            .limit(limit)
            .execute()
        )
        return result.data or []

    def get_recent_articles(self, limit: int = 10, community: Optional[str] = None) -> list[dict]:
        """Get most recent articles."""
        query = self.client.table("articles").select("*")
        
        if community:
            query = query.eq("community_slug", community)
        
        result = (
            query
            .order("discovered_at", desc=True)
            .limit(limit)
            .execute()
        )
        return result.data or []
