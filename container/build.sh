#!/bin/bash
#
# Build MinerU Apptainer container on Biowulf
#
# Usage:
#   # On helix/biowulf
#   sinteractive --gres=gpu:v100:1 --mem=32g --time=02:00:00
#   cd /data/adamt/osm/minerU_osm/container
#   ./build.sh
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

OUTPUT_DIR="${1:-/data/adamt/containers}"
OUTPUT_SIF="$OUTPUT_DIR/mineru.sif"

echo "======================================================================"
echo "BUILDING MINERU CONTAINER"
echo "======================================================================"
echo "Definition: $SCRIPT_DIR/mineru.def"
echo "Output:     $OUTPUT_SIF"
echo "======================================================================"

# Load apptainer module if on Biowulf
if command -v module &> /dev/null; then
    module load apptainer 2>/dev/null || true
fi

# Create output directory
mkdir -p "$OUTPUT_DIR"

# Build container
echo ""
echo "Starting build (this may take 10-20 minutes)..."
echo ""

apptainer build --fakeroot "$OUTPUT_SIF" mineru.def

echo ""
echo "======================================================================"
echo "BUILD COMPLETE"
echo "======================================================================"
echo "Container: $OUTPUT_SIF"
echo ""
echo "Test with:"
echo "  apptainer exec --nv $OUTPUT_SIF python3 -c 'import mineru; print(mineru.__version__)'"
echo ""
echo "Run MinerU:"
echo "  apptainer exec --nv $OUTPUT_SIF mineru -p input.pdf -o output/"
echo "======================================================================"
