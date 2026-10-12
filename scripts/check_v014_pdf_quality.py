from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from pathlib import Path
from typing import Any

from pypdf import PdfReader
from pypdf.generic import ContentStream


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dereference(value: Any) -> Any:
    return value.get_object() if hasattr(value, "get_object") else value


def inspect_font(font: Any, temporary: Path) -> dict[str, Any]:
    font = dereference(font)
    base_name = str(font.get("/BaseFont") or "")
    descriptor = dereference(font.get("/FontDescriptor")) if font.get("/FontDescriptor") else None
    embedded_key = next((key for key in ("/FontFile", "/FontFile2", "/FontFile3") if descriptor and descriptor.get(key)), None)
    result: dict[str, Any] = {
        "base_font": base_name,
        "subtype": str(font.get("/Subtype") or ""),
        "embedded": bool(embedded_key),
        "embedded_key": embedded_key,
    }
    if not embedded_key:
        return result
    stream = dereference(descriptor[embedded_key])
    data = stream.get_data()
    result["embedded_sha256"] = hashlib.sha256(data).hexdigest()
    result["embedded_bytes"] = len(data)
    if embedded_key == "/FontFile2":
        try:
            from fontTools.ttLib import TTFont

            path = temporary / f"{result['embedded_sha256']}.ttf"
            path.write_bytes(data)
            parsed = TTFont(path)
            result["weight_class"] = int(parsed["OS/2"].usWeightClass)
            result["variable"] = "fvar" in parsed
            names = set()
            for record in parsed["name"].names:
                if record.nameID in (1, 2, 17):
                    try:
                        names.add(record.toUnicode())
                    except Exception:
                        pass
            result["names"] = sorted(names)
        except Exception as exc:
            result["font_parse_error"] = type(exc).__name__
    return result


def inspect_pdf(path: Path) -> dict[str, Any]:
    reader = PdfReader(str(path))
    render_modes: dict[str, int] = {}
    font_sizes: dict[str, int] = {}
    image_count = 0
    native_text_characters = 0
    fonts: dict[str, dict[str, Any]] = {}
    with tempfile.TemporaryDirectory() as directory:
        temporary = Path(directory)
        for page in reader.pages:
            native_text_characters += len(page.extract_text() or "")
            resources = dereference(page.get("/Resources") or {})
            for _, font_ref in dereference(resources.get("/Font") or {}).items():
                inspected = inspect_font(font_ref, temporary)
                key = inspected.get("embedded_sha256") or inspected["base_font"]
                fonts[str(key)] = inspected
            for _, object_ref in dereference(resources.get("/XObject") or {}).items():
                object_value = dereference(object_ref)
                if str(object_value.get("/Subtype") or "") == "/Image":
                    image_count += 1
            content = ContentStream(page.get_contents(), reader)
            for operands, operator in content.operations:
                if operator == b"Tr":
                    mode = str(int(operands[0]))
                    render_modes[mode] = render_modes.get(mode, 0) + 1
                elif operator == b"Tf":
                    size = f"{float(operands[1]):.2f}"
                    font_sizes[size] = font_sizes.get(size, 0) + 1
                elif operator == b"INLINE IMAGE":
                    image_count += 1
    return {
        "file": str(path.resolve()),
        "sha256": sha256(path),
        "bytes": path.stat().st_size,
        "pages": len(reader.pages),
        "native_text_characters": native_text_characters,
        "image_objects": image_count,
        "text_render_modes": render_modes,
        "font_sizes": dict(sorted(font_sizes.items(), key=lambda item: float(item[0]))),
        "fonts": sorted(fonts.values(), key=lambda item: item["base_font"]),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf", nargs="+", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    payload = {"documents": [inspect_pdf(path) for path in args.pdf]}
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")


if __name__ == "__main__":
    main()
