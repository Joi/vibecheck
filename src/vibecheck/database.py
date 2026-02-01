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
