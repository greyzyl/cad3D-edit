# CAD Edit Coverage Audit - Expert 3

Input: `data_expert3_fixed_paths.jsonl`
Records: 120
Elapsed seconds: 5.325

## Branch Summary

| Branch | Candidates | Validated | Pass Rate | Failed Validation |
|---|---:|---:|---:|---:|
| V3 delete | 82 | 38 | 46.3415% | 44 |

## By Category

### V3 delete

| Category | Candidates | Validated | Pass Rate |
|---|---:|---:|---:|
| Circles | 0 | 0 | 0.0% |
| Polygons | 82 | 38 | 46.3415% |
| Rects | 0 | 0 | 0.0% |

## By Edit Type

### V3 delete

| Edit Type | Candidates | Validated | Pass Rate |
|---|---:|---:|---:|
| delete_fillet | 27 | 0 | 0.0% |
| delete_hole | 20 | 3 | 15.0% |
| delete_polygonal_cutout | 35 | 35 | 100.0% |

## Top Rejection Reasons

### V3 delete

| Reason | Count |
|---|---:|
| `validation:failed check: bbox_stable` | 40 |
| `skipped_no_delete_candidate` | 38 |
| `skipped_unsupported_hole_context` | 20 |
| `validation:failed check: changed_region_not_global` | 2 |
| `validation:changed-region check failed: Bnd_Box is void` | 2 |

## V4 Hole Diagnostics

| Type | Count |
|---|---:|
| hole_calls_total | 20 |
| simple_loop_holes | 20 |
| circular_cutout_via_cut_circle_extrude | 0 |

### V4 Hole Diagnostics By Category

#### Polygons

| Type | Count |
|---|---:|
| hole_calls_total | 20 |
| simple_loop_holes | 20 |
| circular_cutout_via_cut_circle_extrude | 0 |

## Render Preview

Sample JSONL: `outputs\coverage_v3_delete_branch_smoke\preview_samples.jsonl`
Gallery: `outputs\coverage_v3_delete_branch_smoke\preview_gallery\index.html`
