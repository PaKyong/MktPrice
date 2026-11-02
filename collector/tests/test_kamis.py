"""KAMIS 받기(실제·샘플) 시험."""

import io
from contextlib import contextmanager
from datetime import date
from pathlib import Path
from typing import Iterator, List, Optional, Union

import pytest

from collector.kamis import KamisSource, SampleSource, make_source
from collector.models import Item
from collector.parse import KamisError

APPLE = Item(
    id="411-05", category_code="400", category_name="과일류", item_code="411", item_name="사과",
    kind_code="05", kind_name="홍로", rank_code="04", unit="10개", measure="count",
    amount=10.0, unit_label="개")


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
    assert src.category("400")["data"]["error_code"] == "000"
    assert waits == [2, 4, 8]
    assert "p_item_category_code=400" in opener.urls[0]
    assert "p_product_cls_code=01" in opener.urls[0]
    assert "action=dailyPriceByCategoryList" in opener.urls[0]


def test_kamis_gives_up_after_four_tries_without_leaking_key() -> None:
    opener = FakeOpener([OSError("https://x?p_cert_key=SECRETKEY")] * 4)
    src = KamisSource("SECRETKEY", "me", opener=opener, sleep=no_sleep)
    with pytest.raises(KamisError) as err:
        src.category("400")
    assert len(opener.urls) == 4
    assert "SECRETKEY" not in str(err.value)
    assert err.value.__cause__ is None and err.value.__suppress_context__


def test_kamis_does_not_retry_no_data() -> None:
    opener = FakeOpener([b'{"data": ["001"]}'])
    assert KamisSource("k", "me", opener=opener, sleep=no_sleep).category("400") == {"data": ["001"]}
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
    assert src.category("400") == {"data": ["001"]}
    assert src.category("100") == {"data": ["001"]}
    assert src.period(APPLE, date(2026, 10, 3), date(2026, 11, 2))["data"]["error_code"] == "000"
    other = Item(**{**APPLE.__dict__, "id": "999-01"})
    assert src.period(other, date(2026, 10, 3), date(2026, 11, 2)) == {"data": ["001"]}
