# CAD Edit Coverage Audit - Expert 3

Input: `data_expert3_fixed_paths.jsonl`
Records: 300
Elapsed seconds: 25.083

## Branch Summary

| Branch | Candidates | Validated | Pass Rate | Failed Validation |
|---|---:|---:|---:|---:|
| V4 replace | 159 | 61 | 38.3648% | 98 |

## By Category

### V4 replace

| Category | Candidates | Validated | Pass Rate |
|---|---:|---:|---:|
| Circles | 0 | 0 | 0.0% |
| Polygons | 159 | 61 | 38.3648% |
| Rects | 0 | 0 | 0.0% |

## By Edit Type

### V4 replace

| Edit Type | Candidates | Validated | Pass Rate |
|---|---:|---:|---:|
| replace_fillet_with_chamfer | 63 | 0 | 0.0% |
| replace_loop_holes_with_slots | 12 | 11 | 91.6667% |
| replace_polygonal_cutout_with_circular_cutout | 80 | 46 | 57.5% |
| replace_polygonal_cutout_with_slot | 4 | 4 | 100.0% |

## Top Rejection Reasons

### V4 replace

| Reason | Count |
|---|---:|
| `skipped_no_replace_candidate` | 145 |
| `delete_skipped_no_delete_candidate` | 86 |
| `skipped_slot_geometry` | 76 |
| `delete_skipped_unsupported_hole_context` | 71 |
| `skipped_delete_validation_failed` | 59 |
| `validation:failed check: bbox_stable` | 59 |
| `validation:failed check: new_feature_changed_region_local` | 28 |
| `validation:Bnd_Box is void` | 6 |
| `validation:BRep_API: command not done` | 4 |
| `validation:failed check: slot_changed_region_local` | 1 |

## V4 Hole Diagnostics

| Type | Count |
|---|---:|
| hole_calls_total | 71 |
| simple_loop_holes | 71 |
| circular_cutout_via_cut_circle_extrude | 0 |

### V4 Hole Diagnostics By Category

#### Polygons

| Type | Count |
|---|---:|
| hole_calls_total | 71 |
| simple_loop_holes | 71 |
| circular_cutout_via_cut_circle_extrude | 0 |

## Render Preview

Sample JSONL: `outputs\coverage_v4_replace_expanded_smoke_polygons\preview_samples.jsonl`
Gallery: `outputs\coverage_v4_replace_expanded_smoke_polygons\preview_gallery\index.html`
