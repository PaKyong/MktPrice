"""저장소에 넣은 화면 글꼴(fonts/mkt-sans.woff2)이 화면에 맞게 만들어졌는지 본다.

원본(tools/fonts-src/)은 git 밖이라, 원본 없이도 도는 결과물 시험만 둔다.
"""

from pathlib import Path

from fontTools.ttLib import TTFont

from tools.make_font import FAMILY, ks_x_1001_hangul, screen_chars

ROOT = Path(__file__).parent.parent.parent
FONT = ROOT / "fonts" / "mkt-sans.woff2"


def test_font_covers_names_and_screen_text() -> None:
    """지금 품목·상품 이름과 화면 문구의 글자가 모두 글꼴에 있다(없으면 도구로 다시 만든다)."""
    cmap = TTFont(FONT).getBestCmap()
    missing = "".join(sorted({c for c in screen_chars() if ord(c) not in cmap}))
    assert not missing, f"글꼴에 없는 글자: {missing} (uv run python tools/make_font.py로 다시 만든다)"


def test_font_covers_common_hangul() -> None:
    """자주 쓰는 한글 2,350자가 모두 있어 새 상품 이름도 대개 같은 글꼴로 보인다."""
    cmap = TTFont(FONT).getBestCmap()
    hangul = ks_x_1001_hangul()
    assert len(hangul) == 2350
    assert all(ord(c) in cmap for c in hangul)


def test_font_keeps_every_weight() -> None:
    """한 파일에 굵기 400~700이 다 들어 있다(가변 글꼴)."""
    axes = {axis.axisTag: (axis.minValue, axis.maxValue) for axis in TTFont(FONT)["fvar"].axes}
    assert axes["wght"][0] <= 400
    assert axes["wght"][1] >= 700


def test_font_keeps_tabular_figures() -> None:
    """줄끼리 숫자 자리를 맞추는 기능(tnum)이 남아 있다."""
    gsub = TTFont(FONT)["GSUB"].table
    tags = {record.FeatureTag for record in gsub.FeatureList.FeatureRecord}
    assert "tnum" in tags


def test_font_is_renamed_and_keeps_license() -> None:
    """고친 글꼴은 예약 이름(Pretendard)을 쓰지 않고, 저작권·사용 조건 문구와 OFL.txt는 남긴다."""
    name = TTFont(FONT)["name"]
    assert name.getDebugName(1) == FAMILY
    assert all("Pretendard" not in record.toUnicode() for record in name.names if record.nameID not in (0, 13, 14))
    assert "Open Font License" in str(name.getDebugName(13))
    assert (ROOT / "fonts" / "OFL.txt").read_text(encoding="utf-8").startswith("Copyright (c) 2021, Kil Hyung-jin")


def test_font_is_small_enough() -> None:
    """폰에 한 번 저장하는 파일이라 원본(2MB)보다 훨씬 작아야 한다."""
    assert FONT.stat().st_size < 700_000
