# CAD Edit Coverage Audit - Expert 3

Input: `data_expert3_fixed_paths.jsonl`
Records: 2490
Elapsed seconds: 284.563

## Branch Summary

| Branch | Candidates | Validated | Pass Rate | Failed Validation |
|---|---:|---:|---:|---:|
| V4 replace | 1540 | 987 | 64.0909% | 553 |

## By Category

### V4 replace

| Category | Candidates | Validated | Pass Rate |
|---|---:|---:|---:|
| Circles | 493 | 493 | 100.0% |
| Polygons | 798 | 245 | 30.7018% |
| Rects | 249 | 249 | 100.0% |

## By Edit Type

### V4 replace

| Edit Type | Candidates | Validated | Pass Rate |
|---|---:|---:|---:|
| replace_chamfer_with_fillet | 132 | 132 | 100.0% |
| replace_circular_cutout_with_polygonal_cutout | 172 | 172 | 100.0% |
| replace_circular_cutout_with_slot | 172 | 172 | 100.0% |
| replace_fillet_with_chamfer | 468 | 117 | 25.0% |
| replace_loop_holes_with_slots | 213 | 209 | 98.1221% |
| replace_polygonal_cutout_with_circular_cutout | 363 | 165 | 45.4545% |
| replace_polygonal_cutout_with_slot | 20 | 20 | 100.0% |

## Top Rejection Reasons

### V4 replace

| Reason | Count |
|---|---:|
| `skipped_no_replace_candidate` | 1142 |
| `delete_skipped_no_delete_candidate` | 812 |
| `delete_skipped_unsupported_hole_context` | 534 |
| `skipped_slot_geometry` | 343 |
| `validation:failed check: bbox_stable` | 335 |
| `skipped_delete_validation_failed` | 321 |
| `validation:failed check: new_feature_changed_region_local` | 152 |
| `validation:Bnd_Box is void` | 46 |
| `validation:BRep_API: command not done` | 16 |
| `delete_skipped_geometry_error` | 6 |
| `delete_geometry_error:result variable was not defined` | 6 |
| `validation:failed check: slot_changed_region_local` | 4 |
| `delete_skipped_syntax_error` | 3 |
| `delete_syntax_error:unexpected indent (<unknown>, line 3)` | 2 |
| `delete_skipped_unsupported_cut_context` | 2 |
| `delete_syntax_error:unexpected indent (<unknown>, line 2)` | 1 |

## V4 Hole Diagnostics

| Type | Count |
|---|---:|
| hole_calls_total | 534 |
| simple_loop_holes | 534 |
| circular_cutout_via_cut_circle_extrude | 173 |
| hole_parse_error_records | 3 |

### V4 Hole Diagnostics By Category

#### Circles

| Type | Count |
|---|---:|
| circular_cutout_via_cut_circle_extrude | 173 |
| hole_calls_total | 149 |
| simple_loop_holes | 149 |
| hole_parse_error_records | 1 |

#### Polygons

| Type | Count |
|---|---:|
| hole_calls_total | 385 |
| simple_loop_holes | 385 |
| circular_cutout_via_cut_circle_extrude | 0 |

#### Rects

| Type | Count |
|---|---:|
| hole_parse_error_records | 2 |
| circular_cutout_via_cut_circle_extrude | 0 |

## Render Preview

Sample JSONL: `outputs\coverage_v4_replace_expanded\chunks\chunk_01\preview_samples.jsonl`
Gallery: `outputs\coverage_v4_replace_expanded\chunks\chunk_01\preview_gallery\index.html`
