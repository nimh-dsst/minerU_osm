#!/bin/bash
# Quick test of mineru_p100.sif container
# Run this in an interactive GPU session on Biowulf
#
# Usage:
#   sinteractive --gres=gpu:p100:1 --mem=64g --time=00:30:00
#   bash /data/adamt/osm/minerU_osm/scripts/test_p100_container.sh

set -e

CONTAINER="${CONTAINER:-/data/adamt/containers/mineru_p100.sif}"
TEST_PDF="/data/NIMH_scratch/adamt/osm/datalad-osm/pdfs/126/12657658.pdf"
OUTPUT_DIR="/tmp/p100_test_$(date +%Y%m%d_%H%M%S)"

echo "=== P100 Container Test ==="
echo "Container: $CONTAINER"
echo "Hostname: $(hostname)"
echo ""

# Check container exists
if [[ ! -f "$CONTAINER" ]]; then
    echo "Error: Container not found: $CONTAINER"
    echo "Build and transfer it first:"
    echo "  cd /path/to/minerU_osm/container && bash build_p100_container.sh"
    echo "  scp mineru_p100.sif helix:/data/adamt/containers/"
    exit 1
fi

# Load modules
module load apptainer
source /usr/local/current/singularity/app_conf/sing_binds

# GPU info
echo "=== GPU Information ==="
nvidia-smi --query-gpu=name,memory.total,compute_cap --format=csv
echo ""

# Check CUDA in container
echo "=== Container PyTorch/CUDA Check ==="
apptainer exec --nv "$CONTAINER" python3 -c "
import torch
print(f'PyTorch version: {torch.__version__}')
print(f'CUDA available: {torch.cuda.is_available()}')
if torch.cuda.is_available():
    print(f'CUDA device: {torch.cuda.get_device_name(0)}')
    print(f'CUDA capability: {torch.cuda.get_device_capability(0)}')
    print(f'Supported archs: {torch.cuda.get_arch_list()}')
else:
    print('WARNING: CUDA not available')
"
echo ""

# Test actual PDF processing
echo "=== Testing PDF Processing ==="
mkdir -p "$OUTPUT_DIR"

MANIFEST="$OUTPUT_DIR/test_manifest.csv"
echo "pmid,pdf_path" > "$MANIFEST"
echo "12657658,$TEST_PDF" >> "$MANIFEST"

START_TIME=$(date +%s)

apptainer exec --nv "$CONTAINER" python3 \
    /data/adamt/osm/minerU_osm/scripts/process_pdfs_mineru.py \
    --manifest "$MANIFEST" \
    --output-dir "$OUTPUT_DIR" \
    --results-file "$OUTPUT_DIR/result.csv" \
    --verbose

END_TIME=$(date +%s)
ELAPSED=$((END_TIME - START_TIME))

echo ""
echo "=== Results ==="
echo "Processing time: ${ELAPSED}s"

if find "$OUTPUT_DIR" -name "*_content_list.json" -type f | grep -q .; then
    echo "STATUS: SUCCESS - Output files generated"
    ls -la "$OUTPUT_DIR"
else
    echo "STATUS: FAILURE - No output files"
    cat "$OUTPUT_DIR/result.csv" 2>/dev/null || true
fi

# Cleanup
rm -rf "$OUTPUT_DIR"
