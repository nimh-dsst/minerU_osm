# minerU_osm

MinerU-based PDF-to-JSON conversion pipeline for PubMed Open Access articles on NIH Biowulf HPC.

## Overview

This repository processes PDFs downloaded by `osm-pipeline` through [MinerU](https://github.com/opendatalab/MinerU) to extract structured document content (text, tables, figures) as JSON/Markdown.

**Input:** ~700K PDFs from `/data/adamt/osm/datafiles/pdfs/`
**Output:** Structured JSON with layout-aware text extraction

## Quick Start

```bash
# 1. Build container (on Biowulf compute node)
cd container && ./build.sh

# 2. Test single PDF
apptainer exec --nv mineru.sif mineru -p test.pdf -o output/

# 3. Generate swarm for batch processing
./scripts/generate_mineru_swarm.sh \
    --manifest /data/adamt/osm/datafiles/pdf_manifest.csv \
    --chunk-size 100 \
    --output-swarm mineru_batch.swarm

# 4. Submit with NIMH GPU priority
swarm -f mineru_batch.swarm \
    -g 64 -t 16 --time 04:00:00 \
    --partition gpu --gres=gpu:a100:1 \
    --qos=gpunimh2025.1 \
    --logdir logs/mineru_batch
```

## Directory Structure

```
minerU_osm/
├── scripts/
│   ├── process_pdfs_mineru.py   # Main processing script
│   ├── generate_mineru_swarm.sh # Swarm generator
│   ├── merge_mineru_results.py  # Merge outputs
│   └── mineru_registry.py       # DuckDB tracker
├── container/
│   ├── mineru.def               # Apptainer definition
│   └── build.sh
└── docs/
    └── MINERU_HPC_PLAN.md       # Full strategic plan
```

## GPU Resources

Uses NIMH priority GPU allocation (`--qos=gpunimh2025.1`):
- Up to 64 concurrent GPUs
- A100 (80GB), V100 (16-32GB) available
- MinerU pipeline backend needs 6GB+ VRAM

## Related

- `osm-pipeline` - PDF download and oddpub processing
- [MinerU](https://github.com/opendatalab/MinerU) - Document parsing tool
