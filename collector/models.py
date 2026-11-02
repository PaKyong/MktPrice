"""수집 스크립트가 주고받는 데이터 묶음.

KAMIS 응답을 해석한 결과(전체 평균 줄, 가게별 값 줄)와 품종 목록 파일의
한 항목을 담는 작은 데이터 클래스들이다.
"""

from dataclasses import dataclass
from datetime import date
from typing import Dict, Optional

# KAMIS 부류 코드 → 부류 이름.
CATEGORIES: Dict[str, str] = {
    "100": "식량작물",
    "200": "채소류",
    "300": "특용작물",
    "400": "과일류",
    "500": "축산물",
    "600": "수산물",
}


@dataclass(frozen=True)
class Item:
    """품종 목록 파일의 품종 하나.

    Attributes:
        id: "{item_code}-{kind_code}" 모양의 품종 id. 목록 저장과 화면이 이 값을 쓴다.
        category_code: KAMIS 부류 코드(예: "400").
        category_name: 부류 이름(예: "과일류").
        item_code: KAMIS 품목 코드.
        item_name: 품목 이름(예: "사과").
        kind_code: KAMIS 품종 코드.
        kind_name: 품종 이름(예: "홍로").
        rank_code: KAMIS 등급 코드(상품).
        unit: KAMIS 조사 단위 원문(예: "10개", "1kg").
        measure: "weight"(무게) 또는 "count"(개수).
        amount: 조사 단위의 양. 무게면 g, 개수면 개수.
        unit_label: 단위 가격의 단위 이름. 무게면 "100g", 개수면 "개"·"포기" 등.
    """

    id: str
    category_code: str
    category_name: str
    item_code: str
    item_name: str
    kind_code: str
    kind_name: str
    rank_code: str
    unit: str
    measure: str
    amount: float
    unit_label: str


@dataclass(frozen=True)
class OverallRow:
    """전체 평균 API 응답의 품종 한 줄.

    Attributes:
        category_code: 이 줄을 받은 부류 코드.
        item_code: 품목 코드.
        item_name: 품목 이름.
        kind_code: 품종 코드.
        kind_name: 품종 이름.
        rank: 등급 이름(예: "상품").
        unit: 조사 단위 원문.
        as_of: 당일 날짜.
        today: 당일 값.
        week_ago: 1주 전 값.
        month_ago: 1개월 전 값.
        year_ago: 1년 전 값.
        normal: 평년 값.
    """

    category_code: str
    item_code: str
    item_name: str
    kind_code: str
    kind_name: str
    rank: str
    unit: str
    as_of: date
    today: Optional[int]
    week_ago: Optional[int]
    month_ago: Optional[int]
    year_ago: Optional[int]
    normal: Optional[int]


@dataclass(frozen=True)
class StoreRow:
    """가게별 값 API 응답의 가게 한 줄.

    Attributes:
        day: 조사 날짜.
        county: 지역 이름.
        market: 가게 이름.
        price: 가격(조사 단위 기준).
        large: 대형유통 가게면 True.
    """

    day: date
    county: str
    market: str
    price: int
    large: bool
