#!/usr/bin/env python3
"""Parse WhatsApp chat export and extract tool mentions for vibecheck."""

import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import httpx

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
    
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Split by message boundaries (new lines starting with [date)
    raw_messages = re.split(r'(?=\[\d{4}/\d{2}/\d{2})', content)
    
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


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Ingest WhatsApp chat export to vibecheck')
    parser.add_argument('chatfile', help='Path to WhatsApp _chat.txt export')
    parser.add_argument('--community', default='agi', help='Community slug (default: agi)')
    parser.add_argument('--dry-run', action='store_true', help='Print what would be pushed without pushing')
    args = parser.parse_args()
    
    filepath = Path(args.chatfile)
    if not filepath.exists():
        print(f"Error: {filepath} not found")
        return 1
    
    print(f"Parsing {filepath}...")
    messages = parse_whatsapp_export(filepath)
    print(f"Found {len(messages)} messages")
    
    print("Extracting tool mentions...")
    all_tools = []
    for msg in messages:
        tools = extract_tools_from_message(msg)
        all_tools.extend(tools)
    
    print(f"Found {len(all_tools)} tool mentions")
    
    push_to_vibecheck(all_tools, community=args.community, dry_run=args.dry_run)
    
    return 0


if __name__ == '__main__':
    exit(main())
