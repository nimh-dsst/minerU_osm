# MinerU HPC Processing Pipeline - Strategic Plan

## Overview

This document outlines a strategy for processing PubMed Open Access PDFs through MinerU on NIH Biowulf HPC to convert them to structured JSON/Markdown format. This is a standalone repository (`minerU_osm`) separate from the main `osm-pipeline`.

**Repository:** `/data/adamt/osm/minerU_osm`
**Input:** PDFs from datalad-osm (`/data/NIMH_scratch/adamt/osm/datalad-osm/pdfs/`)
**Output:** Structured JSON files (`/data/NIMH_scratch/adamt/osm/datalad-osm/minerU_out/`)

## Current State (Updated 2024-12-31)

| Metric | Value |
|--------|-------|
| PDFs in registry | 163,315 |
| Container | Built (6.5 GB) at `/data/adamt/containers/mineru.sif` |
| Registry | Initialized at `/data/adamt/osm/datafiles/mineru_registry.duckdb` |
| Test status | Running (Job 8364045, 5 chunks of 100 PDFs) |

### Implementation Progress

| Phase | Status | Notes |
|-------|--------|-------|
| 1. Container | **Complete** | Built via Docker on Curium, converted to SIF |
| 2. Scripts | **Complete** | All 4 scripts implemented and tested |
| 3. Registry | **Complete** | 163,315 PDFs registered |
| 4. Test run | **In Progress** | 5-job test swarm running on K80 GPUs |
| 5. Production | Pending | Awaiting test validation |

## Observed Performance Metrics

From test run (Job 8364045) on K80 GPUs:

| Metric | Value |
|--------|-------|
| GPUs used | 5 (K80) |
| PDFs processed | ~37 in 18 min |
| Rate (total) | ~2.06 PDFs/min |
| Rate (per GPU) | ~0.41 PDFs/min |
| Time per PDF | **~2.5 min** |
| Chunk time (100 PDFs) | **~4 hours** |

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
├── mineru_registry.duckdb            # Processing tracker
├── mineru_manifest_scratch.csv       # PDF manifest (163K entries)
├── mineru_full.swarm                 # Full production swarm
├── mineru_test.swarm                 # Test swarm (5 chunks)
├── mineru_results/                   # Per-chunk result CSVs
└── mineru_logs/                      # Swarm job logs
    ├── test/                         # Test job logs
    └── full/                         # Production job logs

/data/NIMH_scratch/adamt/osm/datalad-osm/
├── pdfs/{prefix}/{pmid}.pdf          # Input PDFs
└── minerU_out/{pmid}/                # Output JSON/MD files
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
    --db /data/adamt/osm/datafiles/mineru_registry.duckdb \
    init --manifest /data/adamt/osm/datafiles/mineru_manifest_scratch.csv

# Check status
/data/adamt/osm/venvHPC/bin/python /data/adamt/osm/minerU_osm/scripts/mineru_registry.py \
    --db /data/adamt/osm/datafiles/mineru_registry.duckdb status

# Export pending
/data/adamt/osm/venvHPC/bin/python /data/adamt/osm/minerU_osm/scripts/mineru_registry.py \
    --db /data/adamt/osm/datafiles/mineru_registry.duckdb \
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
4. ~~Initialize registry~~ **Done**
5. ~~Test on 500 PDFs (swarm)~~ **In Progress**
6. Validate test outputs
7. Run full production (163K PDFs)
8. Merge and export results
9. Update registry with completion status
10. Transfer outputs to permanent storage
