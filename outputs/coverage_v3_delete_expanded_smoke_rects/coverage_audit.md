# CAD Edit Coverage Audit - Expert 3

Input: `data_expert3_fixed_paths.jsonl`
Records: 400
Elapsed seconds: 84.467

## Branch Summary

| Branch | Candidates | Validated | Pass Rate | Failed Validation |
|---|---:|---:|---:|---:|
| V1 parameter | 604 | 585 | 96.8543% | 19 |
| V2 add | 1596 | 1596 | 100.0% | 0 |
| V3 delete | 205 | 205 | 100.0% | 0 |
| V4 replace | 0 | 0 | 0.0% | 0 |

## By Category

### V1 parameter

| Category | Candidates | Validated | Pass Rate |
|---|---:|---:|---:|
| Circles | 0 | 0 | 0.0% |
| Polygons | 0 | 0 | 0.0% |
| Rects | 604 | 585 | 96.8543% |

### V2 add

| Category | Candidates | Validated | Pass Rate |
|---|---:|---:|---:|
| Circles | 0 | 0 | 0.0% |
| Polygons | 0 | 0 | 0.0% |
| Rects | 1596 | 1596 | 100.0% |

### V3 delete

| Category | Candidates | Validated | Pass Rate |
|---|---:|---:|---:|
| Circles | 0 | 0 | 0.0% |
| Polygons | 0 | 0 | 0.0% |
| Rects | 205 | 205 | 100.0% |

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
| chamfer | 100 | 91 | 91.0% |
| extrude | 399 | 399 | 100.0% |
| fillet | 105 | 95 | 90.4762% |

### V2 add

| Edit Type | Candidates | Validated | Pass Rate |
|---|---:|---:|---:|
| add_blind_hole | 399 | 399 | 100.0% |
| add_pocket | 399 | 399 | 100.0% |
| add_rectangular_slot | 399 | 399 | 100.0% |
| add_through_hole | 399 | 399 | 100.0% |

### V3 delete

| Edit Type | Candidates | Validated | Pass Rate |
|---|---:|---:|---:|
| delete_chamfer | 100 | 100 | 100.0% |
| delete_fillet | 105 | 105 | 100.0% |

### V4 replace

| Edit Type | Candidates | Validated | Pass Rate |
|---|---:|---:|---:|

## Top Rejection Reasons

### V1 parameter

| Reason | Count |
|---|---:|
| `validation:StdFail_NotDone: BRep_API: command not done` | 19 |
| `skipped_no_candidates` | 1 |

### V2 add

| Reason | Count |
|---|---:|
| `skipped_geometry_error` | 1 |
| `geometry_error:result variable was not defined` | 1 |

### V3 delete

| Reason | Count |
|---|---:|
| `skipped_no_delete_candidate` | 194 |
| `skipped_geometry_error` | 1 |
| `geometry_error:result variable was not defined` | 1 |

### V4 replace

| Reason | Count |
|---|---:|
| `skipped_no_replace_candidate` | 400 |
| `delete_skipped_no_delete_candidate` | 399 |
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

Sample JSONL: `outputs\coverage_v3_delete_expanded_smoke_rects\preview_samples.jsonl`
Gallery: `outputs\coverage_v3_delete_expanded_smoke_rects\preview_gallery\index.html`
