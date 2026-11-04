"""화면에 쓰는 글꼴 파일을 만든다(설계 8절 "글꼴").

원본 Pretendard(가변 글꼴, 모든 굵기가 한 파일)에서 자주 쓰는 한글 2,350자(KS X 1001),
영문·숫자·기호, 지금 품목·상품 이름과 화면 문구에 든 글자만 남긴 woff2 하나를 `fonts/`에
만든다. 원본의 사용 조건(SIL OFL)은 고친 글꼴에 예약 이름 "Pretendard"를 쓰지 못하게 하므로
글꼴 이름을 `MktSans`로 바꾸고, 저작권과 사용 조건 문구, OFL.txt는 남긴다.
품목·상품 이름에 새 글자가 생기면(시험 test_font_covers_names_and_screen_text가 알려 준다) 다시 돌린다.

    uv run python tools/make_font.py

원본은 git에 넣지 않는다. 없으면 아래 주소에서 `tools/fonts-src/`로 받는다.
https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/packages/pretendard/dist/web/variable/woff2/PretendardVariable.woff2
(사용 조건은 같은 저장소의 LICENSE를 `Pretendard-OFL.txt`라는 이름으로)
"""

import json
import shutil
from pathlib import Path

from fontTools import subset
from fontTools.ttLib import TTFont

ROOT = Path(__file__).parent.parent
SRC_FONT = ROOT / "tools" / "fonts-src" / "PretendardVariable.woff2"
SRC_LICENSE = ROOT / "tools" / "fonts-src" / "Pretendard-OFL.txt"
OUT_FONT = ROOT / "fonts" / "mkt-sans.woff2"
OUT_LICENSE = ROOT / "fonts" / "OFL.txt"
FAMILY = "MktSans"
SCREEN_FILES = [ROOT / "index.html", ROOT / "app.js", ROOT / "manifest.webmanifest"]
DATA_FILES = [ROOT / "data" / "prices.json", ROOT / "data" / "emart.json"]
# 화면 문구 말고도 이름과 값에 흔히 나오는 기호(가운뎃점, 별, 화살표, 물결, 따옴표, 곱하기 등).
EXTRA = "·★☆✕◀▶~…–—‘’“”×%₩㎏㎖㎗ℓ"
# 저작권(0), 사용 조건 설명(13), 사용 조건 주소(14)는 원래 문구를 남겨야 한다.
KEEP_NAME_IDS = (0, 13, 14)


def ks_x_1001_hangul() -> str:
    """자주 쓰는 한글 2,350자(KS X 1001 완성형)를 차례대로 돌려준다.

    EUC-KR의 한글 영역(첫 바이트 0xB0~0xC8, 둘째 바이트 0xA1~0xFE)을 풀어 모은다.

    Returns:
        한글 2,350자를 이은 문자열.
    """
    return "".join(bytes([lead, trail]).decode("euc-kr") for lead in range(0xB0, 0xC9) for trail in range(0xA1, 0xFF))


def screen_chars() -> str:
    """화면에 나올 수 있는 글자를 모은다.

    화면 파일(HTML, JS, 앱 설정)의 모든 글자와 가격 파일의 이름·단위·부류·묶음 글자를 모은다.
    줄바꿈 같은 제어 문자와 띄어쓰기는 빼고, 겹치지 않게 정렬해 돌려준다.

    Returns:
        글자를 정렬해 이은 문자열.
    """
    chars: set[str] = set()
    for path in SCREEN_FILES:
        chars.update(path.read_text(encoding="utf-8"))
    for path in DATA_FILES:
        if not path.exists():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        chars.update("".join(data.get("groups", [])))
        for item in data["items"]:
            for key in ("item", "kind", "unit", "unit_label", "category", "name", "group"):
                chars.update(str(item.get(key) or ""))
    return "".join(sorted(c for c in chars if c.isprintable() and not c.isspace()))


def make_font(src: Path, out: Path, chars: str) -> None:
    """원본 가변 글꼴에서 주어진 글자만 남기고 이름을 바꿔 woff2로 쓴다.

    굵기 축은 그대로 두어 한 파일에 모든 굵기를 남긴다. 줄끼리 숫자 자리를 맞추는 기능(tnum)을
    기본 기능에 더해 남기고, 힌팅은 뺀다. 이름표의 가족·전체·PostScript·고유 이름을 FAMILY로
    바꾸고, 저작권과 사용 조건 문구가 아니면서 "Pretendard"가 든 나머지 기록(상표 문구 등)은 지운다.

    Args:
        src: 원본 Pretendard 가변 글꼴(woff2) 경로.
        out: 만들 글꼴(woff2) 경로.
        chars: 남길 글자들.
    """
    font = TTFont(src)
    options = subset.Options()
    options.flavor = "woff2"
    options.hinting = False
    options.layout_features = [*options.layout_features, "tnum"]
    options.name_IDs = ["*"]
    options.name_languages = ["*"]
    subsetter = subset.Subsetter(options)
    subsetter.populate(text=chars)
    subsetter.subset(font)
    name = font["name"]
    for name_id, text in ((1, FAMILY), (3, FAMILY), (4, FAMILY), (6, f"{FAMILY}-Regular"), (25, FAMILY)):
        name.setName(text, name_id, 3, 1, 0x409)
    name.names = [record for record in name.names
                  if record.nameID in KEEP_NAME_IDS or "Pretendard" not in record.toUnicode()]
    out.parent.mkdir(exist_ok=True)
    font.flavor = "woff2"
    font.save(out)


def main() -> None:
    """원본에서 화면 글꼴을 만들고 사용 조건 파일을 옆에 복사한다."""
    chars = "".join(chr(c) for c in range(0x20, 0x7F)) + EXTRA + ks_x_1001_hangul() + screen_chars()
    make_font(SRC_FONT, OUT_FONT, chars)
    shutil.copyfile(SRC_LICENSE, OUT_LICENSE)
    print(f"{OUT_FONT.relative_to(ROOT)}: {OUT_FONT.stat().st_size:,} 바이트")


if __name__ == "__main__":
    main()
