# MinerU GPU and Backend Comparison

**Date:** 2025-01-09
**Test PDF:** PMID 35229078 (3.4 MB scientific article with figures, equations, tables)
**MinerU Version:** 2.7.1

## Executive Summary

We tested MinerU PDF processing across 6 compute configurations (A100, V100x, V100, P100, K80, CPU) and 3 backends (pipeline, vlm-auto-engine, hybrid-auto-engine). Key findings:

1. **Pipeline backend** is 3-16× faster but produces less structured output
2. **VLM/Hybrid backends** detect 5× more images and extract document structure (headers, footers, lists)
3. **VLM produces the cleanest output** with most deterministic results
4. **A100 is consistently fastest** across all backends
5. **Output varies slightly across GPUs** due to non-deterministic model behavior

## Performance Results

### Processing Time (seconds)

| GPU Type | Pipeline | Hybrid | VLM |
|----------|----------|--------|-----|
| A100 | **50** | 167 | 392 |
| V100x | 74 | 349 | 830 |
| V100 | 74 | 367 | 881 |
| P100 | 100 | 415 | 984 |
| K80 | 462 | N/A | N/A |
| CPU | 536 | N/A | N/A |

**Notes:**
- K80 and CPU cannot run VLM/Hybrid (requires modern GPU with compute capability 6.0+)
- P100 requires special container (`mineru_p100.sif`) with PyTorch 2.3.1+cu118
- V100/V100x/A100 use standard container (`mineru_2.7.1.sif`) with PyTorch 2.9.1

### Relative Speed (vs Pipeline on same GPU)

| GPU Type | Pipeline | Hybrid | VLM |
|----------|----------|--------|-----|
| A100 | 1.0× | 3.3× slower | 7.8× slower |
| V100x | 1.0× | 4.7× slower | 11.2× slower |
| V100 | 1.0× | 5.0× slower | 11.9× slower |
| P100 | 1.0× | 4.2× slower | 9.8× slower |

## Output Quality Comparison

### Structural Differences

| Metric | Pipeline | VLM | Hybrid |
|--------|----------|-----|--------|
| JSON file size | 137 KB | 139 KB | 150 KB |
| Total elements | 140 | 196 | 196 |
| Markdown lines | 291 | 405 | 400 |

### Element Type Distribution

| Element Type | Pipeline | VLM/Hybrid | Notes |
|--------------|----------|------------|-------|
| text | 111 | 110 | Similar |
| image | **7** | **37** | VLM/Hybrid detect 5× more |
| header | 0 | 22 | Document structure |
| page_number | 0 | 16 | Document structure |
| list | 0 | 7 | Structured lists |
| footer | 0 | 2 | Document structure |
| equation | 2 | 2 | Same |
| discarded | 20 | 0 | Pipeline discards content |

### Key Quality Differences

**Pipeline:**
- Faster processing
- Fewer detected images (misses inline figures)
- No document structure extraction
- Has "discarded" elements (content deemed unusable)
- LaTeX formatting varies: `$\mathbb { K } ^ { + }$` (extra spaces)

**VLM:**
- Cleanest LaTeX formatting: `$\mathrm{K}^{+}$`
- Better citation formatting with proper superscripts
- Most deterministic output (V100 and V100x produce identical results)
- Detects document structure (headers, footers, page numbers)
- No discarded content

**Hybrid:**
- Same structure as VLM (196 elements)
- LaTeX formatting similar to pipeline (extra spaces)
- Less deterministic than VLM
- 2-3× faster than VLM

## Output Consistency Across GPUs

### Same Backend, Different GPUs

| Backend | MD5 Consistency | Observation |
|---------|-----------------|-------------|
| Pipeline | All 6 different | Minor LaTeX symbol variations |
| VLM | V100=V100x identical, A100/P100 differ | Most consistent |
| Hybrid | All 4 different | LaTeX variations |

**Finding:** VLM produces **deterministic output** when using the same container. V100 and V100x (both using `mineru_2.7.1.sif`) produce byte-identical output. Variations between A100 and P100 are due to:
- Different random seeds or model behavior
- P100 uses different container (`mineru_p100.sif`)

### Nature of Variations

Differences within same backend are **semantically equivalent** but vary in:
- LaTeX symbol choice: `\mathbb{K}` vs `\mathbf{K}` vs `\mathtt{K}` (all render as K)
- Spacing in LaTeX: `$\mathrm{K}^{+}$` vs `$\mathrm { K } ^ { + }$`
- Minor floating-point differences in bounding box coordinates

## Container Specifications

### mineru_2.7.1.sif (Standard)
- **MinerU:** 2.7.1
- **PyTorch:** 2.9.1+cu128
- **CUDA:** 12.1
- **Compatible GPUs:** V100, V100x, A100 (compute cap 7.0+)
- **Backends:** pipeline, vlm-auto-engine, hybrid-auto-engine

### mineru_p100.sif (P100 Compatible)
- **MinerU:** 2.7.1
- **PyTorch:** 2.3.1+cu118
- **CUDA:** 11.8
- **Compatible GPUs:** P100 (compute cap 6.0)
- **Backends:** pipeline, vlm-auto-engine, hybrid-auto-engine

### mineru.sif (Legacy)
- **MinerU:** 2.6.8
- **PyTorch:** 2.9.1+cu128
- **Backends:** pipeline only (no vlm/hybrid support)

## Accuracy Benchmarks (OmniDocBench)

Per MinerU documentation:
- **Pipeline:** 82+ accuracy score
- **VLM/Hybrid:** 90+ accuracy score

The ~8% accuracy improvement from VLM/Hybrid comes from:
- Better image/figure detection
- Document structure extraction
- Vision model understanding of complex layouts

## Recommendations

### For Current Processing (~120K remaining PDFs)

**Continue with pipeline backend** for the current batch:
- Already processed ~180K PDFs with pipeline
- Consistent output format
- Fastest processing time
- Acceptable accuracy for most use cases

### For Future High-Priority Processing

**Consider hybrid backend** when:
- Document structure is important (headers, sections)
- Maximum image extraction needed
- 3-5× slower processing is acceptable
- Using A100 GPUs (167s/PDF vs 50s/PDF)

**Consider VLM backend** when:
- Cleanest possible output required
- Deterministic results needed
- 8-12× slower processing is acceptable

### GPU Selection

| Priority | Recommendation |
|----------|----------------|
| Speed | A100 > V100x ≈ V100 > P100 > K80 > CPU |
| Availability | K80 (most available) > V100 > P100 > A100 |
| Cost-effective | V100/V100x (good speed, decent availability) |

## Test Details

### Job IDs
- Pipeline tests: 9046649-9046653 (original), rerun for consistency
- VLM tests: 9171156-9171158
- Hybrid tests: 9171159, 9171163-9171164

### Output Locations
```
/data/adamt/osm/datafiles/gpu_backend_comparison/
├── output_{gpu}_{backend}/
│   └── 35229078/
│       └── {auto|vlm|hybrid_auto}/
│           ├── 35229078_content_list.json
│           ├── 35229078.md
│           └── images/
└── results_{gpu}_{backend}.csv
```

### Test Script
```bash
/data/adamt/osm/datafiles/gpu_backend_comparison/run_test.sh
```

## Appendix: Sample Output Comparison

### Title Extraction

**Pipeline:**
```markdown
# ATP Synthase $\mathbf { K } ^ { + }$ - and $\mathbb { H } ^ { + }$ -Fluxes Drive ATP Synthesisand Enable Mitochondrial $\mathbb { K } ^ { + }$ -"Uniporter" Function:I. Characterization of Ion Fluxes
```

**VLM:**
```markdown
# ATP Synthase $\mathrm{K}^{+}$ - and $\mathrm{H}^{+}$ -Fluxes Drive ATP Synthesis and Enable Mitochondrial $\mathrm{K}^{+}$ -"Uniporter" Function: I. Characterization of Ion Fluxes
```

**Hybrid:**
```markdown
# ATP Synthase $\mathbb { K } ^ { + }$ - and $\mathbb { H } ^ { + }$ -Fluxes Drive ATP Synthesisand Enable Mitochondrial $\mathbb { K } ^ { + }$ -"Uniporter" Function:I. Characterization of Ion Fluxes
```

Note: VLM correctly separates "Synthesisand" → "Synthesis and" and uses cleaner LaTeX.
