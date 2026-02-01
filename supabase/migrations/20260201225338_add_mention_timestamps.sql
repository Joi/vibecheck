-- Track individual mention timestamps for tools in communities
-- Each row = one mention of a tool in a community at a specific time

-- Ensure tool_mentions has all needed fields
ALTER TABLE tool_mentions 
  ADD COLUMN IF NOT EXISTS mentioned_at TIMESTAMPTZ DEFAULT now();

-- Create index for time-based queries
CREATE INDEX IF NOT EXISTS idx_tool_mentions_mentioned_at ON tool_mentions(mentioned_at);
CREATE INDEX IF NOT EXISTS idx_tool_mentions_tool_community ON tool_mentions(tool_id, community_id);

-- View for easy querying of tool mention history
CREATE OR REPLACE VIEW tool_mention_history AS
SELECT 
  tm.id,
  tm.tool_id,
  t.slug as tool_slug,
  t.name as tool_name,
  tm.community_id,
  c.slug as community_slug,
  c.name as community_name,
  tm.mentioned_at,
  tm.context_snippet,
  tm.sentiment
FROM tool_mentions tm
JOIN tools t ON tm.tool_id = t.id
LEFT JOIN communities c ON tm.community_id = c.id
ORDER BY tm.mentioned_at DESC;

COMMENT ON VIEW tool_mention_history IS 'Tool mentions with community and timestamp info';
COMMENT ON COLUMN tool_mentions.mentioned_at IS 'When the tool was mentioned in the community';
