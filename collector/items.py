"""품종 목록 파일(`collector/items.json`)을 만들고 읽고 쓴다.

품종 목록 파일은 화면 이름과 KAMIS 코드를 잇는 파일이다. 전체 평균 API
응답에서 자동으로 만들고, 이름이나 무게/개수 구분이 틀린 것은 손으로 고친다.
"""

import json
from dataclasses import asdict
from pathlib import Path
from typing import Dict, List

from collector.models import CATEGORIES, Item, OverallRow
from collector.units import classify_unit

TOP_RANK = "상품"
ITEMS_PATH = Path(__file__).parent / "items.json"


# 품종마다 쓸 등급의 우선순위. 농산물은 "상품", 수산물은 "상품"이 없어 등급 없음(-),
# 中, 중멸(마른멸치), 大 순서로 고른다(2026-11-03 결정). 여기 없는 등급(중품, 小, 축산물의
# 1등급 등)만 있는 품종은 넣지 않는다.
RANK_PREFERENCE = (TOP_RANK, "-", "中", "중멸", "大")


def _drop_unit(kind_name: str, unit: str) -> str:
    """품종 이름 끝에 붙은 "(조사 단위)"를 지운다(예: "가지(3개)" → "가지")."""
    suffix = f"({unit})"
    if unit and kind_name.endswith(suffix) and len(kind_name) > len(suffix):
        return kind_name[:-len(suffix)]
    return kind_name


def build_items(rows: List[OverallRow], rank_code: str) -> List[Item]:
    """전체 평균 줄들로 품종 목록을 만든다.

    품종(품목·품종 코드)마다 `RANK_PREFERENCE`에서 가장 앞선 등급의 줄 하나를 골라,
    조사 단위를 무게/개수 구분과 양으로 나누고, 부류 이름을 붙여 품종 id 순으로
    정렬한다. 품종 이름 끝의 "(조사 단위)"는 지운다. 등급 번호는 그 줄의 것을 쓴다.

    Args:
        rows: 전체 평균 API를 해석한 줄들.
        rank_code: 줄에 등급 번호가 없을 때 쓸 상품 등급의 KAMIS 코드.

    Returns:
        품종 id 순으로 정렬한 품종 목록.

    Raises:
        ValueError: 조사 단위를 읽을 수 없는 줄이 있는 경우.
    """
    best: Dict[str, OverallRow] = {}
    for row in rows:
        if row.rank not in RANK_PREFERENCE:
            continue
        item_id = f"{row.item_code}-{row.kind_code}"
        chosen = best.get(item_id)
        if chosen is None or RANK_PREFERENCE.index(row.rank) < RANK_PREFERENCE.index(chosen.rank):
            best[item_id] = row
    items = []
    for item_id in sorted(best):
        row = best[item_id]
        measure, amount, label = classify_unit(row.unit)
        items.append(Item(
            id=item_id,
            category_code=row.category_code,
            category_name=CATEGORIES.get(row.category_code, ""),
            item_code=row.item_code,
            item_name=row.item_name,
            kind_code=row.kind_code,
            kind_name=_drop_unit(row.kind_name, row.unit),
            rank_code=row.rank_code or rank_code,
            unit=row.unit,
            measure=measure,
            amount=amount,
            unit_label=label,
        ))
    return items


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
