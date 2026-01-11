#!/usr/bin/env python3
"""
Merge MinerU processing results from multiple chunk files.

Combines per-chunk result CSV/parquet files into a single consolidated file
and optionally updates the registry database.

Usage:
    python merge_mineru_results.py \
        --input-dir /path/to/results \
        --output combined_results.parquet \
        --update-registry
"""

import argparse
import csv
import sys
from datetime import datetime
from pathlib import Path

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False

try:
    import duckdb
    DUCKDB_AVAILABLE = True
except ImportError:
    DUCKDB_AVAILABLE = False


def parse_args():
    parser = argparse.ArgumentParser(
        description="Merge MinerU processing results",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Merge all chunk results
    python merge_mineru_results.py \\
        --input-dir /data/adamt/osm/datafiles/mineru_results \\
        --output combined.parquet

    # Merge and update registry
    python merge_mineru_results.py \\
        --input-dir /data/adamt/osm/datafiles/mineru_results \\
        --output combined.parquet \\
        --update-registry
        """,
    )

    parser.add_argument(
        "--input-dir",
        type=Path,
        required=True,
        help="Directory containing chunk result files (CSV/parquet)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Output file path (.parquet or .csv)",
    )
    parser.add_argument(
        "--pattern",
        type=str,
        default="chunk_*.csv",
        help="Glob pattern for input files (default: chunk_*.csv)",
    )
    parser.add_argument(
        "--update-registry",
        action="store_true",
        help="Update the registry database with merged results",
    )
    parser.add_argument(
        "--registry-db",
        type=Path,
        default=Path("/data/NIMH_scratch/adamt/osm/datalad-osm/duckdbs/mineru_registry.duckdb"),
        help="Path to registry database",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Verbose output",
    )

    return parser.parse_args()


def load_csv_files(input_dir: Path, pattern: str) -> list[dict]:
    """Load all CSV files matching pattern and return combined records."""
    all_records = []
    files = sorted(input_dir.glob(pattern))

    if not files:
        return []

    for filepath in files:
        with open(filepath, "r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                all_records.append(row)

    return all_records


def load_parquet_files(input_dir: Path, pattern: str) -> "pd.DataFrame":
    """Load all parquet files matching pattern."""
    if not PANDAS_AVAILABLE:
        raise ImportError("pandas required for parquet support")

    files = sorted(input_dir.glob(pattern))
    if not files:
        return pd.DataFrame()

    dfs = [pd.read_parquet(f) for f in files]
    return pd.concat(dfs, ignore_index=True)


def save_output(records: list[dict], output_path: Path):
    """Save records to output file."""
    if not records:
        print("No records to save")
        return

    if PANDAS_AVAILABLE:
        df = pd.DataFrame(records)

        # Deduplicate by pmid, keeping last entry
        if "pmid" in df.columns:
            df = df.drop_duplicates(subset=["pmid"], keep="last")

        if output_path.suffix == ".parquet":
            df.to_parquet(output_path, index=False)
        else:
            df.to_csv(output_path, index=False)
    else:
        # CSV-only fallback
        output_path = output_path.with_suffix(".csv")

        # Deduplicate
        seen = {}
        for record in records:
            pmid = record.get("pmid", "")
            if pmid:
                seen[pmid] = record
            else:
                # Keep records without pmid
                seen[id(record)] = record

        records = list(seen.values())

        with open(output_path, "w", newline="", encoding="utf-8") as f:
            if records:
                writer = csv.DictWriter(f, fieldnames=records[0].keys())
                writer.writeheader()
                writer.writerows(records)


def update_registry(records: list[dict], db_path: Path, verbose: bool = False):
    """Update registry database with processing results."""
    if not DUCKDB_AVAILABLE:
        print("Warning: duckdb not available, skipping registry update")
        return

    if not db_path.exists():
        print(f"Warning: Registry not found: {db_path}")
        return

    conn = duckdb.connect(str(db_path))

    updated = 0
    for record in records:
        pmid = record.get("pmid", "").strip()
        if not pmid:
            continue

        status = record.get("status", "").strip()
        json_path = record.get("json_path", "").strip() or None
        md_path = record.get("md_path", "").strip() or None
        error_msg = record.get("error_msg", "").strip() or None
        processing_time = record.get("processing_time")

        if processing_time:
            try:
                processing_time = float(processing_time)
            except (ValueError, TypeError):
                processing_time = None

        result = conn.execute("""
            UPDATE mineru_status
            SET status = ?,
                json_path = ?,
                md_path = ?,
                error_msg = ?,
                processing_time = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE pmid = ?
        """, [status, json_path, md_path, error_msg, processing_time, pmid])

        if result.rowcount > 0:
            updated += 1

    conn.commit()
    conn.close()

    if verbose:
        print(f"Updated {updated} registry entries")


def print_summary(records: list[dict]):
    """Print summary statistics."""
    if not records:
        print("No records to summarize")
        return

    total = len(records)
    completed = sum(1 for r in records if r.get("status") == "completed")
    failed = sum(1 for r in records if r.get("status") == "failed")
    pending = sum(1 for r in records if r.get("status") == "pending")

    # Calculate average processing time
    times = []
    for r in records:
        try:
            t = float(r.get("processing_time", 0))
            if t > 0:
                times.append(t)
        except (ValueError, TypeError):
            pass

    avg_time = sum(times) / len(times) if times else 0

    print("-" * 40)
    print("Summary")
    print("-" * 40)
    print(f"Total records:  {total}")
    print(f"Completed:      {completed} ({100*completed/total:.1f}%)")
    print(f"Failed:         {failed} ({100*failed/total:.1f}%)")
    print(f"Pending:        {pending} ({100*pending/total:.1f}%)")

    if avg_time > 0:
        print(f"Avg time:       {avg_time:.1f}s")

    # Count unique PMIDs
    pmids = set(r.get("pmid") for r in records if r.get("pmid"))
    print(f"Unique PMIDs:   {len(pmids)}")
    print("-" * 40)


def main():
    args = parse_args()

    if not args.input_dir.exists():
        print(f"Error: Input directory not found: {args.input_dir}")
        return 1

    # Find input files
    input_files = list(args.input_dir.glob(args.pattern))

    if not input_files:
        print(f"No files matching '{args.pattern}' in {args.input_dir}")
        return 1

    print(f"Found {len(input_files)} input files")

    # Load all records
    if args.verbose:
        print("Loading files...")

    # Determine if parquet or CSV
    if args.pattern.endswith(".parquet") and PANDAS_AVAILABLE:
        df = load_parquet_files(args.input_dir, args.pattern)
        records = df.to_dict("records") if not df.empty else []
    else:
        records = load_csv_files(args.input_dir, args.pattern)

    if not records:
        print("No records found in input files")
        return 1

    print(f"Loaded {len(records)} total records")

    # Print summary
    print_summary(records)

    # Save output
    args.output.parent.mkdir(parents=True, exist_ok=True)
    save_output(records, args.output)
    print(f"Saved to: {args.output}")

    # Update registry if requested
    if args.update_registry:
        print("Updating registry...")
        update_registry(records, args.registry_db, args.verbose)
        print(f"Registry updated: {args.registry_db}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
