"""품종 목록 파일 시험."""

from datetime import date
from pathlib import Path

from collector.items import build_items, load_items, save_items
from collector.models import OverallRow


def make_row(item_code: str, kind_code: str, rank: str, unit: str, rank_code: str = "",
             category_code: str = "400", item_name: str = "사과", kind_name: str = "홍로") -> OverallRow:
    """시험용 전체 평균 줄을 만든다."""
    return OverallRow(
        category_code=category_code, item_code=item_code, item_name=item_name, kind_code=kind_code,
        kind_name=kind_name, rank=rank, unit=unit, as_of=date(2026, 11, 2),
        today=32000, week_ago=None, month_ago=None, year_ago=None, normal=None, rank_code=rank_code)


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


def test_build_items_picks_one_grade_per_kind() -> None:
    # 2026-11-03 실제 응답: 수산물에는 "상품"이 없고 등급 없음(-)이나 크기(大·中·小, 대멸·중멸·세멸)로 온다.
    fish = dict(category_code="600", item_name="생선", kind_name="국산")
    rows = [
        make_row("411", "05", "상품", "10개", "04"), make_row("411", "05", "중품", "10개", "05"),
        make_row("613", "03", "大", "1마리", "20", **fish), make_row("613", "03", "中", "1마리", "21", **fish),
        make_row("613", "03", "小", "1마리", "22", **fish),
        make_row("611", "05", "大", "1마리", "20", **fish),
        make_row("638", "00", "대멸", "100g", "27", **fish), make_row("638", "00", "중멸", "100g", "28", **fish),
        make_row("638", "00", "세멸", "100g", "29", **fish),
        make_row("644", "00", "-", "1kg", "30", **fish),
        make_row("4301", "21", "1등급", "100g", "01", category_code="500", item_name="소고기", kind_name="안심"),
    ]
    got = {i.id: i.rank_code for i in build_items(rows, rank_code="04")}
    assert got == {"411-05": "04", "613-03": "21", "611-05": "20", "638-00": "28", "644-00": "30"}


def test_build_items_drops_survey_unit_from_kind_name() -> None:
    rows = [make_row("613", "03", "中", "1마리", "21", category_code="600", item_name="갈치",
                     kind_name="국산(냉장)(1마리)"),
            make_row("251", "00", "상품", "3개", "04", category_code="200", item_name="가지", kind_name="가지(3개)"),
            make_row("411", "05", "상품", "10개", "04", kind_name="후지")]
    assert {i.id: i.kind_name for i in build_items(rows, rank_code="04")} == {
        "613-03": "국산(냉장)", "251-00": "가지", "411-05": "후지"}
