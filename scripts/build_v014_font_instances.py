from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FONT_DIR = ROOT / "backend" / "assets" / "fonts"
FONT_SPECS = (
    ("NotoSansJP-VF.ttf", "NotoSansJP-Regular.ttf", 400),
    ("NotoSansJP-VF.ttf", "NotoSansJP-Bold.ttf", 700),
    ("NotoSansSC-VF.ttf", "NotoSansSC-Regular.ttf", 400),
    ("NotoSansSC-VF.ttf", "NotoSansSC-Bold.ttf", 700),
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def build(source: Path, target: Path, weight: int) -> dict[str, object]:
    try:
        from fontTools.ttLib import TTFont
        from fontTools.varLib.instancer import instantiateVariableFont
    except ImportError as exc:
        raise SystemExit(
            "fonttools is required only for the build step; install it in an isolated build environment"
        ) from exc

    if target.is_file():
        existing = TTFont(target)
        if "fvar" not in existing and int(existing["OS/2"].usWeightClass) == weight:
            verified = existing
        else:
            target.unlink()
            verified = None
    else:
        verified = None
    if verified is None:
        variable_font = TTFont(source)
        if "fvar" not in variable_font:
            raise SystemExit(f"source is not a variable font: {source}")
        instance = instantiateVariableFont(
            variable_font,
            {"wght": float(weight)},
            inplace=False,
            optimize=True,
            updateFontNames=True,
        )
        target.parent.mkdir(parents=True, exist_ok=True)
        instance.save(target)
        verified = TTFont(target)

    actual_weight = int(verified["OS/2"].usWeightClass)
    if "fvar" in verified or actual_weight != weight:
        raise SystemExit(
            f"invalid static font instance: {target} fvar={'fvar' in verified} weight={actual_weight}"
        )
    return {
        "source": source.name,
        "source_sha256": sha256(source),
        "file": target.name,
        "sha256": sha256(target),
        "weight": actual_weight,
        "size": target.stat().st_size,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build static Regular/Bold fonts for V0.14 PDFs")
    parser.add_argument(
        "--manifest",
        type=Path,
        default=FONT_DIR / "V014_FONT_INSTANCES.json",
    )
    args = parser.parse_args()
    results = [
        build(FONT_DIR / source, FONT_DIR / target, weight)
        for source, target, weight in FONT_SPECS
    ]
    payload = {"schema_version": 1, "instances": results}
    args.manifest.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
