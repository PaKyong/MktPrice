"""품종 목록 파일로 샘플 응답을 만든다.

KAMIS 문서의 응답 모양을 따라, 부류별 전체 평균 응답(`category_<코드>.json`)과
품종별 가게 값 응답(`period/<품종id>.json`)을 지어낸 값으로 만든다. 가게
이름과 지역은 KAMIS 코드표 "지역 및 시장 코드"의 실제 소매 가게들이다.
같은 seed면 늘 같은 샘플이 나온다.

    uv run python -m collector.make_sample [기준일 YYYY-MM-DD]
"""

import json
import random
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from collector.items import ITEMS_PATH, load_items
from collector.kamis import SAMPLE_DIR
from collector.models import CATEGORIES, Item
from collector.units import round_won

DEFAULT_AS_OF = date(2026, 11, 2)
DEFAULT_SEED = 20261102

# KAMIS 코드표 "지역 및 시장 코드"의 소매 대형유통업체 51곳(지역, 가게 이름).
LARGE_MARKETS: List[Tuple[str, str]] = [
    ("강릉", "A-유통"), ("고양", "B-유통"), ("고양", "J-유통"), ("광주", "A-유통"), ("광주", "C-유통"),
    ("광주", "E-유통"), ("김해", "A-유통"), ("대구", "A-유통"), ("대구", "B-유통"), ("대구", "C-유통"),
    ("대구", "E-유통"), ("대전", "A-유통"), ("대전", "C-유통"), ("대전", "E-유통"), ("부산", "A-유통"),
    ("부산", "B-유통"), ("부산", "D-유통"), ("부산", "H-유통"), ("서울", "A-유통"), ("서울", "B-유통"),
    ("서울", "B`-유통"), ("서울", "C-유통"), ("서울", "E-유통"), ("서울", "F-유통"), ("서울", "G-유통"),
    ("서울", "I-유통"), ("서울", "K-유통"), ("서울", "L-유통"), ("서울", "M'-유통"), ("서울", "M-유통"),
    ("서울", "R-마트"), ("성남", "B-유통"), ("세종", "C-유통"), ("수원", "B-유통"), ("순천", "A-유통"),
    ("안동", "C-유통"), ("용인", "C-유통"), ("용인", "E-유통"), ("울산", "A-유통"), ("울산", "B-유통"),
    ("의정부", "A-유통"), ("인천", "E-유통"), ("전주", "C-유통"), ("제주", "C-유통"), ("제주", "E-유통"),
    ("창원", "B-유통"), ("창원", "C-유통"), ("천안", "C-유통"), ("청주", "B-유통"), ("춘천", "E-유통"),
    ("포항", "E-유통"),
]
# 같은 표의 전통시장 가운데 다섯 곳.
TRADITIONAL_MARKETS: List[Tuple[str, str]] = [
    ("서울", "경동"), ("대구", "칠성"), ("부산", "부전"), ("광주", "양동"), ("청주", "육거리"),
]
# 평년 대비 차이를 고루 퍼뜨려 비싼 편·보통·싼 편이 모두 나오게 한다.
NORMAL_GAPS = (-0.3, -0.2, -0.05, 0.0, 0.05, 0.2, 0.3)


def _won(x: float) -> str:
    return f"{round_won(x):,}"


def _md(d: date) -> str:
    return d.strftime("%m/%d")


def _weekdays(as_of: date) -> List[date]:
    start = as_of - timedelta(days=30)
    return [start + timedelta(days=i) for i in range(31) if (start + timedelta(days=i)).weekday() < 5]


def _base_price(item: Item, rng: random.Random) -> float:
    if item.measure == "weight":
        return rng.uniform(150, 2500) * item.amount / 100
    return rng.uniform(300, 6000) * item.amount


def _category_row(item: Item, rank: str, base: float, slope: float, gap: float,
                  year_gap: float, as_of: date, has_month: bool) -> Dict[str, Any]:
    days = [as_of, as_of - timedelta(days=1), as_of - timedelta(days=7), as_of - timedelta(days=14),
            as_of - timedelta(days=30), date(as_of.year - 1, as_of.month, as_of.day)]
    prices = [base, base * (1 - slope / 30), base * (1 - slope * 7 / 30), base * (1 - slope * 14 / 30),
              base * (1 - slope), base / (1 + year_gap)]
    labels = ["당일", "1일전", "1주일전", "2주일전", "1개월전", "1년전"]
    row: Dict[str, Any] = {"item_name": item.item_name, "itemcode": item.item_code,
                           "kind_name": item.kind_name, "kindcode": item.kind_code,
                           "rank": rank, "rank_code": item.rank_code if rank == "상품" else "05",
                           "unit": item.unit}
    for n, (label, d, p) in enumerate(zip(labels, days, prices), start=1):
        row[f"day{n}"] = f"{label} ({_md(d)})"
        row[f"dpr{n}"] = _won(p)
    if not has_month:
        row["dpr5"] = "-"
    row["day7"] = "평년"
    row["dpr7"] = _won(base / (1 + gap))
    return row


def build_sample(items: List[Item], as_of: date,
                 seed: int = DEFAULT_SEED) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    """품종 목록으로 샘플 응답을 만든다.

    품종마다 기준 가격, 30일 동안의 오르내림, 평년 대비 차이를 난수로 정한다.
    전체 평균 응답에는 상품 줄(다섯 품종마다 중품 줄 하나 더)을, 가게 값
    응답에는 평일 31일 동안 대형유통 가게(그날 65% 확률로 조사)와 전통시장
    다섯 곳의 값, 그리고 지역 "평균" 요약 줄을 넣는다.

    Args:
        items: 품종 목록.
        as_of: 샘플의 기준일.
        seed: 난수 seed.

    Returns:
        (부류 코드 → 전체 평균 응답, 품종 id → 가게 값 응답).
    """
    rng = random.Random(seed)
    days = _weekdays(as_of)
    by_category: Dict[str, List[Dict[str, Any]]] = {code: [] for code in CATEGORIES}
    periods: Dict[str, Dict[str, Any]] = {}
    for n, item in enumerate(items):
        base = _base_price(item, rng)
        slope = rng.uniform(-0.15, 0.15)
        gap = rng.choice(NORMAL_GAPS) + rng.uniform(-0.02, 0.02)
        year_gap = rng.uniform(-0.2, 0.3)
        has_month = rng.random() > 0.1
        by_category[item.category_code].append(
            _category_row(item, "상품", base, slope, gap, year_gap, as_of, has_month))
        if n % 5 == 0:
            by_category[item.category_code].append(
                _category_row(item, "중품", base * 0.85, slope, gap, year_gap, as_of, has_month))

        large_factor = {m: rng.uniform(0.92, 1.08) for m in LARGE_MARKETS}
        trad_factor = {m: rng.uniform(0.8, 0.97) for m in TRADITIONAL_MARKETS}
        rows: List[Dict[str, Any]] = []
        for i, d in enumerate(days):
            level = base * (1 + slope * (i / (len(days) - 1) - 1))
            day_prices = []
            for market, factor in large_factor.items():
                if rng.random() < 0.65:
                    day_prices.append((market, level * factor * rng.uniform(0.98, 1.02)))
            for market, factor in trad_factor.items():
                day_prices.append((market, level * factor * rng.uniform(0.98, 1.02)))
            for (county, name), price in day_prices:
                rows.append({"itemname": item.item_name, "kindname": item.kind_name,
                             "countyname": county, "marketname": name,
                             "yyyy": str(d.year), "regday": _md(d), "price": _won(price)})
            avg = sum(p for _, p in day_prices) / len(day_prices)
            rows.append({"itemname": item.item_name, "kindname": item.kind_name,
                         "countyname": "평균", "marketname": "",
                         "yyyy": str(d.year), "regday": _md(d), "price": _won(avg)})
        periods[item.id] = {"data": {"error_code": "000", "item": rows}}

    categories: Dict[str, Dict[str, Any]] = {}
    for code, cat_rows in by_category.items():
        categories[code] = {"data": {"error_code": "000", "item": cat_rows}} if cat_rows else {"data": ["001"]}
    return categories, periods


def write_sample(sample_dir: Path, items: List[Item], as_of: date, seed: int = DEFAULT_SEED) -> None:
    """샘플 응답을 파일로 쓴다.

    Args:
        sample_dir: 쓸 폴더. `period/` 하위 폴더도 만든다.
        items: 품종 목록.
        as_of: 샘플의 기준일.
        seed: 난수 seed.
    """
    categories, periods = build_sample(items, as_of, seed)
    (sample_dir / "period").mkdir(parents=True, exist_ok=True)
    for code, raw in categories.items():
        (sample_dir / f"category_{code}.json").write_text(
            json.dumps(raw, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    for item_id, raw in periods.items():
        (sample_dir / "period" / f"{item_id}.json").write_text(
            json.dumps(raw, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def main(argv: Optional[List[str]] = None) -> int:
    """품종 목록 파일로 `collector/sample/`에 샘플 응답을 쓴다.

    Args:
        argv: 명령줄 인자. 첫 값이 있으면 기준일(YYYY-MM-DD)로 쓴다.

    Returns:
        종료 코드. 성공하면 0.
    """
    args = sys.argv[1:] if argv is None else argv
    as_of = date.fromisoformat(args[0]) if args else DEFAULT_AS_OF
    items = load_items(ITEMS_PATH)
    write_sample(SAMPLE_DIR, items, as_of)
    print(f"품종 {len(items)}개의 샘플 응답({as_of} 기준)을 {SAMPLE_DIR}에 썼습니다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
