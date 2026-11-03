"""영수증 화면에 쓰는 글꼴 파일을 만든다(설계 8절 "생김새").

원본 나눔고딕코딩(보통·굵게)에서 앱이 쓰는 글자만 남긴 woff2 두 개를 `fonts/`에
만든다. 원본 글꼴의 사용 조건(OFL)은 고친 글꼴에 "Nanum" 같은 이름을 쓰지 못하게
하므로 글꼴 이름을 `MktReceipt`로 바꾸고, 저작권 문구와 사용 조건 파일은 남긴다.
품종 목록 파일(`collector/items.json`)이나 화면 문구를 바꾸면 다시 돌린다.

    uv run python tools/make_font.py

원본은 git에 넣지 않는다. 없으면 아래 주소에서 `tools/fonts-src/`로 받는다.
https://raw.githubusercontent.com/google/fonts/main/ofl/nanumgothiccoding/
(NanumGothicCoding-Regular.ttf, NanumGothicCoding-Bold.ttf, OFL.txt)
"""

import json
import shutil
import sys
from pathlib import Path
from typing import List

from fontTools import subset
from fontTools.ttLib import TTFont

ROOT = Path(__file__).parent.parent
SRC_DIR = ROOT / "tools" / "fonts-src"
OUT_DIR = ROOT / "fonts"
ITEMS_PATH = ROOT / "collector" / "items.json"
SCREEN_FILES = [ROOT / "index.html", ROOT / "app.js"]
FAMILY = "MktReceipt"
SOURCE_URL = "https://raw.githubusercontent.com/google/fonts/main/ofl/nanumgothiccoding/"
# (원본 파일, 만들 파일, 굵기 이름)
FONTS = [
    ("NanumGothicCoding-Regular.ttf", "receipt-regular.woff2", "Regular"),
    ("NanumGothicCoding-Bold.ttf", "receipt-bold.woff2", "Bold"),
]
# 저작권(0), 사용 조건 설명(13), 사용 조건 주소(14)는 원래 문구를 남겨야 한다.
KEEP_NAME_IDS = (0, 13, 14)
ITEM_TEXT_KEYS = ("item_name", "kind_name", "unit", "unit_label", "category_name")


def used_chars(items_path: Path, screen_files: List[Path]) -> str:
    """앱 화면에 나올 수 있는 글자를 모은다.

    품종 목록 파일의 이름·단위·부류 글자와 화면 파일의 모든 글자, 그리고 출력
    가능한 ASCII(0x20~0x7E) 전부를 모은다. 줄바꿈 같은 제어 문자는 빼고, 겹치지
    않게 정렬해 돌려준다.

    Args:
        items_path: 품종 목록 파일 경로.
        screen_files: 화면 문구가 든 파일 경로들(HTML, JS).

    Returns:
        글자를 정렬해 이은 문자열.
    """
    chars = {chr(c) for c in range(0x20, 0x7F)}
    for item in json.loads(items_path.read_text(encoding="utf-8")):
        for key in ITEM_TEXT_KEYS:
            chars.update(str(item.get(key, "")))
    for path in screen_files:
        chars.update(path.read_text(encoding="utf-8"))
    return "".join(sorted(c for c in chars if c.isprintable()))


def subset_font(src: Path, dst: Path, chars: str, family: str, style: str) -> None:
    """원본 글꼴에서 주어진 글자만 남기고 이름을 바꿔 woff2로 쓴다.

    fontTools로 글자를 덜어내고(힌팅은 뺀다), 이름표의 가족·굵기·전체·PostScript·
    고유 이름을 새 이름으로 바꾼다. 저작권과 사용 조건 문구가 아니면서 "Nanum"이
    든 나머지 이름 기록은 지운다.

    Args:
        src: 원본 글꼴(TTF) 경로.
        dst: 만들 글꼴(woff2) 경로.
        chars: 남길 글자들.
        family: 새 글꼴 가족 이름.
        style: 굵기 이름("Regular" 또는 "Bold").
    """
    font = TTFont(src)
    options = subset.Options()
    options.flavor = "woff2"
    options.hinting = False
    # fontTools는 기본으로 이름 기록 0~6번만 남긴다. 사용 조건 문구(13·14번)도 남긴다.
    options.name_IDs = [0, 1, 2, 3, 4, 5, 6, *KEEP_NAME_IDS[1:]]
    subsetter = subset.Subsetter(options)
    subsetter.populate(text=chars)
    subsetter.subset(font)

    names = font["name"]
    names.names = [rec for rec in names.names
                   if rec.nameID in KEEP_NAME_IDS or "Nanum" not in rec.toUnicode()]
    for name_id, text in ((1, family), (2, style), (3, f"{family}-{style}"),
                          (4, f"{family} {style}"), (6, f"{family}-{style}")):
        names.setName(text, name_id, 3, 1, 0x409)
    font.flavor = "woff2"
    dst.parent.mkdir(parents=True, exist_ok=True)
    font.save(dst)


def main() -> int:
    """원본 두 개로 영수증 글꼴 두 개를 만들고 사용 조건 파일을 옮긴다.

    Returns:
        종료 코드. 만들었으면 0, 원본이 없으면 1.
    """
    missing = [name for name, _, _ in FONTS if not (SRC_DIR / name).exists()]
    if missing or not (SRC_DIR / "OFL.txt").exists():
        print(f"원본 글꼴이 없습니다. {SOURCE_URL} 에서 "
              f"{', '.join(name for name, _, _ in FONTS)}, OFL.txt를 {SRC_DIR}에 받으세요.",
              file=sys.stderr)
        return 1
    chars = used_chars(ITEMS_PATH, SCREEN_FILES)
    for name, out, style in FONTS:
        subset_font(SRC_DIR / name, OUT_DIR / out, chars, FAMILY, style)
    shutil.copyfile(SRC_DIR / "OFL.txt", OUT_DIR / "OFL.txt")
    sizes = ", ".join(f"{out} {(OUT_DIR / out).stat().st_size // 1024}KB" for _, out, _ in FONTS)
    print(f"글자 {len(chars)}개로 만들었습니다: {sizes}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
