import importlib.util
import sys
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "generate_cad_edit_dataset.py"
SPEC = importlib.util.spec_from_file_location("generate_cad_edit_dataset", MODULE_PATH)
cadedit = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = cadedit
SPEC.loader.exec_module(cadedit)


class GenerateCadEditDatasetTests(unittest.TestCase):
    def test_extracts_hidden_original_code(self):
        record = {
            "hidden": {
                "original_code": 'import cadquery as cq\nresult = cq.Workplane("XZ").circle(88).extrude(32)'
            }
        }

        code = cadedit.extract_original_code(record)

        self.assertIn("circle(88)", code)

    def test_extracts_cadquery_from_assistant_fence(self):
        record = {
            "messages": [
                {"role": "user", "content": "make a CAD part"},
                {
                    "role": "assistant",
                    "content": 'Reasoning text.\n```python\nimport cadquery as cq\nresult = cq.Workplane("XY").box(1, 2, 3)\n```',
                },
            ]
        }

        code = cadedit.extract_original_code(record)

        self.assertEqual(code, 'import cadquery as cq\nresult = cq.Workplane("XY").box(1, 2, 3)')

    def test_extracts_cadquery_from_generic_tag(self):
        record = {
            "conversations": [
                {
                    "from": "assistant",
                    "value": '<cadquery_code>\nimport cadquery as cq\nresult = cq.Workplane("XY").circle(5)\n</cadquery_code>',
                }
            ]
        }

        code = cadedit.extract_original_code(record)

        self.assertEqual(code, 'import cadquery as cq\nresult = cq.Workplane("XY").circle(5)')

    def test_extracts_cadquery_from_nested_generic_tag(self):
        record = {
            "conversation": [
                {
                    "role": "assistant",
                    "content": '<answer>\n<cadquery_code>\nimport cadquery as cq\nresult = cq.Workplane("XY").circle(5)\n</cadquery_code>\n</answer>',
                }
            ]
        }

        code = cadedit.extract_original_code(record)

        self.assertEqual(code, 'import cadquery as cq\nresult = cq.Workplane("XY").circle(5)')

    def test_generates_deterministic_circle_edit(self):
        source = 'import cadquery as cq\nresult = cq.Workplane("XZ").circle(88).extrude(32)'
        candidates = cadedit.find_edit_candidates(source)

        edited, edit_record = cadedit.apply_edit(source, candidates[0], scale_factor=1.5)

        self.assertIn("circle(132)", edited)
        self.assertEqual(edit_record.kind, "circle")
        self.assertEqual(edit_record.old, 88.0)
        self.assertEqual(edit_record.new, 132.0)
        self.assertEqual(cadedit.instruction_for_edit(edit_record), "将 circle 的参数从 88.0 修改为 132.0。")

    def test_builds_intermediate_candidate_record_before_target_code(self):
        source = 'import cadquery as cq\nresult = cq.Workplane("XZ").circle(88).extrude(32)'
        candidate = cadedit.find_edit_candidates(source)[0]

        record = cadedit.build_candidate_record(
            sample_index=1,
            source_line=7,
            candidate_index=1,
            images=["a.png", "b.png", "c.png"],
            original_code=source,
            candidate=candidate,
            scale_factor=1.5,
        )

        self.assertEqual(record["candidate_id"], "000001_001")
        self.assertNotIn("target_code", record)
        self.assertEqual(record["source_line"], 7)
        self.assertEqual(record["original_code"], source)
        self.assertEqual(record["edit_candidate"]["old"], 88.0)
        self.assertEqual(record["edit_candidate"]["new"], 132.0)
        self.assertEqual(record["edit_candidate"]["replacement"], "132")
        self.assertEqual(record["edit_candidate"]["matched_text"], "88")

    def test_builds_validated_edit_record_after_validation(self):
        source = 'import cadquery as cq\nresult = cq.Workplane("XZ").circle(88).extrude(32)'
        candidate = cadedit.find_edit_candidates(source)[0]
        candidate_record = cadedit.build_candidate_record(
            sample_index=1,
            source_line=1,
            candidate_index=1,
            images=["a.png", "b.png", "c.png"],
            original_code=source,
            candidate=candidate,
            scale_factor=1.5,
        )
        edited, edit_record = cadedit.apply_edit(source, candidate, scale_factor=1.5)

        record = cadedit.validated_edit_record(candidate_record, edited, edit_record, {"ok": True, "mode": "syntax"})

        self.assertEqual(record["candidate_id"], "000001_001")
        self.assertIn("target_code", record)
        self.assertNotIn("instruction", record)
        self.assertEqual(record["validation_report"]["ok"], True)

    def test_output_record_can_use_external_instruction(self):
        source = 'import cadquery as cq\nresult = cq.Workplane("XZ").circle(88)'
        edit_record = cadedit.EditRecord("circle", "circle", 0, 88.0, 132.0, "88")

        record = cadedit.output_record(
            ["a.png", "b.png", "c.png"],
            source,
            source.replace("88", "132"),
            edit_record,
            {"ok": True, "mode": "syntax"},
            candidate_id="000001_001",
            instruction="把外圆半径从 88 调整到 132。",
            instruction_meta={"generator": "bailian_mllm"},
        )

        self.assertEqual(record["instruction"], "把外圆半径从 88 调整到 132。")
        self.assertEqual(record["hidden"]["candidate_id"], "000001_001")
        self.assertEqual(record["hidden"]["instruction_meta"]["generator"], "bailian_mllm")

    def test_syntax_validation_requires_result(self):
        ok_report = cadedit.validate_code("result = 1", "syntax", 1)
        bad_report = cadedit.validate_code("value = 1", "syntax", 1)

        self.assertTrue(ok_report["ok"])
        self.assertFalse(bad_report["ok"])


if __name__ == "__main__":
    unittest.main()
