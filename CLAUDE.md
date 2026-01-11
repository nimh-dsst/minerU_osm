# CLAUDE.md

## Repository Overview

`minerU_osm` converts PubMed Open Access PDFs to structured JSON using MinerU on NIH Biowulf HPC. This is a standalone repository separate from `osm-pipeline`.

## Path Variables

```bash
# EC2/Curium
export MINERU_DIR=$HOME/claude/osm/minerU_osm

# HPC (Biowulf)
export MINERU_DIR=/data/adamt/osm/minerU_osm
export PDF_DIR=/data/NIMH_scratch/adamt/osm/datalad-osm/pdfs
export OUTPUT_DIR=/data/NIMH_scratch/adamt/osm/datalad-osm/minerU_out
```

## Local Access via CIFS (gio mount)

Access HPC filesystems locally via symlinks:

```bash
~/helix_mnt_data/         -> /data/adamt/ on HPC
~/helix_mnt_home/         -> /home/adamt/ on HPC
~/helix_mnt_nimh_scratch/ -> /data/NIMH_scratch/ on HPC
```

Example paths:
- `~/helix_mnt_data/osm/minerU_osm/` - This repository on HPC
- `~/helix_mnt_nimh_scratch/adamt/osm/datalad-osm/duckdbs/` - Registry database
- `~/helix_mnt_nimh_scratch/adamt/osm/datalad-osm/` - PDFs and outputs

See `~/claude/osm/docs/HPC_SOPS.md` for mount setup instructions.

## Current Status (2025-01-11)

### Processing Results

| Status | Count | Percent |
|--------|-------|---------|
| Completed | 303,750 | 67.5% |
| Failed | 2,015 | 0.4% |
| Pending | 144,210 | 32.0% |
| **Total** | **449,975** | |

**Active job:** Hybrid backend processing (job 9213073) running on V100/V100x/A100 GPUs.
- Progress: ~800/5000 chunks (16%) after ~12 hours
- Rate: ~65 chunks/hour
- ETA: ~2.5 days remaining (~Jan 13)
- Success rate: ~99% with 1800s timeout (up from 70% with 600s timeout)

**Backend comparison:** See `docs/GPU_BACKEND_COMPARISON.md` for detailed analysis of pipeline vs vlm vs hybrid backends.

### Output Structure

After cleanup, outputs are organized as:
```
minerU_out/{prefix}/{pmid}/auto/
├── {pmid}_content_list.json
├── {pmid}_middle.json
├── {pmid}.md
├── {pmid}_model.json
└── images/
```

## Key Files

- **Containers:**
  - `mineru_2.7.1.sif` - MinerU 2.7.1, PyTorch 2.9.1 (V100/A100, all backends)
  - `mineru_p100.sif` - MinerU 2.7.1, PyTorch 2.3.1+cu118 (P100 compatible)
  - `mineru.sif` - MinerU 2.6.8 (legacy, pipeline only)
- **Registry:** `/data/NIMH_scratch/adamt/osm/datalad-osm/duckdbs/mineru_registry.duckdb` (450K PDFs with file sizes)
- **Results:** `mineru_results_v2/`, `mineru_results_hybrid/` - Per-chunk CSVs
- **Logs:** `mineru_logs/hybrid_*/`

## Key Scripts

### Processing Script (Fixed 2025-01-06)

`scripts/process_pdfs_mineru.py` - Fixed two bugs:
1. **False "completed" status:** Now verifies output files exist before marking success
2. **Double-nested directories:** Now outputs to `{prefix}/{pmid}/auto/` (not `{prefix}/{pmid}/{pmid}/auto/`)

### Registry

```bash
# Check status
/data/adamt/osm/venvHPC/bin/python scripts/mineru_registry.py \
    --db /data/NIMH_scratch/adamt/osm/datalad-osm/duckdbs/mineru_registry.duckdb status

# Scan for new PDFs and add to registry
/data/adamt/osm/venvHPC/bin/python scripts/mineru_registry.py \
    --db /data/NIMH_scratch/adamt/osm/datalad-osm/duckdbs/mineru_registry.duckdb \
    scan-pdfs --pdf-dir /data/NIMH_scratch/adamt/osm/datalad-osm/pdfs

# Export pending
/data/adamt/osm/venvHPC/bin/python scripts/mineru_registry.py \
    --db /data/NIMH_scratch/adamt/osm/datalad-osm/duckdbs/mineru_registry.duckdb \
    export-pending -o pending.csv

# Update from results
/data/adamt/osm/venvHPC/bin/python scripts/mineru_registry.py \
    --db /data/NIMH_scratch/adamt/osm/datalad-osm/duckdbs/mineru_registry.duckdb \
    update --results /path/to/results.csv
```

## HPC Submission

**IMPORTANT:** Use timestamped log directories to preserve logs. Test GPU compatibility before bulk runs.

```bash
# Create timestamped log directory
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Small PDFs (<5MB) - 40 PDFs/chunk, 2hr limit
# Use V100 for speed, K80 for availability. DO NOT use P100.
swarm -f /data/adamt/osm/datafiles/mineru_small.swarm \
    -g 64 -t 16 --time 02:00:00 \
    --partition gpu --gres=gpu:k80:1 \
    --logdir /data/adamt/osm/datafiles/mineru_logs/small_$TIMESTAMP

# Large PDFs (≥5MB) - 20 PDFs/chunk, 4hr limit
swarm -f /data/adamt/osm/datafiles/mineru_large.swarm \
    -g 64 -t 16 --time 04:00:00 \
    --partition gpu --gres=gpu:k80:1 \
    --logdir /data/adamt/osm/datafiles/mineru_logs/large_$TIMESTAMP
```

## GPU Compatibility (Confirmed 2025-01-07)

| GPU Type | Works | Mode | Time/PDF |
|----------|-------|------|----------|
| K80 | Yes | CPU fallback | ~3.5 min |
| P100 | **NO** | Silent fail | ~30s |
| V100 | Yes | GPU | ~1 min |
| V100x | Yes | GPU | ~1 min |
| A100 | Yes | GPU | ~51s |

- **P100 is broken:** PyTorch 2.9.1+cu128 requires compute cap 7.0+. P100 (6.0) fails silently.
- **K80 works via CPU fallback:** Slower but functional.
- **NIMH QOS:** `--qos=gpunimh2025.1` is optional

## Monitoring

```bash
squeue -u $USER                    # Check job status
ls $OUTPUT_DIR | wc -l             # Count processed PDFs
tail -f $LOG_DIR/test/swarm_*.o    # Watch output logs

# GPU utilization across all running jobs
bash /data/adamt/osm/minerU_osm/scripts/gpustat.sh

# CPU/memory for specific job
jobload -j JOBID
```

## Performance Notes

- **V100/V100x/A100:** ~1 min/PDF (GPU mode)
- **K80:** ~3.5 min/PDF (CPU fallback mode)
- **P100:** ~30 sec (silent failure - no output)
- **Silent failure indicator:** Processing time <50 sec = no actual processing
- **NIMH QOS:** Separate GPU quota from standard 56-GPU limit

## Known Issues

See `docs/TROUBLESHOOTING_SILENT_FAILURES.md` for details on:
- **Root cause:** P100 GPUs (compute cap 6.0) silently fail - container needs compute cap 7.0+
- **Silent failure indicator:** Processing time <50s = failure, >100s = success
- **Log preservation:** Always use timestamped log directories
