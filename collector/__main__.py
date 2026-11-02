"""수집 순서 전체(설계 5절).

    uv run python -m collector

키(환경변수 KAMIS_CERT_KEY, KAMIS_CERT_ID)가 있으면 실제 KAMIS를, 없으면
`collector/sample/`의 샘플 응답을 읽어 `data/prices.json`을 만든다.
"""

import os
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
from zoneinfo import ZoneInfo

from collector.compute import LARGE_ONLY, THRESHOLD_PCT, WINDOW_DAYS, build_entry
from collector.items import ITEMS_PATH, TOP_RANK, load_items
from collector.kamis import SAMPLE_DIR, Source, make_source
from collector.models import CATEGORIES, Item, OverallRow
from collector.output import (
    PRICES_PATH,
    SAMPLE_NAME,
    CollectError,
    SampleGuardError,
    carry_over,
    check_sample_guard,
    load_prices,
    should_skip,
    write_prices,
)
from collector.parse import KamisError, parse_category, parse_period

KST = ZoneInfo("Asia/Seoul")


def _collect_overall(source: Source, today: date) -> Tuple[Dict[Tuple[str, str], OverallRow], Set[str]]:
    """부류 6개의 전체 평균을 받아 품종별 상품 줄과 실패한 부류를 돌려준다."""
    overall: Dict[Tuple[str, str], OverallRow] = {}
    failed: Set[str] = set()
    for code in CATEGORIES:
        try:
            rows = parse_category(source.category(code), code, today)
        except KamisError:
            failed.add(code)
            continue
        for row in rows:
            if row.rank == TOP_RANK:
                overall[(row.item_code, row.kind_code)] = row
    return overall, failed


def run(source: Source, items: List[Item], out_path: Path, today: date) -> str:
    """한 번 수집해 화면용 파일을 만든다.

    1. 기존 파일을 읽고, 샘플이 실제 데이터를 덮어쓰려 하면 멈춘다.
    2. 부류 6개의 전체 평균을 받는다. 실패한 부류의 품종은 실패로 다룬다.
    3. 전체 평균의 당일 날짜 가운데 가장 늦은 날을 기준일로 삼고, 기존 파일과
       기준일·출처가 같으면 건너뛴다.
    4. 품종마다 기준일부터 거꾸로 31일의 가게 값을 받아 항목을 만든다.
    5. 실패한 품종은 기존 항목을 남기고, 새 파일을 통째로 바꿔 넣는다.

    Args:
        source: KAMIS 또는 샘플 받기 쪽.
        items: 품종 목록.
        out_path: 화면용 파일 경로.
        today: 오늘 날짜(한국 시각). 날짜 글자의 연도를 정하는 데 쓴다.

    Returns:
        "updated" 또는 "skipped".

    Raises:
        SampleGuardError: 샘플로 실제 데이터를 덮어쓰려 한 경우.
        CollectError: 전체 평균을 하나도 못 받았거나, 모든 품종을 못 받은 경우.
    """
    existing = load_prices(out_path)
    check_sample_guard(existing, source.name)

    overall, failed_categories = _collect_overall(source, today)
    if len(failed_categories) == len(CATEGORIES):
        raise CollectError("전체 평균을 한 부류도 받지 못했습니다.")
    if not overall:
        hint = " 샘플이면 먼저 `uv run python -m collector.make_sample`을 돌리세요." \
            if source.name == SAMPLE_NAME else ""
        raise CollectError("전체 평균 응답에 값이 없어 기준일을 정할 수 없습니다." + hint)
    as_of = max(row.as_of for row in overall.values())
    if should_skip(existing, as_of, source.name):
        return "skipped"

    start = as_of - timedelta(days=WINDOW_DAYS - 1)
    entries: List[Dict[str, Any]] = []
    failed_ids: Set[str] = set()
    for item in items:
        if item.category_code in failed_categories:
            failed_ids.add(item.id)
            continue
        try:
            stores = parse_period(source.period(item, start, as_of))
        except KamisError:
            failed_ids.add(item.id)
            continue
        entry = build_entry(item, overall.get((item.item_code, item.kind_code)), stores, as_of)
        if entry is not None:
            entries.append(entry)
    if items and len(failed_ids) == len(items):
        raise CollectError("모든 품종의 가게 값을 받지 못했습니다.")

    write_prices(out_path, {
        "as_of": as_of.isoformat(),
        "source": source.name,
        "generated_at": datetime.now(KST).isoformat(timespec="seconds"),
        "basis": {"compare": "전국 대형유통 평균" if LARGE_ONLY else "전국 평균",
                  "season": "KAMIS 전체 평균"},
        "threshold_pct": THRESHOLD_PCT,
        "items": carry_over(entries, failed_ids, existing),
    })
    return "updated"


def main(argv: Optional[List[str]] = None) -> int:
    """환경변수로 받기 쪽을 골라 한 번 수집한다.

    Args:
        argv: 명령줄 인자(쓰지 않음).

    Returns:
        종료 코드. 갱신했거나 건너뛰었으면 0, 실패했으면 1.
    """
    source = make_source(os.environ, SAMPLE_DIR)
    today = datetime.now(KST).date()
    try:
        result = run(source, load_items(ITEMS_PATH), PRICES_PATH, today)
    except (CollectError, SampleGuardError) as err:
        print(f"수집 실패: {err}", file=sys.stderr)
        return 1
    if result == "skipped":
        print(f"{source.name}: 새 값이 없어 건너뜁니다(기준일이 기존 파일과 같음).")
    else:
        print(f"{source.name}: {PRICES_PATH}를 새로 썼습니다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
