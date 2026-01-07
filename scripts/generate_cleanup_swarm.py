#!/usr/bin/env python3
"""Generate swarm file for MinerU output cleanup operations."""

import argparse
from pathlib import Path

def generate_swarm(pmid_file: Path, output_file: Path, mode: str, chunk_size: int):
    """Generate swarm file with chunked cleanup commands."""

    script = "/data/adamt/osm/minerU_osm/scripts/cleanup_mineru_output.sh"
    mode_flag = "--flatten-only" if mode == "flatten" else "--move"

    with open(pmid_file) as f:
        pmids = [line.strip() for line in f if line.strip() and not line.startswith('#')]

    with open(output_file, 'w') as out:
        for i in range(0, len(pmids), chunk_size):
            chunk = pmids[i:i + chunk_size]
            # Pass PMIDs directly as arguments
            pmid_args = ' '.join(chunk)
            out.write(f"bash {script} {mode_flag} {pmid_args}\n")

    num_chunks = (len(pmids) + chunk_size - 1) // chunk_size
    print(f"Generated {output_file}")
    print(f"  Total PMIDs: {len(pmids)}")
    print(f"  Chunk size: {chunk_size}")
    print(f"  Total chunks: {num_chunks}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate cleanup swarm file")
    parser.add_argument("--pmid-file", required=True, help="File with PMIDs to process")
    parser.add_argument("--output", required=True, help="Output swarm file")
    parser.add_argument("--mode", choices=["move", "flatten"], default="move",
                        help="Cleanup mode: move (non-nested) or flatten (already-nested)")
    parser.add_argument("--chunk-size", type=int, default=500,
                        help="PMIDs per swarm task (default: 500)")

    args = parser.parse_args()
    generate_swarm(
        Path(args.pmid_file),
        Path(args.output),
        args.mode,
        args.chunk_size
    )
