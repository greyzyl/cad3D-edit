# CAD Edit Coverage Audit - Expert 3

Input: `data_expert3_fixed_paths.jsonl`
Records: 2435
Elapsed seconds: 137.929

## Branch Summary

| Branch | Candidates | Validated | Pass Rate | Failed Validation |
|---|---:|---:|---:|---:|
| V3 delete | 1645 | 1001 | 60.8511% | 644 |

## By Category

### V3 delete

| Category | Candidates | Validated | Pass Rate |
|---|---:|---:|---:|
| Circles | 324 | 324 | 100.0% |
| Polygons | 1058 | 414 | 39.1304% |
| Rects | 263 | 263 | 100.0% |

## By Edit Type

### V3 delete

| Edit Type | Candidates | Validated | Pass Rate |
|---|---:|---:|---:|
| delete_chamfer | 127 | 127 | 100.0% |
| delete_circular_cutout | 178 | 178 | 100.0% |
| delete_fillet | 484 | 136 | 28.0992% |
| delete_hole | 502 | 206 | 41.0359% |
| delete_polygonal_cutout | 354 | 354 | 100.0% |

## Top Rejection Reasons

### V3 delete

| Reason | Count |
|---|---:|
| `skipped_no_delete_candidate` | 764 |
| `validation:failed check: bbox_stable` | 607 |
| `skipped_unsupported_hole_context` | 506 |
| `validation:failed check: changed_region_not_global` | 35 |
| `skipped_syntax_error` | 15 |
| `syntax_error:unexpected indent (<unknown>, line 3)` | 12 |
| `skipped_geometry_error` | 11 |
| `geometry_error:result variable was not defined` | 11 |
| `skipped_unsupported_cut_context` | 5 |
| `syntax_error:unexpected indent (<unknown>, line 2)` | 2 |
| `validation:changed-region check failed: Bnd_Box is void` | 2 |
| `syntax_error:invalid syntax (<unknown>, line 2)` | 1 |

## V4 Hole Diagnostics

| Type | Count |
|---|---:|
| hole_calls_total | 506 |
| simple_loop_holes | 502 |
| circular_cutout_via_cut_circle_extrude | 179 |
| hole_parse_error_records | 15 |
| other_unsupported_hole_contexts | 4 |

### V4 Hole Diagnostics By Category

#### Circles

| Type | Count |
|---|---:|
| circular_cutout_via_cut_circle_extrude | 179 |
| hole_calls_total | 149 |
| simple_loop_holes | 146 |
| hole_parse_error_records | 6 |
| other_unsupported_hole_contexts | 3 |

#### Polygons

| Type | Count |
|---|---:|
| hole_calls_total | 357 |
| simple_loop_holes | 356 |
| hole_parse_error_records | 3 |
| other_unsupported_hole_contexts | 1 |
| circular_cutout_via_cut_circle_extrude | 0 |

#### Rects

| Type | Count |
|---|---:|
| hole_parse_error_records | 6 |
| circular_cutout_via_cut_circle_extrude | 0 |

## Render Preview

Sample JSONL: `C:\Users\13105\Desktop\AAAI\outputs\coverage_v3_delete_expanded\chunks\chunk_06\preview_samples.jsonl`
Gallery: `C:\Users\13105\Desktop\AAAI\outputs\coverage_v3_delete_expanded\chunks\chunk_06\preview_gallery\index.html`
