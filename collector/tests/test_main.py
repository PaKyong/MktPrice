"""수집 순서 전체(run) 시험."""

import json
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Set

import pytest

from collector.__main__ import run
from collector.items import ITEMS_PATH, load_items
from collector.kamis import SampleSource
from collector.make_sample import write_sample
from collector.models import Item
from collector.output import CollectError, SampleGuardError
from collector.parse import KamisError

ALL_ITEMS: List[Item] = load_items(ITEMS_PATH)
# 부류마다 한 품종(축산물 500은 품종이 없다).
ITEMS: List[Item] = [next(i for i in ALL_ITEMS if i.category_code == code)
                     for code in ("100", "200", "300", "400", "600")]


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
