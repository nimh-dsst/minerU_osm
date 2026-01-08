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
- `~/helix_mnt_data/osm/datafiles/` - Registry, manifests, results
- `~/helix_mnt_nimh_scratch/adamt/osm/datalad-osm/` - PDFs and outputs

See `~/claude/osm/docs/HPC_SOPS.md` for mount setup instructions.

## Current Status (2025-01-07)

### Processing Results

| Metric | Value |
|--------|-------|
| Result CSVs: "completed" | 253,443 |
| Actual output directories | 134,688 |
| Silent failures (no output) | ~122K |
| Explicit failures (timeout) | 769 |

**Root cause (confirmed 2025-01-07):** P100 GPUs silently fail because container's PyTorch 2.9.1+cu128 only supports compute capability 7.0+. P100 (compute cap 6.0) is incompatible. See `docs/TROUBLESHOOTING_SILENT_FAILURES.md`.

**Working GPU types:** K80 (CPU fallback), V100, V100x, A100. **DO NOT use P100.**

**Next step:** Re-run ~122K failed PDFs on working GPU types (exclude P100).

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

- **Container:** `/data/adamt/containers/mineru.sif` (6.5 GB)
- **Registry:** `/data/adamt/osm/datafiles/mineru_registry.duckdb` (450K PDFs with file sizes)
- **Manifests:**
  - `mineru_manifest_full.csv` - All 450K PDFs
  - `mineru_manifest_small.csv` - PDFs <5MB (358K)
  - `mineru_manifest_large.csv` - PDFs ≥5MB (67K)
- **Results:** `mineru_results_v2/`, `mineru_results_large/` - Per-chunk CSVs
- **Logs:** `mineru_logs/{small,large}/`

## Key Scripts

### Processing Script (Fixed 2025-01-06)

`scripts/process_pdfs_mineru.py` - Fixed two bugs:
1. **False "completed" status:** Now verifies output files exist before marking success
2. **Double-nested directories:** Now outputs to `{prefix}/{pmid}/auto/` (not `{prefix}/{pmid}/{pmid}/auto/`)

### Registry

```bash
# Check status
/data/adamt/osm/venvHPC/bin/python scripts/mineru_registry.py \
    --db /data/adamt/osm/datafiles/mineru_registry.duckdb status

# Export pending
/data/adamt/osm/venvHPC/bin/python scripts/mineru_registry.py \
    --db /data/adamt/osm/datafiles/mineru_registry.duckdb \
    export-pending -o pending.csv
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
