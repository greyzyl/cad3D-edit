# CAD Edit Coverage Audit - Expert 3

Input: `data_expert3_fixed_paths.jsonl`
Records: 300
Elapsed seconds: 16.167

## Branch Summary

| Branch | Candidates | Validated | Pass Rate | Failed Validation |
|---|---:|---:|---:|---:|
| V4 replace | 150 | 150 | 100.0% | 0 |

## By Category

### V4 replace

| Category | Candidates | Validated | Pass Rate |
|---|---:|---:|---:|
| Circles | 0 | 0 | 0.0% |
| Polygons | 0 | 0 | 0.0% |
| Rects | 150 | 150 | 100.0% |

## By Edit Type

### V4 replace

| Edit Type | Candidates | Validated | Pass Rate |
|---|---:|---:|---:|
| replace_chamfer_with_fillet | 72 | 72 | 100.0% |
| replace_fillet_with_chamfer | 78 | 78 | 100.0% |

## Top Rejection Reasons

### V4 replace

| Reason | Count |
|---|---:|
| `skipped_no_replace_candidate` | 150 |
| `delete_skipped_no_delete_candidate` | 149 |
| `delete_skipped_geometry_error` | 1 |
| `delete_geometry_error:result variable was not defined` | 1 |

## V4 Hole Diagnostics

| Type | Count |
|---|---:|
| circular_cutout_via_cut_circle_extrude | 0 |

### V4 Hole Diagnostics By Category

#### Rects

| Type | Count |
|---|---:|
| circular_cutout_via_cut_circle_extrude | 0 |

## Render Preview

Sample JSONL: `outputs\coverage_v4_replace_expanded_smoke_rects\preview_samples.jsonl`
Gallery: `outputs\coverage_v4_replace_expanded_smoke_rects\preview_gallery\index.html`
