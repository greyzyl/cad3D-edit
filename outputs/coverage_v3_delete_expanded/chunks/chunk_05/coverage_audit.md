# CAD Edit Coverage Audit - Expert 3

Input: `data_expert3_fixed_paths.jsonl`
Records: 2500
Elapsed seconds: 149.474

## Branch Summary

| Branch | Candidates | Validated | Pass Rate | Failed Validation |
|---|---:|---:|---:|---:|
| V3 delete | 1751 | 814 | 46.4877% | 937 |

## By Category

### V3 delete

| Category | Candidates | Validated | Pass Rate |
|---|---:|---:|---:|
| Circles | 0 | 0 | 0.0% |
| Polygons | 1502 | 565 | 37.6165% |
| Rects | 249 | 249 | 100.0% |

## By Edit Type

### V3 delete

| Edit Type | Candidates | Validated | Pass Rate |
|---|---:|---:|---:|
| delete_chamfer | 121 | 121 | 100.0% |
| delete_fillet | 612 | 128 | 20.915% |
| delete_hole | 528 | 75 | 14.2045% |
| delete_polygonal_cutout | 490 | 490 | 100.0% |

## Top Rejection Reasons

### V3 delete

| Reason | Count |
|---|---:|
| `validation:failed check: bbox_stable` | 879 |
| `skipped_no_delete_candidate` | 712 |
| `skipped_unsupported_hole_context` | 529 |
| `validation:failed check: changed_region_not_global` | 48 |
| `skipped_syntax_error` | 20 |
| `skipped_geometry_error` | 17 |
| `geometry_error:result variable was not defined` | 13 |
| `validation:changed-region check failed: Bnd_Box is void` | 10 |
| `syntax_error:unexpected indent (<unknown>, line 3)` | 9 |
| `syntax_error:unexpected indent (<unknown>, line 2)` | 8 |
| `skipped_unsupported_cut_context` | 5 |
| `geometry_error:Cannot cut type '<class 'ellipsis'>'` | 3 |
| `syntax_error:invalid syntax (<unknown>, line 3)` | 2 |
| `geometry_error:BRep_API: command not done` | 1 |
| `syntax_error:invalid syntax (<unknown>, line 2)` | 1 |

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

Sample JSONL: `C:\Users\13105\Desktop\AAAI\outputs\coverage_v3_delete_expanded\chunks\chunk_05\preview_samples.jsonl`
Gallery: `C:\Users\13105\Desktop\AAAI\outputs\coverage_v3_delete_expanded\chunks\chunk_05\preview_gallery\index.html`
