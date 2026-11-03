"""이마트 계산과 `collector.emart` 명령 시험."""

import json
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, Iterator, List

import pytest

from collector import emart
from collector.champrice import ChampriceError, Month
from collector.emart import (KST, ShopRow, build_emart, build_products, is_emart, parse_rows,
                             representative, run)

NOW = datetime(2026, 11, 13, 19, 5, 12, tzinfo=KST)
M7, M8, M9 = Month("/m7", date(2026, 7, 24)), Month("/m8", date(2026, 8, 28)), Month("/m9", date(2026, 9, 25))


def raw(name: str, day: str, price: Any, store: str = "이마트강릉점") -> Dict[str, Any]:
    """API 응답의 줄 하나를 만든다(칸 이름은 응답과 같다)."""
    return {"상품명": name, "조사일": day, "판매가격": price, "판매업소": store,
            "제조사": "", "세일여부": "", "원플러스원": ""}


def shop(name: str, day: str, price: int, n: int) -> List[ShopRow]:
    """같은 날 같은 값을 받은 이마트 지점 n곳의 줄을 만든다."""
    return [ShopRow(name, date.fromisoformat(day), price, f"이마트{i}점") for i in range(n)]


def test_is_emart() -> None:
    assert is_emart("이마트강릉점")
    assert not is_emart("이마트24(본사)")
    assert not is_emart("롯데슈퍼전농점")
    assert not is_emart("신세계백화점본점")


def test_parse_rows_keeps_emart_and_skips_bad_rows() -> None:
    rows = parse_rows([
        raw("치킨너겟", "2026-09-11", 4970),
        raw("치킨너겟", "2026-09-25", "10980", "이마트검단점"),
        raw("치킨너겟", "2026-09-25", 9000, "이마트24(본사)"),
        raw("치킨너겟", "2026-09-25", 9000, "롯데슈퍼전농점"),
        raw("치킨너겟", "2026-09-25", ""),
        raw("치킨너겟", "2026-09-25", None),
        raw("치킨너겟", "2026-09-25", "abc"),
        raw("치킨너겟", "2026-09-25", 0),
        raw("치킨너겟", "2026/09/25", 4970),
        raw("", "2026-09-25", 4970),
    ])
    assert rows == [ShopRow("치킨너겟", date(2026, 9, 11), 4970, "이마트강릉점"),
                    ShopRow("치킨너겟", date(2026, 9, 25), 10980, "이마트검단점")]


def test_representative_most_common_then_higher() -> None:
    assert representative([10980] * 3 + [4970] * 2) == 10980
    assert representative([4970, 10980]) == 10980
    assert representative([3950, 3950, 4150]) == 3950


def test_products_usual_low_and_history() -> None:
    name = "오뚜기 크런치 치킨너겟(480g)"
    rows = shop(name, "2026-08-28", 10980, 1) + shop(name, "2026-09-11", 4970, 2) + shop(name, "2026-09-25", 10980, 3)
    assert build_products(rows) == [{
        "name": name, "usual": 10980, "low": {"price": 4970, "day": "2026-09-11", "pct": -55},
        "last_day": "2026-09-25", "stores": 3,
        "history": [["2026-09-25", 10980, 3], ["2026-09-11", 4970, 2], ["2026-08-28", 10980, 1]],
    }]


def test_products_no_sale_when_all_same() -> None:
    rows = shop("고향만두(900g)", "2026-09-11", 7980, 2) + shop("고향만두(900g)", "2026-09-25", 7980, 2)
    assert build_products(rows)[0]["low"] is None


def test_products_low_tie_takes_latest_day() -> None:
    rows = (shop("신라면(5개입)", "2026-07-24", 3950, 1) + shop("신라면(5개입)", "2026-08-28", 4150, 1)
            + shop("신라면(5개입)", "2026-09-11", 3950, 1))
    assert build_products(rows)[0]["low"]["day"] == "2026-09-11"


def test_build_emart_file() -> None:
    data = build_emart([raw("신라면(5개입)", "2026-09-11", 4150), raw("고향만두(900g)", "2026-09-25", 7980),
                        raw("신라면(5개입)", "2026-08-28", 4150)], [M8, M9], NOW)
    assert data["source"] == "참가격"
    assert data["months"] == ["2026-08-28", "2026-09-25"]
    assert data["as_of"] == "2026-09-25"
    assert data["generated_at"] == "2026-11-13T19:05:12+09:00"
    assert [e["name"] for e in data["items"]] == ["고향만두(900g)", "신라면(5개입)"]


def test_build_emart_raises_without_emart_rows() -> None:
    with pytest.raises(ChampriceError):
        build_emart([raw("신라면(5개입)", "2026-09-11", 4150, "롯데슈퍼전농점")], [M9], NOW)


class FakeSource:
    """정해 둔 달 목록과 달마다의 줄을 돌려주고, 줄을 부른 달을 모은다."""

    def __init__(self, months: List[Month], rows: Dict[str, List[Dict[str, Any]]],
                 fail: bool = False) -> None:
        self._months = months
        self._rows = rows
        self._fail = fail
        self.asked: List[Month] = []

    def months(self) -> List[Month]:
        return list(self._months)

    def rows(self, month: Month) -> Iterator[Dict[str, Any]]:
        self.asked.append(month)
        if self._fail:
            raise ChampriceError("참가격 요청 실패(OSError): 2026-09-25 1쪽")
        yield from self._rows.get(month.path, [])


def test_run_writes_latest_three_months(tmp_path: Path) -> None:
    m6 = Month("/m6", date(2026, 6, 26))
    src = FakeSource([m6, M7, M8, M9], {"/m9": [raw("신라면(5개입)", "2026-09-25", 4150)]})
    out = tmp_path / "emart.json"
    assert run(src, out, NOW) == "updated"
    assert src.asked == [M7, M8, M9]
    assert json.loads(out.read_text(encoding="utf-8"))["months"] == ["2026-07-24", "2026-08-28", "2026-09-25"]


def test_run_skips_when_newest_month_already_in_file(tmp_path: Path) -> None:
    out = tmp_path / "emart.json"
    out.write_text(json.dumps({"months": ["2026-07-24", "2026-08-28", "2026-09-25"], "items": []}), encoding="utf-8")
    before = out.read_text(encoding="utf-8")
    src = FakeSource([M7, M8, M9], {})
    assert run(src, out, NOW) == "skipped"
    assert src.asked == []
    assert out.read_text(encoding="utf-8") == before


@pytest.mark.parametrize("src", [
    FakeSource([M8, M9], {}, fail=True),
    FakeSource([M8, M9], {"/m9": [raw("신라면(5개입)", "2026-09-25", 4150, "롯데슈퍼전농점")]}),
])
def test_run_keeps_file_on_failure(tmp_path: Path, src: FakeSource) -> None:
    out = tmp_path / "emart.json"
    out.write_text(json.dumps({"months": ["2026-07-24"], "items": []}), encoding="utf-8")
    before = out.read_text(encoding="utf-8")
    with pytest.raises(ChampriceError):
        run(src, out, NOW)
    assert out.read_text(encoding="utf-8") == before


def test_main_without_key_skips(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                                capsys: pytest.CaptureFixture[str]) -> None:
    out = tmp_path / "emart.json"
    monkeypatch.delenv("DATA_GO_KR_KEY", raising=False)
    monkeypatch.setattr(emart, "EMART_PATH", out)
    assert emart.main() == 0
    assert "참가격 키 없음" in capsys.readouterr().out
    assert not out.exists()


def test_main_returns_1_on_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                                   capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setenv("DATA_GO_KR_KEY", "SECRETKEY")
    monkeypatch.setattr(emart, "EMART_PATH", tmp_path / "emart.json")
    monkeypatch.setattr(emart, "ChampriceSource", lambda key: FakeSource([M9], {}, fail=True))
    assert emart.main() == 1
    assert "참가격 수집 실패" in capsys.readouterr().err
