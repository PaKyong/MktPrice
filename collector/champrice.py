"""참가격(한국소비자원 생필품 가격 정보) 값을 받아 온다.

공공데이터포털은 참가격 파일을 달마다 하나씩 올리고, 같은 내용을 API로도 준다.
API 설명서(키 없이 읽힌다)에서 달 목록을 읽고, 한 달 치 줄(23만 줄쯤)을 쪽마다
나눠 받는다(설계 15절). 줄 해석과 계산은 `collector.emart`가 맡는다.
키는 주소 대신 머리말(Authorization)에 싣는다. 주소는 오류나 기록에 남기 쉬워서다.
"""

import json
import re
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import date
from typing import Any, Callable, Dict, Iterator, List, Optional, Protocol

from collector.kamis import RETRY_WAITS, TIMEOUT_SECONDS

DOCS_URL = "https://infuser.odcloud.kr/oas/docs?namespace=15083256/v1"
API_BASE = "https://api.odcloud.kr/api"
# 한 번에 받는 줄 수. 서버 상한은 아직 모른다(적게 주면 그만큼 쪽을 더 받는다).
PER_PAGE = 10000
# 설명서의 달 이름 끝 기준일. 요즘 것은 "_20260925", 옛것 하나는 "_09/24/2021" 모양이다.
_YMD = re.compile(r"_(\d{4})(\d{2})(\d{2})$")
_MDY = re.compile(r"_(\d{2})/(\d{2})/(\d{4})$")


class ChampriceError(Exception):
    """참가격을 받지 못했다(메시지에 키를 넣지 않는다)."""


@dataclass(frozen=True)
class Month:
    """설명서에 있는 달 하나.

    Attributes:
        path: API 경로(예: "/15083256/v1/uddi:…").
        as_of: 이름 끝의 기준일.
    """

    path: str
    as_of: date


class MonthSource(Protocol):
    """참가격 달 목록과 줄을 주는 쪽."""

    def months(self) -> List[Month]:
        """설명서의 달 목록을 기준일 오래된 것부터 돌려준다."""
        ...

    def rows(self, month: Month) -> Iterator[Dict[str, Any]]:
        """그 달의 줄을 하나씩 내준다."""
        ...


def _as_of(summary: str) -> Optional[date]:
    """달 이름 끝의 기준일을 읽는다. 날짜가 없으면 None."""
    m = _YMD.search(summary)
    if m:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    m = _MDY.search(summary)
    if m:
        return date(int(m.group(3)), int(m.group(1)), int(m.group(2)))
    return None


def parse_months(doc: Dict[str, Any]) -> List[Month]:
    """설명서 JSON에서 달 목록을 뽑는다.

    `paths`의 경로마다 `get.summary` 끝의 기준일을 읽고, 날짜가 없는 경로는 뺀 뒤
    기준일 순으로 세운다.

    Args:
        doc: API 설명서 JSON.

    Returns:
        달 목록. 기준일 오래된 것부터.
    """
    months: List[Month] = []
    for path, ops in doc.get("paths", {}).items():
        as_of = _as_of(str(ops.get("get", {}).get("summary", "")))
        if as_of is not None:
            months.append(Month(path, as_of))
    return sorted(months, key=lambda m: m.as_of)


class ChampriceSource:
    """실제 공공데이터포털 참가격 API를 부른다."""

    name: str = "참가격"

    def __init__(self, key: str,
                 opener: Callable[..., Any] = urllib.request.urlopen,
                 sleep: Callable[[float], None] = time.sleep) -> None:
        self._key = key
        self._opener = opener
        self._sleep = sleep

    def _get(self, url: str, what: str, with_key: bool) -> Dict[str, Any]:
        """요청을 보내고 JSON 응답을 돌려준다.

        받기나 JSON 읽기가 실패하면 2·4·8초를 기다리며 3번까지 다시 한다.

        Args:
            url: 요청 주소(키는 넣지 않는다).
            what: 오류 메시지에 쓸 요청 설명.
            with_key: 참이면 머리말에 키를 싣는다.

        Returns:
            JSON 응답.

        Raises:
            ChampriceError: 네 번 모두 실패한 경우. 원래 예외는 키를 담고 있을 수
                있어 붙이지 않는다.
        """
        headers = {"Authorization": f"Infuser {self._key}"} if with_key else {}
        reason = ""
        for attempt in range(len(RETRY_WAITS) + 1):
            try:
                req = urllib.request.Request(url, headers=headers)
                with self._opener(req, timeout=TIMEOUT_SECONDS) as response:
                    return json.loads(response.read().decode("utf-8"))
            except (OSError, ValueError) as err:
                # 원래 예외의 글은 키를 담을 수 있어 종류 이름만 남긴다.
                reason = type(err).__name__
                if attempt < len(RETRY_WAITS):
                    self._sleep(RETRY_WAITS[attempt])
        raise ChampriceError(f"참가격 요청 실패({reason}): {what}") from None

    def months(self) -> List[Month]:
        """API 설명서를 키 없이 받아 달 목록을 돌려준다.

        Returns:
            달 목록. 기준일 오래된 것부터.
        """
        return parse_months(self._get(DOCS_URL, "설명서", with_key=False))

    def rows(self, month: Month) -> Iterator[Dict[str, Any]]:
        """그 달의 줄을 1쪽부터 차례로 받아 하나씩 내준다.

        받은 줄 수가 응답의 `totalCount`에 이르거나 빈 쪽이 오면 멈춘다. 서버가
        `PER_PAGE`보다 적게 줘도 쪽을 더 받아 끝까지 받는다.

        Args:
            month: 받을 달.

        Yields:
            응답 `data`의 줄(칸 이름은 상품명, 조사일, 판매가격, 판매업소 등).

        Raises:
            ChampriceError: 한 쪽이라도 끝내 받지 못한 경우.
        """
        got = 0
        page = 1
        while True:
            query = urllib.parse.urlencode({"page": page, "perPage": PER_PAGE, "returnType": "JSON"})
            raw = self._get(f"{API_BASE}{month.path}?{query}", f"{month.as_of} {page}쪽", with_key=True)
            data = raw.get("data") or []
            yield from data
            got += len(data)
            if not data or got >= int(raw.get("totalCount") or 0):
                return
            page += 1
