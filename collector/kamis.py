"""KAMIS 응답을 받아 온다.

실제 KAMIS를 부르는 `KamisSource`와 저장소 안의 샘플 응답 파일을 읽는
`SampleSource`가 같은 모양으로 응답(JSON 사전)을 돌려준다. 응답 해석은
`collector.parse`가 맡는다. 키는 요청 주소에 실려 가므로 주소를 출력하거나
오류 메시지에 넣지 않는다.
"""

import json
import time
import urllib.parse
import urllib.request
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Protocol, Tuple

from collector.models import CATEGORIES, Item, OverallRow
from collector.parse import KamisError, parse_category, parse_price

# 문서에는 http://로 나오지만 키가 주소에 실려 가므로 https://를 쓴다(키를 받은 뒤 확인).
BASE_URL = "https://www.kamis.or.kr/service/price/xml.do"
RETRY_WAITS = (2, 4, 8)
TIMEOUT_SECONDS = 30
NO_DATA_RESPONSE: Dict[str, Any] = {"data": ["001"]}
SAMPLE_DIR = Path(__file__).parent / "sample"
# 오늘 값이 없으면(아직 안 올라왔거나 공휴일) 하루씩 거꾸로 이만큼까지 찾는다.
LOOKBACK_DAYS = 7


class Source(Protocol):
    """KAMIS 응답을 주는 쪽(실제 또는 샘플)."""

    name: str

    def category(self, category_code: str, day: date) -> Dict[str, Any]:
        """부류 하나의 그날 전체 평균 응답을 돌려준다."""
        ...

    def period(self, item: Item, start: date, end: date) -> Dict[str, Any]:
        """품종 하나의 기간 가게별 값 응답을 돌려준다."""
        ...


class KamisSource:
    """실제 KAMIS Open API를 부른다."""

    name: str = "KAMIS"

    def __init__(self, cert_key: str, cert_id: str,
                 opener: Callable[..., Any] = urllib.request.urlopen,
                 sleep: Callable[[float], None] = time.sleep) -> None:
        self._cert_key = cert_key
        self._cert_id = cert_id
        self._opener = opener
        self._sleep = sleep

    def _get(self, params: Dict[str, str], what: str) -> Dict[str, Any]:
        """요청을 보내고 JSON 응답을 돌려준다.

        받기나 JSON 읽기가 실패하면 2·4·8초를 기다리며 3번까지 다시 한다.
        응답을 읽었으면 오류 코드와 상관없이 그대로 돌려준다("데이터 없음"을
        다시 시도하지 않으려고).

        Args:
            params: 인증 정보를 뺀 요청 변수.
            what: 오류 메시지에 쓸 요청 설명(주소나 키는 넣지 않는다).

        Returns:
            KAMIS JSON 응답.

        Raises:
            KamisError: 네 번 모두 실패한 경우. 원래 예외는 주소를 담고 있을 수
                있어 붙이지 않는다.
        """
        query = {"p_cert_key": self._cert_key, "p_cert_id": self._cert_id,
                 "p_returntype": "json", **params}
        url = f"{BASE_URL}?{urllib.parse.urlencode(query)}"
        reason = ""
        for attempt in range(len(RETRY_WAITS) + 1):
            try:
                with self._opener(url, timeout=TIMEOUT_SECONDS) as response:
                    return json.loads(response.read().decode("utf-8"))
            except (OSError, ValueError) as err:
                # 원래 예외의 글은 주소(키)를 담을 수 있어 종류 이름만 남긴다.
                reason = type(err).__name__
                if attempt < len(RETRY_WAITS):
                    self._sleep(RETRY_WAITS[attempt])
        raise KamisError(f"KAMIS 요청 실패({reason}): {what}") from None

    def category(self, category_code: str, day: date) -> Dict[str, Any]:
        """부류 하나의 그날 전체 평균(소매) 응답을 받는다.

        문서에는 날짜(p_regday)를 빼면 최근 조사일을 쓴다고 되어 있지만, 실제로는
        날짜가 없으면 "잘못된 요청 변수"(200)로 거절하므로 늘 날짜를 넣는다.

        Args:
            category_code: KAMIS 부류 코드.
            day: 조사일.

        Returns:
            KAMIS JSON 응답.
        """
        return self._get({
            "action": "dailyPriceByCategoryList",
            "p_product_cls_code": "01",
            "p_item_category_code": category_code,
            "p_regday": day.isoformat(),
            "p_convert_kg_yn": "N",
        }, f"전체 평균 {category_code} {day.isoformat()}")

    def period(self, item: Item, start: date, end: date) -> Dict[str, Any]:
        """품종 하나의 기간 가게별 값 응답을 받는다.

        Args:
            item: 품종.
            start: 시작 날짜.
            end: 끝 날짜.

        Returns:
            KAMIS JSON 응답.
        """
        return self._get({
            "action": "periodRetailProductList",
            "p_startday": start.isoformat(),
            "p_endday": end.isoformat(),
            "p_itemcategorycode": item.category_code,
            "p_itemcode": item.item_code,
            "p_kindcode": item.kind_code,
            "p_productrankcode": item.rank_code,
            "p_convert_kg_yn": "N",
        }, f"가게별 값 {item.id}")


class SampleSource:
    """저장소 안의 샘플 응답 파일을 읽는다."""

    name: str = "샘플"

    def __init__(self, sample_dir: Path) -> None:
        self._dir = sample_dir

    def _read(self, path: Path) -> Dict[str, Any]:
        if not path.exists():
            return dict(NO_DATA_RESPONSE)
        return json.loads(path.read_text(encoding="utf-8"))

    def category(self, category_code: str, day: date) -> Dict[str, Any]:
        """`category_<부류코드>.json`을 읽는다. 없으면 "데이터 없음" 응답.

        샘플은 미리 만든 날의 응답을 그대로 돌려주므로 day는 쓰지 않는다.

        Args:
            category_code: KAMIS 부류 코드.
            day: 조사일(쓰지 않음).

        Returns:
            샘플 JSON 응답.
        """
        return self._read(self._dir / f"category_{category_code}.json")

    def period(self, item: Item, start: date, end: date) -> Dict[str, Any]:
        """`period/<품종id>.json`을 읽는다. 없으면 "데이터 없음" 응답.

        샘플은 미리 만든 기간을 그대로 돌려주므로 start, end는 쓰지 않는다.

        Args:
            item: 품종.
            start: 시작 날짜(쓰지 않음).
            end: 끝 날짜(쓰지 않음).

        Returns:
            샘플 JSON 응답.
        """
        return self._read(self._dir / "period" / f"{item.id}.json")


def describe_response(raw: Any) -> str:
    """응답의 모양을 키 없이 짧게 적는다(실패 원인을 찾을 때 로그에 남긴다).

    KAMIS 응답의 condition 칸은 요청 변수(키 포함)를 그대로 되돌려 주므로 쓰지 않고,
    오류 코드와 줄 수만 적는다. 예: "001", "000 53줄 값43", "빈 목록".

    Args:
        raw: KAMIS JSON 응답.

    Returns:
        짧은 설명.
    """
    data = raw.get("data") if isinstance(raw, dict) else None
    if isinstance(data, list):
        if not data:
            return "빈 목록"
        first = data[0]
        return str(first)[:10] if isinstance(first, (str, int)) else f"모양 모름({type(first).__name__})"
    if isinstance(data, dict):
        items = data.get("item") or []
        items = [items] if isinstance(items, dict) else items
        priced = sum(isinstance(i, dict) and parse_price(i.get("dpr1")) is not None for i in items)
        return f"{str(data.get('error_code', '?'))[:10]} {len(items)}줄 값{priced}"
    return f"모양 모름({type(data).__name__})"


def latest_overall(source: Source, today: date,
                   useful: Callable[[OverallRow], bool]) -> Tuple[List[OverallRow], Dict[str, str], List[str]]:
    """전체 평균 값이 있는 가장 최근 날의 줄을 받는다.

    오늘부터 하루씩 거꾸로 최대 `LOOKBACK_DAYS`일 동안, 날마다 부류 6개를 부르고
    응답을 해석한다. 쓰는 줄(useful) 가운데 당일 값이 있는 줄이 있으면 그날에서
    멈춘다(값이 "-"뿐인 줄은 값이 없는 것으로 본다). 쓰지 않는 줄은 보지 않는다.
    농수산물 값이 아직 안 올라온 오전에도 축산물 줄에는 값이 있기 때문이다(2026-11-03
    실제 응답). 모든 부류가 실패한 날은 더 거슬러 가지 않는다.
    날마다 부류별 응답 모양을 한 줄씩 남긴다(예: "2026-11-03 100:001 200:000 53줄 값43 ...").

    Args:
        source: KAMIS 또는 샘플 받기 쪽.
        today: 오늘 날짜(한국 시각). 날짜 글자의 연도를 정하는 데도 쓴다.
        useful: 값이 있는지 볼 줄을 고르는 함수(예: 상품 등급이고 품종 목록에 있는 줄).

    Returns:
        (그날의 모든 등급 줄, 실패한 부류 코드 → 이유, 날마다의 응답 모양).
        찾지 못하면 줄 목록이 비어 있다.
    """
    failed: Dict[str, str] = {}
    tried: List[str] = []
    for back in range(LOOKBACK_DAYS):
        day = today - timedelta(days=back)
        rows: List[OverallRow] = []
        failed = {}
        notes: List[str] = []
        for code in CATEGORIES:
            note = "실패"
            try:
                raw = source.category(code, day)
                note = describe_response(raw)
                rows.extend(parse_category(raw, code, today))
            except KamisError as err:
                failed[code] = str(err)
            notes.append(f"{code}:{note}")
        tried.append(f"{day.isoformat()} " + " ".join(notes))
        if len(failed) == len(CATEGORIES):
            return [], failed, tried
        if any(useful(row) and row.today is not None for row in rows):
            return rows, failed, tried
    return [], failed, tried


def make_source(env: Mapping[str, str], sample_dir: Path) -> Source:
    """환경변수를 보고 실제 KAMIS 또는 샘플을 고른다.

    Args:
        env: 환경변수(보통 os.environ).
        sample_dir: 샘플 응답 폴더.

    Returns:
        `KAMIS_CERT_KEY`와 `KAMIS_CERT_ID`가 둘 다 비어 있지 않으면
        KamisSource, 아니면 SampleSource.
    """
    key = env.get("KAMIS_CERT_KEY", "")
    cert_id = env.get("KAMIS_CERT_ID", "")
    if key and cert_id:
        return KamisSource(key, cert_id)
    return SampleSource(sample_dir)
