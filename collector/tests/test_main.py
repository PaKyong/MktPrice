"""수집 순서 전체(run) 시험."""

import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

import pytest

from collector.__main__ import run
from collector.items import ITEMS_PATH, load_items
from collector.kamis import KamisDown, KamisSource, SampleSource
from collector.make_sample import write_sample
from collector.models import Item
from collector.output import CollectError, SampleGuardError
from collector.parse import KamisError

ALL_ITEMS: List[Item] = load_items(ITEMS_PATH)
# 농수산물 부류마다 한 품종. 축산물은 가게별 값이 없어 따로 시험한다.
ITEMS: List[Item] = [next(i for i in ALL_ITEMS if i.category_code == code)
                     for code in ("100", "200", "300", "400", "600")]
LIVESTOCK_ITEM: Item = next(i for i in ALL_ITEMS if i.category_code == "500")


def sample_source(tmp_path: Path, as_of: date) -> SampleSource:
    """임시 폴더에 샘플 응답을 만들고 그것을 읽는 받기 쪽을 돌려준다."""
    sample_dir = tmp_path / f"sample-{as_of}"
    write_sample(sample_dir, ITEMS, as_of)
    return SampleSource(sample_dir)


class FailingSource:
    """샘플을 읽되, 정한 부류나 품종에서 KamisError를 내는 받기 쪽."""

    def __init__(self, inner: SampleSource, fail_categories: Set[str] = frozenset(),
                 fail_items: Set[str] = frozenset()) -> None:
        self.inner = inner
        self.name = inner.name
        self.fail_categories = fail_categories
        self.fail_items = fail_items

    def category(self, category_code: str, day: date) -> Dict[str, Any]:
        if category_code in self.fail_categories:
            raise KamisError("시험용 실패")
        return self.inner.category(category_code, day)

    def period(self, item: Item, start: date, end: date) -> Dict[str, Any]:
        if item.id in self.fail_items:
            raise KamisError("시험용 실패")
        return self.inner.period(item, start, end)


def read(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_run_with_sample_then_skip(tmp_path: Path) -> None:
    out = tmp_path / "prices.json"
    src = sample_source(tmp_path, date(2026, 11, 2))
    assert run(src, ITEMS, out, date(2026, 11, 3)) == "updated"
    data = read(out)
    assert (data["as_of"], data["source"]) == ("2026-11-02", "샘플")
    assert data["basis"] == {"compare": "전국 대형유통 평균", "season": "KAMIS 전체 평균"}
    assert data["threshold_pct"] == 15
    assert [e["id"] for e in data["items"]] == [i.id for i in ITEMS]
    assert all(e["as_of"] == "2026-11-02" and e["stores"] >= 20 for e in data["items"])
    before = out.read_bytes()
    assert run(src, ITEMS, out, date(2026, 11, 3)) == "skipped"
    assert out.read_bytes() == before


def test_run_keeps_old_value_when_one_item_fails(tmp_path: Path) -> None:
    out = tmp_path / "prices.json"
    run(sample_source(tmp_path, date(2026, 11, 2)), ITEMS, out, date(2026, 11, 2))
    old = {e["id"]: e for e in read(out)["items"]}
    failing = ITEMS[1].id
    src = FailingSource(sample_source(tmp_path, date(2026, 11, 3)), fail_items={failing})
    assert run(src, ITEMS, out, date(2026, 11, 3)) == "updated"
    new = {e["id"]: e for e in read(out)["items"]}
    assert read(out)["as_of"] == "2026-11-03"
    assert new[failing] == old[failing]
    assert all(new[i.id]["as_of"] == "2026-11-03" for i in ITEMS if i.id != failing)


def test_run_failed_category_keeps_its_items(tmp_path: Path) -> None:
    out = tmp_path / "prices.json"
    run(sample_source(tmp_path, date(2026, 11, 2)), ITEMS, out, date(2026, 11, 2))
    src = FailingSource(sample_source(tmp_path, date(2026, 11, 3)), fail_categories={"200"})
    run(src, ITEMS, out, date(2026, 11, 3))
    for e in read(out)["items"]:
        expected = "2026-11-02" if e["category"] == "채소류" else "2026-11-03"
        assert e["as_of"] == expected


def test_run_total_failure_keeps_file(tmp_path: Path) -> None:
    out = tmp_path / "prices.json"
    run(sample_source(tmp_path, date(2026, 11, 2)), ITEMS, out, date(2026, 11, 2))
    before = out.read_bytes()
    every = {"100", "200", "300", "400", "500", "600"}
    with pytest.raises(CollectError, match="부류 100: 시험용 실패"):
        run(FailingSource(sample_source(tmp_path, date(2026, 11, 3)), fail_categories=every),
            ITEMS, out, date(2026, 11, 3))
    with pytest.raises(CollectError):
        run(FailingSource(sample_source(tmp_path, date(2026, 11, 3)), fail_items={i.id for i in ITEMS}),
            ITEMS, out, date(2026, 11, 3))
    assert out.read_bytes() == before


def test_run_stops_early_and_keeps_file_when_kamis_does_not_answer(tmp_path: Path) -> None:
    out = tmp_path / "prices.json"
    out.write_text('{"as_of": "2026-11-01", "source": "KAMIS", "items": []}', encoding="utf-8")
    before = out.read_bytes()
    tries: List[str] = []

    def dead(url: str, timeout: float) -> Any:
        tries.append(url)
        raise OSError("연결 안 됨")

    src = KamisSource("k", "me", opener=dead, sleep=lambda seconds: None)
    with pytest.raises(KamisDown):
        run(src, ITEMS, out, date(2026, 11, 3))
    # 부류 6개를 다 불러 보지 않고, 요청 3번(4번씩 시도)에서 멈춘다.
    assert len(tries) == 12
    assert out.read_bytes() == before


def test_main_returns_1_when_kamis_does_not_answer(monkeypatch: pytest.MonkeyPatch,
                                                   capsys: pytest.CaptureFixture[str]) -> None:
    import collector.__main__ as entry

    def down(*args: Any, **kwargs: Any) -> str:
        raise KamisDown("KAMIS가 요청 3번에 연달아 응답하지 않아 수집을 멈춥니다.")

    monkeypatch.setattr(entry, "run", down)
    monkeypatch.delenv("KAMIS_CERT_KEY", raising=False)
    assert entry.main([]) == 1
    assert "수집 실패: KAMIS가 요청 3번에" in capsys.readouterr().err


def test_run_sample_does_not_overwrite_real_data(tmp_path: Path) -> None:
    out = tmp_path / "prices.json"
    out.write_text('{"as_of": "2026-11-01", "source": "KAMIS", "items": []}', encoding="utf-8")
    before = out.read_bytes()
    with pytest.raises(SampleGuardError):
        run(sample_source(tmp_path, date(2026, 11, 2)), ITEMS, out, date(2026, 11, 3))
    assert out.read_bytes() == before


def test_first_real_run_does_not_keep_sample_values(tmp_path: Path) -> None:
    out = tmp_path / "prices.json"
    run(sample_source(tmp_path, date(2026, 11, 2)), ITEMS, out, date(2026, 11, 2))
    real = FailingSource(sample_source(tmp_path, date(2026, 11, 3)), fail_items={ITEMS[1].id})
    real.name = "KAMIS"
    assert run(real, ITEMS, out, date(2026, 11, 3)) == "updated"
    data = read(out)
    assert data["source"] == "KAMIS"
    assert ITEMS[1].id not in {e["id"] for e in data["items"]}


class HolidaySource(FailingSource):
    """샘플을 읽되, 한 달 전 같은 날(10-02)이 공휴일이었던 것처럼 흉내 낸다.

    기준일 응답은 모든 줄의 1개월 전 칸이 비고, 10-02는 "데이터 없음", 그 전날 10-01에는 당일 값이
    1,000원으로 온다.
    """

    def __init__(self, inner: SampleSource) -> None:
        super().__init__(inner)
        self.days: List[date] = []

    def category(self, category_code: str, day: date) -> Dict[str, Any]:
        self.days.append(day)
        raw = json.loads(json.dumps(self.inner.category(category_code, day)))
        if day == date(2026, 10, 2) or day < date(2026, 10, 1):
            return {"data": ["001"]}
        for row in raw["data"]["item"] if isinstance(raw["data"], dict) else []:
            if day == date(2026, 10, 1):
                row["day1"], row["dpr1"] = "당일 (10/01)", "1,000"
            else:
                row["dpr5"] = "-"
        return raw


def test_run_fills_month_ago_from_nearest_survey_day(tmp_path: Path) -> None:
    out = tmp_path / "prices.json"
    src = HolidaySource(sample_source(tmp_path, date(2026, 11, 2)))
    assert run(src, ITEMS, out, date(2026, 11, 2)) == "updated"
    today = {(r["itemcode"], r["kindcode"]): int(r["dpr1"].replace(",", ""))
             for code in ("100", "200", "300", "400", "600")
             for r in src.inner.category(code, date(2026, 11, 2))["data"]["item"] if r["rank"] == "상품"}
    for e in read(out)["items"]:
        item = next(i for i in ITEMS if i.id == e["id"])
        expected = round((today[(item.item_code, item.kind_code)] - 1000) / 1000 * 100, 1)
        assert e["change"]["month"] == expected
    # 부류마다 10-02(공휴일)와 10-01만 더 부르고, 1년 전은 값이 있어 부르지 않는다.
    past = [d for d in src.days if d < date(2026, 11, 1)]
    assert sorted(set(past)) == [date(2026, 10, 1), date(2026, 10, 2)]
    assert len(past) == 2 * 5


class MondaySource(FailingSource):
    """샘플을 읽되, 월요일(11-09)에 수산물 줄의 평년 칸만 비어서 오는 것을 흉내 낸다.

    주말(11-08, 11-07)은 "데이터 없음"이고, 금요일(11-06)에는 모든 줄의 평년 칸에 `friday_normal`이 온다.
    """

    def __init__(self, inner: SampleSource, friday_normal: str) -> None:
        super().__init__(inner)
        self.friday_normal = friday_normal
        self.calls: List[Tuple[str, date]] = []

    def category(self, category_code: str, day: date) -> Dict[str, Any]:
        self.calls.append((category_code, day))
        if day in (date(2026, 11, 8), date(2026, 11, 7)):
            return {"data": ["001"]}
        raw = json.loads(json.dumps(self.inner.category(category_code, day)))
        for row in raw["data"]["item"] if isinstance(raw["data"], dict) else []:
            if day == date(2026, 11, 6):
                row["day1"], row["dpr7"] = "당일 (11/06)", self.friday_normal
            elif category_code == "600":
                row["dpr7"] = "-"
        return raw


def test_run_fills_empty_normal_from_previous_survey_day(tmp_path: Path) -> None:
    out = tmp_path / "prices.json"
    src = MondaySource(sample_source(tmp_path, date(2026, 11, 9)), friday_normal="2,000")
    assert run(src, ITEMS, out, date(2026, 11, 9)) == "updated"
    fish = next(i for i in ITEMS if i.category_code == "600")
    row = next(r for r in src.inner.category("600", date(2026, 11, 9))["data"]["item"] if r["rank"] == "상품")
    today = int(row["dpr1"].replace(",", ""))
    entries = {e["id"]: e for e in read(out)["items"]}
    assert entries[fish.id]["change"]["normal"] == round((today - 2000) / 2000 * 100, 1)
    assert entries[fish.id]["signal"] is not None
    # 평년 값이 온 다른 부류는 받은 값 그대로다.
    run(src.inner, ITEMS, tmp_path / "plain.json", date(2026, 11, 9))
    plain = {e["id"]: e for e in read(tmp_path / "plain.json")["items"]}
    assert all(entries[i.id]["change"] == plain[i.id]["change"] for i in ITEMS if i is not fish)
    # 수산물만, 주말을 건너 금요일까지 더 부른다.
    near = [(code, day) for code, day in src.calls if date(2026, 11, 2) <= day < date(2026, 11, 9)]
    assert near == [("600", date(2026, 11, 8)), ("600", date(2026, 11, 7)), ("600", date(2026, 11, 6))]


def test_run_leaves_normal_empty_when_previous_survey_day_has_none_either(tmp_path: Path) -> None:
    out = tmp_path / "prices.json"
    src = MondaySource(sample_source(tmp_path, date(2026, 11, 9)), friday_normal="-")
    assert run(src, ITEMS, out, date(2026, 11, 9)) == "updated"
    fish = next(e for e in read(out)["items"] if e["category"] == "수산물")
    assert fish["change"]["normal"] is None and fish["signal"] is None


class RenamedSource(FailingSource):
    """가게 이름이나 전체 평균 줄을 바꿔, 해석 가정이 틀린 실제 응답을 흉내 낸다."""

    def __init__(self, inner: SampleSource, market_prefix: str = "", kind_suffix: str = "",
                 unit: str = "") -> None:
        super().__init__(inner)
        self.market_prefix = market_prefix
        self.kind_suffix = kind_suffix
        self.unit = unit

    def category(self, category_code: str, day: date) -> Dict[str, Any]:
        raw = json.loads(json.dumps(self.inner.category(category_code, day)))
        if isinstance(raw.get("data"), dict):
            for row in raw["data"]["item"]:
                row["kindcode"] += self.kind_suffix
                if self.unit:
                    row["unit"] = self.unit
        return raw

    def period(self, item: Item, start: date, end: date) -> Dict[str, Any]:
        raw = json.loads(json.dumps(self.inner.period(item, start, end)))
        for row in raw["data"]["item"]:
            row["marketname"] = self.market_prefix + row["marketname"]
        return raw


def test_run_fails_when_no_large_retail_store_matches(tmp_path: Path) -> None:
    out = tmp_path / "prices.json"
    src = RenamedSource(sample_source(tmp_path, date(2026, 11, 2)), market_prefix="가게 ")
    with pytest.raises(CollectError, match="대형유통"):
        run(src, ITEMS, out, date(2026, 11, 3))
    assert not out.exists()


def test_run_fails_when_no_item_matches_overall(tmp_path: Path) -> None:
    out = tmp_path / "prices.json"
    src = RenamedSource(sample_source(tmp_path, date(2026, 11, 2)), kind_suffix="x")
    with pytest.raises(CollectError, match="전체 평균"):
        run(src, ITEMS, out, date(2026, 11, 3))
    assert not out.exists()


def with_livestock(tmp_path: Path, out: Path) -> Tuple[List[Item], SampleSource]:
    """농수산물 다섯과 축산물 한 줄로 11-02 파일을 만들어 두고, 품종 목록과 11-03 샘플 받기 쪽을 돌려준다."""
    items = ITEMS + [LIVESTOCK_ITEM]
    write_sample(tmp_path / "day1", items, date(2026, 11, 2))
    assert run(SampleSource(tmp_path / "day1"), items, out, date(2026, 11, 2)) == "updated"
    write_sample(tmp_path / "day2", items, date(2026, 11, 3))
    return items, SampleSource(tmp_path / "day2")


def test_run_fails_when_only_livestock_entries_are_made(tmp_path: Path) -> None:
    # 가게 이름 규칙이 바뀌면 농수산물 항목은 하나도 안 만들어지는데, 축산물은 가게 값 없이도 만들어진다.
    out = tmp_path / "prices.json"
    items, day2 = with_livestock(tmp_path, out)
    before = out.read_bytes()
    with pytest.raises(CollectError, match="대형유통"):
        run(RenamedSource(day2, market_prefix="가게 "), items, out, date(2026, 11, 3))
    assert out.read_bytes() == before


def test_run_fails_when_every_farm_item_fails_though_livestock_is_fine(tmp_path: Path) -> None:
    out = tmp_path / "prices.json"
    items, day2 = with_livestock(tmp_path, out)
    before = out.read_bytes()
    with pytest.raises(CollectError, match="받지 못했습니다"):
        run(FailingSource(day2, fail_items={i.id for i in ITEMS}), items, out, date(2026, 11, 3))
    assert out.read_bytes() == before


def test_run_prints_item_counts_of_old_and_new_file(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    out = tmp_path / "prices.json"
    run(sample_source(tmp_path, date(2026, 11, 2)), ITEMS, out, date(2026, 11, 2))
    assert f"앞 파일 0개 → 새 파일 {len(ITEMS)}개(옛 값으로 남긴 품종 0개)" in capsys.readouterr().out
    src = FailingSource(sample_source(tmp_path, date(2026, 11, 3)), fail_items={ITEMS[1].id})
    run(src, ITEMS, out, date(2026, 11, 3))
    assert f"앞 파일 {len(ITEMS)}개 → 새 파일 {len(ITEMS)}개(옛 값으로 남긴 품종 1개)" in capsys.readouterr().out


def test_run_treats_unit_mismatch_as_failure_and_reports_it(tmp_path: Path,
                                                            capsys: pytest.CaptureFixture[str]) -> None:
    out = tmp_path / "prices.json"
    run(sample_source(tmp_path, date(2026, 11, 2)), ITEMS, out, date(2026, 11, 2))
    src = RenamedSource(sample_source(tmp_path, date(2026, 11, 3)), unit="3kg")
    with pytest.raises(CollectError):
        run(src, ITEMS, out, date(2026, 11, 3))
    assert "단위가 다른 품종" in capsys.readouterr().out


def test_run_prints_summary(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    run(sample_source(tmp_path, date(2026, 11, 2)), ITEMS, tmp_path / "prices.json", date(2026, 11, 3))
    printed = capsys.readouterr().out
    assert f"새 항목 {len(ITEMS)}개" in printed and f"전체 평균과 맞은 품종 {len(ITEMS)}개" in printed


class NewKindSource(FailingSource):
    """샘플 과일류에 품종 목록에 없는 줄을 더해 준다.

    감귤 노지는 상품 줄과 중품 줄이, 딸기 설향은 중품 줄만 온다. 품종 목록은 상품 줄로 만들므로
    목록을 다시 만들면 감귤 노지만 새로 들어온다.
    """

    def category(self, category_code: str, day: date) -> Dict[str, Any]:
        raw = json.loads(json.dumps(self.inner.category(category_code, day)))
        if category_code == "400":
            top = next(row for row in raw["data"]["item"] if row["rank"] == "상품")
            tangerine = {**top, "itemcode": "915", "kindcode": "01", "item_name": "감귤", "kind_name": "노지"}
            raw["data"]["item"] += [
                tangerine,
                {**tangerine, "rank": "중품", "rank_code": "05"},
                {**top, "itemcode": "926", "kindcode": "02", "item_name": "딸기", "kind_name": "설향",
                 "rank": "중품", "rank_code": "05"},
            ]
        return raw


def test_run_reports_kinds_missing_from_item_list(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    out = tmp_path / "prices.json"
    src = NewKindSource(sample_source(tmp_path, date(2026, 11, 2)))
    assert run(src, ITEMS, out, date(2026, 11, 2)) == "updated"
    printed = capsys.readouterr().out
    assert "품종 목록에 없는 품종 1개: 감귤 노지." in printed
    assert "딸기" not in printed
    # 기록만 남기고 화면용 파일에는 넣지 않는다.
    assert [e["id"] for e in read(out)["items"]] == [i.id for i in ITEMS]


def test_run_reports_nothing_when_every_kind_is_listed(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    run(sample_source(tmp_path, date(2026, 11, 2)), ITEMS, tmp_path / "prices.json", date(2026, 11, 2))
    assert "품종 목록에 없는" not in capsys.readouterr().out


def test_run_reports_livestock_rows_missing_from_item_list_by_grade(tmp_path: Path,
                                                                    capsys: pytest.CaptureFixture[str]) -> None:
    # 축산물은 등급마다 한 품종이라, 등급만 다른 줄도 목록에 없으면 남긴다.
    livestock = [i for i in ALL_ITEMS if i.category_code == "500"]
    write_sample(tmp_path / "sample", ITEMS + livestock, date(2026, 11, 2))
    run(SampleSource(tmp_path / "sample"), ITEMS + [LIVESTOCK_ITEM], tmp_path / "prices.json", date(2026, 11, 2))
    assert f"품종 목록에 없는 품종 {len(livestock) - 1}개: " in capsys.readouterr().out


def test_run_without_sample_files_says_how_to_make_them(tmp_path: Path) -> None:
    with pytest.raises(CollectError, match="make_sample") as err:
        run(SampleSource(tmp_path / "없음"), ITEMS, tmp_path / "prices.json", date(2026, 11, 3))
    # 실패 원인을 찾을 수 있게 날마다 받은 응답 모양을 남긴다.
    assert "2026-11-03 100:001 200:001" in str(err.value)
    assert "2026-10-28 100:001" in str(err.value)


class LivestockOnlyTodaySource(FailingSource):
    """정한 날 뒤에는 농수산물 줄의 값이 비고 축산물에만 값이 있는 전체 평균을 준다(2026-11-03 오전 실제 응답)."""

    def __init__(self, inner: SampleSource, last_day: date) -> None:
        super().__init__(inner)
        self.last_day = last_day

    def category(self, category_code: str, day: date) -> Dict[str, Any]:
        raw = json.loads(json.dumps(self.inner.category(category_code, day)))
        if day <= self.last_day:
            return raw
        if category_code == "500":
            return {"data": {"error_code": "000", "item": [{
                "itemcode": "4301", "kindcode": "21", "item_name": "소고기", "kind_name": "안심", "rank": "1등급",
                "unit": "100g", "day1": f"당일 ({day.month:02d}/{day.day:02d})", "dpr1": "14,000"}]}}
        if isinstance(raw.get("data"), dict):
            for row in raw["data"]["item"]:
                row["dpr1"] = "-"
        return raw


def test_run_steps_back_when_only_unused_rows_have_values_today(tmp_path: Path) -> None:
    out = tmp_path / "prices.json"
    src = LivestockOnlyTodaySource(sample_source(tmp_path, date(2026, 11, 2)), last_day=date(2026, 11, 2))
    assert run(src, ITEMS, out, date(2026, 11, 3)) == "updated"
    assert read(out)["as_of"] == "2026-11-02"


class RankCodeSource(FailingSource):
    """전체 평균 줄의 등급 번호만 바꾼다(품종 목록의 등급과 다른 줄을 흉내 낸다)."""

    def category(self, category_code: str, day: date) -> Dict[str, Any]:
        raw = json.loads(json.dumps(self.inner.category(category_code, day)))
        if isinstance(raw.get("data"), dict):
            for row in raw["data"]["item"]:
                row["rank_code"] = "99"
        return raw


def test_run_matches_overall_rows_by_grade_code(tmp_path: Path) -> None:
    # 수산물처럼 등급 이름이 "상품"이 아닌 품종도 있어, 품종 목록의 등급 번호로 전체 평균 줄을 고른다.
    with pytest.raises(CollectError, match="값이 없어"):
        run(RankCodeSource(sample_source(tmp_path, date(2026, 11, 2))), ITEMS, tmp_path / "prices.json",
            date(2026, 11, 3))


def test_run_force_rewrites_even_when_day_is_same(tmp_path: Path) -> None:
    # 품종 목록을 다시 만든 날은 기준일이 같아도 새 목록으로 다시 써야 한다.
    out = tmp_path / "prices.json"
    src = sample_source(tmp_path, date(2026, 11, 2))
    run(src, ITEMS, out, date(2026, 11, 3))
    assert run(src, ITEMS[:2], out, date(2026, 11, 3), force=True) == "updated"
    assert [e["id"] for e in read(out)["items"]] == [i.id for i in ITEMS[:2]]


def test_main_reads_force_flag(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    import collector.__main__ as entry

    calls: List[bool] = []
    monkeypatch.setattr(entry, "run", lambda source, items, out, today, force=False: calls.append(force) or "updated")
    monkeypatch.delenv("KAMIS_CERT_KEY", raising=False)
    assert entry.main(["--force"]) == 0
    assert entry.main([]) == 0
    assert calls == [True, False]


class LivestockDaySource(FailingSource):
    """샘플을 읽되, 축산물 부류는 부른 날짜마다 그날 날짜와 값(일 × 100원)으로 바꿔 주는 받기 쪽.

    10-20은 받기에 실패하고, 닭 절단육은 실제처럼 늘 0원이다. 축산물에 기간 API를 부르면 시험이 실패한다.
    """

    def __init__(self, inner: SampleSource) -> None:
        """샘플 받기 쪽을 감싸고, 축산물 부류를 부른 날짜를 모은다."""
        super().__init__(inner)
        self.livestock_days: List[date] = []

    def category(self, category_code: str, day: date) -> Dict[str, Any]:
        """축산물이면 그날 날짜와 값으로 바꾼 샘플 응답을 준다."""
        raw = self.inner.category(category_code, day)
        if category_code != "500":
            return raw
        self.livestock_days.append(day)
        if day == date(2026, 10, 20):
            raise KamisError("시험용 실패")
        raw = json.loads(json.dumps(raw))
        for row in raw["data"]["item"]:
            row["day1"] = f"당일 ({day:%m/%d})"
            row["dpr1"] = "0" if row["kind_name"] == "절단육" else f"{day.day * 100:,}"
        return raw

    def period(self, item: Item, start: date, end: date) -> Dict[str, Any]:
        """농수산물만 가게별 값을 부른다(축산물을 부르면 실패)."""
        assert item.category_code != "500"
        return self.inner.period(item, start, end)


def test_run_livestock_trend_comes_from_daily_category_calls(tmp_path: Path, capsys: Any) -> None:
    out = tmp_path / "prices.json"
    livestock = [i for i in ALL_ITEMS if i.category_code == "500"]
    items = ITEMS + livestock
    write_sample(tmp_path / "sample", items, date(2026, 11, 2))
    src = LivestockDaySource(SampleSource(tmp_path / "sample"))
    assert run(src, items, out, date(2026, 11, 2)) == "updated"
    entries = {e["id"]: e for e in read(out)["items"] if e["category"] == "축산물"}
    assert len(entries) == len(livestock) - 1
    e = entries[LIVESTOCK_ITEM.id]
    assert (e["as_of"], e["price"]) == ("2026-11-02", 200)
    assert e["stores"] is None and e["range"] is None and e["unit_range"] is None
    # 기준일부터 거꾸로 31일 가운데 받기에 실패한 10-20만 빠진다. 큰 가격과 그래프 끝 값은 같은 날 값이다.
    window = [date(2026, 10, 3) + timedelta(days=k) for k in range(31)]
    assert e["trend"] == [[d.isoformat(), d.day * 100] for d in window if d != date(2026, 10, 20)]
    assert e["change"]["normal"] is not None
    # 기준일 것은 이미 받은 값을 쓰고, 나머지 30일만 더 부른다.
    assert sorted(d for d in src.livestock_days if d < date(2026, 11, 2)) == window[:-1]
    log = capsys.readouterr().out
    assert "축산물 새 항목 28개, 값이 없어 빠진 품종 1개(닭고기 절단육)" in log


class MorningSource(FailingSource):
    """11-03 아침처럼 축산물만 오늘 값이 있고 농수산물은 아직 없는 받기 쪽(11-02까지는 샘플 그대로)."""

    def category(self, category_code: str, day: date) -> Dict[str, Any]:
        raw = self.inner.category(category_code, day)
        if day < date(2026, 11, 3):
            return raw
        if category_code != "500":
            return {"data": ["001"]}
        raw = json.loads(json.dumps(raw))
        for row in raw["data"]["item"]:
            row["day1"] = "당일 (11/03)"
        return raw


def test_run_date_is_not_pushed_ahead_by_livestock_alone(tmp_path: Path) -> None:
    out = tmp_path / "prices.json"
    items = ITEMS + [LIVESTOCK_ITEM]
    write_sample(tmp_path / "sample", items, date(2026, 11, 2))
    assert run(MorningSource(SampleSource(tmp_path / "sample")), items, out, date(2026, 11, 3)) == "updated"
    data = read(out)
    assert data["as_of"] == "2026-11-02"
    assert all(e["change"]["normal"] is not None for e in data["items"])
