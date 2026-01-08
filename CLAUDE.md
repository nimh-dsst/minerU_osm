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

**Preliminary finding:** Silent failures strongly correlate with cn23xx nodes (100% failure, 13.7s avg). cn30xx/cn4xxx nodes work correctly (~0.2% failure, 190s avg). Need to verify GPU type mapping. See `docs/TROUBLESHOOTING_SILENT_FAILURES.md`.

**Next step:** Test all 5 GPU types (k80, p100, v100, v100x, a100) with `scripts/test_gpu_compatibility.sh` before re-running failed PDFs.

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
# Specify GPU type after testing (k80, p100, v100, v100x, a100)
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

## GPU Requirements

- **MinerU pipeline backend:** 6GB VRAM minimum
- **Processing time:** ~3 min/PDF on working GPUs
- **GPU compatibility:** Test all types before bulk runs - cn23xx nodes show 100% failure (see troubleshooting doc)
- **Available types:** k80, p100, v100, v100x, a100
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

- **Working GPUs (cn30xx, cn4xxx):** ~190-200 sec/PDF (actual processing)
- **Failing nodes (cn23xx):** 100% silent failure - ~14 sec (container startup only)
- **Silent failure indicator:** Processing time <50 sec = container startup only, no actual processing
- **NIMH QOS:** Separate GPU quota from standard 56-GPU limit

## Known Issues

See `docs/TROUBLESHOOTING_SILENT_FAILURES.md` for details on:
- **Preliminary finding:** cn23xx nodes fail silently (100%), cn30xx/cn4xxx work (~0.2% failure)
- **Next step:** Test all 5 GPU types to verify which work
- Processing time correlation: <50s = failure, >100s = success
- **Log preservation:** Always use timestamped log directories
