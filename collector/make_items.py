"""품종 목록 파일(`collector/items.json`)을 전체 평균 응답으로 다시 만든다.

키(환경변수)가 있으면 실제 KAMIS 응답으로, 없으면 샘플 응답으로 만든다.
키를 받은 뒤 한 번 돌려 실제 품종과 조사 단위로 바꾸는 데 쓴다.

    uv run python -m collector.make_items
"""

import os
import sys
from datetime import date
from typing import List, Optional

from collector.items import ITEMS_PATH, build_items, save_items
from collector.kamis import SAMPLE_DIR, make_source
from collector.models import CATEGORIES, OverallRow
from collector.parse import parse_category

# KAMIS 코드표 "등급코드" 시트의 상품 등급 코드(p_productrankcode).
TOP_RANK_CODE = "04"


def main(argv: Optional[List[str]] = None) -> int:
    """부류 6개의 전체 평균 응답으로 품종 목록 파일을 다시 쓴다.

    Args:
        argv: 명령줄 인자(쓰지 않음).

    Returns:
        종료 코드. 성공하면 0.
    """
    source = make_source(os.environ, SAMPLE_DIR)
    rows: List[OverallRow] = []
    for code in CATEGORIES:
        rows.extend(parse_category(source.category(code), code, date.today()))
    items = build_items(rows, TOP_RANK_CODE)
    save_items(ITEMS_PATH, items)
    print(f"{source.name} 응답으로 품종 {len(items)}개를 {ITEMS_PATH}에 썼습니다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
