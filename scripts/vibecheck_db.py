#!/usr/bin/env python3
"""
Vibecheck Database Helper

Direct PostgreSQL access to Supabase via kura (age-encrypted secrets).
No need to use the Supabase dashboard SQL editor.

Usage:
    # Interactive SQL
    uv run python scripts/vibecheck_db.py "SELECT * FROM tools LIMIT 5"
    
    # Quick stats
    uv run python scripts/vibecheck_db.py
    
    # From Python
    from vibecheck_db import get_connection, run_sql
    conn = get_connection()
    results = run_sql("SELECT COUNT(*) FROM tools")
"""
import sys
from pathlib import Path

# Add src to path for kura import
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import psycopg2
from vibecheck.kura import get_secret


def get_connection():
    """Get a PostgreSQL connection to vibecheck database."""
    return psycopg2.connect(
        host="db.pycvrvounfzlrwjdmuij.supabase.co",
        port=5432,
        database="postgres",
        user="postgres",
        password=get_secret("SUPABASE_DB_PASSWORD"),
        sslmode="require"
    )


def run_sql(sql: str, params: tuple = None, fetch: bool = True) -> list:
    """Run SQL and return results."""
    conn = get_connection()
    conn.autocommit = True
    cur = conn.cursor()
    
    cur.execute(sql, params)
    
    if fetch and cur.description:
        columns = [desc[0] for desc in cur.description]
        rows = cur.fetchall()
        results = [dict(zip(columns, row)) for row in rows]
    else:
        results = []
    
    cur.close()
    conn.close()
    return results


def print_results(results: list, max_width: int = 50):
    """Pretty print query results."""
    if not results:
        print("(no results)")
        return
    
    # Get column widths
    columns = list(results[0].keys())
    widths = {col: min(max(len(str(col)), max(len(str(r.get(col, ''))) for r in results)), max_width) 
              for col in columns}
    
    # Header
    header = " | ".join(str(col).ljust(widths[col])[:widths[col]] for col in columns)
    print(header)
    print("-" * len(header))
    
    # Rows
    for row in results:
        line = " | ".join(str(row.get(col, '')).ljust(widths[col])[:widths[col]] for col in columns)
        print(line)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        print("\nQuick stats:")
        for table in ['tools', 'communities', 'tool_mentions', 'evaluations', 'articles']:
            try:
                results = run_sql(f"SELECT COUNT(*) as count FROM {table}")
                print(f"  {table}: {results[0]['count']}")
            except Exception as e:
                print(f"  {table}: (error: {e})")
    else:
        sql = " ".join(sys.argv[1:])
        try:
            results = run_sql(sql)
            print_results(results)
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)
