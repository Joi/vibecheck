-- Security fix: Enable RLS on tables flagged by Supabase security advisor
-- Tables: categories, import_batches, tool_mentions

-- 1. categories table
-- Reference data, public read, admin write
ALTER TABLE categories ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Categories are viewable by everyone" ON categories
  FOR SELECT USING (true);

CREATE POLICY "Admins can manage categories" ON categories
  FOR ALL USING (
    EXISTS (SELECT 1 FROM users WHERE id = auth.uid() AND is_admin = true)
  );

-- 2. import_batches table
-- Admin-only data (tracks bulk imports)
ALTER TABLE import_batches ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Import batches are viewable by everyone" ON import_batches
  FOR SELECT USING (true);

CREATE POLICY "Admins can manage import_batches" ON import_batches
  FOR ALL USING (
    EXISTS (SELECT 1 FROM users WHERE id = auth.uid() AND is_admin = true)
  );

-- 3. tool_mentions table
-- Already has an anon INSERT policy; enable RLS and add SELECT
ALTER TABLE tool_mentions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Tool mentions are viewable by everyone" ON tool_mentions
  FOR SELECT USING (true);

CREATE POLICY "Admins can manage tool_mentions" ON tool_mentions
  FOR ALL USING (
    EXISTS (SELECT 1 FROM users WHERE id = auth.uid() AND is_admin = true)
  );
