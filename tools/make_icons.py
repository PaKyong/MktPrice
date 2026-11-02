"""홈 화면 아이콘 PNG를 만든다.

짙은 녹색 바탕 가운데에 마트 가격표의 노란 원 하나를 그린다. 표준 라이브러리
(zlib, struct)로 PNG를 직접 쓰므로 추가 패키지가 필요 없다.

    uv run python tools/make_icons.py
"""

import struct
import zlib
from pathlib import Path
from typing import Tuple

Color = Tuple[int, int, int]

BACKGROUND: Color = (0x1E, 0x2A, 0x22)
CIRCLE: Color = (0xFF, 0xE4, 0x5C)
# 원의 반지름 비율. 안드로이드가 아이콘 가장자리를 잘라도(가운데 80%만 남김) 원이 다 보이게 한다.
RADIUS_RATIO = 0.28
ICONS_DIR = Path(__file__).parent.parent / "icons"


def _chunk(tag: bytes, data: bytes) -> bytes:
    crc = zlib.crc32(tag + data) & 0xFFFFFFFF
    return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", crc)


def icon_png(size: int, background: Color = BACKGROUND, circle: Color = CIRCLE) -> bytes:
    """정사각형 아이콘 PNG를 만든다.

    줄마다 필터 바이트(0) 뒤에 RGB 점들을 이어 붙이고, 가운데 원 안의 점은
    원 색으로 칠한 뒤 zlib으로 압축해 PNG 덩어리로 묶는다.

    Args:
        size: 한 변의 점 수.
        background: 바탕 색(RGB).
        circle: 원 색(RGB).

    Returns:
        PNG 파일 내용.
    """
    center = (size - 1) / 2
    radius_sq = (size * RADIUS_RATIO) ** 2
    raw = bytearray()
    for y in range(size):
        raw.append(0)
        for x in range(size):
            inside = (x - center) ** 2 + (y - center) ** 2 <= radius_sq
            raw.extend(circle if inside else background)
    header = struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + _chunk(b"IHDR", header)
            + _chunk(b"IDAT", zlib.compress(bytes(raw), 9)) + _chunk(b"IEND", b""))


def main() -> None:
    """아이콘 세 개(192, 512, 애플 180)를 `icons/`에 쓴다."""
    ICONS_DIR.mkdir(exist_ok=True)
    for name, size in (("icon-192.png", 192), ("icon-512.png", 512), ("apple-touch-icon.png", 180)):
        (ICONS_DIR / name).write_bytes(icon_png(size))
        print(f"{ICONS_DIR / name} ({size}×{size})")


if __name__ == "__main__":
    main()
