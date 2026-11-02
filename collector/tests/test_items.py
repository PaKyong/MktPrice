"""품종 목록 파일 시험."""

from datetime import date
from pathlib import Path

from collector.items import build_items, load_items, save_items
from collector.models import OverallRow


def make_row(item_code: str, kind_code: str, rank: str, unit: str) -> OverallRow:
    """시험용 전체 평균 줄을 만든다."""
    return OverallRow(
        category_code="400", item_code=item_code, item_name="사과", kind_code=kind_code,
        kind_name="홍로", rank=rank, unit=unit, as_of=date(2026, 11, 2),
        today=32000, week_ago=None, month_ago=None, year_ago=None, normal=None)


def test_build_items_keeps_top_grade_and_round_trips(tmp_path: Path) -> None:
    rows = [make_row("411", "05", "상품", "10개"), make_row("411", "05", "중품", "10개")]
    items = build_items(rows, rank_code="04")
    assert [i.id for i in items] == ["411-05"]
    item = items[0]
    assert (item.category_code, item.category_name, item.item_name, item.kind_name) == (
        "400", "과일류", "사과", "홍로")
    assert (item.rank_code, item.unit) == ("04", "10개")
    assert (item.measure, item.amount, item.unit_label) == ("count", 10, "개")
    save_items(tmp_path / "items.json", items)
    assert load_items(tmp_path / "items.json") == items
