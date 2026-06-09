# CAD Edit Coverage Audit - Expert 3

Input: `data_expert3_fixed_paths.jsonl`
Records: 14935
Elapsed seconds: 314.185

## Branch Summary

| Branch | Candidates | Validated | Pass Rate | Failed Validation |
|---|---:|---:|---:|---:|
| V4 replace | 9903 | 8012 | 80.9048% | 1891 |

## By Category

### V4 replace

| Category | Candidates | Validated | Pass Rate |
|---|---:|---:|---:|
| Circles | 4770 | 4770 | 100.0% |
| Polygons | 2660 | 769 | 28.9098% |
| Rects | 2473 | 2473 | 100.0% |

## By Edit Type

### V4 replace

| Edit Type | Candidates | Validated | Pass Rate |
|---|---:|---:|---:|
| replace_chamfer_with_fillet | 1260 | 1260 | 100.0% |
| replace_circular_cutout_with_polygonal_cutout | 1600 | 1600 | 100.0% |
| replace_circular_cutout_with_slot | 1600 | 1600 | 100.0% |
| replace_fillet_with_chamfer | 2396 | 1213 | 50.626% |
| replace_loop_holes_with_slots | 1769 | 1749 | 98.8694% |
| replace_polygonal_cutout_with_circular_cutout | 1207 | 519 | 42.9992% |
| replace_polygonal_cutout_with_slot | 71 | 71 | 100.0% |

## Top Rejection Reasons

### V4 replace

| Reason | Count |
|---|---:|
| `skipped_no_replace_candidate` | 6703 |
| `delete_skipped_no_delete_candidate` | 5455 |
| `delete_skipped_unsupported_hole_context` | 2850 |
| `validation:failed check: bbox_stable` | 1140 |
| `skipped_slot_geometry` | 1136 |
| `skipped_delete_validation_failed` | 1070 |
| `validation:failed check: new_feature_changed_region_local` | 519 |
| `validation:Bnd_Box is void` | 169 |
| `delete_skipped_syntax_error` | 96 |
| `delete_skipped_geometry_error` | 82 |
| `delete_geometry_error:result variable was not defined` | 78 |
| `delete_syntax_error:unexpected indent (<unknown>, line 3)` | 72 |
| `validation:BRep_API: command not done` | 43 |
| `delete_skipped_unsupported_cut_context` | 40 |
| `validation:failed check: slot_changed_region_local` | 20 |
| `delete_syntax_error:unexpected indent (<unknown>, line 2)` | 16 |
| `delete_syntax_error:invalid syntax (<unknown>, line 2)` | 4 |
| `delete_geometry_error:Cannot cut type '<class 'ellipsis'>'` | 3 |
| `delete_syntax_error:invalid syntax (<unknown>, line 4)` | 2 |
| `delete_syntax_error:invalid syntax (<unknown>, line 3)` | 2 |
| `delete_geometry_error:BRep_API: command not done` | 1 |

## V4 Hole Diagnostics

| Type | Count |
|---|---:|
| hole_calls_total | 2850 |
| simple_loop_holes | 2839 |
| circular_cutout_via_cut_circle_extrude | 1607 |
| hole_parse_error_records | 96 |
| other_unsupported_hole_contexts | 11 |

### V4 Hole Diagnostics By Category

#### Circles

| Type | Count |
|---|---:|
| circular_cutout_via_cut_circle_extrude | 1607 |
| hole_calls_total | 1579 |
| simple_loop_holes | 1570 |
| hole_parse_error_records | 40 |
| other_unsupported_hole_contexts | 9 |

#### Polygons

| Type | Count |
|---|---:|
| hole_calls_total | 1271 |
| simple_loop_holes | 1269 |
| hole_parse_error_records | 22 |
| other_unsupported_hole_contexts | 2 |
| circular_cutout_via_cut_circle_extrude | 0 |

#### Rects

| Type | Count |
|---|---:|
| hole_parse_error_records | 34 |
| circular_cutout_via_cut_circle_extrude | 0 |

## Render Preview

Sample JSONL: `outputs\coverage_v4_replace_expanded\preview_samples.jsonl`
Gallery: `outputs\coverage_v4_replace_expanded\preview_gallery\index.html`
