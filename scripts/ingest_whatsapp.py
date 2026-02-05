#!/usr/bin/env python3
"""Parse WhatsApp chat export and extract tool mentions for vibecheck.

Supports incremental imports with deduplication:
- Use --since DATE to only process messages after a certain date
- Use --auto-since to automatically detect the last import date from the database
- Existing URLs are automatically skipped (deduplication)

Example:
    # Auto-detect where we left off (recommended for vibez-agi)
    python ingest_whatsapp.py chat.zip --community agi --auto-since
    
    # Process only messages since a specific date
    python ingest_whatsapp.py chat.zip --since 2026-02-01
    
    # Dry run to see what would be imported
    python ingest_whatsapp.py chat.zip --auto-since --dry-run
"""

import re
import zipfile
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import httpx  # type: ignore[import-not-found]

# vibecheck API
VIBECHECK_API = "https://vibecheck.ito.com/api/v1"

# Known tool patterns - maps URL patterns or names to tool info
KNOWN_TOOLS = {
    # GitHub repos - will be parsed from URL
    "github.com": "github",
    
    # Specific tools mentioned by name
    "clawdbot": {"slug": "clawdbot", "name": "Clawdbot", "categories": ["app", "agent-framework"]},
    "claude code": {"slug": "claude-code", "name": "Claude Code", "categories": ["coding-assistant", "cli"]},
    "cursor": {"slug": "cursor", "name": "Cursor", "categories": ["coding-assistant", "editor"]},
    "amplifier": {"slug": "amplifier", "name": "Amplifier", "categories": ["agent-framework", "cli"]},
    "superpowers": {"slug": "superpowers", "name": "Superpowers", "categories": ["library"]},
    "ollama": {"slug": "ollama", "name": "Ollama", "categories": ["infrastructure"]},
    "vercel": {"slug": "vercel", "name": "Vercel", "categories": ["infrastructure"]},
    "mcp": {"slug": "mcp", "name": "Model Context Protocol", "categories": ["library"]},
    "chatgpt": {"slug": "chatgpt", "name": "ChatGPT", "categories": ["app", "coding-assistant"]},
    "gemini": {"slug": "gemini", "name": "Gemini", "categories": ["app"]},
    "aider": {"slug": "aider", "name": "Aider", "categories": ["coding-assistant", "cli"]},
    "cline": {"slug": "cline", "name": "Cline", "categories": ["coding-assistant"]},
    "windsurf": {"slug": "windsurf", "name": "Windsurf", "categories": ["coding-assistant", "editor"]},
    "copilot": {"slug": "github-copilot", "name": "GitHub Copilot", "categories": ["coding-assistant"]},
    "molt": {"slug": "molt", "name": "Molt", "categories": ["app"]},
    "wacli": {"slug": "wacli", "name": "wacli", "categories": ["cli"]},
    "verbal": {"slug": "verbal", "name": "Verbal", "categories": ["app"]},
    "a2ui": {"slug": "a2ui", "name": "a2ui", "categories": ["app"]},
    "beads": {"slug": "beads", "name": "Beads", "categories": ["cli"]},
}

# WhatsApp message pattern: [date, time] sender: message
MESSAGE_PATTERN = re.compile(
    r'\[(\d{4}/\d{2}/\d{2}),?\s*(\d{1,2}:\d{2}:\d{2})\]\s*([^:]+):\s*(.+)',
    re.DOTALL
)


def parse_whatsapp_export(filepath: Path) -> list[dict]:
    """Parse WhatsApp chat export into structured messages."""
    messages = []
    
    # Handle zip files
    if filepath.suffix == '.zip':
        with zipfile.ZipFile(filepath, 'r') as zf:
            # Find the chat file (usually _chat.txt)
            chat_files = [f for f in zf.namelist() if f.endswith('.txt') and 'chat' in f.lower()]
            if not chat_files:
                chat_files = [f for f in zf.namelist() if f.endswith('.txt')]
            if not chat_files:
                raise ValueError(f"No chat .txt file found in {filepath}")
            
            with zf.open(chat_files[0]) as f:
                content = f.read().decode('utf-8', errors='replace')
    else:
        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
    
    # Split by message boundaries (lines starting with [YYYY/MM/DD, HH:MM:SS])
    raw_messages = re.split(r'(?=\[\d{4}/\d{2}/\d{2},\s*\d{1,2}:\d{2}:\d{2}\])', content)
    
    for raw in raw_messages:
        raw = raw.strip()
        if not raw:
            continue
            
        match = MESSAGE_PATTERN.match(raw)
        if match:
            date_str, time_str, sender, text = match.groups()
            
            # Clean sender name (remove ~ prefix)
            sender = sender.strip().lstrip('~\u202f').strip()
            
            # Parse datetime
            try:
                dt = datetime.strptime(f"{date_str} {time_str}", "%Y/%m/%d %H:%M:%S")
            except ValueError:
                continue
            
            # Skip system messages
            if sender.endswith('(code code code)') or 'joined' in text.lower() or 'added' in text.lower():
                continue
                
            messages.append({
                'timestamp': dt.isoformat(),
                'sender': sender,
                'text': text.strip(),
            })
    
    return messages


def extract_github_tool(url: str) -> dict | None:
    """Extract tool info from GitHub URL."""
    parsed = urlparse(url)
    if 'github.com' not in parsed.netloc:
        return None
        
    parts = parsed.path.strip('/').split('/')
    if len(parts) >= 2:
        owner, repo = parts[0], parts[1]
        slug = repo.lower().replace('_', '-')
        return {
            'slug': slug,
            'name': repo,
            'github_url': f"https://github.com/{owner}/{repo}",
            'categories': ['library'],  # Default, can be refined
        }
    return None


def extract_tools_from_message(msg: dict) -> list[dict]:
    """Extract tool mentions from a message."""
    tools = []
    text = msg['text'].lower()
    
    # Check for URLs
    urls = re.findall(r'https?://[^\s\r\n\]]+', msg['text'])
    for url in urls:
        url = url.rstrip('.,;:!?)>"\']')
        
        # GitHub repos
        if 'github.com' in url:
            tool = extract_github_tool(url)
            if tool:
                tool['mentioned_at'] = msg['timestamp']
                tool['context'] = msg['text'][:200]  # First 200 chars
                tool['sender'] = msg['sender']
                tools.append(tool)
        
        # arxiv papers
        elif 'arxiv.org' in url:
            tools.append({
                'slug': 'arxiv-' + url.split('/')[-1].replace('.pdf', ''),
                'name': f"arXiv Paper {url.split('/')[-1]}",
                'url': url,
                'categories': ['paper', 'research'],
                'mentioned_at': msg['timestamp'],
                'context': msg['text'][:200],
                'sender': msg['sender'],
            })
    
    # Check for known tool names
    for name, info in KNOWN_TOOLS.items():
        if name == 'github.com':
            continue
        if name in text:
            if isinstance(info, dict):
                tool = info.copy()
                tool['mentioned_at'] = msg['timestamp']
                tool['context'] = msg['text'][:200]
                tool['sender'] = msg['sender']
                tools.append(tool)
    
    return tools


def detect_sentiment(text: str) -> str:
    """Simple sentiment detection."""
    text = text.lower()
    
    positive = ['love', 'great', 'awesome', 'cool', 'nice', 'works', 'recommend', 'impressed', 'amazing']
    negative = ['broken', 'sucks', 'bad', 'hate', 'frustrat', 'annoying', 'doesn\'t work', 'failed']
    question = ['?', 'how do', 'anyone', 'has anyone', 'what is', 'which']
    
    if any(q in text for q in question):
        return 'question'
    if any(p in text for p in positive):
        return 'positive'
    if any(n in text for n in negative):
        return 'negative'
    return 'neutral'


def sanitize_context(text: str, max_len: int = 200) -> str:
    """Sanitize context - remove phone numbers, emails, etc."""
    # Remove phone numbers
    text = re.sub(r'\+?\d{10,}', '[phone]', text)
    # Remove emails
    text = re.sub(r'\S+@\S+\.\S+', '[email]', text)
    # Truncate
    if len(text) > max_len:
        text = text[:max_len] + '...'
    return text


def push_to_vibecheck(tools: list[dict], community: str = 'agi', dry_run: bool = False):
    """Push extracted tools to vibecheck API."""
    
    # Deduplicate by slug
    seen = {}
    for tool in tools:
        slug = tool['slug']
        if slug not in seen:
            seen[slug] = tool
        else:
            # Keep the one with more context or earlier timestamp
            pass
    
    tools = list(seen.values())
    print(f"\n=== Pushing {len(tools)} unique tools to vibecheck ===\n")
    
    if dry_run:
        for tool in tools:
            print(f"  {tool['slug']}: {tool.get('name', tool['slug'])}")
            print(f"    Categories: {tool.get('categories', [])}")
            print(f"    Context: {sanitize_context(tool.get('context', ''), 100)}")
            print()
        return
    
    # Push to API
    with httpx.Client() as client:
        for tool in tools:
            payload = {
                'tool_name': tool.get('name', tool['slug']),
                'tool_slug': tool['slug'],
                'github_url': tool.get('github_url'),
                'tool_url': tool.get('url'),
                'community': community,
                'mentioned_at': tool.get('mentioned_at'),
                'context_snippet': sanitize_context(tool.get('context', '')),
                'sentiment': detect_sentiment(tool.get('context', '')),
                'source': 'whatsapp-import',
            }
            
            try:
                resp = client.post(f"{VIBECHECK_API}/ingest", json=payload)
                if resp.status_code == 200:
                    result = resp.json()
                    print(f"  ✓ {tool['slug']}: created={result.get('created')}, updated={result.get('updated')}")
                else:
                    print(f"  ✗ {tool['slug']}: {resp.status_code} - {resp.text[:100]}")
            except Exception as e:
                print(f"  ✗ {tool['slug']}: {e}")


def get_existing_urls() -> set[str]:
    """Fetch existing article URLs from database for deduplication."""
    try:
        resp = httpx.get(f"{VIBECHECK_API}/articles", params={"per_page": 1000}, timeout=30)
        if resp.status_code == 200:
            data = resp.json()
            articles = data.get("articles", [])
            return {a.get("url", "") for a in articles if a.get("url")}
    except Exception as e:
        print(f"Warning: Could not fetch existing URLs: {e}")
    return set()


def get_last_import_date() -> datetime | None:
    """Get the most recent mention date from the database."""
    try:
        # Query the API for the most recent article/mention
        resp = httpx.get(
            f"{VIBECHECK_API}/articles",
            params={"per_page": 1, "sort_by": "discovered_at", "sort_order": "desc"},
            timeout=30,
        )
        if resp.status_code == 200:
            data = resp.json()
            articles = data.get("articles", [])
            if articles:
                discovered_at = articles[0].get("discovered_at")
                if discovered_at:
                    # Parse ISO format
                    return datetime.fromisoformat(discovered_at.replace("Z", "+00:00"))
    except Exception as e:
        print(f"Warning: Could not fetch last import date: {e}")
    return None


def extract_articles_from_message(msg: dict) -> list[dict]:
    """Extract article URLs from a message."""
    articles = []
    urls = re.findall(r'https?://[^\s\r\n\]]+', msg['text'])
    
    # URLs to skip (social media, video, chat platforms)
    skip_patterns = [
        'youtube.com/watch', 'youtu.be', 'twitter.com', 'x.com/status',
        'instagram.com', 'facebook.com', 'tiktok.com', 'linkedin.com/posts',
        'whatsapp.com', 't.me', 'discord.gg', 'meet.google.com', 'zoom.us',
        'github.com',  # Tools are handled separately
    ]
    
    for url in urls:
        url = url.rstrip('.,;:!?)>"\']\r\n')
        
        # Skip non-article URLs
        if any(skip in url.lower() for skip in skip_patterns):
            continue
            
        articles.append({
            'url': url,
            'mentioned_at': msg['timestamp'],
            'context': msg['text'][:200],
            'sender': msg['sender'],
        })
    
    return articles


def generate_title_from_url(url: str) -> str:
    """Generate a readable title from URL (fallback when fetch fails)."""
    parsed = urlparse(url)
    path = parsed.path.strip('/')
    
    # Common patterns
    if 'blog' in path or 'posts' in path:
        # Blog post - use last path segment
        parts = path.split('/')
        title = parts[-1] if parts else parsed.netloc
    elif parsed.netloc == 'arxiv.org':
        return f"arXiv Paper {path.split('/')[-1]}"
    elif 'github.com' in parsed.netloc:
        parts = path.split('/')
        if len(parts) >= 2:
            return f"{parts[0]}/{parts[1]} on GitHub"
        return f"GitHub: {path}"
    else:
        # Use domain + path
        title = path.split('/')[-1] if path else parsed.netloc
    
    # Clean up
    title = title.replace('-', ' ').replace('_', ' ')
    title = re.sub(r'\.(html?|php|aspx?)$', '', title)
    return title.title() if title else parsed.netloc


def fetch_url_metadata(url: str, client: httpx.Client) -> dict:
    """Fetch URL and extract title and description from HTML metadata.
    
    Returns dict with 'title' and 'description' keys (may be None if not found).
    """
    result = {'title': None, 'description': None}
    
    try:
        resp = client.get(url, follow_redirects=True, timeout=15)
        if resp.status_code != 200:
            return result
        
        html = resp.text[:50000]  # Only parse first 50KB
        
        # Extract <title> tag
        title_match = re.search(r'<title[^>]*>([^<]+)</title>', html, re.IGNORECASE)
        if title_match:
            result['title'] = title_match.group(1).strip()[:500]
        
        # Extract meta description (prefer og:description, then twitter:description, then description)
        for pattern in [
            r'<meta[^>]+property=["\']og:description["\'][^>]+content=["\']([^"\']+)["\']',
            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:description["\']',
            r'<meta[^>]+name=["\']twitter:description["\'][^>]+content=["\']([^"\']+)["\']',
            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']twitter:description["\']',
            r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)["\']',
            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']description["\']',
        ]:
            desc_match = re.search(pattern, html, re.IGNORECASE)
            if desc_match:
                result['description'] = desc_match.group(1).strip()[:2000]
                break
        
        # Also try og:title if title tag is empty
        if not result['title']:
            for pattern in [
                r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)["\']',
                r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:title["\']',
            ]:
                og_title_match = re.search(pattern, html, re.IGNORECASE)
                if og_title_match:
                    result['title'] = og_title_match.group(1).strip()[:500]
                    break
    
    except Exception:
        pass  # Silently fail, will use fallback
    
    return result


def push_articles_to_vibecheck(
    articles: list[dict],
    existing_urls: set[str],
    community: str = 'agi',
    dry_run: bool = False,
    fetch_metadata: bool = True,
) -> tuple[int, int]:
    """Push extracted articles to vibecheck API. Returns (created, skipped).
    
    Args:
        articles: List of article dicts with 'url', 'context', etc.
        existing_urls: Set of URLs already in database (for deduplication)
        community: Community slug to associate articles with
        dry_run: If True, only print what would be done
        fetch_metadata: If True, fetch each URL to get real title/description
    """
    # Deduplicate by URL
    seen: dict[str, dict] = {}
    for article in articles:
        url = article['url']
        if url not in seen and url not in existing_urls:
            seen[url] = article
    
    articles = list(seen.values())
    skipped = len(existing_urls & {a['url'] for a in articles})
    
    print(f"\n=== Processing {len(articles)} new articles ({skipped} already exist) ===\n")
    
    if dry_run:
        for article in articles[:20]:  # Show first 20
            print(f"  {article['url'][:60]}...")
            print(f"    Context: {sanitize_context(article.get('context', ''), 80)}")
            print()
        if len(articles) > 20:
            print(f"  ... and {len(articles) - 20} more")
        return 0, 0
    
    created = 0
    with httpx.Client(timeout=30) as client:
        for article in articles:
            url = article['url']
            
            # Try to fetch real title and description from the URL
            title: str | None = None
            description: str | None = None
            
            if fetch_metadata:
                print(f"  Fetching {url[:50]}...", end=" ", flush=True)
                metadata = fetch_url_metadata(url, client)
                title = metadata.get('title')
                description = metadata.get('description')
            
            # Fallback to generated title if fetch failed
            if not title:
                title = generate_title_from_url(url)
            
            # Use description from page, or fall back to WhatsApp context
            summary = description or sanitize_context(article.get('context', ''), 300)
            
            payload = {
                'url': url,
                'title': title,
                'community_slug': community,
                'summary': summary,
                'source': 'whatsapp-import',
            }
            
            try:
                resp = client.post(f"{VIBECHECK_API}/articles", json=payload)
                if resp.status_code == 200:
                    created += 1
                    if fetch_metadata:
                        print(f"✓ {title[:50]}...")
                    else:
                        print(f"  ✓ {url[:60]}...")
                elif resp.status_code == 409 or resp.status_code == 422:
                    # Already exists or validation error
                    if fetch_metadata:
                        print("(already exists)")
                else:
                    if fetch_metadata:
                        print(f"✗ {resp.status_code}")
                    else:
                        print(f"  ✗ {url[:40]}: {resp.status_code}")
            except Exception as e:
                if fetch_metadata:
                    print(f"✗ {e}")
                else:
                    print(f"  ✗ {url[:40]}: {e}")
    
    return created, len(articles) - created


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Ingest WhatsApp chat export to vibecheck',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Auto-detect where we left off (recommended for vibez-agi incremental imports)
  python ingest_whatsapp.py chat.zip --community agi --auto-since
  
  # Process only messages since a specific date
  python ingest_whatsapp.py chat.zip --since 2026-02-01
  
  # Dry run to see what would be imported
  python ingest_whatsapp.py chat.zip --auto-since --dry-run
        """,
    )
    parser.add_argument('chatfile', help='Path to WhatsApp chat export (.zip or .txt)')
    parser.add_argument('--community', default='agi', help='Community slug (default: agi)')
    parser.add_argument('--dry-run', action='store_true', help='Print what would be imported without pushing')
    parser.add_argument('--since', help='Only process messages after this date (YYYY-MM-DD)')
    parser.add_argument('--auto-since', action='store_true', 
                        help='Auto-detect last import date from database')
    parser.add_argument('--articles-only', action='store_true', help='Only import articles, skip tools')
    parser.add_argument('--tools-only', action='store_true', help='Only import tools, skip articles')
    parser.add_argument('--no-fetch', action='store_true', 
                        help='Skip fetching URLs for metadata (use URL-derived titles)')
    args = parser.parse_args()
    
    filepath = Path(args.chatfile)
    if not filepath.exists():
        print(f"Error: {filepath} not found")
        return 1
    
    # Determine since date
    since_date = None
    if args.auto_since:
        since_date = get_last_import_date()
        if since_date:
            print(f"Auto-detected last import: {since_date.strftime('%Y-%m-%d %H:%M')}")
        else:
            print("No previous imports found, processing all messages")
    elif args.since:
        try:
            since_date = datetime.strptime(args.since, "%Y-%m-%d")
            print(f"Processing messages since: {since_date.strftime('%Y-%m-%d')}")
        except ValueError:
            print(f"Error: Invalid date format '{args.since}'. Use YYYY-MM-DD")
            return 1
    
    # Get existing URLs for deduplication
    print("Fetching existing content for deduplication...")
    existing_urls = get_existing_urls()
    print(f"Found {len(existing_urls)} existing URLs")
    
    print(f"\nParsing {filepath}...")
    messages = parse_whatsapp_export(filepath)
    print(f"Found {len(messages)} total messages")
    
    # Filter by date if specified
    if since_date:
        original_count = len(messages)
        # Make since_date naive if it's aware (for comparison with naive timestamps)
        since_date_naive = since_date.replace(tzinfo=None) if since_date.tzinfo else since_date
        messages = [
            m for m in messages
            if datetime.fromisoformat(m['timestamp']) > since_date_naive
        ]
        print(f"Filtered to {len(messages)} messages after {since_date.strftime('%Y-%m-%d')}")
        print(f"  (Skipped {original_count - len(messages)} older messages)")
    
    if not messages:
        print("\nNo new messages to process.")
        return 0
    
    # Extract and push tools
    if not args.articles_only:
        print("\nExtracting tool mentions...")
        all_tools = []
        for msg in messages:
            tools = extract_tools_from_message(msg)
            all_tools.extend(tools)
        print(f"Found {len(all_tools)} tool mentions")
        push_to_vibecheck(all_tools, community=args.community, dry_run=args.dry_run)
    
    # Extract and push articles
    if not args.tools_only:
        print("\nExtracting article URLs...")
        all_articles = []
        for msg in messages:
            articles = extract_articles_from_message(msg)
            all_articles.extend(articles)
        print(f"Found {len(all_articles)} article URLs")
        push_articles_to_vibecheck(
            all_articles,
            existing_urls,
            community=args.community,
            dry_run=args.dry_run,
            fetch_metadata=not args.no_fetch,
        )
    
    print("\nDone!")
    return 0


if __name__ == '__main__':
    exit(main())
