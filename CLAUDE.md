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

## Key Files

- **Container:** `/data/adamt/containers/mineru.sif` (6.5 GB)
- **Registry:** `/data/adamt/osm/datafiles/mineru_registry.duckdb`
- **Manifest:** `/data/adamt/osm/datafiles/mineru_manifest_scratch.csv` (163K PDFs)
- **Swarm:** `/data/adamt/osm/datafiles/mineru_full.swarm`
- **Logs:** `/data/adamt/osm/datafiles/mineru_logs/`

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
# Test (5 chunks = 500 PDFs)
head -5 /data/adamt/osm/datafiles/mineru_full.swarm > /data/adamt/osm/datafiles/mineru_test.swarm
swarm -f /data/adamt/osm/datafiles/mineru_test.swarm \
    -g 64 -t 16 --time 02:00:00 \
    --partition gpu --gres=gpu:1 \
    --logdir /data/adamt/osm/datafiles/mineru_logs/test

# Full production (1,634 chunks)
swarm -f /data/adamt/osm/datafiles/mineru_full.swarm \
    -g 64 -t 16 --time 06:00:00 \
    --partition gpu --gres=gpu:1 \
    --logdir /data/adamt/osm/datafiles/mineru_logs/full
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
```
