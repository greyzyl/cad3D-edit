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
        candidate = candidates[0]
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
        candidate = candidates[0]

        target_code = replace_dataset.apply_replace_candidate(candidate)
        report = replace_dataset.validate_replace_edit(candidate)

        self.assertEqual(target_code, candidate["target_code"])
        self.assertTrue(report["ok"], report)
        self.assertGreater(report["delete_volume_delta"], 0)
        self.assertLess(report["slot_volume_delta"], 0)

    def test_skips_batch_hole_delete_candidate_for_v1_replace_scope(self):
        code = (
            "import cadquery as cq\n"
            'result = cq.Workplane("XY").circle(39).extrude(27).faces(">Z").workplane()\n'
            "for i in range(3):\n"
            "    result = result.rotate((0,0,0), (0, 0, 1), 120.0).moveTo(15, 0).hole(6)"
        )
        record = {"images": ["a.png", "b.png", "c.png"], "original_code": code}

        candidates, stats = replace_dataset.generate_replace_candidates_for_record(record, 1, 1, 2)

        self.assertEqual(candidates, [])
        self.assertEqual(stats["skipped_batch_hole"], 1)

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
