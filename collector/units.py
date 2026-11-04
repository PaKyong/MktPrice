"""KAMIS 조사 단위를 해석하고 단위 가격을 낸다.

무게로 조사한 품종은 100g당, 부피로 조사한 품종(우유)은 100ml당, 개수로 조사한 품종은
그 단위 하나당 값을 낸다(설계 6·18절). "구"(계란)는 "개"로 바꿔 부른다.
"""

import re
from typing import Tuple

WEIGHT_GRAMS = {"kg": 1000.0, "g": 1.0}
VOLUME_ML = {"l": 1000.0, "ml": 1.0}


def round_won(x: float) -> int:
    """원 단위로 반올림한다.

    파이썬 round()는 .5를 짝수 쪽으로 보내므로 쓰지 않고, 0.5를 더해 버린다.
    값은 늘 양수라고 가정한다.

    Args:
        x: 반올림할 금액.

    Returns:
        반올림한 원 단위 정수.
    """
    return int(x + 0.5)


def classify_unit(unit: str) -> Tuple[str, float, str]:
    """조사 단위 원문을 무게/개수 구분, 양, 단위 이름으로 나눈다.

    앞의 숫자(없으면 1)와 뒤의 단위 글자를 나눈다. kg·g은 무게로 보고 g으로, L·ml은
    부피로 보고 ml로 바꾸며, 그 밖의 글자는 개수 단위 이름으로 쓴다. "구"는 "개"로 바꾼다.

    Args:
        unit: KAMIS 조사 단위 원문(예: "1kg", "10개", "30구").

    Returns:
        (measure, amount, unit_label). 예: "1kg" → ("weight", 1000.0, "100g").

    Raises:
        ValueError: 단위를 읽을 수 없는 경우.
    """
    match = re.fullmatch(r"\s*(\d+(?:\.\d+)?)?\s*(\D+?)\s*", unit)
    if not match:
        raise ValueError(f"조사 단위를 읽을 수 없음: {unit!r}")
    amount = float(match.group(1)) if match.group(1) else 1.0
    name = match.group(2)
    if name.lower() in WEIGHT_GRAMS:
        return ("weight", amount * WEIGHT_GRAMS[name.lower()], "100g")
    if name.lower() in VOLUME_ML:
        return ("volume", amount * VOLUME_ML[name.lower()], "100ml")
    if name == "구":
        name = "개"
    return ("count", amount, name)


def unit_price(price: int, measure: str, amount: float) -> int:
    """조사 단위 값을 단위 가격으로 바꾼다.

    Args:
        price: 조사 단위 하나의 값.
        measure: "weight", "volume" 또는 "count".
        amount: 조사 단위의 양(무게면 g, 부피면 ml, 개수면 개수).

    Returns:
        무게면 100g당, 부피면 100ml당, 개수면 하나당 값(원 단위 반올림).
    """
    if measure in ("weight", "volume"):
        return round_won(price / amount * 100)
    return round_won(price / amount)
