#!/usr/bin/env python3
"""
MinerU processing registry using DuckDB.

Tracks the status of PDF processing through MinerU, including:
- Which PDFs have been processed
- Success/failure status
- Processing times
- Output file paths

Usage:
    # Scan directory for new PDFs and add to registry
    python mineru_registry.py scan-pdfs --pdf-dir /path/to/pdfs

    # Initialize from manifest (alternative to scan-pdfs)
    python mineru_registry.py init --manifest /path/to/manifest.csv

    # Check status
    python mineru_registry.py status

    # Update from results
    python mineru_registry.py update --results /path/to/results.csv

    # Export pending PDFs
    python mineru_registry.py export-pending -o pending.csv

    # Mark failed PDFs for retry
    python mineru_registry.py retry-failed

    # Scan output directory and mark completed
    python mineru_registry.py scan-outputs --output-dir /path/to/outputs
"""

import argparse
import csv
import sys
from datetime import datetime
from pathlib import Path

try:
    import duckdb
except ImportError:
    print("Error: duckdb not installed. Run: pip install duckdb")
    sys.exit(1)


DEFAULT_DB_PATH = Path("/data/NIMH_scratch/adamt/osm/datalad-osm/duckdbs/mineru_registry.duckdb")


def get_db(db_path: Path) -> duckdb.DuckDBPyConnection:
    """Get database connection."""
    return duckdb.connect(str(db_path))


def init_schema(conn: duckdb.DuckDBPyConnection):
    """Create the database schema."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS mineru_status (
            pmid VARCHAR PRIMARY KEY,
            pdf_path VARCHAR,
            json_path VARCHAR,
            md_path VARCHAR,
            status VARCHAR DEFAULT 'pending',
            error_msg VARCHAR,
            processing_time FLOAT,
            file_size BIGINT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Create indexes for common queries
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_status ON mineru_status(status)
    """)

    # Add file_size column if it doesn't exist (for existing databases)
    try:
        conn.execute("ALTER TABLE mineru_status ADD COLUMN file_size BIGINT")
    except duckdb.CatalogException:
        pass  # Column already exists


def cmd_init(args):
    """Initialize registry from manifest CSV."""
    db_path = Path(args.db)
    manifest_path = Path(args.manifest)

    if not manifest_path.exists():
        print(f"Error: Manifest not found: {manifest_path}")
        return 1

    # Create database directory if needed
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = get_db(db_path)
    init_schema(conn)

    # Load manifest
    print(f"Loading manifest: {manifest_path}")

    # Count existing entries
    existing_count = conn.execute("SELECT COUNT(*) FROM mineru_status").fetchone()[0]

    # Read manifest and insert
    inserted = 0
    skipped = 0

    with open(manifest_path, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        for row in reader:
            # Normalize keys
            normalized = {k.lower().strip(): v for k, v in row.items()}
            pmid = normalized.get("pmid", "").strip()
            pdf_path = normalized.get("pdf_path", "").strip()

            if not pmid or not pdf_path:
                continue

            try:
                conn.execute("""
                    INSERT INTO mineru_status (pmid, pdf_path, status, created_at)
                    VALUES (?, ?, 'pending', CURRENT_TIMESTAMP)
                    ON CONFLICT (pmid) DO NOTHING
                """, [pmid, pdf_path])
                inserted += 1
            except duckdb.ConstraintException:
                skipped += 1

    conn.commit()

    total = conn.execute("SELECT COUNT(*) FROM mineru_status").fetchone()[0]
    new_entries = total - existing_count

    print(f"Initialized registry: {db_path}")
    print(f"  New entries: {new_entries}")
    print(f"  Total entries: {total}")

    conn.close()
    return 0


def cmd_status(args):
    """Show registry status summary."""
    db_path = Path(args.db)

    if not db_path.exists():
        print(f"Error: Registry not found: {db_path}")
        print("Run 'init' first to create the registry.")
        return 1

    conn = get_db(db_path)

    # Get counts by status
    status_counts = conn.execute("""
        SELECT status, COUNT(*) as count
        FROM mineru_status
        GROUP BY status
        ORDER BY status
    """).fetchall()

    total = sum(row[1] for row in status_counts)

    print(f"Registry: {db_path}")
    print("-" * 40)
    print(f"{'Status':<15} {'Count':>10} {'Percent':>10}")
    print("-" * 40)

    for status, count in status_counts:
        pct = (count / total * 100) if total > 0 else 0
        print(f"{status:<15} {count:>10} {pct:>9.1f}%")

    print("-" * 40)
    print(f"{'Total':<15} {total:>10}")

    # Show average processing time for completed
    avg_time = conn.execute("""
        SELECT AVG(processing_time)
        FROM mineru_status
        WHERE status = 'completed' AND processing_time IS NOT NULL
    """).fetchone()[0]

    if avg_time:
        print(f"\nAverage processing time: {avg_time:.1f}s")

    # Show recent failures
    if args.verbose:
        failures = conn.execute("""
            SELECT pmid, error_msg, updated_at
            FROM mineru_status
            WHERE status = 'failed'
            ORDER BY updated_at DESC
            LIMIT 5
        """).fetchall()

        if failures:
            print("\nRecent failures:")
            for pmid, error, updated in failures:
                print(f"  {pmid}: {error[:60] if error else 'Unknown error'}...")

    conn.close()
    return 0


def cmd_update(args):
    """Update registry from processing results."""
    db_path = Path(args.db)
    results_path = Path(args.results)

    if not db_path.exists():
        print(f"Error: Registry not found: {db_path}")
        return 1

    if not results_path.exists():
        print(f"Error: Results file not found: {results_path}")
        return 1

    conn = get_db(db_path)

    updated = 0

    # Handle different file formats
    if results_path.suffix == ".parquet":
        try:
            import pandas as pd
            df = pd.read_parquet(results_path)
            results = df.to_dict("records")
        except ImportError:
            print("Error: pandas required for parquet files")
            return 1
    else:
        with open(results_path, "r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            results = list(reader)

    for row in results:
        # Normalize keys
        normalized = {k.lower().strip(): v for k, v in row.items()}

        pmid = normalized.get("pmid", "").strip()
        if not pmid:
            continue

        status = normalized.get("status", "").strip()
        json_path = normalized.get("json_path", "").strip() or None
        md_path = normalized.get("md_path", "").strip() or None
        error_msg = normalized.get("error_msg", "").strip() or None
        processing_time = normalized.get("processing_time")

        if processing_time:
            try:
                processing_time = float(processing_time)
            except (ValueError, TypeError):
                processing_time = None

        conn.execute("""
            UPDATE mineru_status
            SET status = ?,
                json_path = ?,
                md_path = ?,
                error_msg = ?,
                processing_time = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE pmid = ?
        """, [status, json_path, md_path, error_msg, processing_time, pmid])

        updated += 1

    conn.commit()
    print(f"Updated {updated} entries")

    conn.close()
    return 0


def cmd_export_pending(args):
    """Export pending PDFs to a new manifest."""
    db_path = Path(args.db)
    output_path = Path(args.output)

    if not db_path.exists():
        print(f"Error: Registry not found: {db_path}")
        return 1

    conn = get_db(db_path)

    # Get pending entries
    pending = conn.execute("""
        SELECT pmid, pdf_path
        FROM mineru_status
        WHERE status = 'pending'
        ORDER BY pmid
    """).fetchall()

    if not pending:
        print("No pending PDFs to export")
        return 0

    # Write to CSV
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["pmid", "pdf_path"])
        writer.writerows(pending)

    print(f"Exported {len(pending)} pending PDFs to: {output_path}")

    conn.close()
    return 0


def cmd_export_failed(args):
    """Export failed PDFs to a new manifest for retry."""
    db_path = Path(args.db)
    output_path = Path(args.output)

    if not db_path.exists():
        print(f"Error: Registry not found: {db_path}")
        return 1

    conn = get_db(db_path)

    # Get failed entries
    failed = conn.execute("""
        SELECT pmid, pdf_path
        FROM mineru_status
        WHERE status = 'failed'
        ORDER BY pmid
    """).fetchall()

    if not failed:
        print("No failed PDFs to export")
        return 0

    # Write to CSV
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["pmid", "pdf_path"])
        writer.writerows(failed)

    print(f"Exported {len(failed)} failed PDFs to: {output_path}")

    conn.close()
    return 0


def cmd_retry_failed(args):
    """Reset failed PDFs to pending status for retry."""
    db_path = Path(args.db)

    if not db_path.exists():
        print(f"Error: Registry not found: {db_path}")
        return 1

    conn = get_db(db_path)

    # Count failed
    failed_count = conn.execute("""
        SELECT COUNT(*) FROM mineru_status WHERE status = 'failed'
    """).fetchone()[0]

    if failed_count == 0:
        print("No failed PDFs to retry")
        return 0

    # Reset to pending
    conn.execute("""
        UPDATE mineru_status
        SET status = 'pending',
            error_msg = NULL,
            processing_time = NULL,
            updated_at = CURRENT_TIMESTAMP
        WHERE status = 'failed'
    """)
    conn.commit()

    print(f"Reset {failed_count} failed PDFs to pending")

    conn.close()
    return 0


def cmd_scan_outputs(args):
    """Scan output directory and update registry with found outputs."""
    db_path = Path(args.db)
    output_dir = Path(args.output_dir)

    if not db_path.exists():
        print(f"Error: Registry not found: {db_path}")
        return 1

    if not output_dir.exists():
        print(f"Error: Output directory not found: {output_dir}")
        return 1

    conn = get_db(db_path)

    # Find all content_list.json files
    json_files = list(output_dir.glob("**/*_content_list.json"))
    print(f"Found {len(json_files)} output JSON files")

    updated = 0
    for json_path in json_files:
        # Extract PMID from filename
        pmid = json_path.stem.replace("_content_list", "")

        # Look for corresponding MD file
        md_path = json_path.parent / f"{pmid}.md"
        md_path_str = str(md_path) if md_path.exists() else None

        # Update registry
        result = conn.execute("""
            UPDATE mineru_status
            SET status = 'completed',
                json_path = ?,
                md_path = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE pmid = ? AND status != 'completed'
        """, [str(json_path), md_path_str, pmid])

        if result.rowcount > 0:
            updated += 1

    conn.commit()
    print(f"Updated {updated} entries from scan")

    conn.close()
    return 0


def cmd_query(args):
    """Run a custom SQL query on the registry."""
    db_path = Path(args.db)

    if not db_path.exists():
        print(f"Error: Registry not found: {db_path}")
        return 1

    conn = get_db(db_path)

    try:
        result = conn.execute(args.sql)
        rows = result.fetchall()
        columns = [desc[0] for desc in result.description]

        # Print results
        print("\t".join(columns))
        print("-" * 60)
        for row in rows:
            print("\t".join(str(v) if v is not None else "" for v in row))

        print(f"\n({len(rows)} rows)")

    except duckdb.Error as e:
        print(f"SQL Error: {e}")
        return 1

    conn.close()
    return 0


def cmd_update_sizes(args):
    """Update file sizes for all PDFs in registry."""
    import os

    db_path = Path(args.db)

    if not db_path.exists():
        print(f"Error: Registry not found: {db_path}")
        return 1

    conn = get_db(db_path)
    init_schema(conn)  # Ensure file_size column exists

    # Get all entries without file_size
    entries = conn.execute("""
        SELECT pmid, pdf_path
        FROM mineru_status
        WHERE file_size IS NULL
    """).fetchall()

    print(f"Updating file sizes for {len(entries)} PDFs...")

    updated = 0
    missing = 0
    batch_size = 10000
    batch = []

    for pmid, pdf_path in entries:
        try:
            size = os.path.getsize(pdf_path)
            batch.append((size, pmid))
            updated += 1
        except (OSError, FileNotFoundError):
            missing += 1

        # Batch updates for performance
        if len(batch) >= batch_size:
            conn.executemany("""
                UPDATE mineru_status SET file_size = ? WHERE pmid = ?
            """, batch)
            conn.commit()
            print(f"  Updated {updated} / {len(entries)}...")
            batch = []

    # Final batch
    if batch:
        conn.executemany("""
            UPDATE mineru_status SET file_size = ? WHERE pmid = ?
        """, batch)
        conn.commit()

    print(f"Updated {updated} file sizes ({missing} files not found)")

    # Show size distribution
    dist = conn.execute("""
        SELECT
            CASE
                WHEN file_size < 1048576 THEN '<1MB'
                WHEN file_size < 5242880 THEN '1-5MB'
                WHEN file_size < 10485760 THEN '5-10MB'
                ELSE '>10MB'
            END as size_range,
            COUNT(*) as count
        FROM mineru_status
        WHERE file_size IS NOT NULL
        GROUP BY 1
        ORDER BY MIN(file_size)
    """).fetchall()

    print("\nSize distribution:")
    for range_name, count in dist:
        print(f"  {range_name}: {count:,}")

    conn.close()
    return 0


def cmd_scan_pdfs(args):
    """Scan a directory for new PDFs and add them to the registry."""
    import os
    import re

    db_path = Path(args.db)
    pdf_dir = Path(args.pdf_dir)

    if not pdf_dir.exists():
        print(f"Error: PDF directory not found: {pdf_dir}")
        return 1

    # Create database if it doesn't exist
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = get_db(db_path)
    init_schema(conn)

    # Get existing PMIDs for fast lookup
    existing = set(
        row[0] for row in conn.execute("SELECT pmid FROM mineru_status").fetchall()
    )
    print(f"Registry has {len(existing)} existing entries")

    # Scan for PDFs
    print(f"Scanning for PDFs in: {pdf_dir}")

    # Support both flat and nested directory structures
    # Pattern: looks for numeric PMID in filename
    pmid_pattern = re.compile(r"(\d{6,10})\.pdf$", re.IGNORECASE)

    added = 0
    skipped = 0
    batch = []
    batch_size = 10000

    # Use os.walk for efficiency with large directories
    for root, dirs, files in os.walk(pdf_dir):
        for filename in files:
            if not filename.lower().endswith(".pdf"):
                continue

            # Extract PMID from filename
            match = pmid_pattern.search(filename)
            if not match:
                continue

            pmid = match.group(1)

            # Skip if already exists
            if pmid in existing:
                skipped += 1
                continue

            pdf_path = os.path.join(root, filename)

            # Get file size
            try:
                file_size = os.path.getsize(pdf_path)
            except OSError:
                file_size = None

            batch.append((pmid, pdf_path, file_size))
            existing.add(pmid)  # Prevent duplicates within scan
            added += 1

            # Batch inserts for performance
            if len(batch) >= batch_size:
                conn.executemany(
                    """
                    INSERT INTO mineru_status (pmid, pdf_path, file_size, status, created_at)
                    VALUES (?, ?, ?, 'pending', CURRENT_TIMESTAMP)
                    ON CONFLICT (pmid) DO NOTHING
                    """,
                    batch,
                )
                conn.commit()
                print(f"  Added {added} new PDFs...")
                batch = []

    # Final batch
    if batch:
        conn.executemany(
            """
            INSERT INTO mineru_status (pmid, pdf_path, file_size, status, created_at)
            VALUES (?, ?, ?, 'pending', CURRENT_TIMESTAMP)
            ON CONFLICT (pmid) DO NOTHING
            """,
            batch,
        )
        conn.commit()

    total = conn.execute("SELECT COUNT(*) FROM mineru_status").fetchone()[0]

    print(f"\nScan complete:")
    print(f"  New PDFs added: {added}")
    print(f"  Already in registry: {skipped}")
    print(f"  Total in registry: {total}")

    # Show size distribution if we added files
    if added > 0 and args.verbose:
        dist = conn.execute(
            """
            SELECT
                CASE
                    WHEN file_size < 1048576 THEN '<1MB'
                    WHEN file_size < 5242880 THEN '1-5MB'
                    WHEN file_size < 10485760 THEN '5-10MB'
                    ELSE '>10MB'
                END as size_range,
                COUNT(*) as count
            FROM mineru_status
            WHERE file_size IS NOT NULL
            GROUP BY 1
            ORDER BY MIN(file_size)
            """
        ).fetchall()

        print("\nSize distribution:")
        for range_name, count in dist:
            print(f"  {range_name}: {count:,}")

    conn.close()
    return 0


def cmd_export_by_size(args):
    """Export PDFs filtered by file size to a manifest."""
    db_path = Path(args.db)
    output_path = Path(args.output)

    if not db_path.exists():
        print(f"Error: Registry not found: {db_path}")
        return 1

    conn = get_db(db_path)

    # Build size filter
    conditions = ["(status = 'pending' OR status = 'failed')"]
    params = []

    if args.max_size:
        max_bytes = int(args.max_size * 1024 * 1024)  # Convert MB to bytes
        conditions.append("file_size <= ?")
        params.append(max_bytes)

    if args.min_size:
        min_bytes = int(args.min_size * 1024 * 1024)
        conditions.append("file_size >= ?")
        params.append(min_bytes)

    where_clause = " AND ".join(conditions)

    # Get filtered entries
    query = f"""
        SELECT pmid, pdf_path
        FROM mineru_status
        WHERE {where_clause} AND file_size IS NOT NULL
        ORDER BY pmid
    """

    entries = conn.execute(query, params).fetchall()

    if not entries:
        print("No matching PDFs to export")
        return 0

    # Write to CSV
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["pmid", "pdf_path"])
        writer.writerows(entries)

    size_desc = []
    if args.min_size:
        size_desc.append(f">={args.min_size}MB")
    if args.max_size:
        size_desc.append(f"<={args.max_size}MB")
    size_str = " and ".join(size_desc) if size_desc else "all sizes"

    print(f"Exported {len(entries)} PDFs ({size_str}) to: {output_path}")

    conn.close()
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="MinerU processing registry",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--db",
        type=str,
        default=str(DEFAULT_DB_PATH),
        help=f"Path to DuckDB database (default: {DEFAULT_DB_PATH})",
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # init
    init_parser = subparsers.add_parser("init", help="Initialize registry from manifest")
    init_parser.add_argument(
        "--manifest",
        required=True,
        help="CSV file with pmid,pdf_path columns",
    )

    # status
    status_parser = subparsers.add_parser("status", help="Show registry status")
    status_parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Show additional details",
    )

    # update
    update_parser = subparsers.add_parser("update", help="Update from processing results")
    update_parser.add_argument(
        "--results",
        required=True,
        help="Results CSV or parquet file",
    )

    # export-pending
    export_pending_parser = subparsers.add_parser(
        "export-pending",
        help="Export pending PDFs to manifest",
    )
    export_pending_parser.add_argument(
        "-o", "--output",
        required=True,
        help="Output CSV file",
    )

    # export-failed
    export_failed_parser = subparsers.add_parser(
        "export-failed",
        help="Export failed PDFs to manifest",
    )
    export_failed_parser.add_argument(
        "-o", "--output",
        required=True,
        help="Output CSV file",
    )

    # retry-failed
    retry_parser = subparsers.add_parser(
        "retry-failed",
        help="Reset failed PDFs to pending",
    )

    # scan-outputs
    scan_parser = subparsers.add_parser(
        "scan-outputs",
        help="Scan output directory and update registry",
    )
    scan_parser.add_argument(
        "--output-dir",
        required=True,
        help="Directory containing MinerU outputs",
    )

    # query
    query_parser = subparsers.add_parser("query", help="Run SQL query")
    query_parser.add_argument("sql", help="SQL query to execute")

    # update-sizes
    update_sizes_parser = subparsers.add_parser(
        "update-sizes",
        help="Update file sizes for all PDFs",
    )

    # export-by-size
    export_size_parser = subparsers.add_parser(
        "export-by-size",
        help="Export PDFs filtered by file size",
    )
    export_size_parser.add_argument(
        "-o", "--output",
        required=True,
        help="Output CSV file",
    )
    export_size_parser.add_argument(
        "--max-size",
        type=float,
        help="Maximum file size in MB",
    )
    export_size_parser.add_argument(
        "--min-size",
        type=float,
        help="Minimum file size in MB",
    )

    # scan-pdfs
    scan_pdfs_parser = subparsers.add_parser(
        "scan-pdfs",
        help="Scan directory for new PDFs and add to registry",
    )
    scan_pdfs_parser.add_argument(
        "--pdf-dir",
        required=True,
        help="Directory containing PDF files to scan",
    )
    scan_pdfs_parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Show size distribution after scan",
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    commands = {
        "init": cmd_init,
        "status": cmd_status,
        "update": cmd_update,
        "export-pending": cmd_export_pending,
        "export-failed": cmd_export_failed,
        "retry-failed": cmd_retry_failed,
        "scan-outputs": cmd_scan_outputs,
        "scan-pdfs": cmd_scan_pdfs,
        "query": cmd_query,
        "update-sizes": cmd_update_sizes,
        "export-by-size": cmd_export_by_size,
    }

    return commands[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
