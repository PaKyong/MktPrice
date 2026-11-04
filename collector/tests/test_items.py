"""품종 목록 파일 시험."""

from datetime import date
from pathlib import Path

from collector.items import build_items, load_items, merge_items, save_items
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
    # 축산물은 2026-11-04부터 등급마다 넣는다(id 끝에 등급 번호).
    assert got == {"411-05": "04", "613-03": "21", "611-05": "20", "638-00": "28", "644-00": "30",
                   "4301-21-01": "01"}


def test_build_items_drops_survey_unit_from_kind_name() -> None:
    rows = [make_row("613", "03", "中", "1마리", "21", category_code="600", item_name="갈치",
                     kind_name="국산(냉장)(1마리)"),
            make_row("251", "00", "상품", "3개", "04", category_code="200", item_name="가지", kind_name="가지(3개)"),
            make_row("411", "05", "상품", "10개", "04", kind_name="후지")]
    assert {i.id: i.kind_name for i in build_items(rows, rank_code="04")} == {
        "613-03": "국산(냉장)", "251-00": "가지", "411-05": "후지"}


def test_merge_items_updates_seen_kinds_and_keeps_out_of_season_ones() -> None:
    # 전체 평균은 그날 조사한 품종만 준다. 철이 지난 품종을 목록에서 지우면 철이 돌아와도 수집되지 않는다.
    old = build_items([make_row("411", "01", "상품", "10개", "04", kind_name="홍옥"),
                       make_row("251", "00", "상품", "10개", "04", category_code="200", item_name="가지",
                                kind_name="가지")], rank_code="04")
    new = build_items([make_row("251", "00", "상품", "3개", "04", category_code="200", item_name="가지",
                                kind_name="가지(3개)"),
                       make_row("411", "08", "상품", "10개", "04", kind_name="시나노골드")], rank_code="04")
    merged = merge_items(old, new)
    assert [i.id for i in merged] == ["251-00", "411-01", "411-08"]
    assert {i.id: i.unit for i in merged} == {"251-00": "3개", "411-01": "10개", "411-08": "10개"}


def test_build_items_livestock_keeps_every_grade_with_everyday_names() -> None:
    def meat(item_code: str, item_name: str, kind_code: str, kind_name: str, rank: str, rank_code: str,
             unit: str = "100g") -> OverallRow:
        return make_row(item_code, kind_code, rank, unit, rank_code=rank_code, category_code="500",
                        item_name=item_name, kind_name=kind_name)

    rows = [meat("4301", "소", "22", "등심", "1++등급", "01"), meat("4301", "소", "22", "등심", "1+등급", "02"),
            meat("4304", "돼지", "27", "삼겹살", "삼겹살", "00"),
            meat("4401", "수입 소고기", "31", "갈비", "미국산", "81"),
            meat("9901", "닭", "99", "육계(kg)", "육계(kg)", "00", unit="1kg"),
            meat("9903", "계란", "23", "XL30구", "일반란", "71", unit="30구"),
            meat("9908", "우유", "01", "흰우유", "흰우유", "00", unit="1L")]
    items = {i.id: i for i in build_items(rows, rank_code="04")}
    assert {k: (i.category_name, i.item_name, i.kind_name, i.rank_code) for k, i in items.items()} == {
        "4301-22-01": ("축산물", "한우", "등심 1++등급", "01"),
        "4301-22-02": ("축산물", "한우", "등심 1+등급", "02"),
        "4304-27-00": ("축산물", "돼지고기", "삼겹살", "00"),
        "4401-31-81": ("축산물", "수입 소고기", "갈비 미국산", "81"),
        "9901-99-00": ("축산물", "닭고기", "육계", "00"),
        "9903-23-71": ("축산물", "계란", "XL30구", "71"),
        "9908-01-00": ("축산물", "우유", "흰우유", "00"),
    }
    assert (items["9903-23-71"].measure, items["9903-23-71"].unit_label) == ("count", "개")
    assert (items["9908-01-00"].measure, items["9908-01-00"].unit_label) == ("volume", "100ml")
    # 다시 만들어도(이름이 이미 바뀐 줄로) 같은 품종이 나온다.
    again = [meat(i.item_code, i.item_name, i.kind_code, i.kind_name, "상품", i.rank_code, i.unit)
             for i in items.values()]
    assert build_items(again, rank_code="04") == list(items.values())
