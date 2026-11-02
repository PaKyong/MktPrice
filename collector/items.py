"""품종 목록 파일(`collector/items.json`)을 만들고 읽고 쓴다.

품종 목록 파일은 화면 이름과 KAMIS 코드를 잇는 파일이다. 전체 평균 API
응답에서 자동으로 만들고, 이름이나 무게/개수 구분이 틀린 것은 손으로 고친다.
"""

import json
from dataclasses import asdict
from pathlib import Path
from typing import List

from collector.models import CATEGORIES, Item, OverallRow
from collector.units import classify_unit

TOP_RANK = "상품"
ITEMS_PATH = Path(__file__).parent / "items.json"


def build_items(rows: List[OverallRow], rank_code: str) -> List[Item]:
    """전체 평균 줄들로 품종 목록을 만든다.

    등급이 "상품"인 줄만 골라, 조사 단위를 무게/개수 구분과 양으로 나누고,
    부류 이름을 붙여 품종 id 순으로 정렬한다.

    Args:
        rows: 전체 평균 API를 해석한 줄들.
        rank_code: 상품 등급의 KAMIS 코드.

    Returns:
        품종 id 순으로 정렬한 품종 목록.

    Raises:
        ValueError: 조사 단위를 읽을 수 없는 줄이 있는 경우.
    """
    items = {}
    for row in rows:
        if row.rank != TOP_RANK:
            continue
        measure, amount, label = classify_unit(row.unit)
        item_id = f"{row.item_code}-{row.kind_code}"
        items[item_id] = Item(
            id=item_id,
            category_code=row.category_code,
            category_name=CATEGORIES.get(row.category_code, ""),
            item_code=row.item_code,
            item_name=row.item_name,
            kind_code=row.kind_code,
            kind_name=row.kind_name,
            rank_code=rank_code,
            unit=row.unit,
            measure=measure,
            amount=amount,
            unit_label=label,
        )
    return [items[k] for k in sorted(items)]


def save_items(path: Path, items: List[Item]) -> None:
    """품종 목록을 사람이 고치기 쉬운 JSON으로 쓴다.

    Args:
        path: 쓸 파일 경로.
        items: 품종 목록.
    """
    data = [asdict(item) for item in items]
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_items(path: Path) -> List[Item]:
    """품종 목록 파일을 읽는다.

    Args:
        path: 읽을 파일 경로.

    Returns:
        품종 목록.
    """
    data = json.loads(path.read_text(encoding="utf-8"))
    return [Item(**{**d, "amount": float(d["amount"])}) for d in data]
