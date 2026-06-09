# CAD Edit Coverage Audit - Expert 3

Input: `data_expert3_fixed_paths.jsonl`
Records: 2500
Elapsed seconds: 96.054

## Branch Summary

| Branch | Candidates | Validated | Pass Rate | Failed Validation |
|---|---:|---:|---:|---:|
| V3 delete | 1223 | 1223 | 100.0% | 0 |

## By Category

### V3 delete

| Category | Candidates | Validated | Pass Rate |
|---|---:|---:|---:|
| Circles | 0 | 0 | 0.0% |
| Polygons | 0 | 0 | 0.0% |
| Rects | 1223 | 1223 | 100.0% |

## By Edit Type

### V3 delete

| Edit Type | Candidates | Validated | Pass Rate |
|---|---:|---:|---:|
| delete_chamfer | 634 | 634 | 100.0% |
| delete_fillet | 589 | 589 | 100.0% |

## Top Rejection Reasons

### V3 delete

| Reason | Count |
|---|---:|
| `skipped_no_delete_candidate` | 1247 |
| `skipped_syntax_error` | 20 |
| `syntax_error:unexpected indent (<unknown>, line 3)` | 18 |
| `skipped_geometry_error` | 10 |
| `geometry_error:result variable was not defined` | 10 |
| `syntax_error:invalid syntax (<unknown>, line 4)` | 1 |
| `syntax_error:unexpected indent (<unknown>, line 2)` | 1 |

## V4 Hole Diagnostics

| Type | Count |
|---|---:|
| hole_parse_error_records | 20 |
| circular_cutout_via_cut_circle_extrude | 0 |

### V4 Hole Diagnostics By Category

#### Rects

| Type | Count |
|---|---:|
| hole_parse_error_records | 20 |
| circular_cutout_via_cut_circle_extrude | 0 |

## Render Preview

Sample JSONL: `C:\Users\13105\Desktop\AAAI\outputs\coverage_v3_delete_expanded\chunks\chunk_04\preview_samples.jsonl`
Gallery: `C:\Users\13105\Desktop\AAAI\outputs\coverage_v3_delete_expanded\chunks\chunk_04\preview_gallery\index.html`
