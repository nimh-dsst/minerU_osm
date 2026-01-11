#!/bin/bash
# Build MinerU container with P100 GPU support
#
# Run this on Curium (has Docker) then transfer to HPC.
#
# Usage:
#   bash build_p100_container.sh
#
# After build completes:
#   scp mineru_p100.sif helix:/data/adamt/containers/

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=========================================="
echo "Building MinerU P100 Container"
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
docker build -f Dockerfile.p100 -t mineru:p100 .

echo ""
echo "Step 2: Exporting Docker image to tarball..."
docker save mineru:p100 -o mineru_p100.tar

echo ""
echo "Step 3: Converting to Apptainer/Singularity format..."
$CONTAINER_CMD build mineru_p100.sif docker-archive://mineru_p100.tar

echo ""
echo "Step 4: Cleaning up tarball..."
rm -f mineru_p100.tar

echo ""
echo "=========================================="
echo "Build complete: mineru_p100.sif"
echo "=========================================="
echo ""
echo "File size: $(du -h mineru_p100.sif | cut -f1)"
echo ""
echo "Next steps:"
echo "1. Transfer to HPC:"
echo "   scp mineru_p100.sif helix:/data/adamt/containers/"
echo ""
echo "2. Test on P100 node:"
echo "   ssh -q biowulf"
echo "   sinteractive --gres=gpu:p100:1 --mem=64g --time=00:30:00"
echo "   module load apptainer && source /usr/local/current/singularity/app_conf/sing_binds"
echo "   apptainer exec --nv /data/adamt/containers/mineru_p100.sif python3 -c \\"
echo "       \"import torch; print(f'CUDA: {torch.cuda.is_available()}, Device: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else None}')\""
echo ""
echo "3. Run full GPU compatibility test:"
echo "   bash /data/adamt/osm/minerU_osm/scripts/test_gpu_compatibility.sh"
echo "   # (modify CONTAINER path to use mineru_p100.sif)"
