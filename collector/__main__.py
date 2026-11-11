"""수집 순서 전체(설계 5절).

    uv run python -m collector            # 기준일·출처가 기존 파일과 같으면 건너뛴다
    uv run python -m collector --force    # 같아도 다시 쓴다(품종 목록을 다시 만든 날)

키(환경변수 KAMIS_CERT_KEY, KAMIS_CERT_ID)가 있으면 실제 KAMIS를, 없으면
`collector/sample/`의 샘플 응답을 읽어 `data/prices.json`을 만든다.
"""

import os
import sys
from collections import defaultdict
from dataclasses import replace
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
from zoneinfo import ZoneInfo

from collector.compute import LARGE_ONLY, THRESHOLD_PCT, WINDOW_DAYS, build_entry, build_national_entry
from collector.items import ITEMS_PATH, RANK_PREFERENCE, load_items
from collector.kamis import (LOOKBACK_DAYS, SAMPLE_DIR, Source, latest_overall, make_source, months_back,
                             past_overall)
from collector.models import CATEGORIES, LIVESTOCK, Item, OverallRow
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


def _collect_overall(source: Source, items: List[Item], today: date
                     ) -> Tuple[Dict[Tuple[str, str], OverallRow], Dict[str, str], List[str], List[str]]:
    """가장 최근 조사일의 전체 평균에서 품종별 상품 줄, 실패한 부류(부류 → 이유), 날마다의 응답 모양,
    품종 목록에 없는 품종의 이름을 돌려준다.

    품종 목록에 있는 농수산물 줄(품목·품종 코드와 등급 번호가 같은 줄)에 값이 있는 날을 찾는다.
    축산물 줄은 날을 정할 때 보지 않는다. 농수산물 값이 아직 안 올라온 날에도 축산물에는 값이
    있어서, 보면 농수산물 값이 빈 날이 기준일이 된다. 수산물은 등급 이름이 "상품"이 아니라서
    등급 이름 대신 등급 번호로 고른다.
    """
    wanted = {_row_key(item) for item in items}
    rows, failed, tried = latest_overall(
        source, today, lambda row: _row_key(row) in wanted and row.category_code != LIVESTOCK)
    overall = {_row_key(row): row for row in rows if _row_key(row) in wanted}
    return overall, failed, tried, _unlisted(rows, items)


def _unlisted(rows: List[OverallRow], items: List[Item]) -> List[str]:
    """그날 전체 평균에는 있는데 품종 목록에 없는 품종의 이름을 돌려준다(2026-11-11 결정).

    품종 목록을 다시 만들면 새로 들어올 줄만 고른다(`collector.items.build_items`와 같은 기준).
    농수산물은 품종(품목·품종 코드)이 목록에 없고 등급이 목록에 넣는 등급인 줄, 축산물은 등급 번호까지
    같은 줄이 목록에 없는 줄이다.

    Args:
        rows: 그날 전체 평균의 모든 등급 줄.
        items: 품종 목록.

    Returns:
        이름 순으로 정렬한 품종 이름(축산물은 등급까지).
    """
    kinds = {(item.item_code, item.kind_code) for item in items}
    listed = {_row_key(item) for item in items}
    names: Set[str] = set()
    for row in rows:
        if row.category_code == LIVESTOCK:
            if _row_key(row) not in listed:
                names.add(f"{row.item_name} {row.kind_name} {row.rank}")
        elif row.rank in RANK_PREFERENCE and (row.item_code, row.kind_code) not in kinds:
            names.add(f"{row.item_name} {row.kind_name}")
    return sorted(names)


def _fill_past(source: Source, overall: Dict[Tuple[str, str, str], OverallRow], as_of: date,
               today: date) -> Dict[Tuple[str, str, str], OverallRow]:
    """비어서 온 1개월 전·1년 전 값을 가까운 조사일의 당일 값으로 채운다(2026-11-04 결정).

    부류 안에서 당일 값이 있는 줄의 칸이 모두 비었을 때만 그 부류를 다시 부른다. 그날이
    주말·공휴일이라 KAMIS가 칸을 통째로 비운 경우다. 몇 줄만 비었으면 그날 조사는 있었고 그
    품종만 값이 없던 것이라, 다시 불러도 같은 값이 온다.

    Args:
        source: KAMIS 또는 샘플 받기 쪽.
        overall: 품종별 전체 평균 줄.
        as_of: 기준일.
        today: 날짜 글자의 연도를 정할 기준 날짜.

    Returns:
        채운 줄로 바꾼 새 사전.
    """
    filled = dict(overall)
    for field, months in (("month_ago", 1), ("year_ago", 12)):
        for code in CATEGORIES:
            rows = [row for row in filled.values() if row.category_code == code and row.today is not None]
            if not rows or any(getattr(row, field) is not None for row in rows):
                continue
            past = {_row_key(row): row.today
                    for row in past_overall(source, code, months_back(as_of, months), today)}
            for row in rows:
                if past.get(_row_key(row)) is not None:
                    filled[_row_key(row)] = replace(row, **{field: past[_row_key(row)]})
    return filled


def _fill_normal(source: Source, overall: Dict[Tuple[str, str, str], OverallRow], as_of: date,
                 today: date) -> Dict[Tuple[str, str, str], OverallRow]:
    """비어서 온 평년 값을 바로 앞 조사일의 평년 값으로 채운다(2026-11-11 결정).

    월요일에는 수산물 열몇 품종의 평년 칸만 비어서 온다. 당일 값은 있는데 평년 값이 없는 품종이 있는
    부류만 기준일 전날부터 거꾸로 가장 가까운 조사일 것을 한 번 더 받아, 그날 같은 줄의 평년 값을 쓴다.
    그날에도 평년 값이 없는 품종은 비워 둔다.

    Args:
        source: KAMIS 또는 샘플 받기 쪽.
        overall: 품종별 전체 평균 줄.
        as_of: 기준일.
        today: 날짜 글자의 연도를 정할 기준 날짜.

    Returns:
        채운 줄로 바꾼 새 사전.
    """
    filled = dict(overall)
    for code in CATEGORIES:
        empty = [row for row in filled.values()
                 if row.category_code == code and row.today is not None and row.normal is None]
        if not empty:
            continue
        past = {_row_key(row): row.normal
                for row in past_overall(source, code, as_of - timedelta(days=1), today)}
        for row in empty:
            if past.get(_row_key(row)) is not None:
                filled[_row_key(row)] = replace(row, normal=past[_row_key(row)])
    return filled


def _livestock_points(source: Source, overall: Dict[Tuple[str, str, str], OverallRow], as_of: date,
                      today: date) -> Dict[Tuple[str, str, str], List[Tuple[date, int]]]:
    """축산물 줄마다 기준일부터 거꾸로 31일의 날짜별 전국 평균을 모은다(2026-11-04 결정).

    부류별 API를 하루에 한 번씩 불러 그날의 당일 값을 모은다. 한 번 부르면 축산물 모든 줄이 오고,
    기준일 것은 이미 받은 전체 평균 줄을 쓴다. 큰 가격, 그래프, 평년 %가 모두 같은 API의 같은 날짜
    값이 된다. 받기에 실패한 날은 건너뛴다(그래프에서 그날만 빠진다).

    Args:
        source: KAMIS 또는 샘플 받기 쪽.
        overall: 품종별 전체 평균 줄(기준일 것).
        as_of: 기준일.
        today: 날짜 글자의 연도를 정할 기준 날짜.

    Returns:
        (품목 코드, 품종 코드, 등급 번호) → (날짜, 당일 값) 목록.
    """
    points: Dict[Tuple[str, str, str], List[Tuple[date, int]]] = defaultdict(list)
    for key, row in overall.items():
        if row.category_code == LIVESTOCK and row.today is not None:
            points[key].append((row.as_of, row.today))
    for back in range(1, WINDOW_DAYS):
        try:
            rows = parse_category(source.category(LIVESTOCK, as_of - timedelta(days=back)), LIVESTOCK, today)
        except KamisError:
            continue
        for row in rows:
            if row.today is not None:
                points[_row_key(row)].append((row.as_of, row.today))
    return points


def _row_key(x: Any) -> Tuple[str, str, str]:
    """품종이나 전체 평균 줄을 (품목 코드, 품종 코드, 등급 번호)로 나타낸다."""
    return (x.item_code, x.kind_code, x.rank_code)


def _same_unit(a: str, b: str) -> bool:
    """두 조사 단위 글자가 띄어쓰기와 대소문자를 빼고 같은지 본다."""
    return a.replace(" ", "").lower() == b.replace(" ", "").lower()


def run(source: Source, items: List[Item], out_path: Path, today: date, force: bool = False) -> str:
    """한 번 수집해 화면용 파일을 만든다.

    1. 기존 파일을 읽고, 샘플이 실제 데이터를 덮어쓰려 하면 멈춘다.
    2. 부류 6개의 전체 평균을 받는다. 오늘 값이 없으면 하루씩 거꾸로 최대 7일까지
       찾는다. 실패한 부류의 품종은 실패로 다룬다.
    3. 전체 평균의 당일 날짜(값이 있는 줄) 가운데 가장 늦은 날을 기준일로 삼고, 기존 파일과
       기준일·출처가 같으면 건너뛴다. 1개월 전·1년 전 값이 통째로 빈 부류는 가까운 조사일
       값으로, 평년 값이 빈 품종은 바로 앞 조사일의 평년 값으로 채운다.
    4. 품종마다 기준일부터 거꾸로 31일의 가게 값을 받아 항목을 만든다. 축산물은 가게별 값이
       없어, 부류별 API를 날마다 불러 모은 전국 평균으로 만든다. 전체 평균의 조사 단위가 품종
       목록 파일과 다르면 그 품종은 실패로 다룬다.
    5. 한 줄 요약(축산물은 따로 한 줄, 빠진 축산물은 이름까지)과 품종 목록에 없는 품종의 이름을
       찍고, 결과가 수상하면(새 항목이 없음, 전체 평균과 맞은 품종이 없음) 기존 파일을 지키려고 멈춘다.
    6. 실패한 품종은 기존 항목을 남기되(기존 파일 출처가 같을 때만), 새 파일을
       통째로 바꿔 넣는다.

    Args:
        source: KAMIS 또는 샘플 받기 쪽.
        items: 품종 목록.
        out_path: 화면용 파일 경로.
        today: 오늘 날짜(한국 시각). 날짜 글자의 연도를 정하는 데 쓴다.
        force: 참이면 기준일·출처가 기존 파일과 같아도 건너뛰지 않는다(품종 목록을 다시
            만든 날에 쓴다).

    Returns:
        "updated" 또는 "skipped".

    Raises:
        SampleGuardError: 샘플로 실제 데이터를 덮어쓰려 한 경우.
        CollectError: 전체 평균을 하나도 못 받았거나(부류마다 이유를 붙인다), 7일
            동안 값이 없거나, 모든 품종을 못 받았거나,
            새 항목이 하나도 없거나, 전체 평균과 맞은 품종이 없는 경우.
    """
    existing = load_prices(out_path)
    check_sample_guard(existing, source.name)

    overall, failed_categories, tried, unlisted = _collect_overall(source, items, today)
    if len(failed_categories) == len(CATEGORIES):
        reasons = "; ".join(f"부류 {code}: {reason}" for code, reason in failed_categories.items())
        raise CollectError(f"전체 평균을 한 부류도 받지 못했습니다({reasons}).")
    priced = [row for row in overall.values() if row.today is not None and row.category_code != LIVESTOCK]
    if not priced:
        hint = " 샘플이면 먼저 `uv run python -m collector.make_sample`을 돌리세요." \
            if source.name == SAMPLE_NAME else ""
        raise CollectError(f"최근 {LOOKBACK_DAYS}일 동안 전체 평균 응답에 값이 없어 기준일을 정할 수 없습니다." + hint
                           + " 응답에 값이 있는데도(\"값\" 뒤 숫자가 0보다 큼) 이렇다면 품종 코드가 품종 목록 파일과"
                           " 맞지 않을 수 있습니다(`uv run python -m collector.make_items`)."
                           + " 날마다 받은 응답(부류:코드): " + " / ".join(tried))
    as_of = max(row.as_of for row in priced)
    if not force and should_skip(existing, as_of, source.name):
        return "skipped"
    overall = _fill_normal(source, _fill_past(source, overall, as_of, today), as_of, today)
    livestock =[item for item in items if item.category_code == LIVESTOCK]
    points = (_livestock_points(source, overall, as_of, today)
              if livestock and LIVESTOCK not in failed_categories else {})

    start = as_of - timedelta(days=WINDOW_DAYS - 1)
    entries: List[Dict[str, Any]] = []
    failed_ids: Set[str] = set()
    unit_mismatch: List[str] = []
    no_store_value = 0
    livestock_missing: List[str] = []
    matched = 0
    for item in items:
        if item.category_code in failed_categories:
            failed_ids.add(item.id)
            continue
        row = overall.get(_row_key(item))
        if row is not None and not _same_unit(row.unit, item.unit):
            # 품종 목록 파일과 KAMIS가 알려 준 조사 단위가 다르면 단위 가격이 틀리므로 실패로 다룬다.
            unit_mismatch.append(f"{item.id}({item.unit}→{row.unit})")
            failed_ids.add(item.id)
            continue
        if item.category_code == LIVESTOCK:
            # 축산물은 가게별 값이 없어 날짜별 전국 평균으로 만든다(설계 18절).
            entry = build_national_entry(item, row, points.get(_row_key(item), []), as_of)
            if entry is None:
                livestock_missing.append(f"{item.item_name} {item.kind_name}")
                continue
        else:
            try:
                stores = parse_period(source.period(item, start, as_of))
            except KamisError:
                failed_ids.add(item.id)
                continue
            entry = build_entry(item, row, stores, as_of)
            if entry is None:
                no_store_value += 1
                continue
        entries.append(entry)
        matched += row is not None

    print(f"{source.name} {as_of}: 새 항목 {len(entries)}개, "
          f"{'대형유통' if LARGE_ONLY else '가게'} 값이 없어 빠진 품종 {no_store_value}개, "
          f"전체 평균과 맞은 품종 {matched}개, 받지 못한 품종 {len(failed_ids)}개")
    if livestock:
        # 축산물은 철이 없으니 값이 없어 빠진 품종이 있으면 이상한 것이라 이름까지 남긴다.
        made = sum(entry["category"] == CATEGORIES[LIVESTOCK] for entry in entries)
        print(f"축산물 새 항목 {made}개, 값이 없어 빠진 품종 {len(livestock_missing)}개"
              + (f"({', '.join(livestock_missing)})" if livestock_missing else ""))
    if unit_mismatch:
        print(f"단위가 다른 품종 {len(unit_mismatch)}개(목록 파일→KAMIS): {', '.join(unit_mismatch)}. "
              "`uv run python -m collector.make_items`로 품종 목록을 다시 만드세요.")
    if unlisted:
        # 기록만 남기고 목록에 넣지는 않는다. 이름과 조사 단위를 사람이 본 뒤 넣는다.
        print(f"품종 목록에 없는 품종 {len(unlisted)}개: {', '.join(unlisted)}. "
              "화면에 넣으려면 Actions의 \"품종 목록도 다시 만들기\"로 돌리세요.")
    if items and len(failed_ids) == len(items):
        raise CollectError("모든 품종을 받지 못했습니다.")
    if items and not entries:
        raise CollectError(f"새로 만든 품종 항목이 하나도 없습니다({'대형유통' if LARGE_ONLY else '가게'} 값이 "
                           "없음). 가게 이름 규칙이나 응답 모양을 확인하세요. 기존 파일은 그대로 둡니다.")
    if entries and not matched:
        raise CollectError("전체 평균과 맞는 품종이 하나도 없습니다(품목·품종 코드가 맞지 않음). "
                           "응답의 코드 칸 이름을 확인하세요. 기존 파일은 그대로 둡니다.")

    # 출처가 바뀐 첫 실행(샘플 → KAMIS)에서는 실패한 품종의 샘플 값을 남기지 않는다.
    keep = existing if existing is not None and existing.get("source") == source.name else None
    write_prices(out_path, {
        "as_of": as_of.isoformat(),
        "source": source.name,
        "generated_at": datetime.now(KST).isoformat(timespec="seconds"),
        "basis": {"compare": "전국 대형유통 평균" if LARGE_ONLY else "전국 평균",
                  "season": "KAMIS 전체 평균"},
        "threshold_pct": THRESHOLD_PCT,
        "items": carry_over(entries, failed_ids, keep),
    })
    return "updated"


def main(argv: Optional[List[str]] = None) -> int:
    """환경변수로 받기 쪽을 골라 한 번 수집한다.

    Args:
        argv: 명령줄 인자. `--force`가 있으면 기준일이 같아도 다시 쓴다. None이면 sys.argv.

    Returns:
        종료 코드. 갱신했거나 건너뛰었으면 0, 실패했으면 1.
    """
    source = make_source(os.environ, SAMPLE_DIR)
    today = datetime.now(KST).date()
    try:
        args = sys.argv[1:] if argv is None else argv
        result = run(source, load_items(ITEMS_PATH), PRICES_PATH, today, force="--force" in args)
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
