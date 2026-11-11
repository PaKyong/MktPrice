"""KAMIS 받기(실제·샘플) 시험."""

import http.client
import io
from contextlib import contextmanager
from datetime import date
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Union

import pytest

from collector.kamis import (LOOKBACK_DAYS, KamisDown, KamisSource, SampleSource, describe_response,
                             latest_overall, make_source, months_back, past_overall)
from collector.models import Item, OverallRow
from collector.parse import KamisError

APPLE = Item(
    id="411-05", category_code="400", category_name="과일류", item_code="411", item_name="사과",
    kind_code="05", kind_name="홍로", rank_code="04", unit="10개", measure="count",
    amount=10.0, unit_label="개")
DAY = date(2026, 11, 2)


class FakeOpener:
    """응답 목록을 차례로 돌려주거나 예외를 던지고, 받은 주소를 모으는 시험용 도우미."""

    def __init__(self, responses: List[Union[bytes, Exception]]) -> None:
        self.responses = list(responses)
        self.urls: List[str] = []

    @contextmanager
    def __call__(self, url: str, timeout: Optional[float] = None) -> Iterator[io.BytesIO]:
        self.urls.append(url)
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        yield io.BytesIO(response)


def no_sleep(seconds: float) -> None:
    """기다리지 않는다."""


def test_kamis_retries_then_succeeds() -> None:
    opener = FakeOpener([OSError(), OSError(), OSError(), b'{"data": {"error_code": "000", "item": []}}'])
    waits: List[float] = []
    src = KamisSource("SECRETKEY", "me", opener=opener, sleep=waits.append)
    assert src.category("400", DAY)["data"]["error_code"] == "000"
    assert waits == [2, 4, 8]
    assert "p_item_category_code=400" in opener.urls[0]
    assert "p_product_cls_code=01" in opener.urls[0]
    assert "action=dailyPriceByCategoryList" in opener.urls[0]
    # KAMIS는 날짜가 없으면 "잘못된 요청 변수"(200)로 거절한다(2026-11-03 첫 실제 실행).
    assert "p_regday=2026-11-02" in opener.urls[0]


def test_kamis_gives_up_after_four_tries_without_leaking_key() -> None:
    opener = FakeOpener([OSError("https://x?p_cert_key=SECRETKEY")] * 4)
    src = KamisSource("SECRETKEY", "me", opener=opener, sleep=no_sleep)
    with pytest.raises(KamisError) as err:
        src.category("400", DAY)
    assert len(opener.urls) == 4
    assert "SECRETKEY" not in str(err.value)
    assert "OSError" in str(err.value)
    assert err.value.__cause__ is None and err.value.__suppress_context__


def test_kamis_retries_when_answer_is_cut_off_midway() -> None:
    # 받는 도중 연결이 끊기면 OSError가 아니라 http.client의 오류가 난다.
    opener = FakeOpener([http.client.IncompleteRead(b'{"data"'), b'{"data": ["001"]}'])
    src = KamisSource("SECRETKEY", "me", opener=opener, sleep=no_sleep)
    assert src.category("400", DAY) == {"data": ["001"]}
    assert len(opener.urls) == 2


def test_kamis_stops_when_three_requests_in_a_row_get_no_answer() -> None:
    opener = FakeOpener([OSError("https://x?p_cert_key=SECRETKEY")] * 12)
    src = KamisSource("SECRETKEY", "me", opener=opener, sleep=no_sleep)
    for code in ("100", "200"):
        with pytest.raises(KamisError):
            src.category(code, DAY)
    with pytest.raises(KamisDown) as err:
        src.category("300", DAY)
    assert len(opener.urls) == 12
    assert "SECRETKEY" not in str(err.value)
    # 받기 실패 하나를 넘기고 계속하는 곳들(except KamisError)이 삼키면 안 된다.
    assert not isinstance(err.value, KamisError)


def test_kamis_counts_failures_from_zero_again_after_an_answer() -> None:
    opener = FakeOpener([OSError()] * 8 + [b'{"data": ["001"]}'] + [OSError()] * 8)
    src = KamisSource("k", "me", opener=opener, sleep=no_sleep)
    for code in ("100", "200"):
        with pytest.raises(KamisError):
            src.category(code, DAY)
    assert src.category("300", DAY) == {"data": ["001"]}
    for code in ("400", "500"):
        with pytest.raises(KamisError):
            src.category(code, DAY)


def test_kamis_does_not_retry_no_data() -> None:
    opener = FakeOpener([b'{"data": ["001"]}'])
    assert KamisSource("k", "me", opener=opener, sleep=no_sleep).category("400", DAY) == {"data": ["001"]}
    assert len(opener.urls) == 1


def test_period_request_params() -> None:
    opener = FakeOpener([b'{"data": ["001"]}'])
    KamisSource("k", "me", opener=opener, sleep=no_sleep).period(APPLE, date(2026, 10, 3), date(2026, 11, 2))
    for part in ["action=periodRetailProductList", "p_startday=2026-10-03", "p_endday=2026-11-02",
                 "p_itemcategorycode=400", "p_itemcode=411", "p_kindcode=05", "p_productrankcode=04",
                 "p_returntype=json", "p_convert_kg_yn=N"]:
        assert part in opener.urls[0]


def test_make_source_picks_by_env(tmp_path: Path) -> None:
    assert make_source({}, tmp_path).name == "샘플"
    assert make_source({"KAMIS_CERT_KEY": "k"}, tmp_path).name == "샘플"
    assert make_source({"KAMIS_CERT_KEY": "k", "KAMIS_CERT_ID": ""}, tmp_path).name == "샘플"
    assert make_source({"KAMIS_CERT_KEY": "k", "KAMIS_CERT_ID": "i"}, tmp_path).name == "KAMIS"


def test_sample_source_reads_files_and_missing_is_no_data(tmp_path: Path) -> None:
    (tmp_path / "category_400.json").write_text('{"data": ["001"]}', encoding="utf-8")
    (tmp_path / "period").mkdir()
    (tmp_path / "period" / "411-05.json").write_text('{"data": {"error_code": "000", "item": []}}',
                                                      encoding="utf-8")
    src = SampleSource(tmp_path)
    assert src.category("400", DAY) == {"data": ["001"]}
    assert src.category("100", DAY) == {"data": ["001"]}
    assert src.period(APPLE, date(2026, 10, 3), date(2026, 11, 2))["data"]["error_code"] == "000"
    other = Item(**{**APPLE.__dict__, "id": "999-01"})
    assert src.period(other, date(2026, 10, 3), date(2026, 11, 2)) == {"data": ["001"]}


def ANY_ROW(row: OverallRow) -> bool:
    """모든 줄을 쓰는 줄로 본다."""
    return True


def _row(dpr1: str, rank: str = "상품") -> Dict[str, Any]:
    return {"itemcode": "211", "kindcode": "01", "item_name": "배추", "kind_name": "봄", "rank": rank,
            "unit": "1포기", "day1": "당일 (11/02)", "dpr1": dpr1, "dpr3": "-", "dpr5": "-", "dpr6": "-",
            "dpr7": "-"}


class DaySource:
    """정한 날 이후에는 값이 없는 전체 평균을 주고, 부른 날짜를 모으는 시험용 받기 쪽."""

    name = "시험"

    def __init__(self, last_day: Optional[date], blank: bool = False, fail: bool = False,
                 other_rank_value: bool = False) -> None:
        self.last_day = last_day
        self.blank = blank
        self.fail = fail
        self.other_rank_value = other_rank_value
        self.days: List[date] = []

    def category(self, category_code: str, day: date) -> Dict[str, Any]:
        self.days.append(day)
        if self.fail:
            raise KamisError("KAMIS 오류 코드 200")
        if self.last_day is None or day > self.last_day:
            if self.other_rank_value:
                # 2026-11-03 오전 실제 응답: 상품 줄은 값이 비었는데 다른 줄(축산물 등)에만 값이 있다.
                return {"data": {"error_code": "000", "item": [_row("-"), _row("9,000", rank="1등급")]}}
            return {"data": {"error_code": "000", "item": [_row("-")]}} if self.blank else {"data": ["001"]}
        return {"data": {"error_code": "000", "item": [_row("3,000")]}}


def test_latest_overall_steps_back_to_latest_day_with_values() -> None:
    src = DaySource(last_day=date(2026, 11, 2))
    rows, failed, _ = latest_overall(src, date(2026, 11, 4), ANY_ROW)
    assert failed == {}
    assert [r.today for r in rows] == [3000] * 6
    assert sorted(set(src.days), reverse=True) == [date(2026, 11, 4), date(2026, 11, 3), date(2026, 11, 2)]


def test_latest_overall_treats_blank_values_as_no_data() -> None:
    src = DaySource(last_day=date(2026, 11, 2), blank=True)
    rows, _, _ = latest_overall(src, date(2026, 11, 3), ANY_ROW)
    assert {r.today for r in rows} == {3000}
    assert min(src.days) == date(2026, 11, 2)


def test_latest_overall_gives_up_after_seven_days() -> None:
    src = DaySource(last_day=None)
    rows, failed, tried = latest_overall(src, date(2026, 11, 9), ANY_ROW)
    assert rows == [] and failed == {}
    assert len(set(src.days)) == LOOKBACK_DAYS == 7
    assert min(src.days) == date(2026, 11, 3)
    assert len(tried) == 7
    assert tried[0] == "2026-11-09 100:001 200:001 300:001 400:001 500:001 600:001"


def test_latest_overall_stops_when_every_category_fails() -> None:
    src = DaySource(last_day=date(2026, 11, 2), fail=True)
    rows, failed, tried = latest_overall(src, date(2026, 11, 4), ANY_ROW)
    assert rows == []
    assert tried == ["2026-11-04 100:실패 200:실패 300:실패 400:실패 500:실패 600:실패"]
    assert failed == {code: "KAMIS 오류 코드 200" for code in ("100", "200", "300", "400", "500", "600")}
    assert set(src.days) == {date(2026, 11, 4)}


def test_describe_response_names_codes_without_echoed_key() -> None:
    echoed = [{"p_cert_key": "SECRETKEY", "p_cert_id": "me"}]
    assert describe_response({"condition": echoed, "data": ["001"]}) == "001"
    blank_and_priced = {"condition": echoed, "data": {"error_code": "000", "item": [_row("3,000"), _row("-")]}}
    assert describe_response(blank_and_priced) == "000 2줄 값1"
    assert describe_response({"data": []}) == "빈 목록"
    assert describe_response({"condition": echoed}) == "모양 모름(NoneType)"
    for raw in ({"condition": echoed, "data": [{"p_cert_key": "SECRETKEY"}]},):
        assert "SECRETKEY" not in describe_response(raw)


def test_latest_overall_ignores_values_only_in_rows_it_does_not_use() -> None:
    src = DaySource(last_day=date(2026, 11, 2), other_rank_value=True)
    rows, failed, tried = latest_overall(src, date(2026, 11, 3), lambda row: row.rank == "상품")
    assert failed == {}
    assert {r.today for r in rows if r.rank == "상품"} == {3000}
    assert min(src.days) == date(2026, 11, 2)
    assert len(tried) == 2


def test_months_back_keeps_day_or_takes_month_end() -> None:
    assert months_back(date(2026, 11, 3), 1) == date(2026, 10, 3)
    assert months_back(date(2026, 1, 15), 1) == date(2025, 12, 15)
    assert months_back(date(2026, 3, 31), 1) == date(2026, 2, 28)
    assert months_back(date(2028, 2, 29), 12) == date(2027, 2, 28)
    assert months_back(date(2026, 11, 2), 12) == date(2025, 11, 2)


def test_past_overall_steps_back_to_nearest_survey_day() -> None:
    src = DaySource(last_day=date(2026, 10, 2))
    rows = past_overall(src, "200", date(2026, 10, 4), date(2026, 11, 4))
    assert [r.today for r in rows] == [3000]
    assert src.days == [date(2026, 10, 4), date(2026, 10, 3), date(2026, 10, 2)]


def test_past_overall_gives_up_quietly() -> None:
    assert past_overall(DaySource(last_day=date(2026, 10, 2), fail=True), "200", date(2026, 10, 4),
                        date(2026, 11, 4)) == []
    src = DaySource(last_day=None)
    assert past_overall(src, "200", date(2026, 10, 4), date(2026, 11, 4)) == []
    assert len(src.days) == LOOKBACK_DAYS
