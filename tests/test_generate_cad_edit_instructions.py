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

    def structural_record(self):
        return {
            "candidate_id": "v2_000001_001",
            "images": ["a.png", "b.png", "c.png"],
            "original_code": 'import cadquery as cq\nresult = cq.Workplane("XY").box(80, 60, 20)',
            "target_code": 'import cadquery as cq\nresult = cq.Workplane("XY").box(80, 60, 20)\n# edit\n',
            "edit_candidate": {
                "edit_type": "add_through_hole",
                "target_region": {"axis": "z", "side": "+", "region_type": "axis_aligned_exterior_face"},
                "primitive": {"kind": "cylinder", "radius": 4.0, "depth": 24.0},
                "insertion_strategy": {"operation": "cut", "append_csg_block": True},
                "affected_region_bbox": {
                    "xmin": -4.0,
                    "xmax": 4.0,
                    "ymin": -4.0,
                    "ymax": 4.0,
                    "zmin": -12.0,
                    "zmax": 12.0,
                },
                "instruction_template": "在零件主平面上添加一个贯穿圆孔。",
            },
            "validation_report": {"ok": True, "mode": "cadquery_structural"},
            "fallback_instruction": "在零件主平面上添加一个半径为 4.0 的贯穿圆孔。",
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

    def test_structural_prompt_and_quality_checks(self):
        record = self.structural_record()
        prompt = instructions.build_prompt_text(record)

        self.assertIn("instruction_mode", prompt)
        self.assertIn("structural", prompt)
        self.assertIn("可以使用添加孔", prompt)
        self.assertNotIn("target_code", prompt)

        ok, reasons = instructions.validate_instruction("在主平面上添加一个贯穿圆孔。", record, True)
        self.assertTrue(ok)
        self.assertEqual(reasons, [])

        ok, reasons = instructions.validate_instruction("删除主平面上的圆孔。", record, True)
        self.assertFalse(ok)
        self.assertIn("instruction mentions unsupported structural edit", reasons)

        ok, reasons = instructions.validate_instruction("在XZ平面上距离原点57.2的位置添加盲孔。", record, True)
        self.assertFalse(ok)
        self.assertIn("instruction mentions implementation detail", reasons)


if __name__ == "__main__":
    unittest.main()
