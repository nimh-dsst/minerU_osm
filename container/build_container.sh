#!/bin/bash
# Build MinerU container (MinerU 2.7.1 with vlm/hybrid backend support)
#
# Run this on Curium (has Docker) then transfer to HPC.
#
# Usage:
#   bash build_container.sh
#
# After build completes:
#   scp mineru.sif helix:/data/adamt/containers/mineru_2.7.1.sif

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=========================================="
echo "Building MinerU 2.7.1 Container"
echo "=========================================="
echo "Directory: $SCRIPT_DIR"
echo ""

# Check for Docker
if ! command -v docker &> /dev/null; then
    echo "Error: Docker not found. Run this on a machine with Docker installed."
    exit 1
fi

# Check for Apptainer/Singularity
if command -v apptainer &> /dev/null; then
    CONTAINER_CMD="apptainer"
elif command -v singularity &> /dev/null; then
    CONTAINER_CMD="singularity"
else
    echo "Error: Neither apptainer nor singularity found."
    exit 1
fi

echo "Using container command: $CONTAINER_CMD"
echo ""

# Build Docker image
echo "Step 1: Building Docker image..."
docker build -f Dockerfile -t mineru:2.7.1 .

echo ""
echo "Step 2: Exporting Docker image to tarball..."
docker save mineru:2.7.1 -o mineru_2.7.1.tar

echo ""
echo "Step 3: Converting to Apptainer/Singularity format..."
$CONTAINER_CMD build mineru_2.7.1.sif docker-archive://mineru_2.7.1.tar

echo ""
echo "Step 4: Cleaning up tarball..."
rm -f mineru_2.7.1.tar

echo ""
echo "=========================================="
echo "Build complete: mineru_2.7.1.sif"
echo "=========================================="
echo ""
echo "File size: $(du -h mineru_2.7.1.sif | cut -f1)"
echo ""
echo "Next steps:"
echo "1. Transfer to HPC:"
echo "   scp mineru_2.7.1.sif helix:/data/adamt/containers/"
echo ""
echo "2. Test backends:"
echo "   ssh biowulf"
echo "   module load apptainer && source /usr/local/current/singularity/app_conf/sing_binds"
echo "   apptainer exec --nv /data/adamt/containers/mineru_2.7.1.sif mineru --help"
echo ""
echo "3. Verify supported backends include: pipeline, vlm-auto-engine, hybrid-auto-engine"
