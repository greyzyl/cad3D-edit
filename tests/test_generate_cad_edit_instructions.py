import importlib.util
import sys
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "generate_cad_edit_instructions.py"
SPEC = importlib.util.spec_from_file_location("generate_cad_edit_instructions", MODULE_PATH)
instructions = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = instructions
SPEC.loader.exec_module(instructions)


class GenerateCadEditInstructionsTests(unittest.TestCase):
    def sample_record(self):
        return {
            "candidate_id": "000001_001",
            "images": ["a.png", "b.png", "c.png"],
            "original_code": 'import cadquery as cq\nresult = cq.Workplane("XZ").circle(88).extrude(32)',
            "target_code": 'import cadquery as cq\nresult = cq.Workplane("XZ").circle(132).extrude(32)',
            "edit_candidate": {
                "kind": "circle",
                "call": "circle",
                "arg_index": 0,
                "old": 88.0,
                "new": 132.0,
            },
            "edit_record": {
                "kind": "circle",
                "call": "circle",
                "arg_index": 0,
                "old": 88.0,
                "new": 132.0,
            },
            "validation_report": {"ok": True, "mode": "cadquery"},
            "fallback_instruction": "将 circle 的参数从 88.0 修改为 132.0。",
        }

    def test_prompt_excludes_target_code(self):
        prompt = instructions.build_prompt_text(self.sample_record())

        self.assertIn("original_cadquery_code", prompt)
        self.assertIn("edit_candidate", prompt)
        self.assertIn("修改后的目标代码已经通过验证", prompt)
        self.assertNotIn("circle(132)", prompt)
        self.assertNotIn("target_code", prompt)

    def test_instruction_quality_checks_values_and_code_tokens(self):
        record = self.sample_record()

        ok, reasons = instructions.validate_instruction("把外圆半径从 88 调整到 132。", record, True)
        self.assertTrue(ok)
        self.assertEqual(reasons, [])

        ok, reasons = instructions.validate_instruction("把 CadQuery 里的 circle 改成 132。", record, True)
        self.assertFalse(ok)
        self.assertIn("instruction contains code-like token", reasons)


if __name__ == "__main__":
    unittest.main()
