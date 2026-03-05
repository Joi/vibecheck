#!/usr/bin/env python3
"""Backfill article titles and descriptions from actual URLs.

Fetches each article's URL to extract real <title> and meta description,
replacing chat-snippet summaries and URL-derived titles with proper metadata.

Usage:
    # Preview what would change (recommended first)
    python backfill_metadata.py --dry-run

    # Run the backfill
    python backfill_metadata.py

    # Only process articles with chat-snippet summaries
    python backfill_metadata.py --chat-snippets-only

    # Limit to N articles
    python backfill_metadata.py --limit 20
"""

import argparse
import re
import sys
import time
from urllib.parse import urlparse

import httpx  # type: ignore[import-not-found]

VIBECHECK_API = "https://vibecheck.ito.com/api/v1"

# Browser-like headers to avoid being blocked
FETCH_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def fetch_all_articles() -> list[dict]:
    """Fetch all articles from the API, paginating as needed."""
    all_articles: list[dict] = []
    page = 1
    while True:
        resp = httpx.get(
            f"{VIBECHECK_API}/articles",
            params={"page": page, "per_page": 100},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        articles = data.get("articles", [])
        if not articles:
            break
        all_articles.extend(articles)
        if not data.get("has_more"):
            break
        page += 1
    return all_articles


def has_chat_snippet_summary(summary: str) -> bool:
    """Check if a summary looks like a WhatsApp chat snippet."""
    if not summary:
        return False
    indicators = [
        "Context:",
        "\u202f",  # narrow no-break space from WhatsApp sender names
        "~ ",  # WhatsApp sender prefix
    ]
    return any(ind in summary for ind in indicators)


def has_bad_title(title: str, url: str) -> bool:
    """Check if a title looks auto-generated from URL rather than from the page."""
    if not title:
        return True
    # Title is a bare URL or domain
    if title.startswith("http"):
        return True
    # Title looks like a domain/path fragment (e.g. "aistudio.google.com/app/prompts")
    if "." in title and " " not in title and "/" in title:
        return True
    # Very short title that's likely from URL path
    if len(title) < 10:
        parsed = urlparse(url)
        path_slug = parsed.path.strip("/").split("/")[-1] if parsed.path.strip("/") else ""
        if title.lower().replace(" ", "-") == path_slug.lower().replace("_", "-"):
            return True
    return False


def needs_update(article: dict) -> bool:
    """Check if an article needs its metadata updated from the URL."""
    title = article.get("title", "")
    summary = article.get("summary") or ""
    url = article.get("url", "")
    return has_bad_title(title, url) or has_chat_snippet_summary(summary) or not summary


def fetch_url_metadata(url: str, client: httpx.Client) -> dict:
    """Fetch a URL and extract title + description from HTML metadata.

    Returns dict with 'title' and 'description' keys (may be None).
    """
    result: dict[str, str | None] = {"title": None, "description": None}

    try:
        resp = client.get(url, follow_redirects=True, timeout=15, headers=FETCH_HEADERS)
        if resp.status_code != 200:
            return result

        html = resp.text[:50000]

        # Extract <title>
        title_match = re.search(r"<title[^>]*>([^<]+)</title>", html, re.IGNORECASE)
        if title_match:
            title = title_match.group(1).strip()
            # Clean up common title suffixes
            title = re.sub(r"\s*[|–—-]\s*(Medium|Substack|WordPress).*$", "", title)
            result["title"] = title[:500]

        # Try og:title if <title> was empty or missing
        if not result["title"]:
            for pattern in [
                r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)["\']',
                r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:title["\']',
            ]:
                match = re.search(pattern, html, re.IGNORECASE)
                if match:
                    result["title"] = match.group(1).strip()[:500]
                    break

        # Extract description (prefer og:description > twitter:description > meta description)
        for pattern in [
            r'<meta[^>]+property=["\']og:description["\'][^>]+content=["\']([^"\']+)["\']',
            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:description["\']',
            r'<meta[^>]+name=["\']twitter:description["\'][^>]+content=["\']([^"\']+)["\']',
            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']twitter:description["\']',
            r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)["\']',
            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']description["\']',
        ]:
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                desc = match.group(1).strip()
                if len(desc) > 10:  # Skip trivially short descriptions
                    result["description"] = desc[:2000]
                    break

    except Exception:
        pass

    return result


def update_article(slug: str, title: str | None, summary: str | None) -> bool:
    """Update article via API PATCH endpoint."""
    params: dict[str, str] = {}
    if title:
        params["title"] = title
    if summary:
        params["summary"] = summary
    if not params:
        return False

    try:
        resp = httpx.patch(
            f"{VIBECHECK_API}/articles/{slug}",
            params=params,
            timeout=30,
        )
        return resp.status_code == 200
    except Exception as e:
        print(f"    Update failed: {e}")
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill article metadata from URLs")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without updating")
    parser.add_argument("--limit", type=int, default=0, help="Max articles to process (0=all)")
    parser.add_argument(
        "--chat-snippets-only",
        action="store_true",
        help="Only fix articles with chat-snippet summaries",
    )
    parser.add_argument(
        "--force-all",
        action="store_true",
        help="Re-fetch metadata for ALL articles, even ones that look OK",
    )
    args = parser.parse_args()

    print(f"Fetching articles from {VIBECHECK_API}...")
    all_articles = fetch_all_articles()
    print(f"Found {len(all_articles)} total articles")

    # Filter to articles needing work
    if args.force_all:
        to_process = all_articles
    elif args.chat_snippets_only:
        to_process = [
            a for a in all_articles if has_chat_snippet_summary(a.get("summary") or "")
        ]
    else:
        to_process = [a for a in all_articles if needs_update(a)]

    print(f"{len(to_process)} articles need metadata update")

    if args.limit:
        to_process = to_process[: args.limit]
        print(f"Processing first {len(to_process)}")

    if not to_process:
        print("Nothing to do!")
        return 0

    updated = 0
    skipped = 0
    failed = 0

    with httpx.Client(timeout=30) as client:
        for i, article in enumerate(to_process, 1):
            url = article["url"]
            slug = article["slug"]
            old_title = article.get("title", "")
            old_summary = (article.get("summary") or "")[:60]

            print(f"\n[{i}/{len(to_process)}] {old_title[:50]}")
            print(f"  URL: {url[:80]}")

            # Fetch real metadata from the URL
            metadata = fetch_url_metadata(url, client)
            new_title = metadata.get("title")
            new_desc = metadata.get("description")

            if not new_title and not new_desc:
                print("  -> Could not fetch metadata (site unreachable or no meta tags)")
                failed += 1
                continue

            # Decide what to update
            update_title = None
            update_summary = None

            # Update title if we got a better one
            if new_title and has_bad_title(old_title, url):
                update_title = new_title
                print(f"  Title: {old_title[:40]} -> {new_title[:60]}")

            # Update summary if current one is missing or is a chat snippet
            current_summary = article.get("summary") or ""
            if new_desc and (not current_summary or has_chat_snippet_summary(current_summary)):
                update_summary = new_desc
                print(f"  Summary: {old_summary}... -> {new_desc[:60]}...")

            if not update_title and not update_summary:
                print("  -> No improvement found (page metadata not better than current)")
                skipped += 1
                continue

            if args.dry_run:
                print("  [DRY RUN] Would update")
                updated += 1
            else:
                if update_article(slug, update_title, update_summary):
                    print("  -> Updated")
                    updated += 1
                else:
                    print("  -> Update FAILED")
                    failed += 1

            # Be polite to servers
            time.sleep(0.3)

    print(f"\n{'=' * 40}")
    print(f"Results:")
    print(f"  Updated: {updated}")
    print(f"  Skipped (no improvement): {skipped}")
    print(f"  Failed (unreachable): {failed}")
    print(f"  Total processed: {updated + skipped + failed}")

    if failed > 0:
        print(f"\n{failed} articles could not be fetched.")
        print("Run `python enhance_articles.py` to use AI for those.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
