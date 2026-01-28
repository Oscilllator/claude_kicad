#!/usr/bin/env python3
"""
JLCPCB Parts Database Query Tool

Queries the JLCPCB parts database (SQLite FTS5) for finding components.
Outputs JSON to stdout.

Usage:
    python3 jlcpcb_parts_query.py --search "esp32 module" --in-stock --limit 10

Example:
    python3 jlcpcb_parts_query.py -s "0805 capacitor 100nF" --basic-only -l 5
"""

import argparse
import contextlib
import json
import os
import re
import sqlite3
import sys
from pathlib import Path
from zipfile import ZipFile


# Database locations
PRIMARY_DB_PATH = os.path.expanduser(
    "~/.local/share/kicad/7.0/scripting/plugins/kicad-jlcpcb-tools/jlcpcb/parts-fts5.db"
)
FALLBACK_DB_DIR = "/tmp/jlcpcb-parts"
FALLBACK_DB_PATH = os.path.join(FALLBACK_DB_DIR, "parts-fts5.db")

# Download source
DOWNLOAD_URL_BASE = "https://bouni.github.io/kicad-jlcpcb-tools/"
CHUNK_COUNT_FILE = "chunk_num_fts5.txt"
CHUNK_FILE_STUB = "parts-fts5.db.zip."


def find_database() -> str | None:
    """Find the parts database, checking primary then fallback locations."""
    if os.path.isfile(PRIMARY_DB_PATH) and os.path.getsize(PRIMARY_DB_PATH) > 0:
        return PRIMARY_DB_PATH
    if os.path.isfile(FALLBACK_DB_PATH) and os.path.getsize(FALLBACK_DB_PATH) > 0:
        return FALLBACK_DB_PATH
    return None


def download_database() -> str:
    """Download the parts database chunks, combine, and extract to fallback location."""
    try:
        import requests
    except ImportError:
        raise RuntimeError(
            "requests library required for database download. Install with: pip install requests"
        )

    # Create fallback directory
    Path(FALLBACK_DB_DIR).mkdir(parents=True, exist_ok=True)

    # Get chunk count
    print("Fetching database chunk count...", file=sys.stderr)
    r = requests.get(DOWNLOAD_URL_BASE + CHUNK_COUNT_FILE, timeout=60)
    r.raise_for_status()
    chunk_count = int(r.text.strip())
    print(f"Database split into {chunk_count} chunks", file=sys.stderr)

    # Download all chunks
    for i in range(chunk_count):
        chunk_file = f"{CHUNK_FILE_STUB}{i+1:03}"
        chunk_path = os.path.join(FALLBACK_DB_DIR, chunk_file)
        print(f"Downloading chunk {i+1}/{chunk_count}...", file=sys.stderr)
        r = requests.get(DOWNLOAD_URL_BASE + chunk_file, timeout=300)
        r.raise_for_status()
        with open(chunk_path, "wb") as f:
            f.write(r.content)

    # Combine chunks into single zip
    db_zip_file = os.path.join(FALLBACK_DB_DIR, "parts-fts5.db.zip")
    print("Combining chunks...", file=sys.stderr)
    with open(db_zip_file, "wb") as db:
        split_files = [
            f for f in os.listdir(FALLBACK_DB_DIR)
            if f.startswith(CHUNK_FILE_STUB)
        ]
        split_files.sort(key=lambda f: int(f.split(".")[-1]))
        for split_file_name in split_files:
            split_path = os.path.join(FALLBACK_DB_DIR, split_file_name)
            with open(split_path, "rb") as split_file:
                while file_data := split_file.read(1024 * 1024):
                    db.write(file_data)
            os.unlink(split_path)

    # Extract zip
    print("Extracting database...", file=sys.stderr)
    with ZipFile(db_zip_file, "r") as zf:
        zf.extractall(FALLBACK_DB_DIR)
    os.unlink(db_zip_file)

    print("Database download complete.", file=sys.stderr)
    return FALLBACK_DB_PATH


def sanitize_fts5_term(term: str) -> str:
    """Escape special FTS5 characters in a search term."""
    # FTS5 special characters that need escaping
    special_chars = r'["\*\-\+\(\)\:\^\~]'
    # Escape by wrapping in double quotes if needed
    if re.search(special_chars, term):
        # Escape internal quotes by doubling them
        return '"' + term.replace('"', '""') + '"'
    return term


def build_search_query(
    search: str | None = None,
    category: str | None = None,
    package: str | None = None,
    manufacturer: str | None = None,
    in_stock: bool = False,
    basic_only: bool = False,
    limit: int = 20,
) -> tuple[str, list]:
    """Build the FTS5 search query."""
    columns = [
        '"LCSC Part"',
        '"First Category"',
        '"Second Category"',
        '"MFR.Part"',
        '"Package"',
        '"Solder Joint"',
        '"Manufacturer"',
        '"Library Type"',
        '"Description"',
        '"Datasheet"',
        '"Price"',
        '"Stock"',
    ]

    select_clause = f"SELECT {', '.join(columns)} FROM parts WHERE "

    match_chunks = []
    like_chunks = []
    where_chunks = []

    # Process free-text search
    if search:
        keywords = search.split()
        for word in keywords:
            if not word:
                continue
            sanitized = sanitize_fts5_term(word)
            if len(word) >= 3:
                # FTS5 can match terms >= 3 chars with trigram tokenizer
                match_chunks.append(f'"{sanitized}"')
            else:
                # Use LIKE for shorter terms
                like_chunks.append(f'"Description" LIKE \'%{word}%\'')

    # Column-specific filters use FTS5 column syntax
    if category:
        match_chunks.append(f'"First Category":"{sanitize_fts5_term(category)}"')
    if package:
        match_chunks.append(f'"Package":"{sanitize_fts5_term(package)}"')
    if manufacturer:
        match_chunks.append(f'"Manufacturer":"{sanitize_fts5_term(manufacturer)}"')

    # Stock and Library Type are unindexed, use WHERE clauses
    if in_stock:
        where_chunks.append('CAST("Stock" AS INTEGER) > 0')
    if basic_only:
        where_chunks.append('"Library Type" = \'Basic\'')

    # Build the query
    query_parts = []

    if match_chunks:
        query_parts.append("parts MATCH '" + " AND ".join(match_chunks) + "'")

    if like_chunks:
        query_parts.extend(like_chunks)

    if where_chunks:
        query_parts.extend(where_chunks)

    if not query_parts:
        # No search criteria provided
        return select_clause + "1=0", []

    query = select_clause + " AND ".join(query_parts)
    query += f" LIMIT {limit}"

    return query, []


def parse_price_tiers(price_str: str) -> list[dict]:
    """Parse price string into structured price tiers."""
    if not price_str:
        return []

    tiers = []
    # Price format is typically: "1-9:0.0234,10-29:0.0195,..."
    for tier in price_str.split(","):
        tier = tier.strip()
        if not tier or ":" not in tier:
            continue
        try:
            qty_range, price = tier.split(":")
            if "-" in qty_range:
                min_qty, max_qty = qty_range.split("-")
                tiers.append({
                    "min_qty": int(min_qty),
                    "max_qty": int(max_qty) if max_qty else None,
                    "unit_price": float(price),
                })
            else:
                tiers.append({
                    "min_qty": int(qty_range),
                    "max_qty": None,
                    "unit_price": float(price),
                })
        except (ValueError, IndexError):
            continue

    return tiers


def search_parts(
    db_path: str,
    search: str | None = None,
    category: str | None = None,
    package: str | None = None,
    manufacturer: str | None = None,
    in_stock: bool = False,
    basic_only: bool = False,
    limit: int = 20,
) -> dict:
    """Execute the search query and return results as JSON-serializable dict."""
    query, params = build_search_query(
        search=search,
        category=category,
        package=package,
        manufacturer=manufacturer,
        in_stock=in_stock,
        basic_only=basic_only,
        limit=limit,
    )

    results = []
    with contextlib.closing(sqlite3.connect(db_path)) as con:
        con.row_factory = sqlite3.Row
        cur = con.cursor()
        try:
            cur.execute(query, params)
            rows = cur.fetchall()
        except sqlite3.OperationalError as e:
            return {"error": str(e), "query": query, "results": [], "count": 0}

        for row in rows:
            # Parse stock as integer
            try:
                stock = int(row["Stock"]) if row["Stock"] else 0
            except (ValueError, TypeError):
                stock = 0

            results.append({
                "lcsc": row["LCSC Part"],
                "first_category": row["First Category"],
                "second_category": row["Second Category"],
                "mfr_part": row["MFR.Part"],
                "package": row["Package"],
                "solder_joints": row["Solder Joint"],
                "manufacturer": row["Manufacturer"],
                "library_type": row["Library Type"],
                "description": row["Description"],
                "datasheet": row["Datasheet"],
                "price_tiers": parse_price_tiers(row["Price"]),
                "stock": stock,
            })

    return {
        "results": results,
        "count": len(results),
    }


def main():
    parser = argparse.ArgumentParser(
        description="Query the JLCPCB parts database"
    )
    parser.add_argument(
        "--search", "-s",
        help="Free text search (e.g., 'esp32 module')"
    )
    parser.add_argument(
        "--category", "-c",
        help="Filter by first category"
    )
    parser.add_argument(
        "--package", "-p",
        help="Filter by package type"
    )
    parser.add_argument(
        "--manufacturer", "-m",
        help="Filter by manufacturer"
    )
    parser.add_argument(
        "--in-stock",
        action="store_true",
        help="Only show parts with stock > 0"
    )
    parser.add_argument(
        "--basic-only",
        action="store_true",
        help="Only show 'Basic' library type parts"
    )
    parser.add_argument(
        "--limit", "-l",
        type=int,
        default=20,
        help="Maximum number of results (default: 20)"
    )
    parser.add_argument(
        "--download",
        action="store_true",
        help="Download the database if not found"
    )

    args = parser.parse_args()

    # Find or download database
    db_path = find_database()
    if not db_path:
        if args.download:
            try:
                db_path = download_database()
            except Exception as e:
                print(json.dumps({"error": f"Failed to download database: {e}"}))
                sys.exit(1)
        else:
            print(json.dumps({
                "error": "Database not found",
                "hint": "Use --download to fetch the database, or ensure the kicad-jlcpcb-tools plugin is installed"
            }))
            sys.exit(1)

    # Check that at least one search criteria is provided
    if not any([args.search, args.category, args.package, args.manufacturer]):
        print(json.dumps({
            "error": "At least one search criteria required",
            "hint": "Use --search, --category, --package, or --manufacturer"
        }))
        sys.exit(1)

    # Execute search
    result = search_parts(
        db_path=db_path,
        search=args.search,
        category=args.category,
        package=args.package,
        manufacturer=args.manufacturer,
        in_stock=args.in_stock,
        basic_only=args.basic_only,
        limit=args.limit,
    )

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
