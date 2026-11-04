"""설계 6절의 계산 규칙.

가게별 값으로 대형유통 평균·범위·30일 추이를, 전체 평균 값으로 시기 비교 %와
신호를 내고, 품종 하나의 화면용 항목(prices.json의 items 한 칸)을 만든다. 가게별
값이 없는 축산물은 날짜별 전국 평균으로 만든다(설계 18절).
"""

import statistics
from collections import defaultdict
from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Tuple

from collector.models import Item, OverallRow, StoreRow
from collector.units import round_won, unit_price

# 평년 대비 이 % 이상이면 "비싼 편", 이만큼 이하로 낮으면 "싼 편"(임시 기준).
THRESHOLD_PCT = 15.0
# True면 대형유통 가게 값만, False면 모든 가게 값(전국 평균)을 쓴다.
LARGE_ONLY = True
# 기준일을 포함해 거꾸로 볼 날 수.
WINDOW_DAYS = 31


def mean_won(values: List[int]) -> int:
    """값들의 평균을 원 단위로 반올림한다.

    Args:
        values: 가격들. 비어 있으면 안 된다.

    Returns:
        평균(원 단위).
    """
    return round_won(sum(values) / len(values))


def price_range(values: List[int]) -> Tuple[int, int]:
    """가게 값들의 범위를 낸다.

    4곳 이상이면 값 순서로 세운 가운데 절반의 낮은 끝과 높은 끝
    (`statistics.quantiles`의 inclusive 방식 첫째·셋째 값)을, 4곳보다 적으면
    가장 낮은 값과 가장 높은 값을 돌려준다.

    Args:
        values: 그날 가게 값들. 비어 있으면 안 된다.

    Returns:
        (낮은 끝, 높은 끝).
    """
    if len(values) < 4:
        return (min(values), max(values))
    q1, _, q3 = statistics.quantiles(values, n=4, method="inclusive")
    return (round_won(q1), round_won(q3))


def change_pct(today: Optional[int], past: Optional[int]) -> Optional[float]:
    """과거 값 대비 오늘 값이 몇 % 다른지 낸다(반올림하지 않음).

    Args:
        today: 오늘 값.
        past: 비교할 과거 값.

    Returns:
        (today − past) ÷ past × 100. 둘 중 하나라도 없으면 None.
    """
    if today is None or past is None:
        return None
    return (today - past) / past * 100


def signal(pct: Optional[float], threshold: float = THRESHOLD_PCT) -> Optional[str]:
    """평년 대비 %로 "비싼 편"·"보통"·"싼 편" 신호를 붙인다.

    Args:
        pct: 반올림하기 전의 평년 대비 %.
        threshold: 경계 %.

    Returns:
        신호 글자. pct가 없으면 None.
    """
    if pct is None:
        return None
    if pct >= threshold:
        return "비싼 편"
    if pct <= -threshold:
        return "싼 편"
    return "보통"


def _round1(pct: Optional[float]) -> Optional[float]:
    return None if pct is None else round(pct, 1)


def build_entry(item: Item, overall: Optional[OverallRow], stores: List[StoreRow], as_of: date,
                large_only: bool = LARGE_ONLY) -> Optional[Dict[str, Any]]:
    """품종 하나의 화면용 항목을 만든다.

    1. 쓸 가게(대형유통만 또는 전부)와 as_of부터 거꾸로 31일 안의 줄을 고른다.
    2. 날짜별로 묶어, 값이 있는 가장 최근 날을 품종 기준일로 삼는다.
    3. 그날 값으로 평균·조사처 수·범위와 단위 가격을, 날짜별 평균으로 30일
       추이를 낸다.
    4. 전체 평균 줄이 있으면 시기 비교 %(소수 첫째 자리)와 신호(반올림 전
       평년 대비 %로 판단)를 붙인다.

    Args:
        item: 품종.
        overall: 그 품종의 전체 평균 줄. 없으면 시기 비교는 모두 None.
        stores: 그 품종의 가게별 줄들.
        as_of: 파일 기준일.
        large_only: True면 대형유통 가게만 쓴다.

    Returns:
        prices.json의 품종 항목. 31일 안에 값이 하나도 없으면 None.
    """
    start = as_of - timedelta(days=WINDOW_DAYS - 1)
    by_day: Dict[date, List[int]] = defaultdict(list)
    for s in stores:
        if (s.large or not large_only) and start <= s.day <= as_of:
            by_day[s.day].append(s.price)
    if not by_day:
        return None
    latest = max(by_day)
    values = by_day[latest]
    price = mean_won(values)
    low, high = price_range(values)

    def to_unit(won: int) -> int:
        return unit_price(won, item.measure, item.amount)

    pcts: Dict[str, Optional[float]] = {"week": None, "month": None, "year": None, "normal": None}
    if overall is not None:
        pcts = {
            "week": change_pct(overall.today, overall.week_ago),
            "month": change_pct(overall.today, overall.month_ago),
            "year": change_pct(overall.today, overall.year_ago),
            "normal": change_pct(overall.today, overall.normal),
        }
    return {
        "id": item.id,
        "category": item.category_name,
        "item": item.item_name,
        "kind": item.kind_name,
        "unit": item.unit,
        "measure": item.measure,
        "unit_label": item.unit_label,
        "as_of": latest.isoformat(),
        "price": price,
        "unit_price": to_unit(price),
        "stores": len(values),
        "range": [low, high],
        "unit_range": [to_unit(low), to_unit(high)],
        "change": {k: _round1(v) for k, v in pcts.items()},
        "signal": signal(pcts["normal"]),
        "trend": [[d.isoformat(), mean_won(by_day[d])] for d in sorted(by_day)],
    }


def build_national_entry(item: Item, overall: Optional[OverallRow], points: List[Tuple[date, int]],
                         as_of: date) -> Optional[Dict[str, Any]]:
    """가게별 값이 없는 품종(축산물)의 화면용 항목을 날짜별 전국 평균으로 만든다.

    날짜마다 전국 평균을 가게 한 곳의 값처럼 넣어 `build_entry`로 계산한 뒤, 가게가 없어 뜻이 없는
    조사처 수와 범위를 비운다(None). 가격과 30일 추이는 전국 평균, 시기 비교는 `build_entry`와 같다.

    Args:
        item: 품종.
        overall: 그 품종의 전체 평균 줄. 없으면 시기 비교는 모두 None.
        points: (날짜, 전국 평균) 목록.
        as_of: 파일 기준일.

    Returns:
        prices.json의 품종 항목. 31일 안에 값이 하나도 없으면 None.
    """
    stores = [StoreRow(day=day, county="전국", market="평균", price=price, large=True) for day, price in points]
    entry = build_entry(item, overall, stores, as_of)
    if entry is not None:
        entry.update(stores=None, range=None, unit_range=None)
    return entry
