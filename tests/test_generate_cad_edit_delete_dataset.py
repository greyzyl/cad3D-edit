import importlib.util
import sys
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "generate_cad_edit_delete_dataset.py"
SPEC = importlib.util.spec_from_file_location("generate_cad_edit_delete_dataset", MODULE_PATH)
delete_dataset = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = delete_dataset
SPEC.loader.exec_module(delete_dataset)


class GenerateCadEditDeleteDatasetTests(unittest.TestCase):
    def sample_code(self):
        return (
            "import cadquery as cq\n"
            'result = cq.Workplane("XY").box(80, 60, 20).faces(">Z").workplane().hole(10)'
        )

    def test_extracts_high_confidence_hole_delete_candidate(self):
        record = {"images": ["a.png", "b.png", "c.png"], "original_code": self.sample_code()}
        candidates, stats = delete_dataset.generate_delete_candidates_for_record(
            source_record=record,
            sample_index=1,
            source_line=1,
            max_deletes_per_sample=2,
        )

        self.assertEqual(stats["candidate_records"], 1)
        self.assertEqual(len(candidates), 1)
        delete_candidate = candidates[0]["delete_candidate"]
        self.assertEqual(delete_candidate["candidate_type"], "structural_delete")
        self.assertEqual(delete_candidate["edit_type"], "delete_hole")
        self.assertEqual(delete_candidate["source_api"], "hole")
        self.assertEqual(delete_candidate["parameters"]["diameter"], 10.0)
        self.assertEqual(delete_candidate["block_text"], '.faces(">Z").workplane().hole(10)')
        self.assertNotIn("target_code", candidates[0])

    def test_applies_and_validates_hole_delete(self):
        record = {"images": ["a.png", "b.png", "c.png"], "original_code": self.sample_code()}
        candidates, _ = delete_dataset.generate_delete_candidates_for_record(record, 1, 1, 2)
        candidate = candidates[0]

        target_code = delete_dataset.apply_delete_candidate(candidate)
        report = delete_dataset.validate_delete_edit(self.sample_code(), target_code, candidate)

        self.assertNotIn(".hole(", target_code)
        self.assertIn(".box(80, 60, 20)", target_code)
        self.assertTrue(report["ok"], report)
        self.assertGreater(report["volume_delta"], 0)

    def test_skips_push_points_hole_for_v1_delete_scope(self):
        code = (
            "import cadquery as cq\n"
            'result = cq.Workplane("XY").box(80, 60, 20).faces(">Z").workplane().pushPoints([(0, 0)]).hole(10)'
        )
        record = {"images": ["a.png", "b.png", "c.png"], "original_code": code}

        candidates, stats = delete_dataset.generate_delete_candidates_for_record(record, 1, 1, 2)

        self.assertEqual(candidates, [])
        self.assertEqual(stats["skipped_unsupported_hole_context"], 1)

    def test_extracts_simple_for_loop_hole_block(self):
        code = (
            "import cadquery as cq\n"
            'result = cq.Workplane("XY").circle(39).extrude(27).faces(">Z").workplane()\n'
            "for i in range(3):\n"
            "    result = result.rotate((0,0,0), (0, 0, 1), 120.0).moveTo(15, 0).hole(6)"
        )
        record = {"images": ["a.png", "b.png", "c.png"], "original_code": code}

        candidates, stats = delete_dataset.generate_delete_candidates_for_record(record, 1, 1, 2)

        self.assertEqual(stats["candidate_records"], 1)
        candidate = candidates[0]
        delete_candidate = candidate["delete_candidate"]
        self.assertEqual(delete_candidate["deletion_strategy"], "simple_for_hole_block")
        self.assertEqual(delete_candidate["parameters"]["diameter"], 6.0)
        self.assertEqual(delete_candidate["parameters"]["count"], 3)
        self.assertIn("for i in range(3):", delete_candidate["block_text"])

        target_code = delete_dataset.apply_delete_candidate(candidate)
        report = delete_dataset.validate_delete_edit(code, target_code, candidate)
        self.assertNotIn(".hole(", target_code)
        self.assertTrue(report["ok"], report)
        self.assertGreater(report["volume_delta"], 0)

    def test_extracts_and_validates_circular_cutout_delete_candidate(self):
        code = (
            "import cadquery as cq\n"
            'result = cq.Workplane("XZ").moveTo(0, 0).circle(88).extrude(32)'
            '.cut(cq.Workplane("XZ").circle(46).extrude(32))'
        )
        record = {"images": ["a.png", "b.png", "c.png"], "original_code": code}

        candidates, stats = delete_dataset.generate_delete_candidates_for_record(record, 1, 1, 2)

        self.assertEqual(stats["candidate_records"], 1)
        candidate = candidates[0]
        delete_candidate = candidate["delete_candidate"]
        self.assertEqual(delete_candidate["edit_type"], "delete_circular_cutout")
        self.assertEqual(delete_candidate["source_api"], "cut")
        self.assertEqual(delete_candidate["parameters"]["radius"], 46.0)
        self.assertEqual(delete_candidate["parameters"]["diameter"], 92.0)
        self.assertIn(".cut(", delete_candidate["block_text"])

        target_code = delete_dataset.apply_delete_candidate(candidate)
        report = delete_dataset.validate_delete_edit(code, target_code, candidate)
        self.assertNotIn(".cut(", target_code)
        self.assertTrue(report["ok"], report)
        self.assertGreater(report["volume_delta"], 0)

    def test_extracts_and_validates_polygonal_cutout_delete_candidate(self):
        code = (
            "import cadquery as cq\n"
            'result = cq.Workplane("XZ").moveTo(0, 0).polygon(6, 80).extrude(32)'
            '.cut(cq.Workplane("XZ").polygon(6, 30).extrude(32))'
        )
        record = {"images": ["a.png", "b.png", "c.png"], "original_code": code}

        candidates, stats = delete_dataset.generate_delete_candidates_for_record(record, 1, 1, 2)

        self.assertEqual(stats["candidate_records"], 1)
        candidate = candidates[0]
        delete_candidate = candidate["delete_candidate"]
        self.assertEqual(delete_candidate["edit_type"], "delete_polygonal_cutout")
        self.assertEqual(delete_candidate["source_api"], "cut_polygon")
        self.assertEqual(delete_candidate["parameters"]["sides"], 6)
        self.assertEqual(delete_candidate["parameters"]["radius"], 30.0)
        self.assertEqual(delete_candidate["parameters"]["depth"], 32.0)

        target_code = delete_dataset.apply_delete_candidate(candidate)
        report = delete_dataset.validate_delete_edit(code, target_code, candidate)
        self.assertNotIn(".cut(", target_code)
        self.assertTrue(report["ok"], report)
        self.assertGreater(report["volume_delta"], 0)

    def test_extracts_and_validates_fillet_delete_candidate(self):
        code = (
            "import cadquery as cq\n"
            'result = cq.Workplane("XY").moveTo(0, 0).rect(80, 60).extrude(20).edges("|Z").fillet(5)'
        )
        record = {"images": ["a.png", "b.png", "c.png"], "original_code": code}

        candidates, stats = delete_dataset.generate_delete_candidates_for_record(record, 1, 1, 2)

        self.assertEqual(stats["candidate_records"], 1)
        candidate = candidates[0]
        delete_candidate = candidate["delete_candidate"]
        self.assertEqual(delete_candidate["edit_type"], "delete_fillet")
        self.assertEqual(delete_candidate["source_api"], "fillet")
        self.assertEqual(delete_candidate["parameters"]["radius"], 5.0)
        self.assertEqual(delete_candidate["block_text"], '.edges("|Z").fillet(5)')

        target_code = delete_dataset.apply_delete_candidate(candidate)
        report = delete_dataset.validate_delete_edit(code, target_code, candidate)
        self.assertNotIn(".fillet(", target_code)
        self.assertTrue(report["ok"], report)
        self.assertEqual(report["validation_policy"], "finishing_feature_delete")
        self.assertTrue(report["checks"]["volume_changed_nontrivially"])

    def test_extracts_and_validates_chamfer_delete_candidate(self):
        code = (
            "import cadquery as cq\n"
            'result = cq.Workplane("XY").moveTo(0, 0).rect(80, 60).extrude(20).edges("|Z").chamfer(5)'
        )
        record = {"images": ["a.png", "b.png", "c.png"], "original_code": code}

        candidates, stats = delete_dataset.generate_delete_candidates_for_record(record, 1, 1, 2)

        self.assertEqual(stats["candidate_records"], 1)
        candidate = candidates[0]
        delete_candidate = candidate["delete_candidate"]
        self.assertEqual(delete_candidate["edit_type"], "delete_chamfer")
        self.assertEqual(delete_candidate["source_api"], "chamfer")
        self.assertEqual(delete_candidate["parameters"]["distance"], 5.0)
        self.assertEqual(delete_candidate["block_text"], '.edges("|Z").chamfer(5)')

        target_code = delete_dataset.apply_delete_candidate(candidate)
        report = delete_dataset.validate_delete_edit(code, target_code, candidate)
        self.assertNotIn(".chamfer(", target_code)
        self.assertTrue(report["ok"], report)
        self.assertEqual(report["validation_policy"], "finishing_feature_delete")
        self.assertTrue(report["checks"]["geometry_changed_nontrivially"])

    def test_final_record_matches_training_shape(self):
        validated = {
            "candidate_id": "v2del_000001_001",
            "images": ["a.png", "b.png", "c.png"],
            "original_code": self.sample_code(),
            "target_code": 'import cadquery as cq\nresult = cq.Workplane("XY").box(80, 60, 20)',
            "edit_record": {"candidate_type": "structural_delete", "edit_type": "delete_hole"},
            "validation_report": {"ok": True},
            "fallback_instruction": "删除零件上直径为 10.0 的圆孔，其余结构保持不变。",
        }

        record = delete_dataset.final_record(validated)

        self.assertEqual(record["images"], ["a.png", "b.png", "c.png"])
        self.assertEqual(record["hidden"]["candidate_id"], "v2del_000001_001")
        self.assertEqual(record["hidden"]["edit_record"]["edit_type"], "delete_hole")
        self.assertEqual(record["hidden"]["validation_report"]["ok"], True)


if __name__ == "__main__":
    unittest.main()
