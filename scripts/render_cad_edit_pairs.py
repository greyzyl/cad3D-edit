#!/usr/bin/env python3
"""Render before/after CadQuery edit pairs from generated dataset JSONL."""

from __future__ import annotations

import argparse
import html
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cadquery as cq
from cadquery import exporters


@dataclass(frozen=True)
class RenderedPair:
    index: int
    instruction: str
    kind: str
    before_svg: str | None
    after_svg: str | None
    before_step: str | None
    after_step: str | None


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                record = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_number}: invalid JSON: {exc}") from exc
            if not isinstance(record, dict):
                raise ValueError(f"{path}:{line_number}: expected JSON object")
            records.append(record)
    return records


def execute_cadquery(source: str) -> Any:
    namespace: dict[str, Any] = {"cq": cq, "cadquery": cq}
    exec(compile(source, "<cadquery_source>", "exec"), namespace)
    if "result" not in namespace:
        raise RuntimeError("result variable was not defined")
    return namespace["result"]


def as_export_shape(result: Any) -> Any:
    if hasattr(result, "val") and callable(result.val):
        return result.val()
    return result


def export_svg(shape: Any, path: Path) -> None:
    svg = exporters.getSVG(shape)
    path.write_text(svg, encoding="utf-8", newline="\n")


def export_step(shape: Any, path: Path) -> None:
    exporters.export(shape, str(path), exportType="STEP")


def render_record(record: dict[str, Any], index: int, output_dir: Path, formats: set[str]) -> RenderedPair:
    hidden = record.get("hidden")
    if not isinstance(hidden, dict) or not isinstance(hidden.get("original_code"), str):
        raise ValueError(f"record {index}: missing hidden.original_code")
    if not isinstance(record.get("target_code"), str):
        raise ValueError(f"record {index}: missing target_code")

    before_shape = as_export_shape(execute_cadquery(hidden["original_code"]))
    after_shape = as_export_shape(execute_cadquery(record["target_code"]))

    stem = f"sample_{index:06d}"
    before_svg = after_svg = before_step = after_step = None

    if "svg" in formats:
        before_svg_path = output_dir / f"{stem}_before.svg"
        after_svg_path = output_dir / f"{stem}_after.svg"
        export_svg(before_shape, before_svg_path)
        export_svg(after_shape, after_svg_path)
        before_svg = before_svg_path.name
        after_svg = after_svg_path.name

    if "step" in formats:
        before_step_path = output_dir / f"{stem}_before.step"
        after_step_path = output_dir / f"{stem}_after.step"
        export_step(before_shape, before_step_path)
        export_step(after_shape, after_step_path)
        before_step = before_step_path.name
        after_step = after_step_path.name

    edit_record = hidden.get("edit_record")
    kind = ""
    if isinstance(edit_record, dict) and isinstance(edit_record.get("kind"), str):
        kind = edit_record["kind"]

    instruction = record.get("instruction")
    return RenderedPair(
        index=index,
        instruction=instruction if isinstance(instruction, str) else "",
        kind=kind,
        before_svg=before_svg,
        after_svg=after_svg,
        before_step=before_step,
        after_step=after_step,
    )


def html_link(filename: str | None, label: str) -> str:
    if not filename:
        return ""
    escaped_name = html.escape(filename)
    escaped_label = html.escape(label)
    return f'<a href="{escaped_name}">{escaped_label}</a>'


def write_index(rendered: list[RenderedPair], output_dir: Path) -> None:
    cards: list[str] = []
    for item in rendered:
        before_panel = ""
        after_panel = ""
        if item.before_svg:
            before_panel = f'<object data="{html.escape(item.before_svg)}" type="image/svg+xml"></object>'
        if item.after_svg:
            after_panel = f'<object data="{html.escape(item.after_svg)}" type="image/svg+xml"></object>'

        step_links = " ".join(
            link
            for link in (
                html_link(item.before_step, "before STEP"),
                html_link(item.after_step, "after STEP"),
            )
            if link
        )

        cards.append(
            f"""
            <section class="pair">
              <header>
                <h2>Sample {item.index:06d}</h2>
                <p>{html.escape(item.instruction)}</p>
                <span>{html.escape(item.kind)}</span>
              </header>
              <div class="views">
                <figure>
                  <figcaption>Before</figcaption>
                  {before_panel}
                </figure>
                <figure>
                  <figcaption>After</figcaption>
                  {after_panel}
                </figure>
              </div>
              <footer>{step_links}</footer>
            </section>
            """
        )

    document = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <title>CAD Edit V1 Render Preview</title>
  <style>
    body {{
      margin: 0;
      font-family: Arial, "Microsoft YaHei", sans-serif;
      background: #f6f7f8;
      color: #1f2933;
    }}
    main {{
      max-width: 1280px;
      margin: 0 auto;
      padding: 24px;
    }}
    h1 {{
      margin: 0 0 20px;
      font-size: 24px;
    }}
    .pair {{
      background: #fff;
      border: 1px solid #d8dee4;
      border-radius: 8px;
      margin-bottom: 20px;
      padding: 16px;
    }}
    .pair header {{
      display: flex;
      align-items: baseline;
      gap: 12px;
      flex-wrap: wrap;
      margin-bottom: 12px;
    }}
    .pair h2 {{
      margin: 0;
      font-size: 18px;
    }}
    .pair p {{
      margin: 0;
      flex: 1;
    }}
    .pair span {{
      font-size: 12px;
      color: #52616b;
      border: 1px solid #d8dee4;
      border-radius: 999px;
      padding: 2px 8px;
    }}
    .views {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 16px;
    }}
    figure {{
      margin: 0;
      border: 1px solid #d8dee4;
      border-radius: 6px;
      background: #fbfcfd;
      min-height: 360px;
      overflow: hidden;
    }}
    figcaption {{
      padding: 8px 10px;
      border-bottom: 1px solid #d8dee4;
      font-weight: 700;
      background: #eef1f4;
    }}
    object {{
      display: block;
      width: 100%;
      height: 420px;
    }}
    footer {{
      margin-top: 10px;
      display: flex;
      gap: 12px;
    }}
    a {{
      color: #0b63ce;
    }}
    @media (max-width: 820px) {{
      .views {{
        grid-template-columns: 1fr;
      }}
    }}
  </style>
</head>
<body>
  <main>
    <h1>CAD Edit V1 Render Preview</h1>
    {''.join(cards)}
  </main>
</body>
</html>
"""
    (output_dir / "index.html").write_text(document, encoding="utf-8", newline="\n")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default=Path("outputs/cad_edit_v1.jsonl"), type=Path)
    parser.add_argument("--output-dir", default=Path("outputs/cad_edit_v1_renders"), type=Path)
    parser.add_argument("--limit", default=None, type=int)
    parser.add_argument("--formats", default="svg,step", help="Comma-separated formats: svg,step")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    formats = {item.strip().lower() for item in args.formats.split(",") if item.strip()}
    unsupported = formats - {"svg", "step"}
    if unsupported:
        raise ValueError(f"unsupported formats: {sorted(unsupported)}")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    records = read_jsonl(args.input)
    if args.limit is not None:
        records = records[: args.limit]

    rendered: list[RenderedPair] = []
    for index, record in enumerate(records, start=1):
        rendered.append(render_record(record, index, args.output_dir, formats))

    write_index(rendered, args.output_dir)
    summary = {
        "records": len(rendered),
        "output_dir": str(args.output_dir),
        "index": str(args.output_dir / "index.html"),
        "formats": sorted(formats),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
