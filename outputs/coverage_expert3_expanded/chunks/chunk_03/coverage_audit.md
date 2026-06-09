# CAD Edit Coverage Audit - Expert 3

Input: `data_expert3_fixed_paths.jsonl`
Records: 2500
Elapsed seconds: 1395.662

## Branch Summary

| Branch | Candidates | Validated | Pass Rate | Failed Validation |
|---|---:|---:|---:|---:|
| V1 parameter | 6568 | 6524 | 99.3301% | 44 |
| V2 add | 9484 | 9484 | 100.0% | 0 |
| V3 delete | 1584 | 1584 | 100.0% | 0 |
| V4 replace | 1584 | 1584 | 100.0% | 0 |

## By Category

### V1 parameter

| Category | Candidates | Validated | Pass Rate |
|---|---:|---:|---:|
| Circles | 6541 | 6497 | 99.3273% |
| Polygons | 0 | 0 | 0.0% |
| Rects | 27 | 27 | 100.0% |

### V2 add

| Category | Candidates | Validated | Pass Rate |
|---|---:|---:|---:|
| Circles | 9404 | 9404 | 100.0% |
| Polygons | 0 | 0 | 0.0% |
| Rects | 80 | 80 | 100.0% |

### V3 delete

| Category | Candidates | Validated | Pass Rate |
|---|---:|---:|---:|
| Circles | 1584 | 1584 | 100.0% |
| Polygons | 0 | 0 | 0.0% |
| Rects | 0 | 0 | 0.0% |

### V4 replace

| Category | Candidates | Validated | Pass Rate |
|---|---:|---:|---:|
| Circles | 1584 | 1584 | 100.0% |
| Polygons | 0 | 0 | 0.0% |
| Rects | 0 | 0 | 0.0% |

## By Edit Type

### V1 parameter

| Edit Type | Candidates | Validated | Pass Rate |
|---|---:|---:|---:|
| chamfer | 4 | 4 | 100.0% |
| circle | 3256 | 3234 | 99.3243% |
| extrude | 2490 | 2468 | 99.1165% |
| fillet | 3 | 3 | 100.0% |
| hole | 815 | 815 | 100.0% |

### V2 add

| Edit Type | Candidates | Validated | Pass Rate |
|---|---:|---:|---:|
| add_blind_hole | 2371 | 2371 | 100.0% |
| add_pocket | 2371 | 2371 | 100.0% |
| add_rectangular_slot | 2371 | 2371 | 100.0% |
| add_through_hole | 2371 | 2371 | 100.0% |

### V3 delete

| Edit Type | Candidates | Validated | Pass Rate |
|---|---:|---:|---:|
| delete_circular_cutout | 772 | 772 | 100.0% |
| delete_hole | 812 | 812 | 100.0% |

### V4 replace

| Edit Type | Candidates | Validated | Pass Rate |
|---|---:|---:|---:|
| replace_circular_cutout_with_slot | 772 | 772 | 100.0% |
| replace_loop_holes_with_slots | 812 | 812 | 100.0% |

## Top Rejection Reasons

### V1 parameter

| Reason | Count |
|---|---:|
| `validation:result variable was not defined` | 44 |
| `skipped_original_syntax_error` | 10 |

### V2 add

| Reason | Count |
|---|---:|
| `skipped_bad_candidate_geometry` | 388 |
| `skipped_geometry_error` | 32 |
| `geometry_error:result variable was not defined` | 22 |
| `geometry_error:unexpected indent (<cadquery_source>, line 3)` | 8 |
| `geometry_error:invalid syntax (<cadquery_source>, line 4)` | 1 |
| `geometry_error:unexpected indent (<cadquery_source>, line 2)` | 1 |

### V3 delete

| Reason | Count |
|---|---:|
| `skipped_no_delete_candidate` | 884 |
| `skipped_unsupported_hole_context` | 815 |
| `skipped_geometry_error` | 22 |
| `geometry_error:result variable was not defined` | 22 |
| `skipped_unsupported_cut_context` | 14 |
| `skipped_syntax_error` | 10 |
| `syntax_error:unexpected indent (<unknown>, line 3)` | 8 |
| `syntax_error:invalid syntax (<unknown>, line 4)` | 1 |
| `syntax_error:unexpected indent (<unknown>, line 2)` | 1 |

### V4 replace

| Reason | Count |
|---|---:|
| `skipped_no_replace_candidate` | 916 |
| `delete_skipped_no_delete_candidate` | 884 |
| `delete_skipped_unsupported_hole_context` | 815 |
| `delete_skipped_geometry_error` | 22 |
| `delete_geometry_error:result variable was not defined` | 22 |
| `delete_skipped_unsupported_cut_context` | 14 |
| `delete_skipped_syntax_error` | 10 |
| `delete_syntax_error:unexpected indent (<unknown>, line 3)` | 8 |
| `delete_syntax_error:invalid syntax (<unknown>, line 4)` | 1 |
| `delete_syntax_error:unexpected indent (<unknown>, line 2)` | 1 |

## V4 Hole Diagnostics

| Type | Count |
|---|---:|
| hole_calls_total | 815 |
| simple_loop_holes | 812 |
| circular_cutout_via_cut_circle_extrude | 774 |
| hole_parse_error_records | 10 |
| other_unsupported_hole_contexts | 3 |

### V4 Hole Diagnostics By Category

#### Circles

| Type | Count |
|---|---:|
| hole_calls_total | 815 |
| simple_loop_holes | 812 |
| circular_cutout_via_cut_circle_extrude | 774 |
| hole_parse_error_records | 10 |
| other_unsupported_hole_contexts | 3 |

#### Rects

| Type | Count |
|---|---:|
| circular_cutout_via_cut_circle_extrude | 0 |

## Render Preview

Sample JSONL: `C:\Users\13105\Desktop\AAAI\outputs\coverage_expert3_expanded\chunks\chunk_03\preview_samples.jsonl`
Gallery: `C:\Users\13105\Desktop\AAAI\outputs\coverage_expert3_expanded\chunks\chunk_03\preview_gallery\index.html`
