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

## Key Files

- **Container:** `/data/adamt/containers/mineru.sif` (6.5 GB)
- **Registry:** `/data/adamt/osm/datafiles/mineru_registry.duckdb` (450K PDFs with file sizes)
- **Manifests:**
  - `mineru_manifest_full.csv` - All 450K PDFs
  - `mineru_manifest_small.csv` - PDFs <5MB (358K)
  - `mineru_manifest_large.csv` - PDFs ≥5MB (67K)
- **Swarms:**
  - `mineru_small.swarm` - Small PDFs, 40/chunk
  - `mineru_large.swarm` - Large PDFs, 20/chunk, NIMH QOS
- **Results:** `mineru_results_v2/` - Per-chunk CSVs
- **Logs:** `mineru_logs/{small,large}/`

## Key Scripts

### Swarm Generation

```bash
cd /data/adamt/osm/minerU_osm
bash scripts/generate_mineru_swarm.sh \
    --manifest /data/adamt/osm/datafiles/mineru_manifest_scratch.csv \
    --chunk-size 100 \
    --output-dir /data/NIMH_scratch/adamt/osm/datalad-osm/minerU_out \
    --output-swarm /data/adamt/osm/datafiles/mineru_full.swarm
```

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

## Output Format

MinerU produces per-PDF (in `{OUTPUT_DIR}/{pmid}/{pmid}/auto/`):
- `{pmid}_content_list.json` - Structured elements (~140 KB)
- `{pmid}_middle.json` - Intermediate representation (~2.2 MB)
- `{pmid}.md` - Clean markdown (~75 KB)
- `{pmid}_model.json` - Model output (~600 KB)
- `images/` - Extracted images

**Total per PDF:** ~10 MB

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

## Active Jobs (as of 2025-01-05)

| Job ID | Description | Chunks | QOS | Status |
|--------|-------------|--------|-----|--------|
| 8644416 | Small PDFs (<5MB) | 8,949 | global | ~54% complete |
| 8787036 | Large PDFs (≥5MB, sorted by size) | 3,366 | gpunimh2025 | Running |

## Performance Notes

- **K80:** ~120-160 sec/PDF
- **P100:** ~60 sec/PDF
- **A100/V100:** ~12-15 sec/PDF (10x faster than K80)
- **NIMH QOS:** Separate GPU quota from standard 56-GPU limit
