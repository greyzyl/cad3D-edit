# CAD Edit Coverage Audit - Expert 3

Input: `data_expert3_fixed_paths.jsonl`
Records: 2500
Elapsed seconds: 1160.873

## Branch Summary

| Branch | Candidates | Validated | Pass Rate | Failed Validation |
|---|---:|---:|---:|---:|
| V1 parameter | 5376 | 5310 | 98.7723% | 66 |
| V2 add | 9572 | 9572 | 100.0% | 0 |
| V3 delete | 930 | 930 | 100.0% | 0 |
| V4 replace | 930 | 930 | 100.0% | 0 |

## By Category

### V1 parameter

| Category | Candidates | Validated | Pass Rate |
|---|---:|---:|---:|
| Circles | 3898 | 3873 | 99.3586% |
| Polygons | 0 | 0 | 0.0% |
| Rects | 1478 | 1437 | 97.226% |

### V2 add

| Category | Candidates | Validated | Pass Rate |
|---|---:|---:|---:|
| Circles | 5600 | 5600 | 100.0% |
| Polygons | 0 | 0 | 0.0% |
| Rects | 3972 | 3972 | 100.0% |

### V3 delete

| Category | Candidates | Validated | Pass Rate |
|---|---:|---:|---:|
| Circles | 930 | 930 | 100.0% |
| Polygons | 0 | 0 | 0.0% |
| Rects | 0 | 0 | 0.0% |

### V4 replace

| Category | Candidates | Validated | Pass Rate |
|---|---:|---:|---:|
| Circles | 930 | 930 | 100.0% |
| Polygons | 0 | 0 | 0.0% |
| Rects | 0 | 0 | 0.0% |

## By Edit Type

### V1 parameter

| Edit Type | Candidates | Validated | Pass Rate |
|---|---:|---:|---:|
| chamfer | 245 | 224 | 91.4286% |
| circle | 1963 | 1949 | 99.2868% |
| extrude | 2467 | 2456 | 99.5541% |
| fillet | 240 | 220 | 91.6667% |
| hole | 461 | 461 | 100.0% |

### V2 add

| Edit Type | Candidates | Validated | Pass Rate |
|---|---:|---:|---:|
| add_blind_hole | 2393 | 2393 | 100.0% |
| add_pocket | 2393 | 2393 | 100.0% |
| add_rectangular_slot | 2393 | 2393 | 100.0% |
| add_through_hole | 2393 | 2393 | 100.0% |

### V3 delete

| Edit Type | Candidates | Validated | Pass Rate |
|---|---:|---:|---:|
| delete_circular_cutout | 472 | 472 | 100.0% |
| delete_hole | 458 | 458 | 100.0% |

### V4 replace

| Edit Type | Candidates | Validated | Pass Rate |
|---|---:|---:|---:|
| replace_circular_cutout_with_slot | 472 | 472 | 100.0% |
| replace_loop_holes_with_slots | 458 | 458 | 100.0% |

## Top Rejection Reasons

### V1 parameter

| Reason | Count |
|---|---:|
| `validation:StdFail_NotDone: BRep_API: command not done` | 41 |
| `skipped_original_syntax_error` | 28 |
| `validation:result variable was not defined` | 25 |
| `skipped_no_candidates` | 2 |

### V2 add

| Reason | Count |
|---|---:|
| `skipped_bad_candidate_geometry` | 252 |
| `skipped_geometry_error` | 44 |
| `geometry_error:unexpected indent (<cadquery_source>, line 3)` | 23 |
| `geometry_error:result variable was not defined` | 16 |
| `geometry_error:unexpected indent (<cadquery_source>, line 2)` | 3 |
| `geometry_error:invalid syntax (<cadquery_source>, line 2)` | 2 |

### V3 delete

| Reason | Count |
|---|---:|
| `skipped_no_delete_candidate` | 1526 |
| `skipped_unsupported_hole_context` | 461 |
| `skipped_syntax_error` | 28 |
| `syntax_error:unexpected indent (<unknown>, line 3)` | 23 |
| `skipped_geometry_error` | 16 |
| `geometry_error:result variable was not defined` | 16 |
| `skipped_unsupported_cut_context` | 14 |
| `syntax_error:unexpected indent (<unknown>, line 2)` | 3 |
| `syntax_error:invalid syntax (<unknown>, line 2)` | 2 |

### V4 replace

| Reason | Count |
|---|---:|
| `skipped_no_replace_candidate` | 1570 |
| `delete_skipped_no_delete_candidate` | 1526 |
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

Sample JSONL: `C:\Users\13105\Desktop\AAAI\outputs\coverage_expert3_expanded\chunks\chunk_01\preview_samples.jsonl`
Gallery: `C:\Users\13105\Desktop\AAAI\outputs\coverage_expert3_expanded\chunks\chunk_01\preview_gallery\index.html`
