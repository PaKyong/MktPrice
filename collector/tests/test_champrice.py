"""참가격 받기 시험."""

import http.client
import io
import json
import urllib.request
from contextlib import contextmanager
from datetime import date
from typing import Any, Dict, Iterator, List, Optional, Union

import pytest

from collector.champrice import (API_BASE, DOCS_URL, ChampriceError, ChampriceSource, Month,
                                 parse_months)

MONTH = Month("/15083256/v1/uddi:4f684682-d8a2-446e-be30-adfffdaae05a", date(2026, 9, 25))


class FakeOpener:
    """응답 목록을 차례로 돌려주거나 예외를 던지고, 받은 요청의 주소와 머리말을 모으는 시험용 도우미."""

    def __init__(self, responses: List[Union[bytes, Exception]]) -> None:
        self.responses = list(responses)
        self.urls: List[str] = []
        self.auths: List[Optional[str]] = []

    @contextmanager
    def __call__(self, req: urllib.request.Request, timeout: Optional[float] = None) -> Iterator[io.BytesIO]:
        self.urls.append(req.full_url)
        self.auths.append(req.get_header("Authorization"))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        yield io.BytesIO(response)


def no_sleep(seconds: float) -> None:
    """기다리지 않는다."""


def page(total: int, rows: List[Dict[str, Any]]) -> bytes:
    """API 한 쪽 응답을 만든다."""
    return json.dumps({"page": 1, "perPage": 10000, "totalCount": total, "currentCount": len(rows),
                       "matchCount": total, "data": rows}, ensure_ascii=False).encode("utf-8")


def docs(summaries: Dict[str, str]) -> Dict[str, Any]:
    """설명서 JSON을 만든다(경로 → 이름)."""
    return {"paths": {path: {"get": {"summary": summary}} for path, summary in summaries.items()}}


def row(name: str) -> Dict[str, Any]:
    """API 응답의 줄 하나를 만든다."""
    return {"상품명": name, "조사일": "2026-09-25", "판매가격": 1000, "판매업소": "이마트강릉점",
            "제조사": "", "세일여부": "", "원플러스원": ""}


DOC = docs({
    "/p1": "한국소비자원_생필품 가격 정보_20260925",
    "/p2": "한국소비자원 생필품 및 서비스 가격 정보_09/24/2021",
    "/p3": "한국소비자원_생필품 가격 정보_20260828",
    "/p4": "한국소비자원_생필품 가격 정보",
})


def test_parse_months_reads_both_date_shapes() -> None:
    assert parse_months(DOC) == [Month("/p2", date(2021, 9, 24)), Month("/p3", date(2026, 8, 28)),
                                 Month("/p1", date(2026, 9, 25))]


def test_months_reads_docs_without_key() -> None:
    opener = FakeOpener([json.dumps(DOC, ensure_ascii=False).encode("utf-8")])
    src = ChampriceSource("SECRETKEY", opener=opener, sleep=no_sleep)
    assert src.months() == parse_months(DOC)
    assert opener.urls == [DOCS_URL]
    assert opener.auths == [None]


def test_rows_pages_until_total_count() -> None:
    a, b, c = row("가"), row("나"), row("다")
    opener = FakeOpener([page(3, [a, b]), page(3, [c])])
    src = ChampriceSource("SECRETKEY", opener=opener, sleep=no_sleep)
    assert list(src.rows(MONTH)) == [a, b, c]
    assert len(opener.urls) == 2
    for n, url in enumerate(opener.urls, start=1):
        assert url.startswith(API_BASE + MONTH.path + "?")
        assert f"page={n}" in url
        assert "perPage=10000" in url
        assert "returnType=JSON" in url
        assert "SECRETKEY" not in url
    assert opener.auths == ["Infuser SECRETKEY", "Infuser SECRETKEY"]


def test_rows_pages_until_total_even_if_server_gives_fewer() -> None:
    # 서버가 한 번에 주는 줄 수에 상한이 있어 요청(10000)보다 적게 줘도 끝까지 받는다.
    names = ["가", "나", "다", "라", "마"]
    opener = FakeOpener([page(5, [row(n) for n in names[:2]]), page(5, [row(n) for n in names[2:4]]),
                         page(5, [row(names[4])])])
    src = ChampriceSource("SECRETKEY", opener=opener, sleep=no_sleep)
    assert [r["상품명"] for r in src.rows(MONTH)] == names
    assert len(opener.urls) == 3


def test_rows_fails_when_pages_run_out_before_total() -> None:
    # 줄을 덜 받은 채로 끝나면 정가인 날이 빠져 행사 값이 평소 값으로 보이므로, 조용히 멈추지 않고 실패한다.
    opener = FakeOpener([page(10, [row("가"), row("나")]), page(10, [])])
    src = ChampriceSource("SECRETKEY", opener=opener, sleep=no_sleep)
    with pytest.raises(ChampriceError, match="10줄 가운데 2줄"):
        list(src.rows(MONTH))
    assert len(opener.urls) == 2


def test_rows_fails_without_total_count() -> None:
    body = json.dumps({"page": 1, "perPage": 10000, "data": [row("가")]}, ensure_ascii=False).encode("utf-8")
    src = ChampriceSource("SECRETKEY", opener=FakeOpener([body]), sleep=no_sleep)
    with pytest.raises(ChampriceError, match="totalCount"):
        list(src.rows(MONTH))


def test_retries_then_gives_up_without_leaking_key() -> None:
    opener = FakeOpener([OSError("https://x?serviceKey=SECRETKEY")] * 4)
    waits: List[float] = []
    src = ChampriceSource("SECRETKEY", opener=opener, sleep=waits.append)
    with pytest.raises(ChampriceError) as err:
        list(src.rows(MONTH))
    assert "SECRETKEY" not in str(err.value)
    assert err.value.__cause__ is None
    assert waits == [2, 4, 8]


def test_retries_when_answer_is_cut_off_midway() -> None:
    opener = FakeOpener([http.client.IncompleteRead(b'{"paths"'), json.dumps(DOC).encode("utf-8")])
    assert ChampriceSource("k", opener=opener, sleep=no_sleep).months()
    assert len(opener.urls) == 2


def test_retries_then_succeeds() -> None:
    opener = FakeOpener([OSError(), OSError(), OSError(), json.dumps(DOC).encode("utf-8")])
    waits: List[float] = []
    src = ChampriceSource("SECRETKEY", opener=opener, sleep=waits.append)
    assert src.months() == parse_months(DOC)
    assert waits == [2, 4, 8]
