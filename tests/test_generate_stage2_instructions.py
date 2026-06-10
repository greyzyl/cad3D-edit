import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "generate_stage2_instructions.py"
SPEC = importlib.util.spec_from_file_location("generate_stage2_instructions", MODULE_PATH)
stage2 = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = stage2
SPEC.loader.exec_module(stage2)


class GenerateStage2InstructionsTests(unittest.TestCase):
    def parameter_record(self):
        return {
            "sample_id": "v1_parameter_000001_001",
            "source_sample_id": "cadexpert_line_000001",
            "images": ["a.png", "b.png", "c.png"],
            "branch": "v1_parameter",
            "edit_type": "parameter_circle",
            "original_code": 'import cadquery as cq\nresult = cq.Workplane("XZ").circle(88).extrude(32)',
            "target_code": 'import cadquery as cq\nresult = cq.Workplane("XZ").circle(132).extrude(32)',
            "intermediate_code": None,
            "edit_record": {"kind": "circle", "call": "circle", "old": 88.0, "new": 132.0},
            "validation_report": {"ok": True},
            "selection_meta": {"split": "train"},
        }

    def add_record(self):
        return {
            "sample_id": "v2_add_000001_001",
            "source_sample_id": "cadexpert_line_000001",
            "images": ["a.png", "b.png", "c.png"],
            "branch": "v2_add",
            "edit_type": "add_blind_hole",
            "original_code": 'import cadquery as cq\nresult = cq.Workplane("XY").box(80, 60, 20)',
            "target_code": "hidden target code",
            "intermediate_code": None,
            "edit_record": {
                "edit_type": "add_blind_hole",
                "primitive": {"kind": "cylinder", "radius": 5.0, "depth": 8.0},
                "instruction_hints": {
                    "human_feature_name": "blind hole",
                    "diameter": 10.0,
                    "depth": 8.0,
                    "avoid_implementation_details": ["workplane", "origin"],
                },
                "insertion_strategy": {"operation": "cut", "append_csg_block": True},
            },
            "validation_report": {"ok": True},
            "selection_meta": {"split": "val"},
        }

    def delete_record(self):
        return {
            "sample_id": "v3_delete_000001_001",
            "source_sample_id": "cadexpert_line_000001",
            "images": ["a.png", "b.png", "c.png"],
            "branch": "v3_delete",
            "edit_type": "delete_hole",
            "original_code": 'import cadquery as cq\nresult = cq.Workplane("XY").box(80, 60, 20).hole(10)',
            "target_code": "hidden target code",
            "intermediate_code": None,
            "edit_record": {
                "candidate_type": "structural_delete",
                "edit_type": "delete_hole",
                "block_span_start": 10,
                "block_span_end": 20,
                "block_text": ".hole(10)",
                "parameters": {"diameter": 10.0},
                "instruction_hints": {"human_feature_name": "circular hole", "diameter": 10.0},
            },
            "validation_report": {"ok": True},
            "selection_meta": {"split": "test"},
        }

    def replace_record(self):
        return {
            "sample_id": "v4_replace_000001_001",
            "source_sample_id": "cadexpert_line_000001",
            "images": ["a.png", "b.png", "c.png"],
            "branch": "v4_replace",
            "edit_type": "replace_chamfer_with_fillet",
            "original_code": 'import cadquery as cq\nresult = cq.Workplane("XY").box(80, 60, 20).edges().chamfer(2)',
            "target_code": "hidden target code",
            "intermediate_code": "hidden intermediate code",
            "edit_record": {
                "candidate_type": "structural_replace",
                "edit_type": "replace_chamfer_with_fillet",
                "old_feature": {"parameters": {"distance": 2.0}, "block_text": ".chamfer(2)"},
                "new_feature": {"feature_type": "fillet", "radius": 2.0},
                "instruction_hints": {
                    "old_feature_name": "chamfer",
                    "new_feature_name": "fillet",
                    "distance": 2.0,
                    "radius": 2.0,
                },
            },
            "validation_report": {"ok": True},
            "selection_meta": {"split": "train"},
        }

    def test_prompt_is_simplified_and_excludes_hidden_target_code(self):
        prompt = stage2.build_prompt_text(self.replace_record())
        payload = json.loads(prompt)

        self.assertIn("rules", payload)
        self.assertEqual(payload["image_order"], ["Front", "Top", "Left"])
        self.assertIn("edit_type", payload)
        self.assertIn("original_cadquery_code_hidden_context", payload)
        self.assertIn("edit_record", payload)
        self.assertIn("deterministic_template_reference_not_final_style", payload)
        self.assertNotIn("task", payload)
        self.assertNotIn("instruction_mode", payload)
        self.assertNotIn("branch", payload)
        self.assertNotIn("validation_summary", payload)
        self.assertNotIn("not_provided", payload)
        self.assertNotIn("template_fallback_example", payload)
        self.assertNotIn("hidden target code", prompt)
        self.assertNotIn("hidden intermediate code", prompt)
        self.assertNotIn("target_code", prompt)
        self.assertNotIn("intermediate_code", prompt)
        self.assertNotIn("block_span_start", prompt)
        self.assertNotIn("block_text", prompt)

    def test_system_prompt_emphasizes_three_views_and_real_cad_request(self):
        messages, image_count = stage2.build_messages(self.parameter_record(), Path("."), allow_missing_images=True)
        self.assertEqual(image_count, 0)
        system_prompt = messages[0]["content"]
        self.assertIn("dimensioned three-view drawings", system_prompt)
        self.assertIn("Front view, Top view, and Left view", system_prompt)
        self.assertIn("real user request to a CAD engineer", system_prompt)
        self.assertIn("English", system_prompt)

    def test_fallback_templates_are_english_and_validate_by_mode(self):
        cases = [
            self.parameter_record(),
            self.add_record(),
            self.delete_record(),
            self.replace_record(),
        ]
        for record in cases:
            instruction = stage2.fallback_instruction(record)
            ok, reasons = stage2.validate_instruction(instruction, record)
            self.assertTrue(ok, (record["edit_type"], instruction, reasons))
            self.assertIn("keeping the rest of the part unchanged", instruction.lower())
            self.assertFalse(stage2.contains_cjk(instruction))

    def test_quality_checks_reject_wrong_semantics_and_non_english(self):
        ok, reasons = stage2.validate_instruction(
            "Add a circular hole, keeping the rest of the part unchanged.",
            self.delete_record(),
        )
        self.assertFalse(ok)
        self.assertIn("structural delete instruction mentions add or replace", reasons)

        ok, reasons = stage2.validate_instruction(
            "Remove a chamfer, keeping the rest of the part unchanged.",
            self.replace_record(),
        )
        self.assertFalse(ok)
        self.assertIn("structural replace instruction does not mention replace operation", reasons)

        ok, reasons = stage2.validate_instruction("Change the CadQuery code radius to 132.", self.parameter_record())
        self.assertFalse(ok)
        self.assertIn("instruction contains code or implementation detail", reasons)

        ok, reasons = stage2.validate_instruction(
            "Add a blind hole on the XZ workplane along the +Y coordinate axis, keeping the rest of the part unchanged.",
            self.add_record(),
        )
        self.assertFalse(ok)
        self.assertIn("instruction contains code or implementation detail", reasons)

        ok, reasons = stage2.validate_instruction("删除一个圆孔，其余结构保持不变。", self.delete_record())
        self.assertFalse(ok)
        self.assertIn("instruction is not English", reasons)

    def test_dry_run_file_generation_uses_stage2_schema(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            input_path = tmp_path / "train_intermediate.jsonl"
            output_path = tmp_path / "train_instructions.jsonl"
            rows = [self.parameter_record(), self.add_record()]
            input_path.write_text(
                "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
                encoding="utf-8",
            )
            rc = stage2.main(
                [
                    "--input",
                    str(input_path),
                    "--output",
                    str(output_path),
                    "--dry-run",
                    "--overwrite",
                    "--allow-missing-images",
                    "--no-progress",
                ]
            )
            self.assertEqual(rc, 0)
            out_rows = [json.loads(line) for line in output_path.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(len(out_rows), 2)
            for row in out_rows:
                self.assertIn("sample_id", row)
                self.assertIn("source_sample_id", row)
                self.assertIn("instruction", row)
                self.assertIn("instruction_meta", row)
                self.assertNotIn("target_code", row)
                self.assertNotIn("original_code", row)
                self.assertTrue(row["instruction_meta"]["fallback_used"])
                self.assertFalse(row["instruction_meta"]["included_target_code"])
                self.assertFalse(row["instruction_meta"]["included_intermediate_code"])
                self.assertFalse(stage2.contains_cjk(row["instruction"]))

    def test_latest_qwen_defaults_and_structured_output_payload(self):
        self.assertEqual(stage2.DEFAULT_MODEL, "qwen3-vl-plus")
        payload = stage2.response_format_payload("json_schema", True)
        self.assertEqual(payload["response_format"]["type"], "json_schema")
        self.assertTrue(payload["response_format"]["json_schema"]["strict"])
        schema = payload["response_format"]["json_schema"]["schema"]
        self.assertIn("instruction", schema["required"])
        self.assertIn("confidence", schema["required"])
        self.assertIn("English", payload["response_format"]["json_schema"]["description"])

        object_payload = stage2.response_format_payload("json_object", True)
        self.assertEqual(object_payload, {"response_format": {"type": "json_object"}})
        self.assertEqual(stage2.response_format_payload("none", True), {})

    def test_cache_key_includes_request_config(self):
        record = self.parameter_record()
        old_key = stage2.cache_key(record, "qwen3-vl-plus", {"response_format": "json_object"})
        new_key = stage2.cache_key(record, "qwen3-vl-plus", {"response_format": "json_schema"})
        self.assertNotEqual(old_key, new_key)

    def test_prompt_sanitizes_region_and_span_details(self):
        record = self.add_record()
        record["edit_record"]["target_region"] = {
            "plane": "XZ",
            "axis": "y",
            "center": {"x": 1.0, "y": 2.0, "z": 3.0},
        }
        record["edit_record"]["affected_region_bbox"] = {"xmin": 0.0, "xmax": 1.0}
        prompt = stage2.build_prompt_text(record)
        payload = json.loads(prompt)
        sanitized = payload["edit_record"]
        self.assertNotIn("target_region", sanitized)
        self.assertNotIn("affected_region_bbox", sanitized)
        self.assertNotIn("plane", json.dumps(sanitized, ensure_ascii=False))
        self.assertNotIn("center", json.dumps(sanitized, ensure_ascii=False))

    def test_rejected_mllm_instruction_is_kept_when_fallback_is_used(self):
        with tempfile.TemporaryDirectory() as tmp:
            args = stage2.parse_args(
                [
                    "--input",
                    "input.jsonl",
                    "--output",
                    "output.jsonl",
                    "--cache-dir",
                    tmp,
                    "--allow-missing-images",
                ]
            )
            record = self.delete_record()
            original_call = stage2.call_bailian_chat

            def fake_call(*_args, **_kwargs):
                return {
                    "choices": [
                        {
                            "message": {
                                "content": json.dumps(
                                    {
                                        "instruction": "Remove the circular hole, keeping the rest of the part unchanged.",
                                        "confidence": "medium",
                                    }
                                )
                            }
                        }
                    ],
                    "usage": {"total_tokens": 12},
                }

            try:
                stage2.call_bailian_chat = fake_call
                output = stage2.generate_one_instruction(record, args, api_key="test-key")
            finally:
                stage2.call_bailian_chat = original_call

            meta = output["instruction_meta"]
            self.assertTrue(meta["fallback_used"])
            self.assertEqual(meta["generator"], "template_fallback")
            self.assertIn("instruction missing key dimension 10", meta["quality_reasons"])
            self.assertIn("omitted a required dimension", meta["fallback_reason_summary"])
            self.assertEqual(
                meta["rejected_mllm_instruction"],
                "Remove the circular hole, keeping the rest of the part unchanged.",
            )
            self.assertEqual(meta["rejected_mllm_confidence"], "medium")
            self.assertFalse(meta["rejected_mllm_response_cached"])


if __name__ == "__main__":
    unittest.main()
