"""영수증 글꼴 만들기 도구 시험. 원본 글꼴 없이 그 자리에서 만든 작은 글꼴로 돈다."""

import json
from pathlib import Path

from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont

from tools.make_font import FAMILY, subset_font, used_chars


def _square():
    pen = TTGlyphPen(None)
    pen.moveTo((0, 0))
    pen.lineTo((0, 500))
    pen.lineTo((500, 500))
    pen.closePath()
    return pen.glyph()


def _make_font(path: Path) -> Path:
    """원본처럼 이름에 "Nanum"이 든 글자 4개짜리 글꼴을 만든다."""
    glyphs = [".notdef", "A", "B", "uniAC00"]
    fb = FontBuilder(1000, isTTF=True)
    fb.setupGlyphOrder(glyphs)
    fb.setupCharacterMap({ord("A"): "A", ord("B"): "B", ord("가"): "uniAC00"})
    fb.setupGlyf({g: _square() for g in glyphs})
    fb.setupHorizontalMetrics({g: (600, 0) for g in glyphs})
    fb.setupHorizontalHeader(ascent=800, descent=-200)
    fb.setupNameTable({
        "copyright": "Copyright NHN NanumGothic",
        "familyName": "NanumGothicCoding",
        "styleName": "Regular",
        "uniqueFontIdentifier": "NanumGothicCoding-Regular",
        "fullName": "NanumGothicCoding Regular",
        "psName": "NanumGothicCoding-Regular",
        "licenseDescription": "SIL Open Font License, Version 1.1",
    })
    fb.setupOS2()
    fb.setupPost()
    fb.save(str(path))
    return path


def test_used_chars_collects_item_names_and_screen_text(tmp_path):
    items_path = tmp_path / "items.json"
    items_path.write_text(json.dumps([{
        "item_name": "양파", "kind_name": "햇양파", "unit": "1kg", "unit_label": "100g",
        "category_name": "채소류",
    }], ensure_ascii=False), encoding="utf-8")
    screen_path = tmp_path / "app.js"
    screen_path.write_text('const label = "합계(예상)";\n', encoding="utf-8")

    chars = used_chars(items_path, [screen_path])

    for c in "양파햇채소류합계예상":
        assert c in chars
    for c in "0123456789,~/+-%()*x":
        assert c in chars
    assert "\n" not in chars
    assert len(chars) == len(set(chars))
    assert list(chars) == sorted(chars)


def test_subset_font_keeps_only_requested_chars(tmp_path):
    src = _make_font(tmp_path / "src.ttf")
    dst = tmp_path / "out.woff2"

    subset_font(src, dst, "A가", FAMILY, "Regular")

    font = TTFont(dst)
    assert font.flavor == "woff2"
    assert set(font.getBestCmap()) == {ord("A"), ord("가")}


def test_subset_font_renames_reserved_font_name(tmp_path):
    src = _make_font(tmp_path / "src.ttf")
    dst = tmp_path / "out.woff2"

    subset_font(src, dst, "A", FAMILY, "Bold")

    names = TTFont(dst)["name"]
    assert names.getDebugName(1) == "MktReceipt"
    assert names.getDebugName(2) == "Bold"
    for rec in names.names:
        if rec.nameID not in (0, 13, 14):
            assert "Nanum" not in rec.toUnicode()
    assert "NHN" in names.getDebugName(0)
    assert "Open Font License" in names.getDebugName(13)
