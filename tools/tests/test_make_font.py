"""저장소에 넣은 숫자 글꼴(fonts/geist-num.woff2)이 화면에 맞게 만들어졌는지 본다.

원본(tools/fonts-src/)은 git 밖이라, 원본 없이도 도는 결과물 시험만 둔다.
"""

from pathlib import Path

from fontTools.ttLib import TTFont

from tools.make_font import CHARS

ROOT = Path(__file__).parent.parent.parent
FONT = ROOT / "fonts" / "geist-num.woff2"


def test_number_font_has_only_number_glyphs() -> None:
    """가격 숫자에 쓰는 글자는 다 있고, 한글·영문은 없어 파일이 작다."""
    cmap = TTFont(FONT).getBestCmap()
    assert all(ord(c) in cmap for c in CHARS)
    assert ord("원") not in cmap
    assert ord("A") not in cmap
    assert FONT.stat().st_size < 30_000


def test_number_font_keeps_tabular_figures() -> None:
    """줄끼리 숫자 자리를 맞추는 기능(tnum)이 남아 있다."""
    gsub = TTFont(FONT)["GSUB"].table
    tags = {record.FeatureTag for record in gsub.FeatureList.FeatureRecord}
    assert "tnum" in tags


def test_number_font_keeps_license() -> None:
    """글꼴 안의 사용 조건 문구와 옆의 OFL.txt가 남아 있다(SIL OFL 조건)."""
    name = TTFont(FONT)["name"]
    assert "Open Font License" in str(name.getDebugName(13))
    assert (ROOT / "fonts" / "OFL.txt").exists()
