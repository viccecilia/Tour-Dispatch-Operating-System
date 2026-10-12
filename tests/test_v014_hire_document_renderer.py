import runpy
from pathlib import Path

from backend.services.document_model_service import build_document_snapshot
from backend.services.v014_hire_document_renderer import render_hire_sample_packet
ROOT = Path(__file__).resolve().parents[1]
sample_group = runpy.run_path(str(ROOT / "scripts" / "generate_v014_hire_sample_pdf.py"))["sample_group"]


def test_hire_sample_packet_uses_phase2a_snapshot_and_has_four_pages(tmp_path: Path) -> None:
    import fitz
    from pypdf import PdfReader

    snapshot = build_document_snapshot(sample_group(), "docv-renderer-test")
    for order in snapshot["orders"]:
        if order["order_id"] == 201:
            order["applicant_name"] = "SPI"
    output = tmp_path / "sample.pdf"
    pages = render_hire_sample_packet(
        snapshot,
        output,
        jp_font_path=ROOT / "backend" / "assets" / "fonts" / "NotoSansJP-VF.ttf",
    )
    reader = PdfReader(str(output))
    assert pages == 4
    assert len(reader.pages) == 4
    pdf = fitz.open(output)
    text = "\n".join(page.get_text() for page in pdf)
    assert text.count("運送引受書") == 2
    assert text.count("運 行 指 示 書") == 2
    assert "スーパーホテル地下鉄谷町四丁目6号口" in text
    assert "SPI" in text
    for forbidden in ("貸切バス", "別記1", "別記2", "DRAFT", "ツアーコード", "未入力"):
        assert forbidden not in text


def test_airport_acceptance_is_split_at_ten_orders(tmp_path: Path) -> None:
    from pypdf import PdfReader

    group = sample_group()
    airports = [order for order in group["orders"] if order["document_kind"] == "airport_transfer"]
    group["orders"] = []
    for index in range(11):
        order = dict(airports[index % len(airports)])
        order["id"] = 500 + index
        order["oid"] = f"APT-{500 + index}"
        group["orders"].append(order)
    snapshot = build_document_snapshot(group, "docv-ten-page-test")
    output = tmp_path / "eleven.pdf"
    pages = render_hire_sample_packet(
        snapshot,
        output,
        jp_font_path=ROOT / "backend" / "assets" / "fonts" / "NotoSansJP-VF.ttf",
    )
    assert len(snapshot["airport_acceptance_pages"]) == 2
    assert [len(page) for page in snapshot["airport_acceptance_pages"]] == [10, 1]
    assert pages == 5
    assert len(PdfReader(str(output)).pages) == 5


def test_real_operations_manager_name_uses_font_fallback_without_missing_glyph(tmp_path: Path) -> None:
    import fitz

    group = sample_group()
    group["operations_manager"] = "胡東锴"
    snapshot = build_document_snapshot(group, "docv-font-fallback-test")
    output = tmp_path / "font-fallback.pdf"
    render_hire_sample_packet(
        snapshot,
        output,
        jp_font_path=ROOT / "backend" / "assets" / "fonts" / "NotoSansJP-VF.ttf",
    )
    text = "\n".join(page.get_text() for page in fitz.open(output))
    assert "胡東锴" in text
    assert "□" not in text


def test_four_target_page_layout_geometry(tmp_path: Path) -> None:
    import pdfplumber

    snapshot = build_document_snapshot(sample_group(), "docv-layout-geometry-test")
    output = tmp_path / "layout.pdf"
    render_hire_sample_packet(
        snapshot,
        output,
        jp_font_path=ROOT / "backend" / "assets" / "fonts" / "NotoSansJP-VF.ttf",
    )
    expected_y_edges = [
        [82.0, 190.0, 230.0, 250.0, 550.0, 575.0, 737.0],
        [87.0, 165.0, 231.0, 239.0, 271.0, 555.0, 563.0, 623.0, 633.0, 677.0, 703.0],
        [82.0, 125.0, 168.0, 250.0, 299.0, 329.0, 491.0],
        [82.0, 107.0, 132.0, 157.0, 200.0, 288.0, 295.0, 355.0, 362.0, 402.0],
    ]
    expected_x_edges = [
        [28.0, 46.0, 98.0, 297.0, 315.0, 367.0, 567.0, 569.0],
        [28.0, 53.0, 123.0, 345.0, 487.0, 567.0],
        [28.0, 135.0, 298.0, 405.0, 567.0],
        [28.0, 135.0, 298.0, 405.0, 567.0],
    ]
    with pdfplumber.open(output) as pdf:
        assert len(pdf.pages) == 4
        for page, wanted_x, wanted_y in zip(pdf.pages, expected_x_edges, expected_y_edges):
            x_edges = {round(float(value), 1) for rect in page.rects for value in (rect["x0"], rect["x1"])}
            y_edges = {round(float(value), 1) for rect in page.rects for value in (rect["top"], rect["bottom"])}
            assert set(wanted_x).issubset(x_edges)
            assert set(wanted_y).issubset(y_edges)
