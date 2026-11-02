"""화면용 파일(`data/prices.json`)을 읽고 쓴다.

주말·공휴일 건너뛰기 판단, 샘플이 실제 데이터를 덮어쓰지 않게 막기, 실패한
품종의 지난 값 남기기, 파일 통째로 바꿔 넣기를 맡는다(설계 5·10절).
"""

import json
import os
import tempfile
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

PRICES_PATH = Path(__file__).parent.parent / "data" / "prices.json"
SAMPLE_NAME = "샘플"
REAL_NAME = "KAMIS"


class CollectError(Exception):
    """수집이 통째로 실패해 화면용 파일을 바꿀 수 없다."""


class SampleGuardError(Exception):
    """샘플로 실제 데이터 파일을 덮어쓰려 했다."""


def load_prices(path: Path) -> Optional[Dict[str, Any]]:
    """기존 화면용 파일을 읽는다.

    Args:
        path: 화면용 파일 경로.

    Returns:
        파일 내용. 파일이 없으면 None.
    """
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def should_skip(existing: Optional[Dict[str, Any]], as_of: date, source: str) -> bool:
    """이번 수집을 건너뛸지 정한다.

    기존 파일의 기준일과 출처가 둘 다 이번과 같을 때만 건너뛴다. 같은 날
    샘플 파일이 있어도 처음 받은 실제 데이터는 건너뛰지 않기 위해서다.

    Args:
        existing: 기존 파일 내용(없으면 None).
        as_of: 이번 기준일.
        source: 이번 출처("KAMIS" 또는 "샘플").

    Returns:
        건너뛰어야 하면 True.
    """
    if existing is None:
        return False
    return existing.get("as_of") == as_of.isoformat() and existing.get("source") == source


def check_sample_guard(existing: Optional[Dict[str, Any]], source: str) -> None:
    """샘플이 실제 데이터 파일을 덮어쓰지 않게 막는다.

    Args:
        existing: 기존 파일 내용(없으면 None).
        source: 이번 출처.

    Raises:
        SampleGuardError: 이번 출처가 샘플이고 기존 파일이 실제 데이터인 경우.
    """
    if source == SAMPLE_NAME and existing is not None and existing.get("source") == REAL_NAME:
        raise SampleGuardError("실제 데이터가 든 prices.json을 샘플로 덮어쓰지 않습니다. "
                               "키(KAMIS_CERT_KEY, KAMIS_CERT_ID)를 넣고 돌리세요.")


def carry_over(entries: List[Dict[str, Any]], failed_ids: Set[str],
               existing: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """실패한 품종은 기존 항목을 그대로 남겨 새 항목과 합친다.

    Args:
        entries: 이번에 새로 만든 품종 항목들.
        failed_ids: 이번에 받지 못한 품종 id.
        existing: 기존 파일 내용(없으면 None).

    Returns:
        새 항목과 남긴 기존 항목을 합쳐 id 순으로 정렬한 목록. 기존 항목이
        없는 실패 품종은 빠진다.
    """
    merged = {e["id"]: e for e in entries}
    for old in (existing or {}).get("items", []):
        if old["id"] in failed_ids and old["id"] not in merged:
            merged[old["id"]] = old
    return [merged[k] for k in sorted(merged)]


def write_prices(path: Path, data: Dict[str, Any]) -> None:
    """화면용 파일을 통째로 바꿔 넣는다.

    같은 폴더의 임시 파일에 다 쓴 뒤 이름을 바꿔 넣어, 쓰다 멈춰도 기존 파일이
    반쯤 바뀐 채로 남지 않게 한다. BOM 없는 UTF-8, 줄바꿈 없이 쓴다.

    Args:
        path: 화면용 파일 경로.
        data: 쓸 내용.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
