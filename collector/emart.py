"""이마트 상품의 평소 값과 행사 때 최저 값을 내 `data/emart.json`을 쓴다(설계 15절).

    uv run python -m collector.emart    # 새 달이 있을 때만 최근 3개 달을 받는다

키(환경변수 DATA_GO_KR_KEY, 공공데이터포털 인증키)가 없으면 아무것도 하지 않고 끝낸다.
참가격 이마트 값에는 행사 값이 표시 없이 섞여 있어, 조사일마다 지점들에서 가장
흔한 값을 대표값으로 삼고 3개월 대표값 가운데 가장 높은 값을 평소 값으로 본다.
"""

import os
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime
from itertools import chain
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional
from zoneinfo import ZoneInfo

from collector.champrice import ChampriceError, ChampriceSource, Month, MonthSource
from collector.output import load_prices, write_prices

EMART_PATH = Path(__file__).parent.parent / "data" / "emart.json"
SOURCE_NAME = "참가격"
# 가장 새 달과 그 앞 두 달(조사 6번쯤).
MONTHS = 3
KST = ZoneInfo("Asia/Seoul")
_DAY = re.compile(r"^\d{4}-\d{2}-\d{2}$")


@dataclass(frozen=True)
class ShopRow:
    """이마트 지점 한 곳의 그날 값.

    Attributes:
        name: 상품명(브랜드·용량 포함).
        day: 조사일.
        price: 판매가격.
        store: 가게 이름.
    """

    name: str
    day: date
    price: int
    store: str


def is_emart(store: str) -> bool:
    """가게가 이마트 지점인지 본다. 편의점 이마트24는 뺀다.

    Args:
        store: 가게 이름(예: "이마트강릉점").

    Returns:
        이마트 지점이면 True.
    """
    return store.startswith("이마트") and not store.startswith("이마트24")


def _price(value: Any) -> Optional[int]:
    """판매가격 칸을 0보다 큰 정수로 읽는다. 읽을 수 없으면 None."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value > 0 else None
    text = str(value or "").strip()
    return int(text) if text.isdigit() and int(text) > 0 else None


def parse_rows(raw: Iterable[Mapping[str, Any]]) -> List[ShopRow]:
    """응답 줄에서 이마트 지점 줄만 골라 읽는다.

    상품명이 비었거나, 조사일이 YYYY-MM-DD가 아니거나, 판매가격이 0보다 큰 정수가
    아닌 줄은 그 줄만 건너뛴다(이상한 줄 하나가 그달 전체를 멈추지 않게).

    Args:
        raw: API(또는 같은 칸 이름의 CSV) 줄들.

    Returns:
        이마트 지점 줄들. 받은 순서 그대로.
    """
    rows: List[ShopRow] = []
    for r in raw:
        name = str(r.get("상품명") or "").strip()
        store = str(r.get("판매업소") or "").strip()
        day = str(r.get("조사일") or "").strip()
        price = _price(r.get("판매가격"))
        if not name or not is_emart(store) or not _DAY.match(day) or price is None:
            continue
        try:
            rows.append(ShopRow(name, date.fromisoformat(day), price, store))
        except ValueError:
            continue
    return rows


def representative(prices: List[int]) -> int:
    """그날 지점 값들의 대표값을 고른다.

    가장 많은 지점이 받은 값이고, 지점 수가 같으면 높은 값(정가 쪽)이다.

    Args:
        prices: 그날 이마트 지점들의 값.

    Returns:
        대표값.
    """
    counts = Counter(prices)
    return max(counts, key=lambda p: (counts[p], p))


def build_products(rows: List[ShopRow]) -> List[Dict[str, Any]]:
    """상품마다 평소 값, 행사 때 최저 값, 조사일별 대표값을 낸다.

    상품명으로 묶고 조사일마다 대표값과 지점 수를 낸 뒤, 대표값 가운데 가장 높은
    값을 평소 값, 가장 낮은 값을 행사 때 최저 값으로 삼는다. 최저 값이 평소 값과
    같으면 행사가 없었던 것으로 보고, 같은 최저 값이 여러 날이면 가장 최근 날을 쓴다.

    Args:
        rows: 이마트 지점 줄들.

    Returns:
        상품 항목들(상품명 순): 상품명, 평소 값, 행사 때 최저 값(값·날·평소보다 %, 없으면
        None), 마지막 조사일과 그날 지점 수, 조사일별 [날, 대표값, 지점 수](최근 날부터).
    """
    by_name: Dict[str, Dict[date, List[int]]] = defaultdict(lambda: defaultdict(list))
    for row in rows:
        by_name[row.name][row.day].append(row.price)
    products: List[Dict[str, Any]] = []
    for name in sorted(by_name):
        days = sorted(by_name[name].items(), reverse=True)
        history = [[day.isoformat(), representative(prices), len(prices)] for day, prices in days]
        usual = max(price for _, price, _ in history)
        low_price = min(price for _, price, _ in history)
        low = None
        if low_price < usual:
            low_day = next(day for day, price, _ in history if price == low_price)
            low = {"price": low_price, "day": low_day, "pct": round((low_price - usual) / usual * 100)}
        products.append({"name": name, "usual": usual, "low": low, "last_day": history[0][0],
                         "stores": history[0][2], "history": history})
    return products


def build_emart(raw: Iterable[Mapping[str, Any]], months: List[Month], now: datetime) -> Dict[str, Any]:
    """받은 줄로 `data/emart.json` 내용 전체를 만든다.

    Args:
        raw: 받은 달들의 줄.
        months: 받은 달들.
        now: 만든 시각(한국 시각).

    Returns:
        파일 내용.

    Raises:
        ChampriceError: 이마트 줄이 하나도 없는 경우(칸 이름이나 가게 이름 모양이
            바뀌었을 수 있다).
    """
    rows = parse_rows(raw)
    items = build_products(rows)
    if not items:
        raise ChampriceError("이마트 줄이 하나도 없습니다. 응답 칸 이름(상품명, 조사일, 판매가격, 판매업소)이나 "
                             "가게 이름 모양을 확인하세요. 기존 파일은 그대로 둡니다.")
    return {
        "source": SOURCE_NAME,
        "generated_at": now.isoformat(timespec="seconds"),
        "months": [m.as_of.isoformat() for m in months],
        "as_of": max(row.day for row in rows).isoformat(),
        "items": items,
    }


def run(source: MonthSource, out_path: Path, now: datetime) -> str:
    """새 달이 있으면 최근 3개 달을 받아 화면용 파일을 새로 쓴다.

    1. 설명서의 달 목록에서 뒤의 `MONTHS`개를 고른다.
    2. 기존 파일의 달 목록에 가장 새 달이 이미 있으면 건너뛴다.
    3. 고른 달들의 줄을 이어 받아 계산하고, 파일을 통째로 바꿔 넣는다.
    받다가 실패하거나 이마트 줄이 없으면 기존 파일은 그대로 둔다.

    Args:
        source: 참가격 받기 쪽.
        out_path: 화면용 파일 경로.
        now: 만든 시각(한국 시각).

    Returns:
        "updated" 또는 "skipped".

    Raises:
        ChampriceError: 달 목록이 없거나, 받기가 실패했거나, 이마트 줄이 없는 경우.
    """
    months = source.months()[-MONTHS:]
    if not months:
        raise ChampriceError("설명서에 달 목록이 없습니다.")
    existing = load_prices(out_path)
    if existing is not None and months[-1].as_of.isoformat() in existing.get("months", []):
        return "skipped"
    data = build_emart(chain.from_iterable(source.rows(m) for m in months), months, now)
    write_prices(out_path, data)
    # 조사일별 지점 수를 모두 더하면 받은 이마트 줄 수다.
    shop_rows = sum(stores for item in data["items"] for _, _, stores in item["history"])
    print(f"{SOURCE_NAME} {data['as_of']}: 이마트 상품 {len(data['items'])}개, 이마트 줄 {shop_rows}개, "
          f"달 {', '.join(data['months'])}")
    return "updated"


def main() -> int:
    """환경변수의 키로 참가격을 한 번 받는다.

    Returns:
        종료 코드. 갱신했거나 건너뛰었으면(키 없음 포함) 0, 실패했으면 1.
    """
    key = os.environ.get("DATA_GO_KR_KEY", "")
    if not key:
        print("참가격 키 없음: 이마트 값을 건너뜁니다")
        return 0
    try:
        result = run(ChampriceSource(key), EMART_PATH, datetime.now(KST))
    except ChampriceError as err:
        print(f"참가격 수집 실패: {err}", file=sys.stderr)
        return 1
    if result == "skipped":
        print("참가격: 새 달이 없어 건너뜁니다")
    else:
        print(f"참가격: {EMART_PATH}를 새로 썼습니다")
    return 0


if __name__ == "__main__":
    sys.exit(main())
