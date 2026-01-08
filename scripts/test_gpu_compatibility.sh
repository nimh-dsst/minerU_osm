#!/bin/bash
# Test MinerU GPU compatibility across all GPU types
# Usage: Run via swarm with different --gres=gpu:TYPE:1 for each GPU type

set -e

# Configuration
CONTAINER="/data/adamt/containers/mineru.sif"
TEST_PDF="/data/NIMH_scratch/adamt/osm/datalad-osm/pdfs/126/12657658.pdf"
OUTPUT_BASE="/data/adamt/osm/datafiles/gpu_tests"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
HOSTNAME=$(hostname)

# Create output directory
OUTPUT_DIR="${OUTPUT_BASE}/${HOSTNAME}_${TIMESTAMP}"
mkdir -p "$OUTPUT_DIR"

echo "=== MinerU GPU Compatibility Test ==="
echo "Hostname: $HOSTNAME"
echo "Timestamp: $TIMESTAMP"
echo "Output dir: $OUTPUT_DIR"
echo ""

# Capture GPU info
echo "=== GPU Information ==="
nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv 2>&1 | tee "$OUTPUT_DIR/gpu_info.txt"
echo ""

# Capture node info
echo "=== Node Information ==="
echo "Hostname: $HOSTNAME" | tee "$OUTPUT_DIR/node_info.txt"
uname -a >> "$OUTPUT_DIR/node_info.txt"
echo ""

# Load required modules
echo "=== Loading Apptainer ==="
module load apptainer
source /usr/local/current/singularity/app_conf/sing_binds

# Check CUDA availability inside container
echo "=== Checking CUDA inside container ==="
apptainer exec --nv "$CONTAINER" python3 -c "
import torch
print(f'PyTorch version: {torch.__version__}')
print(f'CUDA available: {torch.cuda.is_available()}')
if torch.cuda.is_available():
    print(f'CUDA device: {torch.cuda.get_device_name(0)}')
    print(f'CUDA memory: {torch.cuda.get_device_properties(0).total_memory / 1e9:.1f} GB')
else:
    print('WARNING: CUDA not available')
" 2>&1 | tee "$OUTPUT_DIR/cuda_check.txt"
echo ""

# Test MinerU by running the actual processing script
echo "=== Testing MinerU Processing ==="
echo "Test PDF: $TEST_PDF"
echo ""

START_TIME=$(date +%s.%N)

# Create a simple manifest
MANIFEST="$OUTPUT_DIR/test_manifest.csv"
echo "pmid,pdf_path" > "$MANIFEST"
echo "12657658,$TEST_PDF" >> "$MANIFEST"

# Run the actual processing script inside the container
echo "Running process_pdfs_mineru.py..."
apptainer exec --nv "$CONTAINER" python3 \
    /data/adamt/osm/minerU_osm/scripts/process_pdfs_mineru.py \
    --manifest "$MANIFEST" \
    --output-dir "$OUTPUT_DIR" \
    --results-file "$OUTPUT_DIR/test_result.csv" \
    --verbose 2>&1 | tee "$OUTPUT_DIR/mineru_output.txt"

PROCESS_EXIT_CODE=${PIPESTATUS[0]}

END_TIME=$(date +%s.%N)
ELAPSED=$(echo "$END_TIME - $START_TIME" | bc)

echo ""
echo "=== Test Summary ==="
echo "Total elapsed time: ${ELAPSED}s"
echo "Process exit code: $PROCESS_EXIT_CODE"
echo "Results saved to: $OUTPUT_DIR"

# Check if output was generated
echo ""
echo "=== Checking for output files ==="
if find "$OUTPUT_DIR" -name "*_content_list.json" -type f 2>/dev/null | head -1 | grep -q .; then
    echo "STATUS: SUCCESS - Output files generated"
    find "$OUTPUT_DIR" -name "*.json" -o -name "*.md" 2>/dev/null | head -10
    exit 0
else
    echo "STATUS: FAILURE - No output files generated"
    echo ""
    echo "Check $OUTPUT_DIR/mineru_output.txt for details"
    exit 1
fi
