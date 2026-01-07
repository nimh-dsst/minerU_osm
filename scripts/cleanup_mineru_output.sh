#!/bin/bash
# cleanup_mineru_output.sh - Reorganize MinerU output directories
#
# Fixes two issues:
# 1. Moves non-nested PMIDs from minerU_out/{pmid}/ to minerU_out/{prefix}/{pmid}/
# 2. Flattens redundant nested structure: {pmid}/{pmid}/auto/ -> {pmid}/auto/
#
# Usage:
#   cleanup_mineru_output.sh [--move|--flatten-only] <pmid1> [pmid2] ...
#   cleanup_mineru_output.sh [--move|--flatten-only] --file <pmid_list.txt>
#
# Modes:
#   --move         Move non-nested dirs to prefix and flatten (default)
#   --flatten-only Only flatten already-nested dirs (for {prefix}/{pmid}/{pmid}/)

set -euo pipefail

OUTPUT_DIR="${OUTPUT_DIR:-/data/NIMH_scratch/adamt/osm/datalad-osm/minerU_out}"
MODE="move"

# Flatten nested structure: {base}/{pmid}/ -> {base}/
flatten_nested() {
    local base_dir="$1"
    local pmid="$2"
    local nested_dir="$base_dir/$pmid"

    if [[ -d "$nested_dir" ]]; then
        # Move contents of nested dir up
        mv "$nested_dir"/* "$base_dir/" 2>/dev/null || true
        rmdir "$nested_dir" 2>/dev/null || echo "WARN: Could not remove $nested_dir"
        echo "FLATTENED: $base_dir"
        return 0
    fi
    return 1
}

# Mode: move non-nested dir to prefix + flatten
cleanup_move() {
    local pmid="$1"
    local prefix="${pmid:0:3}"
    local src_dir="$OUTPUT_DIR/$pmid"
    local dest_dir="$OUTPUT_DIR/$prefix/$pmid"

    # Skip if source doesn't exist
    if [[ ! -d "$src_dir" ]]; then
        echo "SKIP: $pmid - source dir does not exist"
        return 0
    fi

    # Skip if destination already exists
    if [[ -d "$dest_dir" ]]; then
        echo "SKIP: $pmid - destination already exists"
        return 0
    fi

    # Flatten nested structure first
    flatten_nested "$src_dir" "$pmid" || true

    # Create prefix directory and move
    mkdir -p "$OUTPUT_DIR/$prefix"
    mv "$src_dir" "$dest_dir"
    echo "MOVED: $pmid -> $prefix/$pmid"
}

# Mode: flatten already-nested dir only
cleanup_flatten() {
    local pmid="$1"
    local prefix="${pmid:0:3}"
    local base_dir="$OUTPUT_DIR/$prefix/$pmid"

    if [[ ! -d "$base_dir" ]]; then
        echo "SKIP: $pmid - dir does not exist at $prefix/$pmid"
        return 0
    fi

    if ! flatten_nested "$base_dir" "$pmid"; then
        echo "SKIP: $pmid - no nested structure to flatten"
    fi
}

cleanup_pmid() {
    local pmid="$1"
    if [[ "$MODE" == "flatten-only" ]]; then
        cleanup_flatten "$pmid"
    else
        cleanup_move "$pmid"
    fi
}

# Parse arguments
PMIDS=()
FILE=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --move)
            MODE="move"
            shift
            ;;
        --flatten-only)
            MODE="flatten-only"
            shift
            ;;
        --file)
            FILE="$2"
            shift 2
            ;;
        *)
            PMIDS+=("$1")
            shift
            ;;
    esac
done

# Process from file or command line
if [[ -n "$FILE" ]]; then
    while IFS= read -r pmid || [[ -n "$pmid" ]]; do
        [[ -z "$pmid" || "$pmid" =~ ^# ]] && continue
        cleanup_pmid "$pmid"
    done < "$FILE"
else
    for pmid in "${PMIDS[@]}"; do
        cleanup_pmid "$pmid"
    done
fi
