-- Communities as first-class entities
-- Tracks which communities have discussed/endorsed tools

CREATE TABLE communities (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  slug TEXT UNIQUE NOT NULL,           -- "agi", "henkaku", "dg"
  name TEXT NOT NULL,                   -- "AGI", "Henkaku", "DG"
  description TEXT,
  url TEXT,                             -- Link to community (Slack, Discord, etc)
  is_private BOOLEAN DEFAULT true,      -- Private communities don't show member details
  created_at TIMESTAMPTZ DEFAULT now()
);

-- Seed initial communities
INSERT INTO communities (slug, name, description, is_private) VALUES
  ('agi', 'AGI', 'AGI community discussions', true),
  ('henkaku', 'Henkaku', 'Henkaku community', true),
  ('dg', 'DG', 'Digital Garage community', true);

-- Junction table: which tools are discussed in which communities
CREATE TABLE tool_communities (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  tool_id UUID REFERENCES tools(id) ON DELETE CASCADE,
  community_id UUID REFERENCES communities(id) ON DELETE CASCADE,
  first_mentioned TIMESTAMPTZ DEFAULT now(),
  mention_count INT DEFAULT 1,
  sentiment_summary TEXT,               -- "mostly positive", "mixed", etc
  created_at TIMESTAMPTZ DEFAULT now(),
  
  UNIQUE(tool_id, community_id)
);

-- Add index for lookups
CREATE INDEX idx_tool_communities_tool ON tool_communities(tool_id);
CREATE INDEX idx_tool_communities_community ON tool_communities(community_id);

-- Update tool_mentions to reference community
ALTER TABLE tool_mentions 
  ADD COLUMN community_id UUID REFERENCES communities(id);

CREATE INDEX idx_tool_mentions_community ON tool_mentions(community_id);

-- RLS for communities
ALTER TABLE communities ENABLE ROW LEVEL SECURITY;
ALTER TABLE tool_communities ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Communities are viewable by everyone" ON communities
  FOR SELECT USING (true);

CREATE POLICY "Tool communities are viewable by everyone" ON tool_communities
  FOR SELECT USING (true);

CREATE POLICY "Admins can manage communities" ON communities
  FOR ALL USING (
    EXISTS (SELECT 1 FROM users WHERE id = auth.uid() AND is_admin = true)
  );

CREATE POLICY "Admins can manage tool_communities" ON tool_communities
  FOR ALL USING (
    EXISTS (SELECT 1 FROM users WHERE id = auth.uid() AND is_admin = true)
  );

COMMENT ON TABLE communities IS 'Communities where tools are discussed (AGI, Henkaku, DG, etc)';
COMMENT ON TABLE tool_communities IS 'Junction table tracking which tools are discussed in which communities';
