# CAD Edit Coverage Audit - Expert 3

Input: `data_expert3_fixed_paths.jsonl`
Records: 2500
Elapsed seconds: 1496.137

## Branch Summary

| Branch | Candidates | Validated | Pass Rate | Failed Validation |
|---|---:|---:|---:|---:|
| V1 parameter | 4692 | 4613 | 98.3163% | 79 |
| V2 add | 9864 | 9467 | 95.9753% | 397 |
| V3 delete_hole | 539 | 218 | 40.4453% | 321 |
| V4 replace_hole_with_slot | 0 | 0 | 0.0% | 0 |

## By Category

### V1 parameter

| Category | Candidates | Validated | Pass Rate |
|---|---:|---:|---:|
| Circles | 1372 | 1366 | 99.5627% |
| Polygons | 2581 | 2538 | 98.334% |
| Rects | 739 | 709 | 95.9405% |

### V2 add

| Category | Candidates | Validated | Pass Rate |
|---|---:|---:|---:|
| Circles | 1964 | 1964 | 100.0% |
| Polygons | 5928 | 5531 | 93.303% |
| Rects | 1972 | 1972 | 100.0% |

### V3 delete_hole

| Category | Candidates | Validated | Pass Rate |
|---|---:|---:|---:|
| Circles | 154 | 154 | 100.0% |
| Polygons | 385 | 64 | 16.6234% |
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
| chamfer | 129 | 111 | 86.0465% |
| circle | 699 | 696 | 99.5708% |
| extrude | 2857 | 2854 | 99.895% |
| fillet | 468 | 413 | 88.2479% |
| hole | 539 | 539 | 100.0% |

### V2 add

| Edit Type | Candidates | Validated | Pass Rate |
|---|---:|---:|---:|
| add_blind_hole | 2466 | 2292 | 92.944% |
| add_pocket | 2466 | 2412 | 97.8102% |
| add_rectangular_slot | 2466 | 2459 | 99.7161% |
| add_through_hole | 2466 | 2304 | 93.4307% |

### V3 delete_hole

| Edit Type | Candidates | Validated | Pass Rate |
|---|---:|---:|---:|
| delete_hole | 539 | 218 | 40.4453% |

### V4 replace_hole_with_slot

| Edit Type | Candidates | Validated | Pass Rate |
|---|---:|---:|---:|

## Top Rejection Reasons

### V1 parameter

| Reason | Count |
|---|---:|
| `validation:StdFail_NotDone: BRep_API: command not done` | 73 |
| `validation:result variable was not defined` | 6 |
| `skipped_no_candidates` | 3 |
| `skipped_original_syntax_error` | 3 |

### V2 add

| Reason | Count |
|---|---:|
| `validation:changed-region check failed: Bnd_Box is void` | 397 |
| `skipped_bad_candidate_geometry` | 100 |
| `skipped_geometry_error` | 9 |
| `geometry_error:result variable was not defined` | 6 |
| `geometry_error:unexpected indent (<cadquery_source>, line 3)` | 2 |
| `geometry_error:unexpected indent (<cadquery_source>, line 2)` | 1 |

### V3 delete_hole

| Reason | Count |
|---|---:|
| `skipped_no_delete_candidate` | 1952 |
| `skipped_unsupported_hole_context` | 539 |
| `validation:failed check: bbox_stable` | 278 |
| `validation:failed check: changed_region_not_global` | 38 |
| `skipped_geometry_error` | 6 |
| `geometry_error:result variable was not defined` | 6 |
| `validation:changed-region check failed: Bnd_Box is void` | 5 |
| `skipped_syntax_error` | 3 |
| `syntax_error:unexpected indent (<unknown>, line 3)` | 2 |
| `syntax_error:unexpected indent (<unknown>, line 2)` | 1 |

### V4 replace_hole_with_slot

| Reason | Count |
|---|---:|
| `skipped_no_replace_candidate` | 2500 |
| `delete_skipped_no_delete_candidate` | 1952 |
| `delete_skipped_unsupported_hole_context` | 539 |
| `skipped_batch_hole` | 539 |
| `delete_skipped_geometry_error` | 6 |
| `delete_geometry_error:result variable was not defined` | 6 |
| `delete_skipped_syntax_error` | 3 |
| `delete_syntax_error:unexpected indent (<unknown>, line 3)` | 2 |
| `delete_syntax_error:unexpected indent (<unknown>, line 2)` | 1 |

## V4 Hole Diagnostics

| Type | Count |
|---|---:|
| hole_calls_total | 539 |
| simple_loop_holes | 539 |
| circular_cutout_via_cut_circle_extrude | 179 |
| hole_parse_error_records | 3 |

### V4 Hole Diagnostics By Category

#### Circles

| Type | Count |
|---|---:|
| circular_cutout_via_cut_circle_extrude | 179 |
| hole_calls_total | 154 |
| simple_loop_holes | 154 |
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

Sample JSONL: `outputs\coverage_expert3\chunks\chunk_01\preview_samples.jsonl`
Gallery: `outputs\coverage_expert3\chunks\chunk_01\preview_gallery\index.html`
