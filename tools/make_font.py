"""가격 숫자에 쓰는 글꼴 파일을 만든다(설계 8절 "글꼴").

원본 Geist(가변 글꼴)를 반굵게(600) 하나로 고정하고, 가격에 쓰는 숫자와 기호만
남긴 woff2 하나를 `fonts/`에 만든다. 한글과 "원"은 폰 기본 글꼴이 맡으므로 넣지
않는다. 사용 조건(SIL OFL) 문구는 글꼴 안에 남기고 OFL.txt도 옆에 둔다.

    uv run python tools/make_font.py

원본은 git에 넣지 않는다. 없으면 아래 주소에서 `tools/fonts-src/`로 받는다
(`Geist[wght].ttf`, 그리고 `OFL.txt`를 `Geist-OFL.txt`라는 이름으로).
https://github.com/google/fonts/tree/main/ofl/geist
"""

import shutil
from pathlib import Path

from fontTools import subset
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer

ROOT = Path(__file__).parent.parent
SRC_FONT = ROOT / "tools" / "fonts-src" / "Geist[wght].ttf"
SRC_LICENSE = ROOT / "tools" / "fonts-src" / "Geist-OFL.txt"
OUT_FONT = ROOT / "fonts" / "geist-num.woff2"
OUT_LICENSE = ROOT / "fonts" / "OFL.txt"
# 가격, 막대 숫자("153~199"), 판정 덧말의 %에 쓰는 글자.
CHARS = "0123456789,.%~"
WEIGHT = 600


def make_font(src: Path, out: Path) -> None:
    """원본 가변 글꼴에서 숫자 글꼴 woff2를 만든다.

    굵기 축을 600 하나로 고정한 뒤 CHARS의 글자만 남긴다. 줄끼리 숫자 자리를
    맞추는 기능(tnum)과 자간(kern)은 남기고, 사용 조건 문구가 사라지지 않게
    이름표 기록은 모두 남긴다.

    Args:
        src: 원본 Geist 가변 글꼴(TTF) 경로.
        out: 만들 글꼴(woff2) 경로.
    """
    font = instancer.instantiateVariableFont(TTFont(src), {"wght": WEIGHT})
    options = subset.Options()
    options.flavor = "woff2"
    options.layout_features = ["tnum", "kern"]
    options.name_IDs = ["*"]
    options.name_languages = ["*"]
    subsetter = subset.Subsetter(options)
    subsetter.populate(text=CHARS)
    subsetter.subset(font)
    out.parent.mkdir(exist_ok=True)
    font.flavor = "woff2"
    font.save(out)


def main() -> None:
    """원본에서 숫자 글꼴을 만들고 사용 조건 파일을 옆에 복사한다."""
    make_font(SRC_FONT, OUT_FONT)
    shutil.copyfile(SRC_LICENSE, OUT_LICENSE)
    print(f"{OUT_FONT.relative_to(ROOT)}: {OUT_FONT.stat().st_size:,} 바이트")


if __name__ == "__main__":
    main()
