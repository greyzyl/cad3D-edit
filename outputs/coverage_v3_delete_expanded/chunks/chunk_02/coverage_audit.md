# CAD Edit Coverage Audit - Expert 3

Input: `data_expert3_fixed_paths.jsonl`
Records: 2500
Elapsed seconds: 140.386

## Branch Summary

| Branch | Candidates | Validated | Pass Rate | Failed Validation |
|---|---:|---:|---:|---:|
| V3 delete | 1677 | 1005 | 59.9284% | 672 |

## By Category

### V3 delete

| Category | Candidates | Validated | Pass Rate |
|---|---:|---:|---:|
| Circles | 332 | 332 | 100.0% |
| Polygons | 1099 | 427 | 38.8535% |
| Rects | 246 | 246 | 100.0% |

## By Edit Type

### V3 delete

| Edit Type | Candidates | Validated | Pass Rate |
|---|---:|---:|---:|
| delete_chamfer | 129 | 129 | 100.0% |
| delete_circular_cutout | 178 | 178 | 100.0% |
| delete_fillet | 468 | 117 | 25.0% |
| delete_hole | 539 | 218 | 40.4453% |
| delete_polygonal_cutout | 363 | 363 | 100.0% |

## Top Rejection Reasons

### V3 delete

| Reason | Count |
|---|---:|
| `skipped_no_delete_candidate` | 814 |
| `validation:failed check: bbox_stable` | 629 |
| `skipped_unsupported_hole_context` | 539 |
| `validation:failed check: changed_region_not_global` | 38 |
| `skipped_geometry_error` | 6 |
| `geometry_error:result variable was not defined` | 6 |
| `validation:changed-region check failed: Bnd_Box is void` | 5 |
| `skipped_syntax_error` | 3 |
| `syntax_error:unexpected indent (<unknown>, line 3)` | 2 |
| `skipped_unsupported_cut_context` | 2 |
| `syntax_error:unexpected indent (<unknown>, line 2)` | 1 |

## V4 Hole Diagnostics

| Type | Count |
|---|---:|
| hole_calls_total | 539 |
| simple_loop_holes | 539 |
| circular_cutout_via_cut_circle_extrude | 179 |
| hole_parse_error_records | 3 |

### V4 Hole Diagnostics By Category

#### Circles

| Type | Count |
|---|---:|
| circular_cutout_via_cut_circle_extrude | 179 |
| hole_calls_total | 154 |
| simple_loop_holes | 154 |
| hole_parse_error_records | 1 |

#### Polygons

| Type | Count |
|---|---:|
| hole_calls_total | 385 |
| simple_loop_holes | 385 |
| circular_cutout_via_cut_circle_extrude | 0 |

#### Rects

| Type | Count |
|---|---:|
| hole_parse_error_records | 2 |
| circular_cutout_via_cut_circle_extrude | 0 |

## Render Preview

Sample JSONL: `C:\Users\13105\Desktop\AAAI\outputs\coverage_v3_delete_expanded\chunks\chunk_02\preview_samples.jsonl`
Gallery: `C:\Users\13105\Desktop\AAAI\outputs\coverage_v3_delete_expanded\chunks\chunk_02\preview_gallery\index.html`
