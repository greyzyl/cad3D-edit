# CAD Edit Coverage Audit - Expert 3

Input: `data_expert3_fixed_paths.jsonl`
Records: 300
Elapsed seconds: 25.776

## Branch Summary

| Branch | Candidates | Validated | Pass Rate | Failed Validation |
|---|---:|---:|---:|---:|
| V4 replace | 274 | 274 | 100.0% | 0 |

## By Category

### V4 replace

| Category | Candidates | Validated | Pass Rate |
|---|---:|---:|---:|
| Circles | 274 | 274 | 100.0% |
| Polygons | 0 | 0 | 0.0% |
| Rects | 0 | 0 | 0.0% |

## By Edit Type

### V4 replace

| Edit Type | Candidates | Validated | Pass Rate |
|---|---:|---:|---:|
| replace_circular_cutout_with_polygonal_cutout | 92 | 92 | 100.0% |
| replace_circular_cutout_with_slot | 92 | 92 | 100.0% |
| replace_loop_holes_with_slots | 90 | 90 | 100.0% |

## Top Rejection Reasons

### V4 replace

| Reason | Count |
|---|---:|
| `skipped_no_replace_candidate` | 118 |
| `delete_skipped_no_delete_candidate` | 113 |
| `delete_skipped_unsupported_hole_context` | 91 |
| `delete_skipped_unsupported_cut_context` | 3 |
| `delete_skipped_syntax_error` | 3 |
| `delete_syntax_error:unexpected indent (<unknown>, line 3)` | 3 |
| `delete_skipped_geometry_error` | 2 |
| `delete_geometry_error:result variable was not defined` | 2 |

## V4 Hole Diagnostics

| Type | Count |
|---|---:|
| circular_cutout_via_cut_circle_extrude | 92 |
| hole_calls_total | 91 |
| simple_loop_holes | 90 |
| hole_parse_error_records | 3 |
| other_unsupported_hole_contexts | 1 |

### V4 Hole Diagnostics By Category

#### Circles

| Type | Count |
|---|---:|
| circular_cutout_via_cut_circle_extrude | 92 |
| hole_calls_total | 91 |
| simple_loop_holes | 90 |
| hole_parse_error_records | 3 |
| other_unsupported_hole_contexts | 1 |

## Render Preview

Sample JSONL: `outputs\coverage_v4_replace_expanded_smoke_circles\preview_samples.jsonl`
Gallery: `outputs\coverage_v4_replace_expanded_smoke_circles\preview_gallery\index.html`
