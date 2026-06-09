# CAD Edit Coverage Audit - Expert 3

Input: `data_expert3_fixed_paths.jsonl`
Records: 2500
Elapsed seconds: 843.357

## Branch Summary

| Branch | Candidates | Validated | Pass Rate | Failed Validation |
|---|---:|---:|---:|---:|
| V1 parameter | 3696 | 3577 | 96.7803% | 119 |
| V2 add | 9880 | 9880 | 100.0% | 0 |
| V3 delete | 0 | 0 | 0.0% | 0 |
| V4 replace | 0 | 0 | 0.0% | 0 |

## By Category

### V1 parameter

| Category | Candidates | Validated | Pass Rate |
|---|---:|---:|---:|
| Circles | 0 | 0 | 0.0% |
| Polygons | 0 | 0 | 0.0% |
| Rects | 3696 | 3577 | 96.7803% |

### V2 add

| Category | Candidates | Validated | Pass Rate |
|---|---:|---:|---:|
| Circles | 0 | 0 | 0.0% |
| Polygons | 0 | 0 | 0.0% |
| Rects | 9880 | 9880 | 100.0% |

### V3 delete

| Category | Candidates | Validated | Pass Rate |
|---|---:|---:|---:|
| Circles | 0 | 0 | 0.0% |
| Polygons | 0 | 0 | 0.0% |
| Rects | 0 | 0 | 0.0% |

### V4 replace

| Category | Candidates | Validated | Pass Rate |
|---|---:|---:|---:|
| Circles | 0 | 0 | 0.0% |
| Polygons | 0 | 0 | 0.0% |
| Rects | 0 | 0 | 0.0% |

## By Edit Type

### V1 parameter

| Edit Type | Candidates | Validated | Pass Rate |
|---|---:|---:|---:|
| chamfer | 635 | 567 | 89.2913% |
| extrude | 2472 | 2470 | 99.9191% |
| fillet | 589 | 540 | 91.6808% |

### V2 add

| Edit Type | Candidates | Validated | Pass Rate |
|---|---:|---:|---:|
| add_blind_hole | 2470 | 2470 | 100.0% |
| add_pocket | 2470 | 2470 | 100.0% |
| add_rectangular_slot | 2470 | 2470 | 100.0% |
| add_through_hole | 2470 | 2470 | 100.0% |

### V3 delete

| Edit Type | Candidates | Validated | Pass Rate |
|---|---:|---:|---:|

### V4 replace

| Edit Type | Candidates | Validated | Pass Rate |
|---|---:|---:|---:|

## Top Rejection Reasons

### V1 parameter

| Reason | Count |
|---|---:|
| `validation:StdFail_NotDone: BRep_API: command not done` | 116 |
| `skipped_original_syntax_error` | 20 |
| `skipped_no_candidates` | 8 |
| `validation:result variable was not defined` | 3 |

### V2 add

| Reason | Count |
|---|---:|
| `skipped_geometry_error` | 30 |
| `geometry_error:unexpected indent (<cadquery_source>, line 3)` | 18 |
| `geometry_error:result variable was not defined` | 10 |
| `geometry_error:invalid syntax (<cadquery_source>, line 4)` | 1 |
| `geometry_error:unexpected indent (<cadquery_source>, line 2)` | 1 |

### V3 delete

| Reason | Count |
|---|---:|
| `skipped_no_delete_candidate` | 2470 |
| `skipped_syntax_error` | 20 |
| `syntax_error:unexpected indent (<unknown>, line 3)` | 18 |
| `skipped_geometry_error` | 10 |
| `geometry_error:result variable was not defined` | 10 |
| `syntax_error:invalid syntax (<unknown>, line 4)` | 1 |
| `syntax_error:unexpected indent (<unknown>, line 2)` | 1 |

### V4 replace

| Reason | Count |
|---|---:|
| `skipped_no_replace_candidate` | 2500 |
| `delete_skipped_no_delete_candidate` | 2470 |
| `delete_skipped_syntax_error` | 20 |
| `delete_syntax_error:unexpected indent (<unknown>, line 3)` | 18 |
| `delete_skipped_geometry_error` | 10 |
| `delete_geometry_error:result variable was not defined` | 10 |
| `delete_syntax_error:invalid syntax (<unknown>, line 4)` | 1 |
| `delete_syntax_error:unexpected indent (<unknown>, line 2)` | 1 |

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

Sample JSONL: `C:\Users\13105\Desktop\AAAI\outputs\coverage_expert3_expanded\chunks\chunk_04\preview_samples.jsonl`
Gallery: `C:\Users\13105\Desktop\AAAI\outputs\coverage_expert3_expanded\chunks\chunk_04\preview_gallery\index.html`
