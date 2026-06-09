# CAD Edit Coverage Audit - Expert 3

Input: `data_expert3_fixed_paths.jsonl`
Records: 2500
Elapsed seconds: 109.55

## Branch Summary

| Branch | Candidates | Validated | Pass Rate | Failed Validation |
|---|---:|---:|---:|---:|
| V3 delete | 1415 | 1415 | 100.0% | 0 |

## By Category

### V3 delete

| Category | Candidates | Validated | Pass Rate |
|---|---:|---:|---:|
| Circles | 930 | 930 | 100.0% |
| Polygons | 0 | 0 | 0.0% |
| Rects | 485 | 485 | 100.0% |

## By Edit Type

### V3 delete

| Edit Type | Candidates | Validated | Pass Rate |
|---|---:|---:|---:|
| delete_chamfer | 245 | 245 | 100.0% |
| delete_circular_cutout | 472 | 472 | 100.0% |
| delete_fillet | 240 | 240 | 100.0% |
| delete_hole | 458 | 458 | 100.0% |

## Top Rejection Reasons

### V3 delete

| Reason | Count |
|---|---:|
| `skipped_no_delete_candidate` | 1041 |
| `skipped_unsupported_hole_context` | 461 |
| `skipped_syntax_error` | 28 |
| `syntax_error:unexpected indent (<unknown>, line 3)` | 23 |
| `skipped_geometry_error` | 16 |
| `geometry_error:result variable was not defined` | 16 |
| `skipped_unsupported_cut_context` | 14 |
| `syntax_error:unexpected indent (<unknown>, line 2)` | 3 |
| `syntax_error:invalid syntax (<unknown>, line 2)` | 2 |

## V4 Hole Diagnostics

| Type | Count |
|---|---:|
| circular_cutout_via_cut_circle_extrude | 475 |
| hole_calls_total | 461 |
| simple_loop_holes | 458 |
| hole_parse_error_records | 28 |
| other_unsupported_hole_contexts | 3 |

### V4 Hole Diagnostics By Category

#### Circles

| Type | Count |
|---|---:|
| circular_cutout_via_cut_circle_extrude | 475 |
| hole_calls_total | 461 |
| simple_loop_holes | 458 |
| hole_parse_error_records | 23 |
| other_unsupported_hole_contexts | 3 |

#### Rects

| Type | Count |
|---|---:|
| hole_parse_error_records | 5 |
| circular_cutout_via_cut_circle_extrude | 0 |

## Render Preview

Sample JSONL: `C:\Users\13105\Desktop\AAAI\outputs\coverage_v3_delete_expanded\chunks\chunk_01\preview_samples.jsonl`
Gallery: `C:\Users\13105\Desktop\AAAI\outputs\coverage_v3_delete_expanded\chunks\chunk_01\preview_gallery\index.html`
