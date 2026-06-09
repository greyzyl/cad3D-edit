# CAD Edit Coverage Audit - Expert 3

Input: `data_expert3_fixed_paths.jsonl`
Records: 2500
Elapsed seconds: 1300.909

## Branch Summary

| Branch | Candidates | Validated | Pass Rate | Failed Validation |
|---|---:|---:|---:|---:|
| V1 parameter | 4232 | 4149 | 98.0388% | 83 |
| V2 add | 9840 | 9268 | 94.187% | 572 |
| V3 delete | 528 | 75 | 14.2045% | 453 |
| V4 replace | 75 | 66 | 88.0% | 9 |

## By Category

### V1 parameter

| Category | Candidates | Validated | Pass Rate |
|---|---:|---:|---:|
| Circles | 0 | 0 | 0.0% |
| Polygons | 3512 | 3457 | 98.4339% |
| Rects | 720 | 692 | 96.1111% |

### V2 add

| Category | Candidates | Validated | Pass Rate |
|---|---:|---:|---:|
| Circles | 0 | 0 | 0.0% |
| Polygons | 7960 | 7388 | 92.8141% |
| Rects | 1880 | 1880 | 100.0% |

### V3 delete

| Category | Candidates | Validated | Pass Rate |
|---|---:|---:|---:|
| Circles | 0 | 0 | 0.0% |
| Polygons | 528 | 75 | 14.2045% |
| Rects | 0 | 0 | 0.0% |

### V4 replace

| Category | Candidates | Validated | Pass Rate |
|---|---:|---:|---:|
| Circles | 0 | 0 | 0.0% |
| Polygons | 75 | 66 | 88.0% |
| Rects | 0 | 0 | 0.0% |

## By Edit Type

### V1 parameter

| Edit Type | Candidates | Validated | Pass Rate |
|---|---:|---:|---:|
| chamfer | 121 | 104 | 85.9504% |
| extrude | 2969 | 2958 | 99.6295% |
| fillet | 613 | 558 | 91.0277% |
| hole | 529 | 529 | 100.0% |

### V2 add

| Edit Type | Candidates | Validated | Pass Rate |
|---|---:|---:|---:|
| add_blind_hole | 2460 | 2204 | 89.5935% |
| add_pocket | 2460 | 2393 | 97.2764% |
| add_rectangular_slot | 2460 | 2450 | 99.5935% |
| add_through_hole | 2460 | 2221 | 90.2846% |

### V3 delete

| Edit Type | Candidates | Validated | Pass Rate |
|---|---:|---:|---:|
| delete_hole | 528 | 75 | 14.2045% |

### V4 replace

| Edit Type | Candidates | Validated | Pass Rate |
|---|---:|---:|---:|
| replace_loop_holes_with_slots | 75 | 66 | 88.0% |

## Top Rejection Reasons

### V1 parameter

| Reason | Count |
|---|---:|
| `validation:StdFail_NotDone: BRep_API: command not done` | 73 |
| `skipped_original_syntax_error` | 20 |
| `validation:result variable was not defined` | 7 |
| `skipped_no_candidates` | 6 |
| `validation:ValueError: Cannot cut type '<class 'ellipsis'>'` | 3 |

### V2 add

| Reason | Count |
|---|---:|
| `validation:changed-region check failed: Bnd_Box is void` | 572 |
| `skipped_geometry_error` | 37 |
| `geometry_error:result variable was not defined` | 13 |
| `skipped_bad_candidate_geometry` | 12 |
| `geometry_error:unexpected indent (<cadquery_source>, line 3)` | 9 |
| `geometry_error:unexpected indent (<cadquery_source>, line 2)` | 8 |
| `geometry_error:Cannot cut type '<class 'ellipsis'>'` | 3 |
| `geometry_error:invalid syntax (<cadquery_source>, line 3)` | 2 |
| `geometry_error:BRep_API: command not done` | 1 |
| `geometry_error:invalid syntax (<cadquery_source>, line 2)` | 1 |

### V3 delete

| Reason | Count |
|---|---:|
| `skipped_no_delete_candidate` | 1935 |
| `skipped_unsupported_hole_context` | 529 |
| `skipped_unsupported_cut_context` | 495 |
| `validation:failed check: bbox_stable` | 395 |
| `validation:failed check: changed_region_not_global` | 48 |
| `skipped_syntax_error` | 20 |
| `skipped_geometry_error` | 17 |
| `geometry_error:result variable was not defined` | 13 |
| `validation:changed-region check failed: Bnd_Box is void` | 10 |
| `syntax_error:unexpected indent (<unknown>, line 3)` | 9 |
| `syntax_error:unexpected indent (<unknown>, line 2)` | 8 |
| `geometry_error:Cannot cut type '<class 'ellipsis'>'` | 3 |
| `syntax_error:invalid syntax (<unknown>, line 3)` | 2 |
| `geometry_error:BRep_API: command not done` | 1 |
| `syntax_error:invalid syntax (<unknown>, line 2)` | 1 |

### V4 replace

| Reason | Count |
|---|---:|
| `skipped_no_replace_candidate` | 2425 |
| `delete_skipped_no_delete_candidate` | 1935 |
| `delete_skipped_unsupported_hole_context` | 529 |
| `delete_skipped_unsupported_cut_context` | 495 |
| `skipped_delete_validation_failed` | 453 |
| `delete_skipped_syntax_error` | 20 |
| `delete_skipped_geometry_error` | 17 |
| `delete_geometry_error:result variable was not defined` | 13 |
| `delete_syntax_error:unexpected indent (<unknown>, line 3)` | 9 |
| `validation:failed check: slot_changed_region_local` | 9 |
| `delete_syntax_error:unexpected indent (<unknown>, line 2)` | 8 |
| `delete_geometry_error:Cannot cut type '<class 'ellipsis'>'` | 3 |
| `delete_syntax_error:invalid syntax (<unknown>, line 3)` | 2 |
| `delete_geometry_error:BRep_API: command not done` | 1 |
| `delete_syntax_error:invalid syntax (<unknown>, line 2)` | 1 |

## V4 Hole Diagnostics

| Type | Count |
|---|---:|
| hole_calls_total | 529 |
| simple_loop_holes | 528 |
| hole_parse_error_records | 20 |
| other_unsupported_hole_contexts | 1 |
| circular_cutout_via_cut_circle_extrude | 0 |

### V4 Hole Diagnostics By Category

#### Polygons

| Type | Count |
|---|---:|
| hole_calls_total | 529 |
| simple_loop_holes | 528 |
| hole_parse_error_records | 19 |
| other_unsupported_hole_contexts | 1 |
| circular_cutout_via_cut_circle_extrude | 0 |

#### Rects

| Type | Count |
|---|---:|
| hole_parse_error_records | 1 |
| circular_cutout_via_cut_circle_extrude | 0 |

## Render Preview

Sample JSONL: `C:\Users\13105\Desktop\AAAI\outputs\coverage_expert3_expanded\chunks\chunk_05\preview_samples.jsonl`
Gallery: `C:\Users\13105\Desktop\AAAI\outputs\coverage_expert3_expanded\chunks\chunk_05\preview_gallery\index.html`
