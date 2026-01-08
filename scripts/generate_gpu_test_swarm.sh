#!/bin/bash
# Generate swarm file to test MinerU on all GPU types
# Usage: bash generate_gpu_test_swarm.sh

OUTPUT_DIR="/data/adamt/osm/datafiles"
SWARM_FILE="${OUTPUT_DIR}/mineru_gpu_test.swarm"
LOG_BASE="${OUTPUT_DIR}/mineru_logs/gpu_test"

# GPU types available on Biowulf
GPU_TYPES=("k80" "p100" "v100" "v100x" "a100")

echo "Generating GPU test swarm file: $SWARM_FILE"
echo ""

# Create swarm file with one test per GPU type
cat > "$SWARM_FILE" << 'EOF'
# MinerU GPU Compatibility Test Swarm
# Each line tests a different GPU type
# Submit with: swarm -f mineru_gpu_test.swarm -g 64 -t 16 --time 00:30:00 --partition gpu --logdir /data/adamt/osm/datafiles/mineru_logs/gpu_test
EOF

for gpu in "${GPU_TYPES[@]}"; do
    echo "export GPU_TYPE=$gpu && bash /data/adamt/osm/minerU_osm/scripts/test_gpu_compatibility.sh" >> "$SWARM_FILE"
done

echo "Generated swarm with ${#GPU_TYPES[@]} GPU type tests"
echo ""
echo "To submit tests for all GPU types, run separate swarms:"
echo ""
for gpu in "${GPU_TYPES[@]}"; do
    echo "# Test $gpu:"
    echo "swarm -f $SWARM_FILE -g 64 -t 16 --time 00:30:00 --partition gpu --gres=gpu:${gpu}:1 --logdir ${LOG_BASE}/${gpu}"
    echo ""
done

echo "Or submit individual sinteractive sessions for quick testing:"
echo ""
for gpu in "${GPU_TYPES[@]}"; do
    echo "# Quick test on $gpu:"
    echo "sinteractive --gres=gpu:${gpu}:1 --mem=64g --time=00:30:00"
    echo ""
done
