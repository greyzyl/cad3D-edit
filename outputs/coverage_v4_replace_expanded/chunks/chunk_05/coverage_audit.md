# CAD Edit Coverage Audit - Expert 3

Input: `data_expert3_fixed_paths.jsonl`
Records: 2485
Elapsed seconds: 287.087

## Branch Summary

| Branch | Candidates | Validated | Pass Rate | Failed Validation |
|---|---:|---:|---:|---:|
| V4 replace | 1581 | 1008 | 63.7571% | 573 |

## By Category

### V4 replace

| Category | Candidates | Validated | Pass Rate |
|---|---:|---:|---:|
| Circles | 502 | 502 | 100.0% |
| Polygons | 816 | 243 | 29.7794% |
| Rects | 263 | 263 | 100.0% |

## By Edit Type

### V4 replace

| Edit Type | Candidates | Validated | Pass Rate |
|---|---:|---:|---:|
| replace_chamfer_with_fillet | 127 | 127 | 100.0% |
| replace_circular_cutout_with_polygonal_cutout | 178 | 178 | 100.0% |
| replace_circular_cutout_with_slot | 178 | 178 | 100.0% |
| replace_fillet_with_chamfer | 491 | 136 | 27.6986% |
| replace_loop_holes_with_slots | 212 | 205 | 96.6981% |
| replace_polygonal_cutout_with_circular_cutout | 373 | 162 | 43.4316% |
| replace_polygonal_cutout_with_slot | 22 | 22 | 100.0% |

## Top Rejection Reasons

### V4 replace

| Reason | Count |
|---|---:|
| `skipped_no_replace_candidate` | 1104 |
| `delete_skipped_no_delete_candidate` | 773 |
| `delete_skipped_unsupported_hole_context` | 521 |
| `skipped_slot_geometry` | 351 |
| `validation:failed check: bbox_stable` | 343 |
| `skipped_delete_validation_failed` | 305 |
| `validation:failed check: new_feature_changed_region_local` | 152 |
| `validation:Bnd_Box is void` | 59 |
| `delete_skipped_syntax_error` | 15 |
| `validation:BRep_API: command not done` | 12 |
| `delete_syntax_error:unexpected indent (<unknown>, line 3)` | 12 |
| `delete_skipped_geometry_error` | 11 |
| `delete_geometry_error:result variable was not defined` | 11 |
| `validation:failed check: slot_changed_region_local` | 7 |
| `delete_skipped_unsupported_cut_context` | 5 |
| `delete_syntax_error:unexpected indent (<unknown>, line 2)` | 2 |
| `delete_syntax_error:invalid syntax (<unknown>, line 2)` | 1 |

## V4 Hole Diagnostics

| Type | Count |
|---|---:|
| hole_calls_total | 521 |
| simple_loop_holes | 517 |
| circular_cutout_via_cut_circle_extrude | 179 |
| hole_parse_error_records | 15 |
| other_unsupported_hole_contexts | 4 |

### V4 Hole Diagnostics By Category

#### Circles

| Type | Count |
|---|---:|
| circular_cutout_via_cut_circle_extrude | 179 |
| hole_calls_total | 149 |
| simple_loop_holes | 146 |
| hole_parse_error_records | 6 |
| other_unsupported_hole_contexts | 3 |

#### Polygons

| Type | Count |
|---|---:|
| hole_calls_total | 372 |
| simple_loop_holes | 371 |
| hole_parse_error_records | 3 |
| other_unsupported_hole_contexts | 1 |
| circular_cutout_via_cut_circle_extrude | 0 |

#### Rects

| Type | Count |
|---|---:|
| hole_parse_error_records | 6 |
| circular_cutout_via_cut_circle_extrude | 0 |

## Render Preview

Sample JSONL: `outputs\coverage_v4_replace_expanded\chunks\chunk_05\preview_samples.jsonl`
Gallery: `outputs\coverage_v4_replace_expanded\chunks\chunk_05\preview_gallery\index.html`
