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

## Current Status (2025-01-06)

### Processing Results (Before Cancellation)

| Metric | Value |
|--------|-------|
| Result CSVs: "completed" | 253,443 |
| Actual output directories | 134,688 |
| Silent failures (no output) | ~172K |
| Explicit failures (timeout) | 769 |

**Jobs cancelled** to investigate silent failure issue. Job 8644416 has 6 tasks still running.

**Issue discovered:** MinerU silently fails on ~47% of PDFs without raising exceptions. See `docs/TROUBLESHOOTING_SILENT_FAILURES.md`.

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

```bash
# Small PDFs (<5MB) - 40 PDFs/chunk, 2hr limit, standard priority
swarm -f /data/adamt/osm/datafiles/mineru_small.swarm \
    -g 64 -t 16 --time 02:00:00 \
    --partition gpu --gres=gpu:1 \
    --logdir /data/adamt/osm/datafiles/mineru_logs/small

# Large PDFs (≥5MB) - 20 PDFs/chunk, 4hr limit, NIMH priority
swarm -f /data/adamt/osm/datafiles/mineru_large.swarm \
    -g 64 -t 16 --time 04:00:00 \
    --partition gpu --gres=gpu:1 \
    --qos=gpunimh2025.1 \
    --logdir /data/adamt/osm/datafiles/mineru_logs/large
```

## GPU Requirements

- **MinerU pipeline backend:** 6GB VRAM minimum (K80 12GB works fine)
- **Processing time:** ~2.5 min/PDF on K80, faster on A100/V100
- **NIMH QOS:** `--qos=gpunimh2025.1` is optional; K80s have low demand

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

- **K80:** ~120-160 sec/PDF (actual processing)
- **P100:** ~60 sec/PDF
- **A100/V100:** ~12-15 sec/PDF (10x faster than K80)
- **Silent failure indicator:** Processing time <50 sec suggests no actual processing occurred
- **NIMH QOS:** Separate GPU quota from standard 56-GPU limit

## Known Issues

See `docs/TROUBLESHOOTING_SILENT_FAILURES.md` for details on:
- MinerU silent failures (~47% of PDFs)
- Processing time correlation with success
- Potential GPU-type correlation (to investigate)
