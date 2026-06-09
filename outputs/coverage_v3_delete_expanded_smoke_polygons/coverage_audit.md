# CAD Edit Coverage Audit - Expert 3

Input: `data_expert3_fixed_paths.jsonl`
Records: 400
Elapsed seconds: 136.058

## Branch Summary

| Branch | Candidates | Validated | Pass Rate | Failed Validation |
|---|---:|---:|---:|---:|
| V1 parameter | 689 | 680 | 98.6938% | 9 |
| V2 add | 1600 | 1472 | 92.0% | 128 |
| V3 delete | 289 | 127 | 43.9446% | 162 |
| V4 replace | 0 | 0 | 0.0% | 0 |

## By Category

### V1 parameter

| Category | Candidates | Validated | Pass Rate |
|---|---:|---:|---:|
| Circles | 0 | 0 | 0.0% |
| Polygons | 689 | 680 | 98.6938% |
| Rects | 0 | 0 | 0.0% |

### V2 add

| Category | Candidates | Validated | Pass Rate |
|---|---:|---:|---:|
| Circles | 0 | 0 | 0.0% |
| Polygons | 1600 | 1472 | 92.0% |
| Rects | 0 | 0 | 0.0% |

### V3 delete

| Category | Candidates | Validated | Pass Rate |
|---|---:|---:|---:|
| Circles | 0 | 0 | 0.0% |
| Polygons | 289 | 127 | 43.9446% |
| Rects | 0 | 0 | 0.0% |

### V4 replace

| Category | Candidates | Validated | Pass Rate |
|---|---:|---:|---:|
| Circles | 0 | 0 | 0.0% |
| Polygons | 0 | 0 | 0.0% |
| Rects | 0 | 0 | 0.0% |

## By Edit Type

### V1 parameter

| Edit Type | Candidates | Validated | Pass Rate |
|---|---:|---:|---:|
| extrude | 511 | 511 | 100.0% |
| fillet | 89 | 80 | 89.8876% |
| hole | 89 | 89 | 100.0% |

### V2 add

| Edit Type | Candidates | Validated | Pass Rate |
|---|---:|---:|---:|
| add_blind_hole | 400 | 343 | 85.75% |
| add_pocket | 400 | 387 | 96.75% |
| add_rectangular_slot | 400 | 396 | 99.0% |
| add_through_hole | 400 | 346 | 86.5% |

### V3 delete

| Edit Type | Candidates | Validated | Pass Rate |
|---|---:|---:|---:|
| delete_fillet | 89 | 0 | 0.0% |
| delete_hole | 89 | 16 | 17.9775% |
| delete_polygonal_cutout | 111 | 111 | 100.0% |

### V4 replace

| Edit Type | Candidates | Validated | Pass Rate |
|---|---:|---:|---:|

## Top Rejection Reasons

### V1 parameter

| Reason | Count |
|---|---:|
| `validation:StdFail_NotDone: BRep_API: command not done` | 9 |

### V2 add

| Reason | Count |
|---|---:|
| `validation:changed-region check failed: Bnd_Box is void` | 128 |

### V3 delete

| Reason | Count |
|---|---:|
| `validation:failed check: bbox_stable` | 148 |
| `skipped_no_delete_candidate` | 111 |
| `skipped_unsupported_hole_context` | 89 |
| `validation:failed check: changed_region_not_global` | 11 |
| `validation:changed-region check failed: Bnd_Box is void` | 3 |

### V4 replace

| Reason | Count |
|---|---:|
| `delete_skipped_no_delete_candidate` | 400 |
| `skipped_no_replace_candidate` | 400 |

## V4 Hole Diagnostics

| Type | Count |
|---|---:|
| hole_calls_total | 89 |
| simple_loop_holes | 89 |
| circular_cutout_via_cut_circle_extrude | 0 |

### V4 Hole Diagnostics By Category

#### Polygons

| Type | Count |
|---|---:|
| hole_calls_total | 89 |
| simple_loop_holes | 89 |
| circular_cutout_via_cut_circle_extrude | 0 |

## Render Preview

Sample JSONL: `outputs\coverage_v3_delete_expanded_smoke_polygons\preview_samples.jsonl`
Gallery: `outputs\coverage_v3_delete_expanded_smoke_polygons\preview_gallery\index.html`
