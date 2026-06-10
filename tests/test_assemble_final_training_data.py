import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "assemble_final_training_data.py"
SPEC = importlib.util.spec_from_file_location("assemble_final_training_data", MODULE_PATH)
stage3 = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = stage3
SPEC.loader.exec_module(stage3)


def write_jsonl(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(record, ensure_ascii=False) for record in records) + "\n", encoding="utf-8")


class AssembleFinalTrainingDataTests(unittest.TestCase):
    def intermediate_record(self, sample_id: str = "s1", split: str = "train") -> dict:
        return {
            "sample_id": sample_id,
            "source_sample_id": "source_1",
            "source_line": 1,
            "images": ["missing_front.png", "missing_top.png", "missing_right.png"],
            "branch": "v1_parameter",
            "edit_type": "parameter_circle",
            "original_code": 'import cadquery as cq\nresult = cq.Workplane("XY").circle(4).extrude(2)',
            "target_code": 'import cadquery as cq\nresult = cq.Workplane("XY").circle(5).extrude(2)',
            "intermediate_code": None,
            "edit_record": {"kind": "circle", "old": 4.0, "new": 5.0},
            "validation_report": {"ok": True},
            "selection_meta": {"split": split},
        }

    def instruction_record(self, sample_id: str = "s1", split: str = "train") -> dict:
        return {
            "sample_id": sample_id,
            "source_sample_id": "source_1",
            "split": split,
            "branch": "v1_parameter",
            "edit_type": "parameter_circle",
            "instruction": "将圆半径从 4 修改为 5，其余结构保持不变。",
            "instruction_meta": {
                "generator": "template_fallback",
                "instruction_mode": "parameter",
                "fallback_used": True,
                "validation_ok": True,
                "quality_reasons": [],
                "included_target_code": False,
                "included_intermediate_code": False,
            },
        }

    def test_merge_builds_full_metadata_record(self):
        merged, reasons = stage3.merge_intermediate_and_instruction(
            self.intermediate_record(),
            self.instruction_record(),
            "train",
        )
        self.assertEqual(reasons, [])
        self.assertIsNotNone(merged)
        assert merged is not None
        self.assertEqual(merged["sample_id"], "s1")
        self.assertEqual(merged["hidden"]["original_code"], self.intermediate_record()["original_code"])
        self.assertEqual(merged["metadata"]["branch"], "v1_parameter")

    def test_training_and_chat_exports_do_not_leak_hidden_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            intermediate_dir = root / "stage1_5"
            instruction_dir = root / "stage2"
            output_dir = root / "final"
            for split in stage3.SPLITS:
                records = [self.intermediate_record(split=split)] if split == "train" else []
                instructions = [self.instruction_record(split=split)] if split == "train" else []
                write_jsonl(intermediate_dir / f"{split}_intermediate.jsonl", records)
                write_jsonl(instruction_dir / f"{split}_instructions.jsonl", instructions)

            rc = stage3.main(
                [
                    "--intermediate-dir",
                    str(intermediate_dir),
                    "--instruction-dir",
                    str(instruction_dir),
                    "--output-dir",
                    str(output_dir),
                    "--export-chat-sft",
                    "--allow-missing-images",
                ]
            )
            self.assertEqual(rc, 0)
            training = [
                json.loads(line)
                for line in (output_dir / "training" / "train.jsonl").read_text(encoding="utf-8").splitlines()
            ]
            self.assertEqual(len(training), 1)
            self.assertEqual(set(training[0]), {"sample_id", "images", "instruction", "target_code"})
            self.assertEqual(stage3.validate_training_record(training[0]), [])

            chat = [
                json.loads(line)
                for line in (output_dir / "chat_sft" / "train.jsonl").read_text(encoding="utf-8").splitlines()
            ][0]
            user_content = chat["messages"][1]["content"]
            assistant_content = chat["messages"][2]["content"]
            self.assertNotIn(self.intermediate_record()["original_code"], user_content)
            self.assertNotIn(self.intermediate_record()["target_code"], user_content)
            self.assertEqual(assistant_content, f"<code>{self.intermediate_record()['target_code']}</code>")

            summary = json.loads((output_dir / "final_summary.json").read_text(encoding="utf-8"))
            self.assertTrue(summary["training_only_leakage_check"]["ok"])
            self.assertTrue(summary["chat_sft_leakage_check"]["ok"])
            self.assertTrue(summary["ready_for_training"])

    def test_missing_instruction_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            intermediate_dir = root / "stage1_5"
            instruction_dir = root / "stage2"
            output_dir = root / "final"
            write_jsonl(intermediate_dir / "train_intermediate.jsonl", [self.intermediate_record()])
            write_jsonl(instruction_dir / "train_instructions.jsonl", [])
            for split in ("val", "test"):
                write_jsonl(intermediate_dir / f"{split}_intermediate.jsonl", [])
                write_jsonl(instruction_dir / f"{split}_instructions.jsonl", [])

            rc = stage3.main(
                [
                    "--intermediate-dir",
                    str(intermediate_dir),
                    "--instruction-dir",
                    str(instruction_dir),
                    "--output-dir",
                    str(output_dir),
                    "--allow-missing-images",
                ]
            )
            self.assertEqual(rc, 1)
            summary = json.loads((output_dir / "final_summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["dropped_reasons"]["missing_instruction_record"], 1)
            self.assertFalse(summary["ready_for_training"])


if __name__ == "__main__":
    unittest.main()
