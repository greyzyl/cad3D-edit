# CAD Edit Coverage Audit - Expert 3

Input: `data_expert3_fixed_paths.jsonl`
Records: 300
Elapsed seconds: 111.233

## Branch Summary

| Branch | Candidates | Validated | Pass Rate | Failed Validation |
|---|---:|---:|---:|---:|
| V1 parameter | 780 | 776 | 99.4872% | 4 |
| V2 add | 1136 | 1136 | 100.0% | 0 |
| V3 delete | 182 | 182 | 100.0% | 0 |
| V4 replace | 182 | 182 | 100.0% | 0 |

## By Category

### V1 parameter

| Category | Candidates | Validated | Pass Rate |
|---|---:|---:|---:|
| Circles | 780 | 776 | 99.4872% |
| Polygons | 0 | 0 | 0.0% |
| Rects | 0 | 0 | 0.0% |

### V2 add

| Category | Candidates | Validated | Pass Rate |
|---|---:|---:|---:|
| Circles | 1136 | 1136 | 100.0% |
| Polygons | 0 | 0 | 0.0% |
| Rects | 0 | 0 | 0.0% |

### V3 delete

| Category | Candidates | Validated | Pass Rate |
|---|---:|---:|---:|
| Circles | 182 | 182 | 100.0% |
| Polygons | 0 | 0 | 0.0% |
| Rects | 0 | 0 | 0.0% |

### V4 replace

| Category | Candidates | Validated | Pass Rate |
|---|---:|---:|---:|
| Circles | 182 | 182 | 100.0% |
| Polygons | 0 | 0 | 0.0% |
| Rects | 0 | 0 | 0.0% |

## By Edit Type

### V1 parameter

| Edit Type | Candidates | Validated | Pass Rate |
|---|---:|---:|---:|
| circle | 392 | 390 | 99.4898% |
| extrude | 297 | 295 | 99.3266% |
| hole | 91 | 91 | 100.0% |

### V2 add

| Edit Type | Candidates | Validated | Pass Rate |
|---|---:|---:|---:|
| add_blind_hole | 284 | 284 | 100.0% |
| add_pocket | 284 | 284 | 100.0% |
| add_rectangular_slot | 284 | 284 | 100.0% |
| add_through_hole | 284 | 284 | 100.0% |

### V3 delete

| Edit Type | Candidates | Validated | Pass Rate |
|---|---:|---:|---:|
| delete_circular_cutout | 92 | 92 | 100.0% |
| delete_hole | 90 | 90 | 100.0% |

### V4 replace

| Edit Type | Candidates | Validated | Pass Rate |
|---|---:|---:|---:|
| replace_circular_cutout_with_slot | 92 | 92 | 100.0% |
| replace_loop_holes_with_slots | 90 | 90 | 100.0% |

## Top Rejection Reasons

### V1 parameter

| Reason | Count |
|---|---:|
| `validation:result variable was not defined` | 4 |
| `skipped_original_syntax_error` | 3 |

### V2 add

| Reason | Count |
|---|---:|
| `skipped_bad_candidate_geometry` | 44 |
| `skipped_geometry_error` | 5 |
| `geometry_error:unexpected indent (<cadquery_source>, line 3)` | 3 |
| `geometry_error:result variable was not defined` | 2 |

### V3 delete

| Reason | Count |
|---|---:|
| `skipped_no_delete_candidate` | 113 |
| `skipped_unsupported_hole_context` | 91 |
| `skipped_unsupported_cut_context` | 3 |
| `skipped_syntax_error` | 3 |
| `syntax_error:unexpected indent (<unknown>, line 3)` | 3 |
| `skipped_geometry_error` | 2 |
| `geometry_error:result variable was not defined` | 2 |

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

Sample JSONL: `outputs\coverage_expert3_expanded_smoke\preview_samples.jsonl`
Gallery: `outputs\coverage_expert3_expanded_smoke\preview_gallery\index.html`
