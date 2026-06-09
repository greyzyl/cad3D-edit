# CAD Edit Coverage Audit - Expert 3

Input: `data_expert3_fixed_paths.jsonl`
Records: 14935
Elapsed seconds: 149.474

## Branch Summary

| Branch | Candidates | Validated | Pass Rate | Failed Validation |
|---|---:|---:|---:|---:|
| V3 delete | 9302 | 7049 | 75.7794% | 2253 |

## By Category

### V3 delete

| Category | Candidates | Validated | Pass Rate |
|---|---:|---:|---:|
| Circles | 3170 | 3170 | 100.0% |
| Polygons | 3659 | 1406 | 38.4258% |
| Rects | 2473 | 2473 | 100.0% |

## By Edit Type

### V3 delete

| Edit Type | Candidates | Validated | Pass Rate |
|---|---:|---:|---:|
| delete_chamfer | 1260 | 1260 | 100.0% |
| delete_circular_cutout | 1600 | 1600 | 100.0% |
| delete_fillet | 2396 | 1213 | 50.626% |
| delete_hole | 2839 | 1769 | 62.3107% |
| delete_polygonal_cutout | 1207 | 1207 | 100.0% |

## Top Rejection Reasons

### V3 delete

| Reason | Count |
|---|---:|
| `skipped_no_delete_candidate` | 5455 |
| `skipped_unsupported_hole_context` | 2850 |
| `validation:failed check: bbox_stable` | 2115 |
| `validation:failed check: changed_region_not_global` | 121 |
| `skipped_syntax_error` | 96 |
| `skipped_geometry_error` | 82 |
| `geometry_error:result variable was not defined` | 78 |
| `syntax_error:unexpected indent (<unknown>, line 3)` | 72 |
| `skipped_unsupported_cut_context` | 40 |
| `validation:changed-region check failed: Bnd_Box is void` | 17 |
| `syntax_error:unexpected indent (<unknown>, line 2)` | 16 |
| `syntax_error:invalid syntax (<unknown>, line 2)` | 4 |
| `geometry_error:Cannot cut type '<class 'ellipsis'>'` | 3 |
| `syntax_error:invalid syntax (<unknown>, line 4)` | 2 |
| `syntax_error:invalid syntax (<unknown>, line 3)` | 2 |
| `geometry_error:BRep_API: command not done` | 1 |

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

Sample JSONL: `outputs\coverage_v3_delete_expanded\preview_samples.jsonl`
Gallery: `outputs\coverage_v3_delete_expanded\preview_gallery\index.html`
