#!/usr/bin/env python3
"""Enhance article titles and descriptions using AI.

Fetches article content and uses Claude/Gemini to generate better
titles and descriptions for articles with poor metadata.

Usage:
    # Enhance all articles missing good descriptions
    python enhance_articles.py
    
    # Dry run to preview changes
    python enhance_articles.py --dry-run
    
    # Limit number of articles to process
    python enhance_articles.py --limit 10
    
    # Force re-enhance even if description exists
    python enhance_articles.py --force
"""

import argparse
import os
import re
import sys
from urllib.parse import urlparse

import httpx

# API endpoints
VIBECHECK_API = "https://vibecheck.ito.com/api/v1"

# Try to import AI libraries
try:
    import anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False

try:
    import google.generativeai as genai
    HAS_GEMINI = True
except ImportError:
    HAS_GEMINI = False


def fetch_page_content(url: str, timeout: int = 15) -> str | None:
    """Fetch and extract text content from a URL."""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        }
        resp = httpx.get(url, headers=headers, timeout=timeout, follow_redirects=True)
        resp.raise_for_status()
        
        html = resp.text
        
        # Extract title
        title_match = re.search(r'<title[^>]*>([^<]+)</title>', html, re.IGNORECASE)
        title = title_match.group(1).strip() if title_match else ""
        
        # Remove script and style tags
        html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)
        
        # Remove HTML tags
        text = re.sub(r'<[^>]+>', ' ', html)
        
        # Clean up whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        
        # Limit content length for AI
        if len(text) > 8000:
            text = text[:8000] + "..."
        
        return f"Title: {title}\n\nContent:\n{text}"
    except Exception as e:
        print(f"    Failed to fetch: {e}")
        return None


def enhance_with_claude(content: str, url: str) -> dict | None:
    """Use Claude to generate better title and description."""
    if not HAS_ANTHROPIC:
        return None
    
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None
    
    client = anthropic.Anthropic(api_key=api_key)
    
    prompt = f"""Analyze this article/page and generate a concise, informative title and description.

URL: {url}

Page content:
{content}

Respond in this exact format (no markdown, no extra text):
TITLE: [A clear, descriptive title - max 80 chars]
DESCRIPTION: [A 1-2 sentence summary of what this article is about - max 200 chars]

If this appears to be a non-article page (login, error, paywall, etc), respond with:
SKIP: [reason]"""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}]
        )
        
        text = response.content[0].text.strip()
        
        if text.startswith("SKIP:"):
            return {"skip": text[5:].strip()}
        
        title_match = re.search(r'TITLE:\s*(.+)', text)
        desc_match = re.search(r'DESCRIPTION:\s*(.+)', text, re.DOTALL)
        
        if title_match and desc_match:
            return {
                "title": title_match.group(1).strip()[:100],
                "summary": desc_match.group(1).strip()[:250]
            }
    except Exception as e:
        print(f"    Claude error: {e}")
    
    return None


def enhance_with_gemini(content: str, url: str) -> dict | None:
    """Use Gemini to generate better title and description."""
    if not HAS_GEMINI:
        return None
    
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        return None
    
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-2.0-flash")
    
    prompt = f"""Analyze this article/page and generate a concise, informative title and description.

URL: {url}

Page content:
{content}

Respond in this exact format (no markdown, no extra text):
TITLE: [A clear, descriptive title - max 80 chars]
DESCRIPTION: [A 1-2 sentence summary of what this article is about - max 200 chars]

If this appears to be a non-article page (login, error, paywall, etc), respond with:
SKIP: [reason]"""

    try:
        response = model.generate_content(prompt)
        text = response.text.strip()
        
        if text.startswith("SKIP:"):
            return {"skip": text[5:].strip()}
        
        title_match = re.search(r'TITLE:\s*(.+)', text)
        desc_match = re.search(r'DESCRIPTION:\s*(.+)', text, re.DOTALL)
        
        if title_match and desc_match:
            return {
                "title": title_match.group(1).strip()[:100],
                "summary": desc_match.group(1).strip()[:250]
            }
    except Exception as e:
        print(f"    Gemini error: {e}")
    
    return None


def needs_enhancement(article: dict) -> bool:
    """Check if an article needs better metadata."""
    title = article.get("title", "")
    summary = article.get("summary", "")
    url = article.get("url", "")
    
    # No summary at all
    if not summary:
        return True
    
    # Title is just a URL or domain
    if title.startswith("http") or "." in title and "/" not in title:
        return True
    
    # Title is very short (likely auto-generated)
    if len(title) < 15:
        return True
    
    # Title matches URL path pattern
    parsed = urlparse(url)
    path_parts = parsed.path.strip("/").split("/")
    if path_parts and title.lower().replace(" ", "-") in [p.lower() for p in path_parts]:
        return True
    
    # Summary is too short
    if len(summary) < 30:
        return True
    
    return False


def update_article(slug: str, title: str, summary: str, dry_run: bool = False) -> bool:
    """Update article in the database."""
    if dry_run:
        print(f"    [DRY RUN] Would update: {title[:50]}...")
        return True
    
    try:
        resp = httpx.patch(
            f"{VIBECHECK_API}/articles/{slug}",
            params={"title": title, "summary": summary},
            timeout=30
        )
        if resp.status_code == 404:
            print(f"    Article not found: {slug}")
            return False
        resp.raise_for_status()
        print(f"    Updated successfully")
        return True
    except Exception as e:
        print(f"    Update failed: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Enhance article metadata with AI")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without updating")
    parser.add_argument("--limit", type=int, default=50, help="Max articles to process")
    parser.add_argument("--force", action="store_true", help="Re-enhance even if description exists")
    args = parser.parse_args()
    
    # Check for AI APIs
    if not HAS_ANTHROPIC and not HAS_GEMINI:
        print("Error: Need anthropic or google-generativeai package")
        sys.exit(1)
    
    has_api_key = (
        os.environ.get("ANTHROPIC_API_KEY") or 
        os.environ.get("GEMINI_API_KEY") or
        os.environ.get("GOOGLE_API_KEY")
    )
    if not has_api_key:
        print("Error: Need ANTHROPIC_API_KEY or GEMINI_API_KEY environment variable")
        sys.exit(1)
    
    print(f"Fetching articles from {VIBECHECK_API}...")
    
    # Fetch all articles (paginate)
    all_articles = []
    page = 1
    while True:
        resp = httpx.get(f"{VIBECHECK_API}/articles", params={"page": page, "per_page": 100})
        data = resp.json()
        articles = data.get("articles", [])
        if not articles:
            break
        all_articles.extend(articles)
        if len(articles) < 100:
            break
        page += 1
    
    print(f"Found {len(all_articles)} total articles")
    
    # Filter to articles needing enhancement
    if args.force:
        to_enhance = all_articles
    else:
        to_enhance = [a for a in all_articles if needs_enhancement(a)]
    
    print(f"{len(to_enhance)} articles need enhancement")
    
    if args.limit:
        to_enhance = to_enhance[:args.limit]
        print(f"Processing first {len(to_enhance)} articles")
    
    enhanced = 0
    skipped = 0
    failed = 0
    
    for i, article in enumerate(to_enhance, 1):
        url = article["url"]
        current_title = article.get("title", "")
        print(f"\n[{i}/{len(to_enhance)}] {current_title[:50]}...")
        print(f"    URL: {url}")
        
        # Fetch page content
        content = fetch_page_content(url)
        if not content:
            failed += 1
            continue
        
        # Try Claude first, then Gemini
        result = enhance_with_claude(content, url)
        if not result:
            result = enhance_with_gemini(content, url)
        
        if not result:
            print("    No AI response")
            failed += 1
            continue
        
        if "skip" in result:
            print(f"    Skipped: {result['skip']}")
            skipped += 1
            continue
        
        new_title = result["title"]
        new_summary = result["summary"]
        
        print(f"    New title: {new_title}")
        print(f"    Summary: {new_summary[:80]}...")
        
        if update_article(article["slug"], new_title, new_summary, args.dry_run):
            enhanced += 1
        else:
            failed += 1
    
    print(f"\n=== Summary ===")
    print(f"Enhanced: {enhanced}")
    print(f"Skipped: {skipped}")
    print(f"Failed: {failed}")


if __name__ == "__main__":
    main()
