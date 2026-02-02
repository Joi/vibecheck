#!/usr/bin/env python3
"""Direct database import bypassing the API."""
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import psycopg2

def get_db_password():
    result = subprocess.run(
        ['op', 'item', 'get', 'Supabase vibecheck database password', 
         '--vault', 'Employee', '--fields', 'password', '--reveal'],
        capture_output=True, text=True
    )
    return result.stdout.strip()

def get_connection():
    return psycopg2.connect(
        host="db.pycvrvounfzlrwjdmuij.supabase.co",
        port=5432,
        database="postgres",
        user="postgres",
        password=get_db_password(),
        sslmode="require"
    )

def import_tools(tools: list[dict], community_slug: str = 'agi'):
    """Import tools directly to database."""
    conn = get_connection()
    conn.autocommit = True
    cur = conn.cursor()
    
    # Get or create community
    cur.execute("SELECT id FROM communities WHERE slug = %s", (community_slug,))
    row = cur.fetchone()
    if row:
        community_id = row[0]
    else:
        cur.execute(
            "INSERT INTO communities (slug, name) VALUES (%s, %s) RETURNING id",
            (community_slug, community_slug.upper())
        )
        community_id = cur.fetchone()[0]
        print(f"Created community: {community_slug}")
    
    created = 0
    updated = 0
    
    for tool in tools:
        slug = tool['slug']
        name = tool.get('name', slug)
        
        # Check if tool exists
        cur.execute("SELECT id FROM tools WHERE slug = %s", (slug,))
        row = cur.fetchone()
        
        if row:
            tool_id = row[0]
            updated += 1
        else:
            # Create tool
            cur.execute("""
                INSERT INTO tools (slug, name, url, github_url, source, first_seen)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (
                slug, name, tool.get('url'), tool.get('github_url'),
                tool.get('source', 'whatsapp-import'),
                tool.get('mentioned_at', datetime.now().isoformat())
            ))
            tool_id = cur.fetchone()[0]
            created += 1
        
        # Record mention
        mentioned_at = tool.get('mentioned_at')
        if mentioned_at and isinstance(mentioned_at, str):
            pass  # Already a string
        elif mentioned_at:
            mentioned_at = mentioned_at.isoformat()
        else:
            mentioned_at = datetime.now().isoformat()
        
        cur.execute("""
            INSERT INTO tool_mentions (tool_id, community_id, mentioned_at, context_snippet, sentiment)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT DO NOTHING
        """, (
            tool_id, community_id, mentioned_at,
            tool.get('context', '')[:500] if tool.get('context') else None,
            tool.get('sentiment')
        ))
        
        # Link tool to community
        cur.execute("""
            INSERT INTO tool_communities (tool_id, community_id, first_mentioned)
            VALUES (%s, %s, %s)
            ON CONFLICT (tool_id, community_id) DO UPDATE SET mention_count = tool_communities.mention_count + 1
        """, (tool_id, community_id, mentioned_at))
    
    cur.close()
    conn.close()
    
    print(f"\n✅ Import complete: {created} created, {updated} updated")
    return created, updated

if __name__ == "__main__":
    # Test
    test_tools = [{"slug": "test-direct", "name": "Test Direct"}]
    import_tools(test_tools, "agi")
