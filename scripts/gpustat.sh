#!/bin/bash
# gpustat.sh - Collect GPU utilization across running GPU jobs
# Usage: gpustat.sh [-u USER] [-j JOBID]

USER_FILTER="${USER}"
JOB_FILTER=""

while getopts "u:j:h" opt; do
    case $opt in
        u) USER_FILTER="$OPTARG" ;;
        j) JOB_FILTER="$OPTARG" ;;
        h) echo "Usage: $0 [-u USER] [-j JOBID]"; exit 0 ;;
    esac
done

# Get unique nodes with running GPU jobs
if [[ -n "$JOB_FILTER" ]]; then
    NODES=$(squeue -j "$JOB_FILTER" -h -t RUNNING -o "%N" | sort -u)
else
    NODES=$(squeue -u "$USER_FILTER" -p gpu -h -t RUNNING -o "%N" | sort -u)
fi

if [[ -z "$NODES" ]]; then
    echo "No running GPU jobs found"
    exit 0
fi

NODE_COUNT=$(echo "$NODES" | wc -w)
echo "Collecting GPU stats from $NODE_COUNT nodes..."
echo ""

# Header
printf "%-12s %-25s %8s %6s %10s %15s %8s\n" \
    "NODE" "GPU_TYPE" "UTIL" "TEMP" "POWER" "MEMORY" "PID"
printf "%s\n" "$(printf '=%.0s' {1..90})"

TOTAL_UTIL=0
TOTAL_GPUS=0

for NODE in $NODES; do
    # Run nvidia-smi on the node and parse output
    OUTPUT=$(ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=no "$NODE" \
        "nvidia-smi --query-gpu=name,utilization.gpu,temperature.gpu,power.draw,memory.used,memory.total --format=csv,noheader,nounits 2>/dev/null" 2>/dev/null)

    if [[ -z "$OUTPUT" ]]; then
        printf "%-12s %-25s %8s %6s %10s %15s %8s\n" \
            "$NODE" "ERROR" "-" "-" "-" "-" "-"
        continue
    fi

    # Get process info
    PIDS=$(ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=no "$NODE" \
        "nvidia-smi --query-compute-apps=pid --format=csv,noheader 2>/dev/null" 2>/dev/null | tr '\n' ',' | sed 's/,$//')
    [[ -z "$PIDS" ]] && PIDS="-"

    while IFS=',' read -r GPU_NAME UTIL TEMP POWER MEM_USED MEM_TOTAL; do
        # Trim whitespace
        GPU_NAME=$(echo "$GPU_NAME" | xargs)
        UTIL=$(echo "$UTIL" | xargs)
        TEMP=$(echo "$TEMP" | xargs)
        POWER=$(echo "$POWER" | xargs)
        MEM_USED=$(echo "$MEM_USED" | xargs)
        MEM_TOTAL=$(echo "$MEM_TOTAL" | xargs)

        # Truncate GPU name
        GPU_SHORT="${GPU_NAME:0:24}"

        # Format memory
        MEM_STR="${MEM_USED}/${MEM_TOTAL}MB"

        printf "%-12s %-25s %7s%% %5sC %9sW %15s %8s\n" \
            "$NODE" "$GPU_SHORT" "$UTIL" "$TEMP" "$POWER" "$MEM_STR" "$PIDS"

        # Accumulate for average
        if [[ "$UTIL" =~ ^[0-9]+$ ]]; then
            TOTAL_UTIL=$((TOTAL_UTIL + UTIL))
            TOTAL_GPUS=$((TOTAL_GPUS + 1))
        fi
    done <<< "$OUTPUT"
done

echo ""
printf "%s\n" "$(printf '=%.0s' {1..90})"

if [[ $TOTAL_GPUS -gt 0 ]]; then
    AVG_UTIL=$((TOTAL_UTIL / TOTAL_GPUS))
    echo "Summary: $TOTAL_GPUS GPUs, Average utilization: ${AVG_UTIL}%"
else
    echo "Summary: No GPU data collected"
fi
