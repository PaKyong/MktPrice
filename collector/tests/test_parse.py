"""KAMIS 응답 해석 시험."""

from datetime import date

import pytest

from collector.parse import (
    KamisError,
    is_large_retail,
    parse_category,
    parse_day,
    parse_period,
    parse_price,
)


def test_parse_price() -> None:
    assert parse_price("2,400") == 2400
    assert parse_price("-") is None
    assert parse_price("") is None
    assert parse_price(None) is None
    assert parse_price("0") is None


def test_parse_price_odd_values() -> None:
    assert parse_price([]) is None  # type: ignore[arg-type]
    assert parse_price(2400) == 2400  # type: ignore[arg-type]


def test_parse_category_accepts_underscored_code_names() -> None:
    raw = {"data": {"error_code": "000", "item": [{
        "item_name": "사과", "item_code": "411", "kind_name": "홍로", "kind_code": "05",
        "rank": "상품", "unit": "10개", "day1": "당일 (11/02)", "dpr1": "32,000"}]}}
    [row] = parse_category(raw, "400", date(2026, 11, 2))
    assert (row.item_code, row.kind_code) == ("411", "05")


def test_parse_category_skips_broken_row_and_accepts_single_item_dict() -> None:
    good = {"item_name": "사과", "itemcode": "411", "kind_name": "홍로", "kindcode": "05",
            "rank": "상품", "unit": "10개", "day1": "당일 (11/02)", "dpr1": "32,000"}
    broken = {**good, "kindcode": "06", "day1": "당일"}
    rows = parse_category({"data": {"error_code": "000", "item": [broken, good]}}, "400", date(2026, 11, 2))
    assert [r.kind_code for r in rows] == ["05"]
    rows = parse_category({"data": {"error_code": "000", "item": good}}, "400", date(2026, 11, 2))
    assert [r.kind_code for r in rows] == ["05"]


def test_parse_period_reads_short_day_and_skips_broken_rows() -> None:
    raw = {"data": {"error_code": "000", "item": [
        {"countyname": "서울", "marketname": "B-유통", "yyyy": "2026", "regday": "11/2", "price": "3,250"},
        {"countyname": "서울", "marketname": "C-유통", "regday": "11/02", "price": "3,000"},
        {"countyname": "서울", "marketname": "D-유통", "yyyy": "2026", "regday": "11/02", "price": []}]}}
    rows = parse_period(raw)
    assert [(r.market, r.day) for r in rows] == [("B-유통", date(2026, 11, 2))]


def test_parse_day_forms() -> None:
    today = date(2026, 11, 2)
    assert parse_day("2026-11-02", today) == date(2026, 11, 2)
    assert parse_day("당일 (11/02)", today) == date(2026, 11, 2)
    # 오늘보다 뒤 달이면 작년 날짜다.
    assert parse_day("12/30", date(2027, 1, 2)) == date(2026, 12, 30)


@pytest.mark.parametrize("market, expected", [
    # KAMIS 코드표 "지역 및 시장 코드"의 대형유통업체 이름들
    ("B-유통", True), ("R-마트", True), ("B`-유통", True), ("M'-유통", True),
    # 도매/전통시장과 온라인몰
    ("경동", False), ("가락소매", False), ("온라인몰A", False), ("대형유통", False),
])
def test_is_large_retail(market: str, expected: bool) -> None:
    assert is_large_retail(market) is expected


def test_parse_category_success() -> None:
    raw = {"data": {"error_code": "000", "item": [{
        "item_name": "사과", "itemcode": "411", "kind_name": "홍로", "kindcode": "05",
        "rank": "상품", "unit": "10개", "day1": "당일 (11/02)", "dpr1": "32,000",
        "day3": "1주일전 (10/26)", "dpr3": "31,000", "day5": "1개월전 (10/02)", "dpr5": "-",
        "day6": "1년전 (11/02)", "dpr6": "28,500", "day7": "평년", "dpr7": "27,100"}]}}
    [row] = parse_category(raw, "400", date(2026, 11, 2))
    assert (row.category_code, row.item_name, row.kind_name) == ("400", "사과", "홍로")
    assert (row.item_code, row.kind_code, row.rank, row.unit) == ("411", "05", "상품", "10개")
    assert row.as_of == date(2026, 11, 2)
    assert (row.today, row.week_ago, row.month_ago, row.year_ago, row.normal) == (
        32000, 31000, None, 28500, 27100)


def test_parse_category_no_data_is_empty() -> None:
    assert parse_category({"data": ["001"]}, "400", date(2026, 11, 2)) == []
    assert parse_category({"data": {"error_code": "001"}}, "400", date(2026, 11, 2)) == []


def test_parse_category_error_raises() -> None:
    with pytest.raises(KamisError):
        parse_category({"data": ["900"]}, "400", date(2026, 11, 2))


def test_parse_period_skips_summary_and_empty_rows() -> None:
    raw = {"data": {"error_code": "000", "item": [
        {"countyname": "서울", "marketname": "B-유통", "yyyy": "2026", "regday": "11/02", "price": "3,250"},
        {"countyname": "서울", "marketname": "경동", "yyyy": "2026", "regday": "11/02", "price": "2,900"},
        {"countyname": "평균", "marketname": "", "yyyy": "2026", "regday": "11/02", "price": "3,100"},
        {"countyname": "부산", "marketname": "C-유통", "yyyy": "2026", "regday": "11/02", "price": "-"}]}}
    rows = parse_period(raw)
    assert [(r.market, r.price, r.large) for r in rows] == [("B-유통", 3250, True), ("경동", 2900, False)]
    assert rows[0].day == date(2026, 11, 2)
