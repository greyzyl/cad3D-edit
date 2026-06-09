# CAD Edit Coverage Audit - Expert 3

Input: `data_expert3_fixed_paths.jsonl`
Records: 2490
Elapsed seconds: 314.185

## Branch Summary

| Branch | Candidates | Validated | Pass Rate | Failed Validation |
|---|---:|---:|---:|---:|
| V4 replace | 2366 | 2366 | 100.0% | 0 |

## By Category

### V4 replace

| Category | Candidates | Validated | Pass Rate |
|---|---:|---:|---:|
| Circles | 2366 | 2366 | 100.0% |
| Polygons | 0 | 0 | 0.0% |
| Rects | 0 | 0 | 0.0% |

## By Edit Type

### V4 replace

| Edit Type | Candidates | Validated | Pass Rate |
|---|---:|---:|---:|
| replace_circular_cutout_with_polygonal_cutout | 776 | 776 | 100.0% |
| replace_circular_cutout_with_slot | 776 | 776 | 100.0% |
| replace_loop_holes_with_slots | 814 | 814 | 100.0% |

## Top Rejection Reasons

### V4 replace

| Reason | Count |
|---|---:|
| `skipped_no_replace_candidate` | 900 |
| `delete_skipped_no_delete_candidate` | 869 |
| `delete_skipped_unsupported_hole_context` | 817 |
| `delete_skipped_geometry_error` | 22 |
| `delete_geometry_error:result variable was not defined` | 22 |
| `delete_skipped_unsupported_cut_context` | 14 |
| `delete_skipped_syntax_error` | 9 |
| `delete_syntax_error:unexpected indent (<unknown>, line 3)` | 7 |
| `delete_syntax_error:invalid syntax (<unknown>, line 4)` | 1 |
| `delete_syntax_error:unexpected indent (<unknown>, line 2)` | 1 |

## V4 Hole Diagnostics

| Type | Count |
|---|---:|
| hole_calls_total | 817 |
| simple_loop_holes | 814 |
| circular_cutout_via_cut_circle_extrude | 778 |
| hole_parse_error_records | 9 |
| other_unsupported_hole_contexts | 3 |

### V4 Hole Diagnostics By Category

#### Circles

| Type | Count |
|---|---:|
| hole_calls_total | 817 |
| simple_loop_holes | 814 |
| circular_cutout_via_cut_circle_extrude | 778 |
| hole_parse_error_records | 9 |
| other_unsupported_hole_contexts | 3 |

## Render Preview

Sample JSONL: `outputs\coverage_v4_replace_expanded\chunks\chunk_02\preview_samples.jsonl`
Gallery: `outputs\coverage_v4_replace_expanded\chunks\chunk_02\preview_gallery\index.html`
