# CAD Edit Coverage Audit - Expert 3

Input: `data_expert3_fixed_paths.jsonl`
Records: 2490
Elapsed seconds: 266.518

## Branch Summary

| Branch | Candidates | Validated | Pass Rate | Failed Validation |
|---|---:|---:|---:|---:|
| V4 replace | 1884 | 1884 | 100.0% | 0 |

## By Category

### V4 replace

| Category | Candidates | Validated | Pass Rate |
|---|---:|---:|---:|
| Circles | 1402 | 1402 | 100.0% |
| Polygons | 0 | 0 | 0.0% |
| Rects | 482 | 482 | 100.0% |

## By Edit Type

### V4 replace

| Edit Type | Candidates | Validated | Pass Rate |
|---|---:|---:|---:|
| replace_chamfer_with_fillet | 242 | 242 | 100.0% |
| replace_circular_cutout_with_polygonal_cutout | 472 | 472 | 100.0% |
| replace_circular_cutout_with_slot | 472 | 472 | 100.0% |
| replace_fillet_with_chamfer | 240 | 240 | 100.0% |
| replace_loop_holes_with_slots | 458 | 458 | 100.0% |

## Top Rejection Reasons

### V4 replace

| Reason | Count |
|---|---:|
| `skipped_no_replace_candidate` | 1078 |
| `delete_skipped_no_delete_candidate` | 1034 |
| `delete_skipped_unsupported_hole_context` | 461 |
| `delete_skipped_syntax_error` | 28 |
| `delete_syntax_error:unexpected indent (<unknown>, line 3)` | 23 |
| `delete_skipped_geometry_error` | 16 |
| `delete_geometry_error:result variable was not defined` | 16 |
| `delete_skipped_unsupported_cut_context` | 14 |
| `delete_syntax_error:unexpected indent (<unknown>, line 2)` | 3 |
| `delete_syntax_error:invalid syntax (<unknown>, line 2)` | 2 |

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

Sample JSONL: `outputs\coverage_v4_replace_expanded\chunks\chunk_00\preview_samples.jsonl`
Gallery: `outputs\coverage_v4_replace_expanded\chunks\chunk_00\preview_gallery\index.html`
