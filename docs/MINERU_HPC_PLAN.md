# MinerU HPC Processing Pipeline - Strategic Plan

## Overview

This document outlines a strategy for processing PubMed Open Access PDFs through MinerU on NIH Biowulf HPC to convert them to structured JSON/Markdown format. This is a standalone repository (`minerU_osm`) separate from the main `osm-pipeline`.

**Repository:** `/data/adamt/osm/minerU_osm`
**Input:** PDFs from datalad-osm (`/data/NIMH_scratch/adamt/osm/datalad-osm/pdfs/`)
**Output:** Structured JSON files (`/data/NIMH_scratch/adamt/osm/datalad-osm/minerU_out/`)

## Current State (Updated 2025-01-06)

| Metric | Value |
|--------|-------|
| Total PDFs in registry | 449,975 |
| Small PDFs (<5MB) | 382,657 |
| Large PDFs (≥5MB) | 67,318 |
| Container | Built (6.5 GB) at `/data/adamt/containers/mineru.sif` |
| Registry | `/data/NIMH_scratch/adamt/osm/datalad-osm/duckdbs/mineru_registry.duckdb` |

### Processing Results (Before Cancellation)

| Metric | Value |
|--------|-------|
| Result CSVs: "completed" | 253,443 |
| Actual output directories | 134,688 |
| Silent failures (no output) | ~172,631 |
| Explicit failures (timeout) | 769 |

**Critical Issue:** MinerU silently fails on ~47% of PDFs. See `TROUBLESHOOTING_SILENT_FAILURES.md`.

### Job Status

| Job ID | Description | Chunks | QOS | Status |
|--------|-------------|--------|-----|--------|
| 8644416 | Small PDFs (<5MB) | 8,949 | global | Cancelled (6 still running) |
| 8787036 | Large PDFs (≥5MB) | 3,366 | gpunimh2025 | Cancelled |

### Implementation Progress

| Phase | Status | Notes |
|-------|--------|-------|
| 1. Container | **Complete** | Built via Docker on Curium, converted to SIF |
| 2. Scripts | **Complete** | Fixed 2025-01-06: output verification, directory structure |
| 3. Registry | **Complete** | 449,975 PDFs with file sizes |
| 4. Small PDF swarm | **Cancelled** | Job 8644416, discovered silent failure issue |
| 5. Large PDF swarm | **Cancelled** | Job 8787036, pending failure investigation |
| 6. Output cleanup | **Complete** | Removed empty dirs, flattened structure |
| 7. Silent failure analysis | **In Progress** | ~47% failure rate discovered |
| 8. Re-run with fixed script | Pending | After root cause identified |

### Size Distribution

| Size Range | Count | Strategy |
|------------|-------|----------|
| <1MB | 116,559 | Small swarm (current) |
| 1-5MB | 266,098 | Small swarm (current) |
| 5-10MB | 46,580 | Large swarm (next) |
| >10MB | 20,738 | Large swarm (next) |

## Observed Performance Metrics

From production runs (Jobs 8372761, 8644416):

| GPU Type | Time per PDF | Nodes |
|----------|--------------|-------|
| K80 (cn30xx) | ~120-160 sec | Older, always available |
| A100/V100 (cn2xxx, cn4xxx) | ~12-15 sec | Newer, higher demand |

### Throughput (Job 8644416 - Small PDFs)

| Metric | Value |
|--------|-------|
| Concurrent GPUs | ~56 (QOS limit) |
| Chunks completed | 4,823 in 67 hours |
| Throughput | ~72 chunks/hour (~2,880 PDFs/hour) |
| Average per PDF | Variable (GPU-dependent) |

### Output Size per PDF

| File | Typical Size |
|------|-------------|
| `*_content_list.json` | ~140 KB |
| `*.md` | ~75 KB |
| `*_middle.json` | ~2.2 MB |
| `*_model.json` | ~600 KB |
| Layout PDFs + images | ~6-9 MB |
| **Total per PDF** | **~10 MB** |

**Estimated total storage:** 163K PDFs × 10 MB = **~1.6 TB**

## Revised Time Estimates

### Based on Observed K80 Performance

| Scenario | GPUs | Time per PDF | Wall Clock |
|----------|------|--------------|------------|
| K80 (slowest) | 64 | 2.5 min | **~4.5 days** |
| P100/V100 (est. 1.5x) | 64 | 1.7 min | **~3 days** |
| A100 (est. 2x) | 64 | 1.25 min | **~2.2 days** |

### Calculation Details

```
163,315 PDFs ÷ 64 GPUs = 2,552 PDFs per GPU
K80: 2,552 × 2.5 min = 6,380 min = 106 hours = 4.4 days
A100: 2,552 × 1.25 min = 3,190 min = 53 hours = 2.2 days
```

### Compute Unit Cost

Per MOU Appendix A charge rates:
- K80: ~2.5 min × 163,315 PDFs = 6,805 GPU-hours
- A100: Charge rate is higher per hour but fewer hours needed
- **Estimated total:** 5,000-10,000 GPU-hours = **5-10M compute units** (~5-10% of quota)

## MinerU Capabilities

MinerU ([opendatalab/MinerU](https://github.com/opendatalab/MinerU)) converts PDFs to LLM-ready formats:

- **Layout analysis** - Element detection (text, tables, figures)
- **OCR** - Multilingual text recognition
- **Table parsing** - Structure recognition
- **Formula recognition** - Mathematical notation
- **Reading order** - Logical content sequencing
- **Output formats:** Markdown + JSON (with bounding boxes, element types)

### Backends

| Backend | VRAM Required | Use Case |
|---------|---------------|----------|
| `pipeline` | 6 GB min | Fast CV-based (used for bulk processing) |
| `vlm` | 8 GB min | Higher accuracy, slower |
| `sglang` | 16+ GB | Accelerated VLM inference |

## Biowulf GPU Resources

### Available GPU Types (as of 2024-12-31)

| GPU Type | VRAM | Nodes | Status |
|----------|------|-------|--------|
| A100 | 80 GB | 83 | 81 mixed, 1 allocated, 1 drained |
| V100x | 32 GB | 52 | 31 mixed, 19 allocated, 2 drained |
| V100 | 16 GB | 7 | 5 mixed, 2 allocated |
| P100 | 16 GB | 46 | 23 mixed, 13 allocated, 10 drained |
| K80 | 12 GB | 95 | Various states, often available |

**Note:** K80 GPUs are older but frequently available. They have sufficient VRAM (12GB) for MinerU pipeline backend.

### NIMH Priority Access

Per GPU allocation MOU (see `docs/email_re_gpu_quos.txt`):

- **QOS:** `--qos=gpunimh2025.1`
- **GPU limit:** 64 GPUs simultaneously (vs 56 standard)
- **Compute units:** ~90 million (FY2025-26 combined)
- **Priority:** Ahead of all non-buy-in jobs

**When to use NIMH QOS:**
- Requesting A100/V100 (high demand, often queued)
- Time-sensitive processing needs
- K80 queue becomes unusually congested

**When to skip NIMH QOS:**
- Using any available GPU (`--gres=gpu:1`) - K80s typically have low demand
- Non-urgent bulk processing
- Preserving compute allocation for other NIMH projects

## Directory Structure

```
/data/adamt/osm/minerU_osm/           # Repository
├── scripts/
│   ├── generate_mineru_swarm.sh      # Swarm file generator
│   ├── process_pdfs_mineru.py        # Main processing script
│   ├── merge_mineru_results.py       # Merge output JSONs
│   └── mineru_registry.py            # DuckDB tracking
├── container/
│   ├── mineru.def                    # Apptainer definition
│   ├── Dockerfile                    # Docker build file
│   └── build.sh                      # Build script
└── docs/
    ├── MINERU_HPC_PLAN.md            # This document
    └── email_re_gpu_quos.txt         # GPU allocation info

/data/adamt/containers/mineru.sif     # Built container (6.5 GB)

/data/adamt/osm/datafiles/            # Data files
├── mineru_registry.duckdb            # Processing tracker (with file sizes)
├── mineru_manifest_full.csv          # Full manifest (450K PDFs)
├── mineru_manifest_small.csv         # Small PDFs <5MB (358K)
├── mineru_manifest_large.csv         # Large PDFs ≥5MB (67K)
├── mineru_small.swarm                # Small PDF swarm (8,949 chunks)
├── mineru_large.swarm                # Large PDF swarm (pending)
├── mineru_results/                   # Old swarm result CSVs
├── mineru_results_v2/                # Current swarm result CSVs
└── mineru_logs/                      # Swarm job logs
    ├── small/                        # Small PDF swarm logs
    └── large/                        # Large PDF swarm logs

/data/NIMH_scratch/adamt/osm/datalad-osm/
├── pdfs/{prefix}/{pmid}.pdf          # Input PDFs (organized by first 3 digits)
└── minerU_out/{prefix}/{pmid}/       # Output JSON/MD files (same structure)
```

## Commands Reference

### Container Build (on Curium)

```bash
cd ~/claude/osm/minerU_osm/container
docker build -t mineru:latest .
docker save mineru:latest -o build/mineru-docker.tar
apptainer build build/mineru.sif docker-archive://build/mineru-docker.tar
scp build/mineru.sif helix:/data/adamt/containers/
```

### Registry Management

```bash
# Initialize (already done)
/data/adamt/osm/venvHPC/bin/python /data/adamt/osm/minerU_osm/scripts/mineru_registry.py \
    --db /data/NIMH_scratch/adamt/osm/datalad-osm/duckdbs/mineru_registry.duckdb \
    init --manifest /data/adamt/osm/datafiles/mineru_manifest_scratch.csv

# Check status
/data/adamt/osm/venvHPC/bin/python /data/adamt/osm/minerU_osm/scripts/mineru_registry.py \
    --db /data/NIMH_scratch/adamt/osm/datalad-osm/duckdbs/mineru_registry.duckdb status

# Export pending
/data/adamt/osm/venvHPC/bin/python /data/adamt/osm/minerU_osm/scripts/mineru_registry.py \
    --db /data/NIMH_scratch/adamt/osm/datalad-osm/duckdbs/mineru_registry.duckdb \
    export-pending -o pending.csv
```

### Swarm Generation

```bash
cd /data/adamt/osm/minerU_osm
bash scripts/generate_mineru_swarm.sh \
    --manifest /data/adamt/osm/datafiles/mineru_manifest_scratch.csv \
    --chunk-size 100 \
    --output-dir /data/NIMH_scratch/adamt/osm/datalad-osm/minerU_out \
    --output-swarm /data/adamt/osm/datafiles/mineru_full.swarm
```

### Job Submission

**Note on QOS:** The `--qos=gpunimh2025.1` flag is optional. K80 GPUs typically have low
demand, so standard priority usually works fine. Use the NIMH QOS only when:
- You need A100/V100 specifically (high competition)
- K80 queue becomes congested
- Time-sensitive processing

```bash
# Test (5 chunks = 500 PDFs) - standard priority
head -5 /data/adamt/osm/datafiles/mineru_full.swarm > /data/adamt/osm/datafiles/mineru_test.swarm
swarm -f /data/adamt/osm/datafiles/mineru_test.swarm \
    -g 64 -t 16 --time 02:00:00 \
    --partition gpu --gres=gpu:1 \
    --logdir /data/adamt/osm/datafiles/mineru_logs/test

# Full production (1,634 chunks) - standard priority, uses any available GPU
swarm -f /data/adamt/osm/datafiles/mineru_full.swarm \
    -g 64 -t 16 --time 06:00:00 \
    --partition gpu --gres=gpu:1 \
    --logdir /data/adamt/osm/datafiles/mineru_logs/full

# Alternative: with NIMH priority (uses compute allocation, guaranteed priority)
swarm -f /data/adamt/osm/datafiles/mineru_full.swarm \
    -g 64 -t 16 --time 06:00:00 \
    --partition gpu --gres=gpu:1 \
    --qos=gpunimh2025.1 \
    --logdir /data/adamt/osm/datafiles/mineru_logs/full
```

### Monitoring

```bash
# Check job status
squeue -u $USER
sacct -j JOBID --format=JobID,State,Elapsed,MaxRSS

# Count processed PDFs
ls /data/NIMH_scratch/adamt/osm/datalad-osm/minerU_out/ | wc -l

# Check logs
tail -f /data/adamt/osm/datafiles/mineru_logs/test/swarm_JOBID_0.o
cat /data/adamt/osm/datafiles/mineru_logs/test/swarm_JOBID_0.e
```

### Post-Processing

```bash
# Merge results
/data/adamt/osm/venvHPC/bin/python /data/adamt/osm/minerU_osm/scripts/merge_mineru_results.py \
    --input-dir /data/adamt/osm/datafiles/mineru_results \
    --output /data/NIMH_scratch/adamt/osm/datalad-osm/minerU_out/mineru_combined.parquet \
    --update-registry
```

## Risk Mitigation

### Timeout Issues

- **Observed:** 100 PDFs takes ~4 hours on K80
- **Solution:** Set `--time 06:00:00` for safety margin
- **Fallback:** Failed chunks can be retried via registry

### GPU Availability

- **Issue:** V100 nodes often fully occupied
- **Solution:** Use `--gres=gpu:1` (any GPU type) instead of specific type
- **Result:** Jobs run on available K80/P100/A100 nodes

### Filesystem Bindings

- **Issue:** Apptainer auto-binds may fail on some nodes
- **Solution:** Source `/usr/local/current/singularity/app_conf/sing_binds` before exec
- **Note:** This is Biowulf best practice per HPC documentation

### Storage

- **Observed:** ~10 MB per PDF
- **Total needed:** ~1.6 TB for 163K PDFs
- **Location:** `/data/NIMH_scratch/` (scratch space, not backed up)
- **Action:** Move final outputs to `/data/adamt/` after validation

## Next Steps

1. ~~Create repository structure~~ **Done**
2. ~~Write Apptainer container definition~~ **Done**
3. ~~Implement scripts~~ **Done**
4. ~~Initialize registry (450K PDFs)~~ **Done**
5. ~~Add file size tracking~~ **Done**
6. ~~Small PDF swarm (<5MB)~~ **Cancelled** - Silent failure issue discovered
7. ~~Large PDF swarm (≥5MB)~~ **Cancelled** - Pending investigation
8. ~~Fix process_pdfs_mineru.py bugs~~ **Done** - Output verification, directory structure
9. **Investigate silent failures** - See TROUBLESHOOTING_SILENT_FAILURES.md
   - Analyze GPU type correlation
   - Enable MinerU debug logging
   - Test on specific failing PDFs
10. Re-run with fixed script after root cause identified
11. Merge results and update registry
12. Validate output quality
13. Transfer outputs to permanent storage

## Local Access via CIFS

Mount HPC filesystems locally using gio (GVFS):

```bash
# Mount shares
gio mount smb://hpcdrive.nih.gov/data
gio mount smb://hpcdrive.nih.gov/adamt
gio mount smb://hpcdrive.nih.gov/NIMH_scratch

# Symlinks for convenient access (example)
ln -s "/run/user/$(id -u)/gvfs/smb-share:server=hpcdrive.nih.gov,share=data/" ~/helix_mnt_data
ln -s "/run/user/$(id -u)/gvfs/smb-share:server=hpcdrive.nih.gov,share=adamt/" ~/helix_mnt_home

# Access files
ls ~/helix_mnt_data/osm/minerU_osm/
cat ~/helix_mnt_nimh_scratch/adamt/osm/datalad-osm/duckdbs/mineru_registry.duckdb
```

See `/home/adamt/claude/osm/docs/HPC_SOPS.md` for full documentation.
