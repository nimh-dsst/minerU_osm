#!/bin/bash
#
# Generate a Biowulf swarm file for MinerU PDF processing.
#
# Usage:
#   ./generate_mineru_swarm.sh \
#       --manifest /data/adamt/osm/datafiles/pdf_manifest.csv \
#       --chunk-size 100 \
#       --gpu-type a100 \
#       --output-swarm mineru.swarm
#

set -euo pipefail

# Default values
CHUNK_SIZE=100
GPU_TYPE="v100"
CONTAINER="/data/adamt/containers/mineru.sif"
OUTPUT_DIR="/data/adamt/osm/datafiles/mineru_output"
SCRIPT_DIR="/data/adamt/osm/minerU_osm/scripts"
RESULTS_DIR="/data/adamt/osm/datafiles/mineru_results"
LOG_DIR="/data/adamt/osm/datafiles/mineru_logs"
OUTPUT_SWARM=""
MANIFEST=""

# Help message
usage() {
    cat << EOF
Generate a Biowulf swarm file for MinerU PDF processing.

Usage:
    $(basename "$0") [OPTIONS]

Required:
    --manifest FILE         CSV manifest with pmid,pdf_path columns
    --output-swarm FILE     Output swarm file path

Options:
    --chunk-size N          PDFs per job (default: $CHUNK_SIZE)
    --gpu-type TYPE         GPU type: v100, a100, p100 (default: $GPU_TYPE)
    --container PATH        Path to MinerU container (default: $CONTAINER)
    --output-dir DIR        Output directory for processed files (default: $OUTPUT_DIR)
    --results-dir DIR       Directory for per-chunk result files (default: $RESULTS_DIR)
    --script-dir DIR        Directory containing processing script (default: $SCRIPT_DIR)
    -h, --help              Show this help message

Example:
    $(basename "$0") \\
        --manifest /data/adamt/osm/datafiles/pdf_manifest.csv \\
        --chunk-size 100 \\
        --gpu-type a100 \\
        --output-swarm mineru.swarm

After generating, submit with:
    swarm -f mineru.swarm \\
        -g 64 -t 16 --time 04:00:00 \\
        --partition gpu --gres=gpu:a100:1 \\
        --qos=gpunimh2025.1 \\
        --logdir logs/mineru
EOF
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --manifest)
            MANIFEST="$2"
            shift 2
            ;;
        --chunk-size)
            CHUNK_SIZE="$2"
            shift 2
            ;;
        --gpu-type)
            GPU_TYPE="$2"
            shift 2
            ;;
        --container)
            CONTAINER="$2"
            shift 2
            ;;
        --output-dir)
            OUTPUT_DIR="$2"
            shift 2
            ;;
        --results-dir)
            RESULTS_DIR="$2"
            shift 2
            ;;
        --script-dir)
            SCRIPT_DIR="$2"
            shift 2
            ;;
        --output-swarm)
            OUTPUT_SWARM="$2"
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            usage
            exit 1
            ;;
    esac
done

# Validate required arguments
if [[ -z "$MANIFEST" ]]; then
    echo "Error: --manifest is required"
    usage
    exit 1
fi

if [[ -z "$OUTPUT_SWARM" ]]; then
    echo "Error: --output-swarm is required"
    usage
    exit 1
fi

if [[ ! -f "$MANIFEST" ]]; then
    echo "Error: Manifest file not found: $MANIFEST"
    exit 1
fi

# Count PDFs in manifest (excluding header)
TOTAL_PDFS=$(($(wc -l < "$MANIFEST") - 1))

if [[ $TOTAL_PDFS -le 0 ]]; then
    echo "Error: No PDFs found in manifest"
    exit 1
fi

# Calculate number of chunks
NUM_CHUNKS=$(( (TOTAL_PDFS + CHUNK_SIZE - 1) / CHUNK_SIZE ))

echo "======================================================================"
echo "GENERATING MINERU SWARM FILE"
echo "======================================================================"
echo "Manifest:      $MANIFEST"
echo "Total PDFs:    $TOTAL_PDFS"
echo "Chunk size:    $CHUNK_SIZE"
echo "Num chunks:    $NUM_CHUNKS"
echo "GPU type:      $GPU_TYPE"
echo "Container:     $CONTAINER"
echo "Output dir:    $OUTPUT_DIR"
echo "Results dir:   $RESULTS_DIR"
echo "Output swarm:  $OUTPUT_SWARM"
echo "======================================================================"

# Validate GPU type
case $GPU_TYPE in
    v100|a100|p100|v100x)
        ;;
    *)
        echo "Warning: Unknown GPU type '$GPU_TYPE'. Proceeding anyway."
        ;;
esac

# Create swarm file
echo "Generating swarm file..."

> "$OUTPUT_SWARM"

for ((i = 0; i < NUM_CHUNKS; i++)); do
    START_INDEX=$((i * CHUNK_SIZE))
    CHUNK_ID=$(printf "%05d" $i)

    # Generate command (module load required on Biowulf)
    # Source sing_binds for proper Biowulf filesystem bindings (best practice per HPC docs)
    CMD="module load apptainer && source /usr/local/current/singularity/app_conf/sing_binds && apptainer exec --nv $CONTAINER python3 $SCRIPT_DIR/process_pdfs_mineru.py"
    CMD="$CMD --manifest $MANIFEST"
    CMD="$CMD --start-index $START_INDEX --count $CHUNK_SIZE"
    CMD="$CMD --output-dir $OUTPUT_DIR"
    CMD="$CMD --results-file $RESULTS_DIR/chunk_${CHUNK_ID}.csv"
    CMD="$CMD --skip-existing"

    echo "$CMD" >> "$OUTPUT_SWARM"
done

echo ""
echo "Generated $NUM_CHUNKS swarm commands"
echo "Swarm file: $OUTPUT_SWARM"
echo ""
echo "======================================================================"
echo "SUBMISSION INSTRUCTIONS"
echo "======================================================================"
echo ""
echo "1. Create required directories:"
echo "   mkdir -p $OUTPUT_DIR"
echo "   mkdir -p $RESULTS_DIR"
echo "   mkdir -p $LOG_DIR"
echo ""
echo "2. Test with a few chunks first:"
echo "   head -5 $OUTPUT_SWARM > ${OUTPUT_SWARM%.swarm}_test.swarm"
echo "   swarm -f ${OUTPUT_SWARM%.swarm}_test.swarm \\"
echo "       -g 64 -t 16 --time 02:00:00 \\"
echo "       --partition gpu --gres=gpu:1 \\"
echo "       --logdir $LOG_DIR/test"
echo ""
echo "3. Full production run:"
echo "   swarm -f $OUTPUT_SWARM \\"
echo "       -g 64 -t 16 --time 06:00:00 \\"
echo "       --partition gpu --gres=gpu:1 \\"
echo "       --logdir $LOG_DIR/full"
echo ""
echo "   # Optional: add --qos=gpunimh2025.1 for NIMH priority (uses compute allocation)"
echo "   # K80 GPUs typically have low demand, so standard priority usually works fine."
echo ""
echo "4. Monitor progress:"
echo "   sjobs        # Check running jobs"
echo "   squeue -u \$USER | grep gpu"
echo ""
echo "5. After completion, merge results:"
echo "   python $SCRIPT_DIR/merge_mineru_results.py \\"
echo "       --input-dir $RESULTS_DIR \\"
echo "       --output $OUTPUT_DIR/mineru_combined.parquet"
echo ""
echo "======================================================================"
