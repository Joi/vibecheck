-- vibecheck schema
-- AI tools intelligence database

-- Enable UUID extension

-- Users table (GitHub OAuth)
CREATE TABLE users (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  github_id TEXT UNIQUE,
  github_username TEXT,
  display_name TEXT,
  avatar_url TEXT,
  is_admin BOOLEAN DEFAULT false,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

-- Tools table
CREATE TABLE tools (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  slug TEXT UNIQUE NOT NULL,
  name TEXT NOT NULL,
  url TEXT,
  github_url TEXT,
  categories TEXT[] DEFAULT '{}',
  description TEXT,
  
  -- Auto-populated from GitHub API
  github_stars INT,
  github_last_commit TIMESTAMPTZ,
  github_open_issues INT,
  github_license TEXT,
  
  -- Source tracking
  first_seen TIMESTAMPTZ DEFAULT now(),
  source TEXT,  -- 'manual', 'channel-import', 'harvested'
  source_context JSONB DEFAULT '{}',
  
  -- Metadata
  created_by UUID REFERENCES users(id),
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

-- Evaluations table
CREATE TABLE evaluations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tool_id UUID REFERENCES tools(id) ON DELETE CASCADE,
  evaluator_id UUID REFERENCES users(id),
  
  -- Structured assessment
  works BOOLEAN,
  actively_maintained BOOLEAN,
  verdict TEXT CHECK (verdict IN ('essential', 'solid', 'situational', 'caution', 'avoid')),
  security_notes TEXT,
  notes TEXT,
  
  -- Community tags
  communities TEXT[] DEFAULT '{}',
  
  -- Metadata
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now(),
  
  -- One evaluation per user per tool
  UNIQUE(tool_id, evaluator_id)
);

-- External links (blog posts, videos, discussions)
CREATE TABLE links (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tool_id UUID REFERENCES tools(id) ON DELETE CASCADE,
  submitted_by UUID REFERENCES users(id),
  
  url TEXT NOT NULL,
  title TEXT,
  link_type TEXT CHECK (link_type IN ('blog', 'video', 'discussion', 'docs', 'tutorial', 'review', 'other')),
  snippet TEXT,  -- Pull quote or summary
  
  created_at TIMESTAMPTZ DEFAULT now(),
  
  -- Prevent duplicate links
  UNIQUE(tool_id, url)
);

-- Import batches (track where data came from)
CREATE TABLE import_batches (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  source_type TEXT NOT NULL,  -- 'slack', 'whatsapp', 'discord', 'awesome-list', 'manual'
  source_name TEXT,           -- Channel name, list URL, etc
  imported_by UUID REFERENCES users(id),
  tool_count INT DEFAULT 0,
  raw_data JSONB,             -- Sanitized import data for reference
  created_at TIMESTAMPTZ DEFAULT now()
);

-- Tool mentions from imports (preserves context)
CREATE TABLE tool_mentions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tool_id UUID REFERENCES tools(id) ON DELETE CASCADE,
  import_batch_id UUID REFERENCES import_batches(id) ON DELETE CASCADE,
  
  mention_date TIMESTAMPTZ,
  context_snippet TEXT,       -- Sanitized discussion snippet
  sentiment TEXT,             -- 'positive', 'negative', 'neutral', 'question'
  
  created_at TIMESTAMPTZ DEFAULT now()
);

-- Categories (for reference and validation)
CREATE TABLE categories (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  slug TEXT UNIQUE NOT NULL,
  name TEXT NOT NULL,
  description TEXT,
  parent_slug TEXT REFERENCES categories(slug),
  created_at TIMESTAMPTZ DEFAULT now()
);

-- Seed categories
INSERT INTO categories (slug, name, description) VALUES
  ('agent-framework', 'Agent Frameworks', 'Libraries and frameworks for building AI agents'),
  ('editor', 'Editors & IDEs', 'AI-powered code editors and IDE plugins'),
  ('cli', 'CLI Tools', 'Command-line AI tools'),
  ('library', 'Libraries', 'AI/ML libraries and SDKs'),
  ('mcp-server', 'MCP Servers', 'Model Context Protocol servers'),
  ('orchestration', 'Orchestration', 'Multi-agent and workflow orchestration'),
  ('coding-assistant', 'Coding Assistants', 'AI pair programming tools'),
  ('code-review', 'Code Review', 'AI-powered code review tools'),
  ('testing', 'Testing', 'AI-assisted testing tools'),
  ('documentation', 'Documentation', 'AI documentation generators'),
  ('research', 'Research Tools', 'AI research and paper tools'),
  ('infrastructure', 'Infrastructure', 'AI infrastructure and deployment'),
  ('paper', 'Papers', 'Research papers and publications'),
  ('app', 'Applications', 'End-user AI applications');

-- Indexes for common queries
CREATE INDEX idx_tools_slug ON tools(slug);
CREATE INDEX idx_tools_categories ON tools USING GIN(categories);
CREATE INDEX idx_tools_github_stars ON tools(github_stars DESC NULLS LAST);
CREATE INDEX idx_tools_created_at ON tools(created_at DESC);
CREATE INDEX idx_evaluations_tool_id ON evaluations(tool_id);
CREATE INDEX idx_evaluations_verdict ON evaluations(verdict);
CREATE INDEX idx_links_tool_id ON links(tool_id);
CREATE INDEX idx_tool_mentions_tool_id ON tool_mentions(tool_id);

-- Updated_at trigger function
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply updated_at triggers
CREATE TRIGGER update_tools_updated_at
  BEFORE UPDATE ON tools
  FOR EACH ROW
  EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_evaluations_updated_at
  BEFORE UPDATE ON evaluations
  FOR EACH ROW
  EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_users_updated_at
  BEFORE UPDATE ON users
  FOR EACH ROW
  EXECUTE FUNCTION update_updated_at_column();

-- Row Level Security (RLS)
ALTER TABLE tools ENABLE ROW LEVEL SECURITY;
ALTER TABLE evaluations ENABLE ROW LEVEL SECURITY;
ALTER TABLE links ENABLE ROW LEVEL SECURITY;
ALTER TABLE users ENABLE ROW LEVEL SECURITY;

-- Public read access for tools, evaluations, links
CREATE POLICY "Tools are viewable by everyone" ON tools
  FOR SELECT USING (true);

CREATE POLICY "Evaluations are viewable by everyone" ON evaluations
  FOR SELECT USING (true);

CREATE POLICY "Links are viewable by everyone" ON links
  FOR SELECT USING (true);

-- Authenticated users can insert
CREATE POLICY "Authenticated users can add tools" ON tools
  FOR INSERT WITH CHECK (auth.role() = 'authenticated');

CREATE POLICY "Authenticated users can add evaluations" ON evaluations
  FOR INSERT WITH CHECK (auth.role() = 'authenticated');

CREATE POLICY "Authenticated users can add links" ON links
  FOR INSERT WITH CHECK (auth.role() = 'authenticated');

-- Users can update their own evaluations
CREATE POLICY "Users can update own evaluations" ON evaluations
  FOR UPDATE USING (auth.uid() = evaluator_id);

-- Admins can do everything
CREATE POLICY "Admins have full access to tools" ON tools
  FOR ALL USING (
    EXISTS (SELECT 1 FROM users WHERE id = auth.uid() AND is_admin = true)
  );

CREATE POLICY "Admins have full access to evaluations" ON evaluations
  FOR ALL USING (
    EXISTS (SELECT 1 FROM users WHERE id = auth.uid() AND is_admin = true)
  );

CREATE POLICY "Admins have full access to links" ON links
  FOR ALL USING (
    EXISTS (SELECT 1 FROM users WHERE id = auth.uid() AND is_admin = true)
  );

-- Users can read their own profile
CREATE POLICY "Users can view own profile" ON users
  FOR SELECT USING (auth.uid() = id);

-- Public can view basic user info (for attribution)
CREATE POLICY "Public can view user display names" ON users
  FOR SELECT USING (true);

COMMENT ON TABLE tools IS 'AI tools catalog with metadata and GitHub stats';
COMMENT ON TABLE evaluations IS 'User evaluations of tools with structured verdicts';
COMMENT ON TABLE links IS 'External resources linked to tools (blogs, videos, docs)';
COMMENT ON TABLE import_batches IS 'Tracks bulk imports from channels and lists';
COMMENT ON TABLE tool_mentions IS 'Preserves sanitized discussion context from imports';
