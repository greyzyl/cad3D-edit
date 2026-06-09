# CAD Edit Coverage Audit - Expert 3

Input: `data_expert3_fixed_paths.jsonl`
Records: 14935
Elapsed seconds: 1395.662

## Branch Summary

| Branch | Candidates | Validated | Pass Rate | Failed Validation |
|---|---:|---:|---:|---:|
| V1 parameter | 29131 | 28661 | 98.3866% | 470 |
| V2 add | 58200 | 56891 | 97.7509% | 1309 |
| V3 delete | 4439 | 3369 | 75.8955% | 1070 |
| V4 replace | 3369 | 3349 | 99.4064% | 20 |

## By Category

### V1 parameter

| Category | Candidates | Validated | Pass Rate |
|---|---:|---:|---:|
| Circles | 13129 | 13040 | 99.3221% |
| Polygons | 8586 | 8445 | 98.3578% |
| Rects | 7416 | 7176 | 96.7638% |

### V2 add

| Category | Candidates | Validated | Pass Rate |
|---|---:|---:|---:|
| Circles | 18844 | 18844 | 100.0% |
| Polygons | 19600 | 18291 | 93.3214% |
| Rects | 19756 | 19756 | 100.0% |

### V3 delete

| Category | Candidates | Validated | Pass Rate |
|---|---:|---:|---:|
| Circles | 3170 | 3170 | 100.0% |
| Polygons | 1269 | 199 | 15.6816% |
| Rects | 0 | 0 | 0.0% |

### V4 replace

| Category | Candidates | Validated | Pass Rate |
|---|---:|---:|---:|
| Circles | 3170 | 3170 | 100.0% |
| Polygons | 199 | 179 | 89.9497% |
| Rects | 0 | 0 | 0.0% |

## By Edit Type

### V1 parameter

| Edit Type | Candidates | Validated | Pass Rate |
|---|---:|---:|---:|
| chamfer | 1261 | 1122 | 88.977% |
| circle | 6593 | 6547 | 99.3023% |
| extrude | 16030 | 15971 | 99.6319% |
| fillet | 2397 | 2171 | 90.5715% |
| hole | 2850 | 2850 | 100.0% |

### V2 add

| Edit Type | Candidates | Validated | Pass Rate |
|---|---:|---:|---:|
| add_blind_hole | 14550 | 13966 | 95.9863% |
| add_pocket | 14550 | 14388 | 98.8866% |
| add_rectangular_slot | 14550 | 14527 | 99.8419% |
| add_through_hole | 14550 | 14010 | 96.2887% |

### V3 delete

| Edit Type | Candidates | Validated | Pass Rate |
|---|---:|---:|---:|
| delete_circular_cutout | 1600 | 1600 | 100.0% |
| delete_hole | 2839 | 1769 | 62.3107% |

### V4 replace

| Edit Type | Candidates | Validated | Pass Rate |
|---|---:|---:|---:|
| replace_circular_cutout_with_slot | 1600 | 1600 | 100.0% |
| replace_loop_holes_with_slots | 1769 | 1749 | 98.8694% |

## Top Rejection Reasons

### V1 parameter

| Reason | Count |
|---|---:|
| `validation:StdFail_NotDone: BRep_API: command not done` | 365 |
| `validation:result variable was not defined` | 102 |
| `skipped_original_syntax_error` | 96 |
| `skipped_no_candidates` | 20 |
| `validation:ValueError: Cannot cut type '<class 'ellipsis'>'` | 3 |

### V2 add

| Reason | Count |
|---|---:|
| `validation:changed-region check failed: Bnd_Box is void` | 1308 |
| `skipped_bad_candidate_geometry` | 828 |
| `skipped_geometry_error` | 178 |
| `geometry_error:result variable was not defined` | 78 |
| `geometry_error:unexpected indent (<cadquery_source>, line 3)` | 72 |
| `geometry_error:unexpected indent (<cadquery_source>, line 2)` | 16 |
| `geometry_error:invalid syntax (<cadquery_source>, line 2)` | 4 |
| `geometry_error:Cannot cut type '<class 'ellipsis'>'` | 3 |
| `geometry_error:invalid syntax (<cadquery_source>, line 4)` | 2 |
| `geometry_error:invalid syntax (<cadquery_source>, line 3)` | 2 |
| `geometry_error:BRep_API: command not done` | 1 |
| `validation:failed check: volume_direction_ok` | 1 |

### V3 delete

| Reason | Count |
|---|---:|
| `skipped_no_delete_candidate` | 10318 |
| `skipped_unsupported_hole_context` | 2850 |
| `skipped_unsupported_cut_context` | 1247 |
| `validation:failed check: bbox_stable` | 932 |
| `validation:failed check: changed_region_not_global` | 121 |
| `skipped_syntax_error` | 96 |
| `skipped_geometry_error` | 82 |
| `geometry_error:result variable was not defined` | 78 |
| `syntax_error:unexpected indent (<unknown>, line 3)` | 72 |
| `validation:changed-region check failed: Bnd_Box is void` | 17 |
| `syntax_error:unexpected indent (<unknown>, line 2)` | 16 |
| `syntax_error:invalid syntax (<unknown>, line 2)` | 4 |
| `geometry_error:Cannot cut type '<class 'ellipsis'>'` | 3 |
| `syntax_error:invalid syntax (<unknown>, line 4)` | 2 |
| `syntax_error:invalid syntax (<unknown>, line 3)` | 2 |
| `geometry_error:BRep_API: command not done` | 1 |

### V4 replace

| Reason | Count |
|---|---:|
| `skipped_no_replace_candidate` | 11566 |
| `delete_skipped_no_delete_candidate` | 10318 |
| `delete_skipped_unsupported_hole_context` | 2850 |
| `delete_skipped_unsupported_cut_context` | 1247 |
| `skipped_delete_validation_failed` | 1070 |
| `delete_skipped_syntax_error` | 96 |
| `delete_skipped_geometry_error` | 82 |
| `delete_geometry_error:result variable was not defined` | 78 |
| `delete_syntax_error:unexpected indent (<unknown>, line 3)` | 72 |
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

Sample JSONL: `outputs\coverage_expert3_expanded\preview_samples.jsonl`
Gallery: `outputs\coverage_expert3_expanded\preview_gallery\index.html`
