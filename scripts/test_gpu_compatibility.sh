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
nvidia-smi --query-gpu=name,memory.total,compute_cap,driver_version --format=csv 2>&1 | tee "$OUTPUT_DIR/gpu_info.txt"
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

# Test MinerU
echo "=== Testing MinerU ==="
echo "Test PDF: $TEST_PDF"
echo ""

START_TIME=$(date +%s.%N)

# Run MinerU with verbose output
apptainer exec --nv "$CONTAINER" python3 - << 'PYTHON_SCRIPT' 2>&1 | tee "$OUTPUT_DIR/mineru_output.txt"
import sys
import time
import os

# Enable verbose logging
import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Check CUDA availability
try:
    import torch
    print(f"PyTorch version: {torch.__version__}")
    print(f"CUDA available: {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"CUDA device: {torch.cuda.get_device_name(0)}")
        print(f"CUDA compute capability: {torch.cuda.get_device_capability(0)}")
        print(f"CUDA memory: {torch.cuda.get_device_properties(0).total_memory / 1e9:.1f} GB")
except Exception as e:
    print(f"PyTorch/CUDA check failed: {e}")

print()

# Test MinerU
from mineru.pdf_extractor import PDFExtractor
import tempfile

test_pdf = os.environ.get('TEST_PDF', '/data/NIMH_scratch/adamt/osm/datalad-osm/pdfs/126/12657658.pdf')
output_dir = os.environ.get('OUTPUT_DIR', '/tmp/mineru_test')

print(f"Processing: {test_pdf}")
print(f"Output to: {output_dir}")

start = time.time()
try:
    extractor = PDFExtractor(
        pdf_path=test_pdf,
        output_dir=output_dir
    )
    extractor.extract()
    elapsed = time.time() - start
    print(f"\nProcessing completed in {elapsed:.1f} seconds")

    # Check for output files
    output_files = []
    for root, dirs, files in os.walk(output_dir):
        for f in files:
            output_files.append(os.path.join(root, f))

    if output_files:
        print(f"\nOutput files generated: {len(output_files)}")
        for f in output_files[:10]:
            print(f"  {f}")
        print("\nSUCCESS: MinerU produced output")
    else:
        print("\nFAILURE: No output files generated")

except Exception as e:
    elapsed = time.time() - start
    print(f"\nERROR after {elapsed:.1f} seconds: {e}")
    import traceback
    traceback.print_exc()
PYTHON_SCRIPT

END_TIME=$(date +%s.%N)
ELAPSED=$(echo "$END_TIME - $START_TIME" | bc)

echo ""
echo "=== Test Summary ==="
echo "Total elapsed time: ${ELAPSED}s"
echo "Results saved to: $OUTPUT_DIR"

# Check if output was generated
if ls "$OUTPUT_DIR"/*_content_list.json 2>/dev/null || ls "$OUTPUT_DIR"/*/*_content_list.json 2>/dev/null; then
    echo "STATUS: SUCCESS"
    exit 0
else
    echo "STATUS: FAILURE (no output files)"
    exit 1
fi
