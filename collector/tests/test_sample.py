"""샘플 응답과 품종 목록 파일 시험."""

from datetime import date

from collector.items import ITEMS_PATH, build_items, load_items
from collector.make_items import TOP_RANK_CODE
from collector.make_sample import build_sample
from collector.parse import parse_category, parse_national, parse_period

AS_OF = date(2026, 11, 2)


def test_sample_round_trips_items() -> None:
    items = load_items(ITEMS_PATH)
    categories, _ = build_sample(items, AS_OF)
    rows = [r for code, raw in categories.items() for r in parse_category(raw, code, AS_OF)]
    assert build_items(rows, TOP_RANK_CODE) == items


def test_sample_has_large_and_traditional_stores_over_31_days() -> None:
    items = load_items(ITEMS_PATH)
    _, periods = build_sample(items, AS_OF)
    rows = parse_period(periods[items[0].id])
    # 대형유통 이름은 지역마다 겹치므로(A-유통이 여러 지역) 지역과 이름으로 센다.
    assert len({(r.county, r.market) for r in rows if r.large}) >= 25
    assert any(not r.large for r in rows)
    assert min(r.day for r in rows) >= date(2026, 10, 3)
    assert max(r.day for r in rows) == AS_OF
    assert all(r.day.weekday() < 5 for r in rows)


def test_sample_signals_are_spread() -> None:
    items = load_items(ITEMS_PATH)
    categories, _ = build_sample(items, AS_OF)
    rows = [r for code, raw in categories.items() for r in parse_category(raw, code, AS_OF)]
    ratios = [r.today / r.normal for r in rows if r.today and r.normal]
    assert any(x >= 1.15 for x in ratios)            # 비싼 편
    assert any(x <= 0.85 for x in ratios)            # 싼 편
    assert any(0.9 < x < 1.1 for x in ratios)        # 보통


def test_sample_is_repeatable() -> None:
    items = load_items(ITEMS_PATH)
    assert build_sample(items, AS_OF) == build_sample(items, AS_OF)


def test_sample_livestock_is_national_average_one_day_earlier() -> None:
    items = [i for i in load_items(ITEMS_PATH) if i.category_code == "500"]
    _, periods = build_sample(items, AS_OF)
    assert parse_period(periods[items[0].id]) == []
    assert max(day for day, _ in parse_national(periods[items[0].id])) == AS_OF
