"""조사 단위 해석과 단위 가격 시험."""

from typing import Tuple

import pytest

from collector.units import classify_unit, round_won, unit_price


def test_round_won_rounds_half_up() -> None:
    assert round_won(2.5) == 3
    assert round_won(3.5) == 4
    assert round_won(239.4) == 239


@pytest.mark.parametrize("unit, expected", [
    ("1kg", ("weight", 1000, "100g")),
    ("500g", ("weight", 500, "100g")),
    ("20kg", ("weight", 20000, "100g")),
    ("1.5kg", ("weight", 1500, "100g")),
    ("10개", ("count", 10, "개")),
    ("30구", ("count", 30, "개")),
    ("1포기", ("count", 1, "포기")),
    ("1마리", ("count", 1, "마리")),
    ("1단", ("count", 1, "단")),
    ("1봉", ("count", 1, "봉")),
])
def test_classify_unit(unit: str, expected: Tuple[str, float, str]) -> None:
    assert classify_unit(unit) == expected


def test_classify_unit_rejects_unreadable() -> None:
    with pytest.raises(ValueError):
        classify_unit("")


def test_unit_price() -> None:
    assert unit_price(2400, "weight", 1000) == 240  # 1kg 2,400원 → 100g당 240원
    assert unit_price(7500, "count", 30) == 250     # 30구 7,500원 → 1개당 250원
    assert unit_price(4000, "count", 1) == 4000     # 1포기


def test_volume_is_per_100ml() -> None:
    assert classify_unit("1L") == ("volume", 1000, "100ml")
    assert classify_unit("500ml") == ("volume", 500, "100ml")
    assert unit_price(2987, "volume", 1000) == 299  # 흰우유 1L 2,987원 → 100ml당 299원
