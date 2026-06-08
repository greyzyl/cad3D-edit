import importlib.util
import sys
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "generate_cad_edit_structural_dataset.py"
SPEC = importlib.util.spec_from_file_location("generate_cad_edit_structural_dataset", MODULE_PATH)
structural = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = structural
SPEC.loader.exec_module(structural)


class GenerateCadEditStructuralDatasetTests(unittest.TestCase):
    def sample_code(self):
        return 'import cadquery as cq\nresult = cq.Workplane("XY").box(80, 60, 20)'

    def test_builds_add_through_hole_candidate(self):
        shape = structural.execute_shape(self.sample_code())
        geometry = structural.geometry_info(shape)
        region = structural.choose_target_region(shape, geometry)

        candidate = structural.build_structural_candidate(
            candidate_id="v2_000001_001",
            sample_index=1,
            source_line=1,
            images=["a.png", "b.png", "c.png"],
            original_code=self.sample_code(),
            geometry=geometry,
            region=region,
            edit_type="add_through_hole",
        )

        self.assertEqual(candidate["structural_candidate"]["edit_type"], "add_through_hole")
        self.assertIn("target_region", candidate["structural_candidate"])
        self.assertIn("primitive", candidate["structural_candidate"])
        self.assertIn("insertion_strategy", candidate["structural_candidate"])
        self.assertIn("affected_region_bbox", candidate["structural_candidate"])
        self.assertIn("instruction_hints", candidate["structural_candidate"])
        self.assertTrue(candidate["structural_candidate"]["instruction_hints"]["do_not_mention_depth"])
        self.assertNotIn("target_code", candidate)

    def test_applies_and_validates_structural_cut(self):
        shape = structural.execute_shape(self.sample_code())
        geometry = structural.geometry_info(shape)
        region = structural.choose_target_region(shape, geometry)
        candidate = structural.build_structural_candidate(
            candidate_id="v2_000001_001",
            sample_index=1,
            source_line=1,
            images=["a.png", "b.png", "c.png"],
            original_code=self.sample_code(),
            geometry=geometry,
            region=region,
            edit_type="add_blind_hole",
        )

        target_code = structural.apply_structural_candidate(candidate)
        report = structural.validate_structural_edit(self.sample_code(), target_code, candidate)

        self.assertIn("V2 structural edit: add_blind_hole", target_code)
        self.assertTrue(report["ok"], report)
        self.assertLess(report["volume_delta"], 0)

    def test_final_record_matches_training_shape(self):
        validated = {
            "candidate_id": "v2_000001_001",
            "images": ["a.png", "b.png", "c.png"],
            "original_code": self.sample_code(),
            "target_code": self.sample_code() + "\n# edit\n",
            "edit_record": {"edit_type": "add_pocket"},
            "validation_report": {"ok": True},
            "fallback_instruction": "在零件主平面上添加一个矩形凹陷。",
        }

        record = structural.final_record(validated)

        self.assertEqual(record["images"], ["a.png", "b.png", "c.png"])
        self.assertEqual(record["hidden"]["candidate_id"], "v2_000001_001")
        self.assertEqual(record["hidden"]["edit_record"]["edit_type"], "add_pocket")
        self.assertEqual(record["hidden"]["validation_report"]["ok"], True)


if __name__ == "__main__":
    unittest.main()
