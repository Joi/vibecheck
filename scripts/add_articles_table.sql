-- Articles table for blog posts and articles about vibe coding
-- Run this in Supabase SQL Editor

-- Create articles table
CREATE TABLE IF NOT EXISTS articles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slug TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    url TEXT NOT NULL UNIQUE,
    author TEXT,
    published_at TIMESTAMPTZ,
    discovered_at TIMESTAMPTZ DEFAULT NOW(),
    summary TEXT,
    tags TEXT[] DEFAULT '{}',
    
    -- Source tracking
    source TEXT,  -- 'whatsapp', 'manual', 'rss', etc.
    community_slug TEXT REFERENCES communities(slug),
    mentioned_by TEXT,  -- Who shared it
    
    -- Engagement
    upvotes INT DEFAULT 0,
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for fast lookups
CREATE INDEX IF NOT EXISTS idx_articles_published_at ON articles(published_at DESC);
CREATE INDEX IF NOT EXISTS idx_articles_community ON articles(community_slug);
CREATE INDEX IF NOT EXISTS idx_articles_tags ON articles USING GIN(tags);

-- Enable RLS
ALTER TABLE articles ENABLE ROW LEVEL SECURITY;

-- RLS policies - allow public read/insert
CREATE POLICY "Allow public select on articles" ON articles
    FOR SELECT TO anon USING (true);

CREATE POLICY "Allow public insert on articles" ON articles
    FOR INSERT TO anon WITH CHECK (true);

CREATE POLICY "Allow public update on articles" ON articles
    FOR UPDATE TO anon USING (true);

-- Add some initial tags for vibe coding articles
COMMENT ON TABLE articles IS 'Blog posts, articles, and content about vibe coding and AI-assisted development';

-- Create view for recent articles with community info
CREATE OR REPLACE VIEW recent_articles AS
SELECT 
    a.*,
    c.name as community_name
FROM articles a
LEFT JOIN communities c ON a.community_slug = c.slug
ORDER BY COALESCE(a.published_at, a.discovered_at) DESC;
