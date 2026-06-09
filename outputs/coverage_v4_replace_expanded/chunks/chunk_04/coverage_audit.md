# CAD Edit Coverage Audit - Expert 3

Input: `data_expert3_fixed_paths.jsonl`
Records: 2490
Elapsed seconds: 281.338

## Branch Summary

| Branch | Candidates | Validated | Pass Rate | Failed Validation |
|---|---:|---:|---:|---:|
| V4 replace | 1319 | 554 | 42.0015% | 765 |

## By Category

### V4 replace

| Category | Candidates | Validated | Pass Rate |
|---|---:|---:|---:|
| Circles | 0 | 0 | 0.0% |
| Polygons | 1046 | 281 | 26.8642% |
| Rects | 273 | 273 | 100.0% |

## By Edit Type

### V4 replace

| Edit Type | Candidates | Validated | Pass Rate |
|---|---:|---:|---:|
| replace_chamfer_with_fillet | 136 | 136 | 100.0% |
| replace_fillet_with_chamfer | 614 | 137 | 22.3127% |
| replace_loop_holes_with_slots | 69 | 60 | 86.9565% |
| replace_polygonal_cutout_with_circular_cutout | 471 | 192 | 40.7643% |
| replace_polygonal_cutout_with_slot | 29 | 29 | 100.0% |

## Top Rejection Reasons

### V4 replace

| Reason | Count |
|---|---:|
| `skipped_no_replace_candidate` | 1200 |
| `delete_skipped_no_delete_candidate` | 718 |
| `delete_skipped_unsupported_hole_context` | 514 |
| `validation:failed check: bbox_stable` | 462 |
| `skipped_delete_validation_failed` | 444 |
| `skipped_slot_geometry` | 442 |
| `validation:failed check: new_feature_changed_region_local` | 215 |
| `validation:Bnd_Box is void` | 64 |
| `delete_skipped_syntax_error` | 21 |
| `delete_skipped_geometry_error` | 17 |
| `validation:BRep_API: command not done` | 15 |
| `delete_geometry_error:result variable was not defined` | 13 |
| `delete_syntax_error:unexpected indent (<unknown>, line 3)` | 10 |
| `validation:failed check: slot_changed_region_local` | 9 |
| `delete_syntax_error:unexpected indent (<unknown>, line 2)` | 8 |
| `delete_skipped_unsupported_cut_context` | 5 |
| `delete_geometry_error:Cannot cut type '<class 'ellipsis'>'` | 3 |
| `delete_syntax_error:invalid syntax (<unknown>, line 3)` | 2 |
| `delete_geometry_error:BRep_API: command not done` | 1 |
| `delete_syntax_error:invalid syntax (<unknown>, line 2)` | 1 |

## V4 Hole Diagnostics

| Type | Count |
|---|---:|
| hole_calls_total | 514 |
| simple_loop_holes | 513 |
| hole_parse_error_records | 21 |
| other_unsupported_hole_contexts | 1 |
| circular_cutout_via_cut_circle_extrude | 0 |

### V4 Hole Diagnostics By Category

#### Polygons

| Type | Count |
|---|---:|
| hole_calls_total | 514 |
| simple_loop_holes | 513 |
| hole_parse_error_records | 19 |
| other_unsupported_hole_contexts | 1 |
| circular_cutout_via_cut_circle_extrude | 0 |

#### Rects

| Type | Count |
|---|---:|
| hole_parse_error_records | 2 |
| circular_cutout_via_cut_circle_extrude | 0 |

## Render Preview

Sample JSONL: `outputs\coverage_v4_replace_expanded\chunks\chunk_04\preview_samples.jsonl`
Gallery: `outputs\coverage_v4_replace_expanded\chunks\chunk_04\preview_gallery\index.html`
