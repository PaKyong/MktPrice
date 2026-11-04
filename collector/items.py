"""품종 목록 파일(`collector/items.json`)을 만들고 읽고 쓴다.

품종 목록 파일은 화면 이름과 KAMIS 코드를 잇는 파일이다. 전체 평균 API
응답에서 자동으로 만들고, 이름이나 무게/개수 구분이 틀린 것은 손으로 고친다.
"""

import json
import re
from dataclasses import asdict
from pathlib import Path
from typing import Dict, List, Tuple

from collector.models import CATEGORIES, LIVESTOCK, Item, OverallRow
from collector.units import classify_unit

TOP_RANK = "상품"
ITEMS_PATH = Path(__file__).parent / "items.json"


# 품종마다 쓸 등급의 우선순위. 농산물은 "상품", 수산물은 "상품"이 없어 등급 없음(-),
# 中, 중멸(마른멸치), 大 순서로 고른다(2026-11-03 결정). 여기 없는 등급(중품, 小 등)만 있는
# 품종은 넣지 않는다. 축산물은 등급마다 따로 넣는다(2026-11-04 결정).
RANK_PREFERENCE = (TOP_RANK, "-", "中", "중멸", "大")
# 축산물 품목 이름을 장볼 때 쓰는 말로 바꾼다. KAMIS의 "소"는 1++~1등급 국산 소고기라 한우로 본다.
LIVESTOCK_NAMES = {"소": "한우", "돼지": "돼지고기", "닭": "닭고기"}


def _drop_unit(kind_name: str, unit: str) -> str:
    """품종 이름 끝에 붙은 "(조사 단위)"를 지운다(예: "가지(3개)" → "가지")."""
    suffix = f"({unit})"
    if unit and kind_name.endswith(suffix) and len(kind_name) > len(suffix):
        return kind_name[:-len(suffix)]
    return kind_name


def _livestock_names(row: OverallRow) -> Tuple[str, str]:
    """축산물 줄의 화면 품목·품종 이름을 정한다.

    품목 이름은 `LIVESTOCK_NAMES`로 바꾸고, 품종 이름 끝의 "(kg)" 같은 단위는 지운다. 등급("1+등급")이나
    산지("미국산")는 품종 이름 뒤에 붙여 등급만 다른 줄을 가른다("등심 1+등급"). 이미 바꾼 이름으로 다시
    만들어도 같은 이름이 나온다.
    """
    kind = re.sub(r"\((?:kg|g)\)$", "", row.kind_name)
    if row.rank.endswith(("등급", "산")) and not kind.endswith(row.rank):
        kind = f"{kind} {row.rank}"
    return LIVESTOCK_NAMES.get(row.item_name, row.item_name), kind


def build_items(rows: List[OverallRow], rank_code: str) -> List[Item]:
    """전체 평균 줄들로 품종 목록을 만든다.

    품종(품목·품종 코드)마다 `RANK_PREFERENCE`에서 가장 앞선 등급의 줄 하나를 골라,
    조사 단위를 무게/개수 구분과 양으로 나누고, 부류 이름을 붙여 품종 id 순으로
    정렬한다. 품종 이름 끝의 "(조사 단위)"는 지운다. 등급 번호는 그 줄의 것을 쓴다.
    축산물은 등급마다 한 품종으로 넣고(id 끝에 등급 번호), 이름은 `_livestock_names`로 정한다.

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
        if row.category_code == LIVESTOCK:
            best[f"{row.item_code}-{row.kind_code}-{row.rank_code}"] = row
            continue
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
        item_name, kind_name = (_livestock_names(row) if row.category_code == LIVESTOCK
                                else (row.item_name, _drop_unit(row.kind_name, row.unit)))
        items.append(Item(
            id=item_id,
            category_code=row.category_code,
            category_name=CATEGORIES.get(row.category_code, ""),
            item_code=row.item_code,
            item_name=item_name,
            kind_code=row.kind_code,
            kind_name=kind_name,
            rank_code=row.rank_code or rank_code,
            unit=row.unit,
            measure=measure,
            amount=amount,
            unit_label=label,
        ))
    return items


def merge_items(old: List[Item], new: List[Item]) -> List[Item]:
    """다시 만든 품종 목록을 기존 목록에 합친다.

    전체 평균 응답에는 그날 조사한 품종만 오므로, 새 목록에 있는 품종은 새 것으로
    바꾸고(조사 단위·이름·등급), 새 목록에 없는 품종(철이 지난 품종)은 그대로 남긴다.

    Args:
        old: 기존 품종 목록.
        new: 전체 평균 응답으로 새로 만든 품종 목록.

    Returns:
        품종 id 순으로 정렬한 합친 목록.
    """
    merged = {item.id: item for item in old}
    merged.update({item.id: item for item in new})
    return [merged[k] for k in sorted(merged)]


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
