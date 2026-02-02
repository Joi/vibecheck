# Vibecheck Development Workflow

## Schema Management

### Golden Rule
**The database schema is the source of truth.** Models in code must match the database, not the other way around.

### Tools

| Tool | Purpose |
|------|---------|
| `supabase db pull` | Pull current schema from production |
| `supabase migration list` | Check migration sync status |
| `supabase db push` | Apply local migrations to production |
| `scripts/schema_check.py` | Compare code models vs database |
| `scripts/vibecheck_db.py` | Direct SQL access via kura |

### Before Making Model Changes

1. **Check current schema**:
   ```bash
   uv run python scripts/schema_check.py
   ```

2. **If adding a field to a model**, ask:
   - Does this column exist in the database? Check with `schema_check.py`
   - If NO: Create a migration first
   - If YES: Safe to add to model

3. **If adding a relationship**, ask:
   - Is there a foreign key in the database?
   - PostgREST relationships are based on FKs, not code

### Creating Migrations

```bash
# Create a new migration
supabase migration new my_feature_name

# Edit the migration file in supabase/migrations/

# Apply to production
supabase db push
```

### Schema Check Script

Run before commits to catch mismatches:

```bash
uv run python scripts/schema_check.py
```

This compares:
- Pydantic model fields vs database columns
- Required fields vs nullable columns
- Types (rough check)

## Secret Management

### Use Kura (Age-Encrypted)

All secrets are stored in `~/dotfiles-private/amplifier-secrets.env.age` and accessed via kura.

**Never use:**
- `op` (1Password CLI) - removed from codebase
- Hardcoded secrets
- Environment variables in git

**Do use:**
```python
from vibecheck.kura import get_secret
password = get_secret("SUPABASE_DB_PASSWORD")
```

### Adding New Secrets

```bash
# Decrypt
age -d -i ~/.config/age/secrets.key ~/dotfiles-private/amplifier-secrets.env.age > /tmp/secrets.env

# Edit
echo "NEW_SECRET=value" >> /tmp/secrets.env

# Re-encrypt (use your public key)
age -r $(age-keygen -y ~/.config/age/secrets.key) -o ~/dotfiles-private/amplifier-secrets.env.age /tmp/secrets.env

# Secure delete
rm -P /tmp/secrets.env

# Commit
cd ~/dotfiles-private && git add -A && git commit -m "Add NEW_SECRET" && git push
```

## Local Development

### Running the API

```bash
cd ~/vibecheck
uv run uvicorn vibecheck.api:app --reload --port 8000
```

### Testing Database Operations

```bash
# Quick stats
uv run python scripts/vibecheck_db.py

# Run SQL
uv run python scripts/vibecheck_db.py "SELECT * FROM tools LIMIT 5"
```

### Schema Comparison

```bash
uv run python scripts/schema_check.py
```

## Deployment

### Vercel (API)

```bash
cd ~/vibecheck
vercel --prod --yes
```

Automatically triggered on push to main.

### Supabase (Database)

```bash
# Check migration status
supabase migration list

# Apply pending migrations
supabase db push
```

## Common Issues

### "Could not find column X in schema cache"

**Cause:** Model has a field that doesn't exist in database.

**Fix:**
1. Run `scripts/schema_check.py` to identify mismatch
2. Either remove field from model OR create migration to add column

### "duplicate key" errors

**Cause:** Trying to insert a row that already exists.

**Fix:** Check for existing record before insert, or use upsert.

### Supabase CLI timeout

**Cause:** Network issues or long-running migrations.

**Fix:** Use `scripts/vibecheck_db.py` for direct access:
```bash
uv run python scripts/vibecheck_db.py "YOUR SQL HERE"
```

## Architecture Notes

### Tables

| Table | Purpose |
|-------|---------|
| `tools` | Core tool records |
| `communities` | Community definitions (agi, henkaku, etc.) |
| `tool_communities` | Join table: which tools are in which communities |
| `tool_mentions` | Individual mentions with timestamps |
| `evaluations` | User evaluations of tools |
| `links` | External links for tools |
| `articles` | Research articles about AI tools |

### Key Relationships

```
tools 1--* tool_communities *--1 communities
tools 1--* tool_mentions *--1 communities
tools 1--* evaluations
tools 1--* links
```

**Important:** There is NO direct FK from `tools` to `communities`. The relationship goes through `tool_communities`.
