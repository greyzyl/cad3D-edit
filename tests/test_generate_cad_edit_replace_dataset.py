import importlib.util
import sys
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "generate_cad_edit_replace_dataset.py"
SPEC = importlib.util.spec_from_file_location("generate_cad_edit_replace_dataset", MODULE_PATH)
replace_dataset = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = replace_dataset
SPEC.loader.exec_module(replace_dataset)


class GenerateCadEditReplaceDatasetTests(unittest.TestCase):
    def sample_code(self):
        return (
            "import cadquery as cq\n"
            'result = cq.Workplane("XY").box(80, 60, 20).faces(">Z").workplane().hole(12)'
        )

    def candidate_by_type(self, candidates, edit_type):
        for candidate in candidates:
            if candidate["replace_candidate"]["edit_type"] == edit_type:
                return candidate
        self.fail(f"missing candidate type {edit_type}: {[c['replace_candidate']['edit_type'] for c in candidates]}")

    def test_generates_replace_hole_with_slot_candidate(self):
        record = {"images": ["a.png", "b.png", "c.png"], "original_code": self.sample_code()}

        candidates, stats = replace_dataset.generate_replace_candidates_for_record(
            source_record=record,
            sample_index=1,
            source_line=1,
            max_replacements_per_sample=1,
        )

        self.assertEqual(stats["candidate_records"], 1, stats)
        self.assertEqual(len(candidates), 1)
        candidate = self.candidate_by_type(candidates, "replace_hole_with_slot")
        replace_candidate = candidate["replace_candidate"]
        self.assertEqual(replace_candidate["candidate_type"], "structural_replace")
        self.assertEqual(replace_candidate["edit_type"], "replace_hole_with_slot")
        self.assertEqual(replace_candidate["old_feature"]["edit_type"], "delete_hole")
        self.assertEqual(replace_candidate["new_feature"]["feature"], "rectangular_slot")
        self.assertNotIn(".hole(", candidate["intermediate_code"])
        self.assertIn("V4 structural replacement: replace_hole_with_slot", candidate["target_code"])
        self.assertIn("v4_slot_cutter", candidate["target_code"])

    def test_applies_and_validates_replace(self):
        record = {"images": ["a.png", "b.png", "c.png"], "original_code": self.sample_code()}
        candidates, _ = replace_dataset.generate_replace_candidates_for_record(record, 1, 1, 1)
        candidate = self.candidate_by_type(candidates, "replace_hole_with_slot")

        target_code = replace_dataset.apply_replace_candidate(candidate)
        report = replace_dataset.validate_replace_edit(candidate)

        self.assertEqual(target_code, candidate["target_code"])
        self.assertTrue(report["ok"], report)
        self.assertGreater(report["delete_volume_delta"], 0)
        self.assertLess(report["slot_volume_delta"], 0)

    def test_replaces_simple_for_loop_holes_with_slot(self):
        code = (
            "import cadquery as cq\n"
            'result = cq.Workplane("XY").circle(39).extrude(27).faces(">Z").workplane()\n'
            "for i in range(3):\n"
            "    result = result.rotate((0,0,0), (0, 0, 1), 120.0).moveTo(15, 0).hole(6)"
        )
        record = {"images": ["a.png", "b.png", "c.png"], "original_code": code}

        candidates, stats = replace_dataset.generate_replace_candidates_for_record(record, 1, 1, 2)

        self.assertEqual(stats["candidate_records"], 1, stats)
        self.assertEqual(len(candidates), 1)
        candidate = self.candidate_by_type(candidates, "replace_loop_holes_with_slots")
        self.assertEqual(candidate["replace_candidate"]["edit_type"], "replace_loop_holes_with_slots")
        self.assertEqual(candidate["replace_candidate"]["old_feature"]["parameters"]["count"], 3)

        report = replace_dataset.validate_replace_edit(candidate)
        self.assertTrue(report["ok"], report)
        self.assertGreater(report["delete_volume_delta"], 0)
        self.assertLess(report["slot_volume_delta"], 0)

    def test_replaces_circular_cutout_with_polygonal_cutout_and_slot(self):
        code = (
            "import cadquery as cq\n"
            'result = cq.Workplane("XZ").moveTo(0, 0).circle(88).extrude(32)'
            '.cut(cq.Workplane("XZ").circle(46).extrude(32))'
        )
        record = {"images": ["a.png", "b.png", "c.png"], "original_code": code}

        candidates, stats = replace_dataset.generate_replace_candidates_for_record(record, 1, 1, 2)

        self.assertEqual(stats["candidate_records"], 2, stats)
        polygon_candidate = self.candidate_by_type(candidates, "replace_circular_cutout_with_polygonal_cutout")
        self.assertEqual(polygon_candidate["replace_candidate"]["old_feature"]["edit_type"], "delete_circular_cutout")
        self.assertIn(".polygon(6, 46)", polygon_candidate["target_code"])

        report = replace_dataset.validate_replace_edit(polygon_candidate)
        self.assertTrue(report["ok"], report)
        self.assertEqual(report["validation_policy"], "cutout_replace")

        candidate = self.candidate_by_type(candidates, "replace_circular_cutout_with_slot")
        self.assertEqual(candidate["replace_candidate"]["old_feature"]["edit_type"], "delete_circular_cutout")

        report = replace_dataset.validate_replace_edit(candidate)
        self.assertTrue(report["ok"], report)
        self.assertGreater(report["delete_volume_delta"], 0)
        self.assertLess(report["slot_volume_delta"], 0)

    def test_replaces_polygonal_cutout_with_circular_cutout_and_slot(self):
        code = (
            "import cadquery as cq\n"
            'result = cq.Workplane("XZ").moveTo(0, 0).circle(88).extrude(32)'
            '.cut(cq.Workplane("XZ").polygon(6, 30).extrude(32))'
        )
        record = {"images": ["a.png", "b.png", "c.png"], "original_code": code}

        candidates, stats = replace_dataset.generate_replace_candidates_for_record(record, 1, 1, 2)

        self.assertEqual(stats["candidate_records"], 2, stats)
        circular_candidate = self.candidate_by_type(candidates, "replace_polygonal_cutout_with_circular_cutout")
        self.assertEqual(circular_candidate["replace_candidate"]["old_feature"]["edit_type"], "delete_polygonal_cutout")
        self.assertIn(".circle(", circular_candidate["target_code"])
        self.assertEqual(circular_candidate["replace_candidate"]["new_feature"]["feature_type"], "circular_cutout")

        report = replace_dataset.validate_replace_edit(circular_candidate)
        self.assertTrue(report["ok"], report)
        self.assertEqual(report["validation_policy"], "cutout_replace")

        slot_candidate = self.candidate_by_type(candidates, "replace_polygonal_cutout_with_slot")
        report = replace_dataset.validate_replace_edit(slot_candidate)
        self.assertTrue(report["ok"], report)
        self.assertGreater(report["delete_volume_delta"], 0)
        self.assertLess(report["slot_volume_delta"], 0)

    def test_replaces_chamfer_with_fillet(self):
        code = (
            "import cadquery as cq\n"
            'result = cq.Workplane("XY").box(80, 60, 20).edges("|Z").chamfer(4)'
        )
        record = {"images": ["a.png", "b.png", "c.png"], "original_code": code}

        candidates, stats = replace_dataset.generate_replace_candidates_for_record(record, 1, 1, 1)

        self.assertEqual(stats["candidate_records"], 1, stats)
        candidate = self.candidate_by_type(candidates, "replace_chamfer_with_fillet")
        self.assertIn(".fillet(4)", candidate["target_code"])
        self.assertNotIn(".chamfer(4)", candidate["target_code"])

        report = replace_dataset.validate_replace_edit(candidate)
        self.assertTrue(report["ok"], report)
        self.assertEqual(report["validation_policy"], "finishing_replace")

    def test_replaces_fillet_with_chamfer(self):
        code = (
            "import cadquery as cq\n"
            'result = cq.Workplane("XY").box(80, 60, 20).edges("|Z").fillet(4)'
        )
        record = {"images": ["a.png", "b.png", "c.png"], "original_code": code}

        candidates, stats = replace_dataset.generate_replace_candidates_for_record(record, 1, 1, 1)

        self.assertEqual(stats["candidate_records"], 1, stats)
        candidate = self.candidate_by_type(candidates, "replace_fillet_with_chamfer")
        self.assertIn(".chamfer(4)", candidate["target_code"])
        self.assertNotIn(".fillet(4)", candidate["target_code"])

        report = replace_dataset.validate_replace_edit(candidate)
        self.assertTrue(report["ok"], report)
        self.assertEqual(report["validation_policy"], "finishing_replace")

    def test_final_record_matches_training_shape(self):
        validated = {
            "candidate_id": "v4rep_000001_001",
            "images": ["a.png", "b.png", "c.png"],
            "original_code": self.sample_code(),
            "intermediate_code": 'import cadquery as cq\nresult = cq.Workplane("XY").box(80, 60, 20)',
            "target_code": self.sample_code() + "\n# replacement\n",
            "edit_record": {"candidate_type": "structural_replace", "edit_type": "replace_hole_with_slot"},
            "validation_report": {"ok": True},
            "fallback_instruction": "将零件上的圆孔替换为矩形槽，其余结构保持不变。",
        }

        record = replace_dataset.final_record(validated)

        self.assertEqual(record["images"], ["a.png", "b.png", "c.png"])
        self.assertEqual(record["hidden"]["candidate_id"], "v4rep_000001_001")
        self.assertEqual(record["hidden"]["edit_record"]["edit_type"], "replace_hole_with_slot")
        self.assertEqual(record["hidden"]["intermediate_code"], validated["intermediate_code"])
        self.assertEqual(record["hidden"]["validation_report"]["ok"], True)


if __name__ == "__main__":
    unittest.main()
