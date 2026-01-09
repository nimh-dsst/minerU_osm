#!/usr/bin/env python3
"""
Process PDFs with MinerU.

Converts PDF files to structured JSON and Markdown using MinerU's layout analysis.

Usage:
    python process_pdfs_mineru.py \
        --manifest manifest.csv \
        --start-index 0 --count 100 \
        --output-dir /path/to/output \
        --backend pipeline
"""

import argparse
import csv
import json
import os
import shutil
import sys
import tempfile
import time
import traceback
from datetime import datetime
from pathlib import Path

try:
    import pandas as pd
except ImportError:
    pd = None

try:
    from mineru.cli import main as mineru_cli
    from mineru.config import MinerUConfig
    MINERU_AVAILABLE = True
except ImportError:
    MINERU_AVAILABLE = False


def parse_args():
    parser = argparse.ArgumentParser(
        description="Process PDFs with MinerU",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Process from manifest
    python process_pdfs_mineru.py --manifest pdfs.csv --output-dir output/

    # Process a chunk (for swarm jobs)
    python process_pdfs_mineru.py --manifest pdfs.csv --start-index 100 --count 100 --output-dir output/

    # Process a single PDF
    python process_pdfs_mineru.py --pdf input.pdf --output-dir output/
        """,
    )

    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument(
        "--manifest",
        type=Path,
        help="CSV file with 'pmid' and 'pdf_path' columns",
    )
    input_group.add_argument(
        "--pdf",
        type=Path,
        help="Single PDF file to process",
    )
    input_group.add_argument(
        "--pdf-dir",
        type=Path,
        help="Directory containing PDF files",
    )

    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Output directory for JSON/MD files",
    )
    parser.add_argument(
        "--start-index",
        type=int,
        default=0,
        help="Starting index in manifest (default: 0)",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=None,
        help="Number of PDFs to process (default: all)",
    )
    parser.add_argument(
        "--backend",
        choices=["pipeline", "vlm", "sglang"],
        default="pipeline",
        help="MinerU backend (default: pipeline)",
    )
    parser.add_argument(
        "--results-file",
        type=Path,
        help="Output parquet/CSV file for chunk results",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Skip PDFs that already have output files",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Verbose output",
    )

    return parser.parse_args()


def load_manifest(manifest_path: Path, start_index: int, count: int | None) -> list[dict]:
    """Load manifest CSV and return list of {pmid, pdf_path} dicts."""
    entries = []

    with open(manifest_path, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        # Normalize column names
        fieldnames = [name.lower().strip() for name in reader.fieldnames]

        for i, row in enumerate(reader):
            if i < start_index:
                continue
            if count is not None and len(entries) >= count:
                break

            # Create normalized row
            normalized = {k.lower().strip(): v for k, v in row.items()}

            pmid = normalized.get("pmid", "").strip()
            pdf_path = normalized.get("pdf_path", "").strip()

            if not pdf_path:
                continue

            entries.append({
                "pmid": pmid or Path(pdf_path).stem,
                "pdf_path": pdf_path,
            })

    return entries


def discover_pdfs(pdf_dir: Path) -> list[dict]:
    """Discover PDF files in a directory."""
    entries = []
    for pdf_path in sorted(pdf_dir.glob("**/*.pdf")):
        entries.append({
            "pmid": pdf_path.stem,
            "pdf_path": str(pdf_path),
        })
    return entries


def get_pmid_prefix(pmid: str) -> str:
    """Get the first 3 digits of a PMID for subdirectory organization."""
    # Handle PMIDs that might be numeric strings
    pmid_str = str(pmid).strip()
    return pmid_str[:3] if len(pmid_str) >= 3 else pmid_str


def check_existing_output(pmid: str, output_dir: Path) -> bool:
    """Check if output files already exist for a PMID."""
    prefix = get_pmid_prefix(pmid)
    # Check both auto/ and hybrid_auto/ (P100 container uses hybrid backend)
    for subdir in ["auto", "hybrid_auto"]:
        # Check in correct structure: {prefix}/{pmid}/{subdir}/{pmid}_content_list.json
        json_path = output_dir / prefix / pmid / subdir / f"{pmid}_content_list.json"
        if json_path.exists():
            return True
        # Also check old double-nested structure for backwards compatibility
        old_json_path = output_dir / prefix / pmid / pmid / subdir / f"{pmid}_content_list.json"
        if old_json_path.exists():
            return True
        # Check non-prefixed structure
        flat_json_path = output_dir / pmid / subdir / f"{pmid}_content_list.json"
        if flat_json_path.exists():
            return True
    return False


def process_single_pdf(
    pmid: str,
    pdf_path: Path,
    output_dir: Path,
    backend: str = "pipeline",
    verbose: bool = False,
) -> dict:
    """
    Process a single PDF with MinerU.

    Returns:
        dict with keys: pmid, status, json_path, md_path, processing_time, error_msg
    """
    result = {
        "pmid": pmid,
        "pdf_path": str(pdf_path),
        "status": "pending",
        "json_path": None,
        "md_path": None,
        "processing_time": None,
        "error_msg": None,
        "processed_at": datetime.now().isoformat(),
    }

    if not pdf_path.exists():
        result["status"] = "failed"
        result["error_msg"] = f"PDF file not found: {pdf_path}"
        return result

    start_time = time.time()

    try:
        # Create prefix directory - MinerU will create {pmid}/auto/ inside
        prefix = get_pmid_prefix(pmid)
        prefix_dir = output_dir / prefix
        prefix_dir.mkdir(parents=True, exist_ok=True)

        # Expected output location after MinerU processes
        pmid_output_dir = prefix_dir / pmid

        if verbose:
            print(f"Processing {pmid}: {pdf_path}")

        # Use MinerU's Python API if available
        if MINERU_AVAILABLE:
            # Import here to avoid slow startup
            from mineru.pdf_extractor import PDFExtractor

            extractor = PDFExtractor(
                pdf_path=str(pdf_path),
                output_dir=str(prefix_dir),  # Pass prefix dir, MinerU creates {pmid}/auto/
            )
            extractor.extract()

        else:
            # Fallback to CLI
            import subprocess

            cmd = [
                "mineru",
                "-p", str(pdf_path),
                "-o", str(prefix_dir),  # Pass prefix dir
            ]

            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=600,  # 10 minute timeout
            )

            if proc.returncode != 0:
                result["status"] = "failed"
                result["error_msg"] = proc.stderr[:500] if proc.stderr else "Unknown error"
                result["processing_time"] = time.time() - start_time
                return result

        # Verify output files actually exist before marking completed
        # MinerU creates: {prefix}/{pmid}/auto/{pmid}_content_list.json
        # P100 container uses hybrid backend: {prefix}/{pmid}/hybrid_auto/{pmid}_content_list.json
        json_path = None
        output_subdir = None

        # Check both auto/ and hybrid_auto/ directories
        for subdir in ["auto", "hybrid_auto"]:
            candidate_json = pmid_output_dir / subdir / f"{pmid}_content_list.json"
            if candidate_json.exists():
                json_path = candidate_json
                output_subdir = subdir
                break
            # Also check for files with PDF filename (MinerU uses PDF stem)
            subdir_path = pmid_output_dir / subdir
            if subdir_path.exists():
                json_files = list(subdir_path.glob("*_content_list.json"))
                if json_files:
                    json_path = json_files[0]
                    output_subdir = subdir
                    break

        if json_path and json_path.exists():
            result["json_path"] = str(json_path)
            result["status"] = "completed"

            # Find markdown file in the same subdir
            subdir_path = pmid_output_dir / output_subdir
            md_files = list(subdir_path.glob("*.md")) if subdir_path.exists() else []
            if md_files:
                result["md_path"] = str(md_files[0])
        else:
            # No output files generated - this is a failure
            result["status"] = "failed"
            result["error_msg"] = "No output files generated by MinerU"

            # Clean up empty directories to avoid inode waste
            if pmid_output_dir.exists():
                try:
                    shutil.rmtree(pmid_output_dir)
                except Exception:
                    pass  # Best effort cleanup

    except subprocess.TimeoutExpired:
        result["status"] = "failed"
        result["error_msg"] = "Processing timeout (10 min)"
    except Exception as e:
        result["status"] = "failed"
        result["error_msg"] = f"{type(e).__name__}: {str(e)[:200]}"
        if verbose:
            traceback.print_exc()

    result["processing_time"] = time.time() - start_time

    return result


def save_results(results: list[dict], output_file: Path):
    """Save processing results to parquet or CSV."""
    if pd is None:
        # Fallback to CSV
        output_file = output_file.with_suffix(".csv")
        with open(output_file, "w", newline="", encoding="utf-8") as f:
            if results:
                writer = csv.DictWriter(f, fieldnames=results[0].keys())
                writer.writeheader()
                writer.writerows(results)
        return

    df = pd.DataFrame(results)

    if output_file.suffix == ".parquet":
        df.to_parquet(output_file, index=False)
    else:
        df.to_csv(output_file, index=False)


def main():
    args = parse_args()

    # Collect PDFs to process
    if args.pdf:
        entries = [{
            "pmid": args.pdf.stem,
            "pdf_path": str(args.pdf),
        }]
    elif args.pdf_dir:
        entries = discover_pdfs(args.pdf_dir)
    else:
        entries = load_manifest(args.manifest, args.start_index, args.count)

    if not entries:
        print("No PDFs to process")
        return 0

    # Create output directory
    args.output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Processing {len(entries)} PDFs")
    print(f"Output directory: {args.output_dir}")
    print(f"Backend: {args.backend}")
    print("-" * 60)

    results = []
    completed = 0
    failed = 0
    skipped = 0

    for i, entry in enumerate(entries, 1):
        pmid = entry["pmid"]
        pdf_path = Path(entry["pdf_path"])

        # Check for existing output
        if args.skip_existing and check_existing_output(pmid, args.output_dir):
            if args.verbose:
                print(f"[{i}/{len(entries)}] Skipping {pmid} (already processed)")
            skipped += 1
            continue

        # Process PDF
        result = process_single_pdf(
            pmid=pmid,
            pdf_path=pdf_path,
            output_dir=args.output_dir,
            backend=args.backend,
            verbose=args.verbose,
        )

        results.append(result)

        if result["status"] == "completed":
            completed += 1
            status_char = "✓"
        else:
            failed += 1
            status_char = "✗"

        print(
            f"[{i}/{len(entries)}] {status_char} {pmid} "
            f"({result['processing_time']:.1f}s)"
        )

        if result["status"] == "failed" and args.verbose:
            print(f"  Error: {result['error_msg']}")

    # Summary
    print("-" * 60)
    print(f"Completed: {completed}")
    print(f"Failed: {failed}")
    print(f"Skipped: {skipped}")

    # Save results
    if args.results_file:
        save_results(results, args.results_file)
        print(f"Results saved to: {args.results_file}")
    elif results:
        # Auto-generate results file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        results_file = args.output_dir / f"results_{timestamp}.csv"
        save_results(results, results_file)
        print(f"Results saved to: {results_file}")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
