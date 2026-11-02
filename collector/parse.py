"""KAMIS 응답을 해석한다.

응답 모양은 KAMIS 문서를 보고 세운 가정이다. 성공은
`{"data": {"error_code": "000", "item": [...]}}`, 데이터 없음은
`{"data": ["001"]}` 또는 `error_code` "001"로 본다. 대형유통은 KAMIS 코드표의
가게 이름 모양("A-유통", "R-마트")으로 가린다. 셋 다 키를 받은 뒤 실제
응답으로 확인한다.
"""

import re
from datetime import date
from typing import Any, Dict, List, Optional

from collector.models import OverallRow, StoreRow

NO_DATA = "001"
SUCCESS = "000"
LARGE_RETAIL_NAME = re.compile(r"[A-Z][`']?-(?:유통|마트)")


class KamisError(Exception):
    """KAMIS가 성공도 "데이터 없음"도 아닌 응답을 돌려줬거나, 받기에 실패했다."""


def parse_price(text: Optional[str]) -> Optional[int]:
    """KAMIS 가격 글자를 원 단위 정수로 바꾼다.

    쉼표를 지운 뒤 정수로 읽는다. "-", 빈 글자, None, 0은 값이 없는 것으로 본다.

    Args:
        text: KAMIS 응답의 가격 글자(예: "2,400").

    Returns:
        가격. 값이 없으면 None.
    """
    if text is None:
        return None
    cleaned = text.replace(",", "").strip()
    if not cleaned.isdigit():
        return None
    value = int(cleaned)
    return value if value > 0 else None


def parse_day(text: str, today: date) -> date:
    """KAMIS 날짜 글자를 날짜로 바꾼다.

    "2026-11-02" 모양을 먼저 찾고, 없으면 "11/02" 모양을 찾아 today의 연도를
    붙인다. 그 날짜가 today보다 뒤면 작년 날짜로 본다.

    Args:
        text: 날짜 글자(예: "당일 (11/02)", "2026-11-02").
        today: 연도를 정할 때 기준이 되는 오늘 날짜.

    Returns:
        해석한 날짜.

    Raises:
        ValueError: 날짜 모양을 찾지 못한 경우.
    """
    full = re.search(r"(\d{4})-(\d{2})-(\d{2})", text)
    if full:
        return date(int(full.group(1)), int(full.group(2)), int(full.group(3)))
    short = re.search(r"(\d{1,2})/(\d{1,2})", text)
    if not short:
        raise ValueError(f"날짜를 읽을 수 없음: {text!r}")
    day = date(today.year, int(short.group(1)), int(short.group(2)))
    if day > today:
        day = date(today.year - 1, day.month, day.day)
    return day


def is_large_retail(market: str) -> bool:
    """가게 이름이 대형유통 가게인지 가린다.

    KAMIS 코드표 "지역 및 시장 코드"에서 대형유통업체 가게는 "A-유통",
    "B`-유통", "M'-유통", "R-마트"처럼 영문자 하나(뒤에 ` 또는 ')와 "-유통" 또는
    "-마트"로 이름이 붙는다. 전통시장은 "경동"처럼 시장 이름, 온라인몰은
    "온라인몰A"처럼 붙는다.

    Args:
        market: KAMIS 응답의 가게 이름.

    Returns:
        대형유통 가게 이름 모양이면 True.
    """
    return LARGE_RETAIL_NAME.fullmatch(market.strip()) is not None


def _items_or_empty(raw: Dict[str, Any]) -> List[Dict[str, Any]]:
    """응답의 오류 코드를 보고 항목 목록을 꺼낸다.

    "data"가 리스트면 첫 값을, 사전이면 "error_code"를 오류 코드로 본다.
    "데이터 없음"이면 빈 목록, 성공이면 항목 목록을 돌려준다.
    """
    data = raw.get("data")
    if isinstance(data, list):
        code = str(data[0]) if data else NO_DATA
        items: List[Dict[str, Any]] = []
    elif isinstance(data, dict):
        code = str(data.get("error_code", SUCCESS))
        items = data.get("item") or []
    else:
        raise KamisError("KAMIS 응답 모양을 알 수 없음")
    if code == NO_DATA:
        return []
    if code != SUCCESS:
        raise KamisError(f"KAMIS 오류 코드 {code}")
    return items


def parse_category(raw: Dict[str, Any], category_code: str, today: date) -> List[OverallRow]:
    """전체 평균 API 응답을 품종별 줄로 바꾼다.

    응답에서 항목 목록을 꺼내고, 항목마다 당일 날짜(day1)와 당일·1주 전·
    1개월 전·1년 전·평년 값(dpr1, dpr3, dpr5, dpr6, dpr7)을 읽는다.

    Args:
        raw: 전체 평균 API의 JSON 응답.
        category_code: 이 응답을 받은 부류 코드.
        today: 날짜 글자의 연도를 정할 기준 날짜.

    Returns:
        품종별 줄. "데이터 없음"이면 빈 목록.

    Raises:
        KamisError: 성공도 "데이터 없음"도 아닌 응답인 경우.
    """
    rows = []
    for it in _items_or_empty(raw):
        rows.append(OverallRow(
            category_code=category_code,
            item_code=str(it.get("itemcode", "")),
            item_name=str(it.get("item_name", "")),
            kind_code=str(it.get("kindcode", "")),
            kind_name=str(it.get("kind_name", "")),
            rank=str(it.get("rank", "")),
            unit=str(it.get("unit", "")),
            as_of=parse_day(str(it.get("day1", "")), today),
            today=parse_price(it.get("dpr1")),
            week_ago=parse_price(it.get("dpr3")),
            month_ago=parse_price(it.get("dpr5")),
            year_ago=parse_price(it.get("dpr6")),
            normal=parse_price(it.get("dpr7")),
        ))
    return rows


def parse_period(raw: Dict[str, Any]) -> List[StoreRow]:
    """가게별 값 API 응답을 가게별 줄로 바꾼다.

    가게 이름이 비었거나, 지역이 "평균"·"평년"인 요약 줄이거나, 가격이 없는
    줄은 뺀다. 남은 줄마다 대형유통 여부를 붙인다.

    Args:
        raw: 가게별 값 API의 JSON 응답.

    Returns:
        가게별 줄. "데이터 없음"이면 빈 목록.

    Raises:
        KamisError: 성공도 "데이터 없음"도 아닌 응답인 경우.
    """
    rows = []
    for it in _items_or_empty(raw):
        market = str(it.get("marketname") or "").strip()
        county = str(it.get("countyname") or "").strip()
        price = parse_price(it.get("price"))
        if not market or county in ("평균", "평년") or price is None:
            continue
        year = int(it.get("yyyy"))
        day = parse_day(f"{year}-{str(it.get('regday')).replace('/', '-')}", date(year, 12, 31))
        rows.append(StoreRow(day=day, county=county, market=market, price=price,
                             large=is_large_retail(market)))
    return rows
