# CAD Edit Coverage Audit - Expert 3

Input: `data_expert3_fixed_paths.jsonl`
Records: 2500
Elapsed seconds: 124.313

## Branch Summary

| Branch | Candidates | Validated | Pass Rate | Failed Validation |
|---|---:|---:|---:|---:|
| V3 delete | 1591 | 1591 | 100.0% | 0 |

## By Category

### V3 delete

| Category | Candidates | Validated | Pass Rate |
|---|---:|---:|---:|
| Circles | 1584 | 1584 | 100.0% |
| Polygons | 0 | 0 | 0.0% |
| Rects | 7 | 7 | 100.0% |

## By Edit Type

### V3 delete

| Edit Type | Candidates | Validated | Pass Rate |
|---|---:|---:|---:|
| delete_chamfer | 4 | 4 | 100.0% |
| delete_circular_cutout | 772 | 772 | 100.0% |
| delete_fillet | 3 | 3 | 100.0% |
| delete_hole | 812 | 812 | 100.0% |

## Top Rejection Reasons

### V3 delete

| Reason | Count |
|---|---:|
| `skipped_no_delete_candidate` | 877 |
| `skipped_unsupported_hole_context` | 815 |
| `skipped_geometry_error` | 22 |
| `geometry_error:result variable was not defined` | 22 |
| `skipped_unsupported_cut_context` | 14 |
| `skipped_syntax_error` | 10 |
| `syntax_error:unexpected indent (<unknown>, line 3)` | 8 |
| `syntax_error:invalid syntax (<unknown>, line 4)` | 1 |
| `syntax_error:unexpected indent (<unknown>, line 2)` | 1 |

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

Sample JSONL: `C:\Users\13105\Desktop\AAAI\outputs\coverage_v3_delete_expanded\chunks\chunk_03\preview_samples.jsonl`
Gallery: `C:\Users\13105\Desktop\AAAI\outputs\coverage_v3_delete_expanded\chunks\chunk_03\preview_gallery\index.html`
