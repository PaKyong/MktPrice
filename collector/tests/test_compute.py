"""계산 규칙(설계 6절) 시험."""

from datetime import date
from typing import Optional

import pytest

from collector.compute import build_entry, change_pct, mean_won, price_range, signal
from collector.models import Item, OverallRow, StoreRow
from collector.parse import is_large_retail

APPLE = Item(
    id="411-05", category_code="400", category_name="과일류", item_code="411", item_name="사과",
    kind_code="05", kind_name="홍로", rank_code="04", unit="1kg", measure="weight",
    amount=1000.0, unit_label="100g")


def store(day: str, market: str, price: int) -> StoreRow:
    """시험용 가게 줄을 만든다."""
    return StoreRow(day=date.fromisoformat(day), county="서울", market=market, price=price,
                    large=is_large_retail(market))


def overall(today: Optional[int] = None, week: Optional[int] = None,
            normal: Optional[int] = None) -> OverallRow:
    """시험용 전체 평균 줄을 만든다."""
    return OverallRow(
        category_code="400", item_code="411", item_name="사과", kind_code="05", kind_name="홍로",
        rank="상품", unit="1kg", as_of=date(2026, 11, 2), today=today, week_ago=week,
        month_ago=None, year_ago=None, normal=normal)


STORES = [store("2026-11-02", "A-유통", 3000), store("2026-11-02", "B-유통", 3400),
          store("2026-11-02", "경동", 2000), store("2026-10-30", "A-유통", 2900)]


def test_mean_won() -> None:
    assert mean_won([3000, 3001]) == 3001


def test_price_range_uses_middle_half() -> None:
    # inclusive 방식 4분의 1 지점: 2.75 → 3, 6.25 → 6
    assert price_range([1, 2, 3, 4, 5, 6, 7, 8]) == (3, 6)


def test_price_range_under_four_uses_min_max() -> None:
    assert price_range([5, 1, 3]) == (1, 5)


def test_change_pct() -> None:
    assert change_pct(118, 100) == 18.0
    assert change_pct(100, None) is None
    assert change_pct(None, 100) is None


@pytest.mark.parametrize("pct, expected", [
    (15.0, "비싼 편"), (14.9, "보통"), (-15.0, "싼 편"), (-14.9, "보통"), (None, None)])
def test_signal_boundaries(pct: Optional[float], expected: Optional[str]) -> None:
    assert signal(pct) == expected


def test_signal_uses_unrounded_pct() -> None:
    # 14.96%는 파일에 15.0으로 적히지만 신호는 반올림 전 값으로 "보통"이다.
    e = build_entry(APPLE, overall(today=11496, normal=10000), STORES, date(2026, 11, 2))
    assert e["change"]["normal"] == 15.0
    assert e["signal"] == "보통"


def test_build_entry_large_only() -> None:
    e = build_entry(APPLE, overall(today=32000, week=31000, normal=27100), STORES, date(2026, 11, 2))
    assert (e["id"], e["category"], e["item"], e["kind"]) == ("411-05", "과일류", "사과", "홍로")
    assert (e["unit"], e["measure"], e["unit_label"]) == ("1kg", "weight", "100g")
    assert e["as_of"] == "2026-11-02"
    assert (e["price"], e["unit_price"], e["stores"]) == (3200, 320, 2)
    assert (e["range"], e["unit_range"]) == ([3000, 3400], [300, 340])
    assert e["trend"] == [["2026-10-30", 2900], ["2026-11-02", 3200]]
    assert e["change"] == {"week": 3.2, "month": None, "year": None, "normal": 18.1}
    assert e["signal"] == "비싼 편"


def test_build_entry_all_stores_when_not_large_only() -> None:
    e = build_entry(APPLE, None, STORES, date(2026, 11, 2), large_only=False)
    assert (e["price"], e["stores"]) == (2800, 3)
    assert e["trend"] == [["2026-10-30", 2900], ["2026-11-02", 2800]]


def test_build_entry_uses_latest_day_within_31_days() -> None:
    e = build_entry(APPLE, None, [store("2026-10-20", "A-유통", 3000)], date(2026, 11, 2))
    assert e["as_of"] == "2026-10-20"
    assert e["change"] == {"week": None, "month": None, "year": None, "normal": None}
    assert e["signal"] is None


def test_build_entry_none_when_no_value_in_31_days() -> None:
    # 31일 안 = 2026-10-03 ~ 2026-11-02
    assert build_entry(APPLE, None, [store("2026-10-02", "A-유통", 3000)], date(2026, 11, 2)) is None
    assert build_entry(APPLE, None, [store("2026-10-03", "A-유통", 3000)], date(2026, 11, 2)) is not None
