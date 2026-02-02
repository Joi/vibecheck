#!/usr/bin/env python3
"""
Schema Check - Compare Pydantic models against database schema.

Catches mismatches like:
- Model fields that don't exist in database
- Required fields that are nullable in database
- Missing model fields for database columns

Usage:
    uv run python scripts/schema_check.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from vibecheck.kura import get_secret
import psycopg2


def get_db_schema() -> dict[str, dict]:
    """Get schema for all tables from database."""
    conn = psycopg2.connect(
        host="db.pycvrvounfzlrwjdmuij.supabase.co",
        port=5432,
        database="postgres",
        user="postgres",
        password=get_secret("SUPABASE_DB_PASSWORD"),
        sslmode="require"
    )
    cur = conn.cursor()
    
    # Get all tables
    cur.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public' 
        AND table_type = 'BASE TABLE'
    """)
    tables = [row[0] for row in cur.fetchall()]
    
    schema = {}
    for table in tables:
        cur.execute("""
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns 
            WHERE table_name = %s AND table_schema = 'public'
            ORDER BY ordinal_position
        """, (table,))
        
        schema[table] = {
            row[0]: {
                "type": row[1],
                "nullable": row[2] == "YES",
                "has_default": row[3] is not None
            }
            for row in cur.fetchall()
        }
    
    conn.close()
    return schema


def get_model_fields() -> dict[str, dict]:
    """Get fields from Pydantic models."""
    from vibecheck.models import (
        ToolCreate, ToolUpdate, ToolResponse,
        EvaluationCreate, LinkCreate,
        ArticleCreate
    )
    
    models = {
        "tools": {
            "create": ToolCreate,
            "update": ToolUpdate,
            "response": ToolResponse,
        },
        "articles": {
            "create": ArticleCreate,
        },
    }
    
    result = {}
    for table, model_set in models.items():
        result[table] = {}
        for model_type, model_class in model_set.items():
            fields = {}
            for name, field_info in model_class.model_fields.items():
                fields[name] = {
                    "required": field_info.is_required(),
                    "has_default": field_info.default is not None or field_info.default_factory is not None,
                }
            result[table][model_type] = fields
    
    return result


def check_schema():
    """Compare models against database schema."""
    print("Fetching database schema...")
    db_schema = get_db_schema()
    
    print("Analyzing Pydantic models...")
    model_fields = get_model_fields()
    
    issues = []
    warnings = []
    
    for table, model_set in model_fields.items():
        if table not in db_schema:
            issues.append(f"❌ Table '{table}' not found in database")
            continue
        
        db_columns = db_schema[table]
        
        for model_type, fields in model_set.items():
            print(f"\nChecking {table}.{model_type}...")
            
            for field_name, field_info in fields.items():
                # Skip internal fields
                if field_name in ("id", "created_at", "updated_at"):
                    continue
                
                if field_name not in db_columns:
                    # This is the critical check - field in model but not in DB
                    if model_type == "create":
                        issues.append(
                            f"❌ {table}.{model_type}.{field_name}: "
                            f"Field exists in CREATE model but NOT in database! "
                            f"This will cause insert failures."
                        )
                    elif model_type == "response":
                        warnings.append(
                            f"⚠️  {table}.{model_type}.{field_name}: "
                            f"Field in response model but not in DB. "
                            f"Make sure it's added manually in API code."
                        )
                else:
                    # Field exists in both - check nullability
                    db_col = db_columns[field_name]
                    if field_info["required"] and db_col["nullable"] and not db_col["has_default"]:
                        warnings.append(
                            f"⚠️  {table}.{model_type}.{field_name}: "
                            f"Required in model but nullable in DB without default"
                        )
    
    # Print results
    print("\n" + "=" * 60)
    print("SCHEMA CHECK RESULTS")
    print("=" * 60)
    
    if issues:
        print("\n🚨 CRITICAL ISSUES (will cause runtime errors):\n")
        for issue in issues:
            print(f"  {issue}")
    
    if warnings:
        print("\n⚠️  WARNINGS (may cause issues):\n")
        for warning in warnings:
            print(f"  {warning}")
    
    if not issues and not warnings:
        print("\n✅ All model fields match database schema!")
    
    print("\n" + "=" * 60)
    
    # Print database schema summary
    print("\nDATABASE TABLES:")
    for table, columns in sorted(db_schema.items()):
        print(f"\n  {table}:")
        for col, info in columns.items():
            nullable = "NULL" if info["nullable"] else "NOT NULL"
            print(f"    {col}: {info['type']} {nullable}")
    
    return len(issues) == 0


if __name__ == "__main__":
    success = check_schema()
    sys.exit(0 if success else 1)
