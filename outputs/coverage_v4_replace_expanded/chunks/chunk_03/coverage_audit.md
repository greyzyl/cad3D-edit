# CAD Edit Coverage Audit - Expert 3

Input: `data_expert3_fixed_paths.jsonl`
Records: 2490
Elapsed seconds: 204.465

## Branch Summary

| Branch | Candidates | Validated | Pass Rate | Failed Validation |
|---|---:|---:|---:|---:|
| V4 replace | 1213 | 1213 | 100.0% | 0 |

## By Category

### V4 replace

| Category | Candidates | Validated | Pass Rate |
|---|---:|---:|---:|
| Circles | 7 | 7 | 100.0% |
| Polygons | 0 | 0 | 0.0% |
| Rects | 1206 | 1206 | 100.0% |

## By Edit Type

### V4 replace

| Edit Type | Candidates | Validated | Pass Rate |
|---|---:|---:|---:|
| replace_chamfer_with_fillet | 623 | 623 | 100.0% |
| replace_circular_cutout_with_polygonal_cutout | 2 | 2 | 100.0% |
| replace_circular_cutout_with_slot | 2 | 2 | 100.0% |
| replace_fillet_with_chamfer | 583 | 583 | 100.0% |
| replace_loop_holes_with_slots | 3 | 3 | 100.0% |

## Top Rejection Reasons

### V4 replace

| Reason | Count |
|---|---:|
| `skipped_no_replace_candidate` | 1279 |
| `delete_skipped_no_delete_candidate` | 1249 |
| `delete_skipped_syntax_error` | 20 |
| `delete_syntax_error:unexpected indent (<unknown>, line 3)` | 18 |
| `delete_skipped_geometry_error` | 10 |
| `delete_geometry_error:result variable was not defined` | 10 |
| `delete_skipped_unsupported_hole_context` | 3 |
| `delete_syntax_error:invalid syntax (<unknown>, line 4)` | 1 |
| `delete_syntax_error:unexpected indent (<unknown>, line 2)` | 1 |

## V4 Hole Diagnostics

| Type | Count |
|---|---:|
| hole_parse_error_records | 20 |
| hole_calls_total | 3 |
| simple_loop_holes | 3 |
| circular_cutout_via_cut_circle_extrude | 2 |

### V4 Hole Diagnostics By Category

#### Circles

| Type | Count |
|---|---:|
| hole_calls_total | 3 |
| simple_loop_holes | 3 |
| circular_cutout_via_cut_circle_extrude | 2 |
| hole_parse_error_records | 1 |

#### Rects

| Type | Count |
|---|---:|
| hole_parse_error_records | 19 |
| circular_cutout_via_cut_circle_extrude | 0 |

## Render Preview

Sample JSONL: `outputs\coverage_v4_replace_expanded\chunks\chunk_03\preview_samples.jsonl`
Gallery: `outputs\coverage_v4_replace_expanded\chunks\chunk_03\preview_gallery\index.html`
