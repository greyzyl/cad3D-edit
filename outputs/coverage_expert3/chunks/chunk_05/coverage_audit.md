# CAD Edit Coverage Audit - Expert 3

Input: `data_expert3_fixed_paths.jsonl`
Records: 2435
Elapsed seconds: 1458.732

## Branch Summary

| Branch | Candidates | Validated | Pass Rate | Failed Validation |
|---|---:|---:|---:|---:|
| V1 parameter | 4567 | 4488 | 98.2702% | 79 |
| V2 add | 9560 | 9220 | 96.4435% | 340 |
| V3 delete_hole | 502 | 206 | 41.0359% | 296 |
| V4 replace_hole_with_slot | 0 | 0 | 0.0% | 0 |

## By Category

### V1 parameter

| Category | Candidates | Validated | Pass Rate |
|---|---:|---:|---:|
| Circles | 1318 | 1304 | 98.9378% |
| Polygons | 2493 | 2450 | 98.2752% |
| Rects | 756 | 734 | 97.0899% |

### V2 add

| Category | Candidates | Validated | Pass Rate |
|---|---:|---:|---:|
| Circles | 1876 | 1876 | 100.0% |
| Polygons | 5712 | 5372 | 94.0476% |
| Rects | 1972 | 1972 | 100.0% |

### V3 delete_hole

| Category | Candidates | Validated | Pass Rate |
|---|---:|---:|---:|
| Circles | 146 | 146 | 100.0% |
| Polygons | 356 | 60 | 16.8539% |
| Rects | 0 | 0 | 0.0% |

### V4 replace_hole_with_slot

| Category | Candidates | Validated | Pass Rate |
|---|---:|---:|---:|
| Circles | 0 | 0 | 0.0% |
| Polygons | 0 | 0 | 0.0% |
| Rects | 0 | 0 | 0.0% |

## By Edit Type

### V1 parameter

| Edit Type | Candidates | Validated | Pass Rate |
|---|---:|---:|---:|
| chamfer | 127 | 112 | 88.189% |
| circle | 675 | 668 | 98.963% |
| extrude | 2775 | 2765 | 99.6396% |
| fillet | 484 | 437 | 90.2893% |
| hole | 506 | 506 | 100.0% |

### V2 add

| Edit Type | Candidates | Validated | Pass Rate |
|---|---:|---:|---:|
| add_blind_hole | 2390 | 2236 | 93.5565% |
| add_pocket | 2390 | 2349 | 98.2845% |
| add_rectangular_slot | 2390 | 2384 | 99.749% |
| add_through_hole | 2390 | 2251 | 94.1841% |

### V3 delete_hole

| Edit Type | Candidates | Validated | Pass Rate |
|---|---:|---:|---:|
| delete_hole | 502 | 206 | 41.0359% |

### V4 replace_hole_with_slot

| Edit Type | Candidates | Validated | Pass Rate |
|---|---:|---:|---:|

## Top Rejection Reasons

### V1 parameter

| Reason | Count |
|---|---:|
| `validation:StdFail_NotDone: BRep_API: command not done` | 62 |
| `validation:result variable was not defined` | 17 |
| `skipped_original_syntax_error` | 15 |
| `skipped_no_candidates` | 1 |

### V2 add

| Reason | Count |
|---|---:|
| `validation:changed-region check failed: Bnd_Box is void` | 339 |
| `skipped_bad_candidate_geometry` | 76 |
| `skipped_geometry_error` | 26 |
| `geometry_error:unexpected indent (<cadquery_source>, line 3)` | 12 |
| `geometry_error:result variable was not defined` | 11 |
| `geometry_error:unexpected indent (<cadquery_source>, line 2)` | 2 |
| `validation:failed check: volume_direction_ok` | 1 |
| `geometry_error:invalid syntax (<cadquery_source>, line 2)` | 1 |

### V3 delete_hole

| Reason | Count |
|---|---:|
| `skipped_no_delete_candidate` | 1907 |
| `skipped_unsupported_hole_context` | 506 |
| `validation:failed check: bbox_stable` | 259 |
| `validation:failed check: changed_region_not_global` | 35 |
| `skipped_syntax_error` | 15 |
| `syntax_error:unexpected indent (<unknown>, line 3)` | 12 |
| `skipped_geometry_error` | 11 |
| `geometry_error:result variable was not defined` | 11 |
| `syntax_error:unexpected indent (<unknown>, line 2)` | 2 |
| `validation:changed-region check failed: Bnd_Box is void` | 2 |
| `syntax_error:invalid syntax (<unknown>, line 2)` | 1 |

### V4 replace_hole_with_slot

| Reason | Count |
|---|---:|
| `skipped_no_replace_candidate` | 2435 |
| `delete_skipped_no_delete_candidate` | 1907 |
| `delete_skipped_unsupported_hole_context` | 506 |
| `skipped_batch_hole` | 502 |
| `delete_skipped_syntax_error` | 15 |
| `delete_syntax_error:unexpected indent (<unknown>, line 3)` | 12 |
| `delete_skipped_geometry_error` | 11 |
| `delete_geometry_error:result variable was not defined` | 11 |
| `delete_syntax_error:unexpected indent (<unknown>, line 2)` | 2 |
| `delete_syntax_error:invalid syntax (<unknown>, line 2)` | 1 |

## V4 Hole Diagnostics

| Type | Count |
|---|---:|
| hole_calls_total | 506 |
| simple_loop_holes | 502 |
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
| hole_calls_total | 357 |
| simple_loop_holes | 356 |
| hole_parse_error_records | 3 |
| other_unsupported_hole_contexts | 1 |
| circular_cutout_via_cut_circle_extrude | 0 |

#### Rects

| Type | Count |
|---|---:|
| hole_parse_error_records | 6 |
| circular_cutout_via_cut_circle_extrude | 0 |

## Render Preview

Sample JSONL: `outputs\coverage_expert3\chunks\chunk_05\preview_samples.jsonl`
Gallery: `outputs\coverage_expert3\chunks\chunk_05\preview_gallery\index.html`
