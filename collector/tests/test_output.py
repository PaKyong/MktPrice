"""화면용 파일 쓰기 시험."""

import json
from datetime import date
from pathlib import Path

import pytest

from collector.output import (
    SampleGuardError,
    carry_over,
    check_sample_guard,
    load_prices,
    should_skip,
    write_prices,
)


def test_should_skip_needs_same_date_and_source() -> None:
    existing = {"as_of": "2026-11-02", "source": "샘플"}
    assert should_skip(existing, date(2026, 11, 2), "샘플") is True
    # 같은 날 샘플 파일이 있어도 처음 받은 실제 데이터는 건너뛰지 않는다(Review Focus 4).
    assert should_skip(existing, date(2026, 11, 2), "KAMIS") is False
    assert should_skip(existing, date(2026, 11, 3), "샘플") is False
    assert should_skip(None, date(2026, 11, 2), "샘플") is False


def test_sample_guard() -> None:
    with pytest.raises(SampleGuardError):
        check_sample_guard({"source": "KAMIS"}, "샘플")
    check_sample_guard({"source": "샘플"}, "샘플")
    check_sample_guard({"source": "KAMIS"}, "KAMIS")
    check_sample_guard(None, "샘플")


def test_carry_over_keeps_old_entry_for_failed() -> None:
    existing = {"items": [{"id": "a", "price": 1}, {"id": "b", "price": 2}]}
    out = carry_over([{"id": "a", "price": 9}], {"b", "c"}, existing)
    assert out == [{"id": "a", "price": 9}, {"id": "b", "price": 2}]
    assert carry_over([{"id": "z"}, {"id": "a"}], {"b"}, None) == [{"id": "a"}, {"id": "z"}]


def test_write_prices_replaces_whole_file(tmp_path: Path) -> None:
    p = tmp_path / "data" / "prices.json"
    write_prices(p, {"as_of": "2026-11-02", "source": "샘플", "items": []})
    assert load_prices(p) == {"as_of": "2026-11-02", "source": "샘플", "items": []}
    assert "샘플" in p.read_text(encoding="utf-8")       # ensure_ascii=False
    assert not p.read_bytes().startswith(b"\xef\xbb\xbf")  # BOM 없음
    write_prices(p, {"as_of": "2026-11-03", "items": []})
    assert json.loads(p.read_text(encoding="utf-8"))["as_of"] == "2026-11-03"
    assert list(p.parent.iterdir()) == [p]                 # 임시 파일이 남지 않음


def test_load_prices_missing_is_none(tmp_path: Path) -> None:
    assert load_prices(tmp_path / "none.json") is None
