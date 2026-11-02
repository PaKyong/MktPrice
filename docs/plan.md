# 장보기 가격 페이지 1차 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** KAMIS 소매가격으로 대형마트 가격표가 적당한지 판단하는 휴대폰용 정적 페이지와, 평일 저녁 가격 파일을 만드는 수집 스크립트를 샘플 데이터로 완성한다. 키를 넣으면 코드 수정 없이 실제 데이터로 바뀐다.

**Architecture:** 수집 스크립트(파이썬)가 KAMIS 응답(또는 샘플 응답)을 받아 해석·계산까지 끝내고 `data/prices.json` 하나를 쓴다. 화면은 빌드 없는 HTML·CSS·JS로 그 파일만 읽고, 서비스 워커로 오프라인에서도 열린다. GitHub Actions가 수집 → 커밋 → Pages 배포를 한 워크플로에서 한다.

**Tech Stack:** Python 3.14 + uv(표준 라이브러리만, 개발용 pytest), HTML·CSS·JS(ES 모듈, 라이브러리 없음), GitHub Actions, GitHub Pages.

**Spec:** `docs/design.md` (정한 이유는 `docs/decisions.md`)

## Global Constraints

- 수집 스크립트는 표준 라이브러리만 쓴다. 패키지는 개발용 pytest 하나(`uv add --dev pytest`).
- 파이썬 버전은 `.python-version`에 `3.14`, `pyproject.toml`의 `requires-python = ">=3.12"`.
- 파이썬 코드는 `anthropic-skills:python-style-guide`를 따른다: 함수마다 타입 힌트와 한국어 docstring.
- JSON은 BOM 없는 UTF-8, `ensure_ascii=False`. `prices.json`은 `separators=(",", ":")`로 줄바꿈 없이, 사람이 고치는 `collector/items.json`은 `indent=2`.
- 원 단위 반올림은 `round()`(짝수 쪽 반올림) 대신 `int(x + 0.5)`를 쓴다(값은 늘 양수).
- 화면은 빌드·npm·프레임워크·차트 라이브러리 없이 쓰고, 모든 경로는 상대 경로(`data/prices.json`, `/data/...` 금지). Pages 주소는 `https://pakyong.github.io/MktPrice/`.
- 키(`KAMIS_CERT_KEY`, `KAMIS_CERT_ID`)는 환경변수로만 받는다. 요청 주소에 키가 들어가므로 주소를 출력·기록하지 않고, 오류 메시지에도 넣지 않는다.
- 화면 문구는 아래 그대로 쓴다: "샘플 데이터예요. 실제 가격이 아니에요" / "인터넷 연결 없음 · {M}월 {D}일 값" / "홈 화면에 추가하면 앱처럼 쓰고, 인터넷 없이도 열려요" / "아래 검색창에서 품목을 찾아 ＋ 담기를 눌러 보세요" / "지금 값 없음" / "값 없는 품목 {N}개 제외" / "＋ 담기" · "✓ 담김" / "목록으로" / "목록에서 빼기" / "KAMIS 전체 평균 기준" / 신호 "비싼 편" · "보통" · "싼 편".
- 커밋은 CLAUDE.md 4절 규칙(한국어 제목 `<prefix>(<scope>): 요약`, 본문, `Co-Authored-By`)을 따른다. 푸시는 사용자가 말할 때만.

## Review Focus

1. KAMIS 가격 칸에 `"2,400"`, `"-"`, `""`, `"0"`이 섞여 온다 → 쉼표는 지우고 나머지는 "값 없음"(`None`)으로 본다. (Task 1)
2. KAMIS가 "데이터 없음"(`001`)을 돌려준다 → 실패가 아니라 값이 없는 것으로 보고, 다시 시도하지 않는다. (Task 1, Task 4)
3. 조사 단위가 `"500g"`, `"20kg"`, `"30구"`, `"1단"`, `"1봉"`처럼 제각각이다 → 무게는 g으로, 나머지는 개수와 단위 이름으로 바꾼다. 읽을 수 없는 단위는 목록 파일을 만들 때 바로 오류로 알린다. (Task 2)
4. 같은 날 샘플 파일이 있는 상태에서 처음 실제 데이터를 받는다 → 기준일이 같아도 출처가 다르면 건너뛰지 않는다. (Task 6)
5. 브라우저 저장 공간을 못 쓰는 환경(사생활 보호 모드 등)에서 localStorage가 오류를 낸다 → 화면은 멈추지 않고, 목록은 그 화면을 연 동안만 유지된다. (Task 7 확인 목록)

---

## 파일 구조

| 파일 | 하는 일 |
|---|---|
| `pyproject.toml`, `.python-version` | 파이썬 버전, pytest 설정(`testpaths = ["collector/tests"]`) |
| `collector/models.py` | 데이터 묶음 `Item`, `OverallRow`, `StoreRow`, 부류 이름표 `CATEGORIES` |
| `collector/parse.py` | KAMIS 응답 해석(가격 글자, 날짜, 대형유통 가려내기) |
| `collector/units.py` | 조사 단위 해석, 단위 가격, 원 단위 반올림 |
| `collector/items.py` | 품종 목록 파일 읽기·쓰기·만들기 |
| `collector/compute.py` | 설계 6절 계산 규칙, 품종 하나의 화면용 값 만들기 |
| `collector/kamis.py` | 실제 KAMIS 받기(다시 시도 포함)와 샘플 받기, 둘 중 고르기 |
| `collector/output.py` | 건너뛰기 판단, 샘플 덮어쓰기 막기, 지난 값 남기기, 파일 바꿔 넣기 |
| `collector/__main__.py` | 수집 순서 전체(`uv run python -m collector`) |
| `collector/make_items.py` | 전체 평균 응답으로 `items.json` 다시 만들기(`uv run python -m collector.make_items`) |
| `collector/make_sample.py` | `items.json`으로 샘플 응답 만들기(`uv run python -m collector.make_sample`) |
| `collector/items.json` | 품종 목록 파일 |
| `collector/sample/` | 샘플 응답(`category_<부류코드>.json`, `period/<품종id>.json`) |
| `collector/tests/` | pytest 시험 |
| `index.html`, `style.css`, `app.js` | 화면 |
| `store.js` | 목록 저장 |
| `sw.js`, `manifest.webmanifest`, `icons/` | 오프라인, 홈 화면 추가 |
| `tools/make_icons.py` | 아이콘 PNG 만들기(표준 라이브러리 `zlib`) |
| `.github/workflows/collect.yml` | 예약 실행, "지금 실행", 키 없음 처리, 커밋, Pages 배포 |
| `data/prices.json` | 화면용 파일 |

---

### Task 1: 프로젝트 뼈대와 KAMIS 응답 해석

**Files:**
- Create: `pyproject.toml`, `.python-version`, `collector/__init__.py`, `collector/models.py`, `collector/parse.py`, `collector/tests/__init__.py`, `collector/tests/test_parse.py`
- Modify: `.gitignore` (`.venv/`, `__pycache__/`, `.pytest_cache/`, `.env` 추가)

**Interfaces:**
- Produces:
  - `models.CATEGORIES: dict[str, str]` = `{"100": "식량작물", "200": "채소류", "300": "특용작물", "400": "과일류", "500": "축산물", "600": "수산물"}`
  - `models.Item` (frozen dataclass): `id: str`(`"{item_code}-{kind_code}"`), `category_code`, `category_name`, `item_code`, `item_name`, `kind_code`, `kind_name`, `rank_code`, `unit: str`(원문, 예 `"10개"`), `measure: str`(`"weight"`|`"count"`), `amount: float`(무게면 g, 개수면 개수), `unit_label: str`(`"100g"` 또는 `"개"`·`"포기"`…)
  - `models.OverallRow` (frozen): `category_code`, `item_code`, `item_name`, `kind_code`, `kind_name`, `rank: str`, `unit: str`, `as_of: date`, `today`, `week_ago`, `month_ago`, `year_ago`, `normal`: 모두 `int | None`
  - `models.StoreRow` (frozen): `day: date`, `county: str`, `market: str`, `price: int`, `large: bool`
  - `parse.KamisError(Exception)`
  - `parse.parse_price(text: str | None) -> int | None`
  - `parse.parse_day(text: str, today: date) -> date`
  - `parse.is_large_retail(market: str) -> bool`
  - `parse.parse_category(raw: dict, category_code: str, today: date) -> list[OverallRow]`
  - `parse.parse_period(raw: dict) -> list[StoreRow]`

KAMIS 응답 모양은 문서 기준 가정이다: 성공은 `{"data": {"error_code": "000", "item": [...]}}`, 데이터 없음은 `{"data": ["001"]}`(또는 `error_code` `"001"`). 전체 평균 항목 이름은 `item_name, itemcode, kind_name, kindcode, rank, unit, day1, dpr1 … day7, dpr7`, 가게별 값 항목 이름은 `itemname, kindname, countyname, marketname, yyyy, regday, price`. 대형유통은 가게 이름이 `"유통"`으로 끝나는 것으로 가정한다(누리집의 "B-유통"). 셋 다 키를 받은 뒤 확인한다.

- [ ] **Step 1: 뼈대를 만든다.** `.python-version`에 `3.14`, `pyproject.toml`에 `[project] name = "market-price"`, `requires-python = ">=3.12"`, `dependencies = []`, `[tool.pytest.ini_options] testpaths = ["collector/tests"]`. `uv add --dev pytest`.

- [ ] **Step 2: 실패하는 시험을 쓴다** (`collector/tests/test_parse.py`)

```python
def test_parse_price():
    assert parse_price("2,400") == 2400
    assert parse_price("-") is None
    assert parse_price("") is None
    assert parse_price(None) is None
    assert parse_price("0") is None

def test_parse_day_forms():
    today = date(2026, 11, 2)
    assert parse_day("2026-11-02", today) == date(2026, 11, 2)
    assert parse_day("당일 (11/02)", today) == date(2026, 11, 2)
    assert parse_day("12/30", date(2027, 1, 2)) == date(2026, 12, 30)  # 오늘보다 뒤 달이면 작년

def test_is_large_retail():
    assert is_large_retail("B-유통") is True
    assert is_large_retail("경동") is False

def test_parse_category_success():
    raw = {"data": {"error_code": "000", "item": [{
        "item_name": "사과", "itemcode": "411", "kind_name": "홍로", "kindcode": "05",
        "rank": "상품", "unit": "10개", "day1": "당일 (11/02)", "dpr1": "32,000",
        "day3": "1주일전 (10/26)", "dpr3": "31,000", "day5": "1개월전 (10/02)", "dpr5": "-",
        "day6": "1년전 (11/02)", "dpr6": "28,500", "day7": "평년", "dpr7": "27,100"}]}}
    [row] = parse_category(raw, "400", date(2026, 11, 2))
    assert (row.item_code, row.kind_code, row.rank, row.unit) == ("411", "05", "상품", "10개")
    assert row.as_of == date(2026, 11, 2)
    assert (row.today, row.week_ago, row.month_ago, row.year_ago, row.normal) == (32000, 31000, None, 28500, 27100)

def test_parse_category_no_data_is_empty():
    assert parse_category({"data": ["001"]}, "400", date(2026, 11, 2)) == []
    assert parse_category({"data": {"error_code": "001"}}, "400", date(2026, 11, 2)) == []

def test_parse_category_error_raises():
    with pytest.raises(KamisError):
        parse_category({"data": ["900"]}, "400", date(2026, 11, 2))

def test_parse_period_skips_summary_and_empty_rows():
    raw = {"data": {"error_code": "000", "item": [
        {"countyname": "서울", "marketname": "B-유통", "yyyy": "2026", "regday": "11/02", "price": "3,250"},
        {"countyname": "서울", "marketname": "경동", "yyyy": "2026", "regday": "11/02", "price": "2,900"},
        {"countyname": "평균", "marketname": "", "yyyy": "2026", "regday": "11/02", "price": "3,100"},
        {"countyname": "부산", "marketname": "C-유통", "yyyy": "2026", "regday": "11/02", "price": "-"}]}}
    rows = parse_period(raw)
    assert [(r.market, r.price, r.large) for r in rows] == [("B-유통", 3250, True), ("경동", 2900, False)]
    assert rows[0].day == date(2026, 11, 2)
```

- [ ] **Step 3: 시험이 실패하는지 본다.** Run: `uv run pytest collector/tests/test_parse.py -v` / Expected: 불러오기 오류로 FAIL.

- [ ] **Step 4: `models.py`와 `parse.py`를 쓴다.** `parse_day`는 `\d{4}-\d{2}-\d{2}`를 먼저 찾고, 없으면 `(\d{1,2})/(\d{1,2})`를 찾아 `today`의 연도를 붙이되 그 날짜가 `today`보다 뒤면 한 해를 뺀다. `parse_category`의 `as_of`는 `day1`에서 읽는다. `"data"`가 리스트면 첫 값을 오류 코드로 본다. `001`은 빈 리스트, `000`이 아닌 다른 코드는 `KamisError(f"KAMIS 오류 코드 {code}")`. `parse_period`는 `marketname`이 비었거나 `countyname`이 `"평균"`·`"평년"`이거나 가격이 `None`인 줄을 뺀다.

- [ ] **Step 5: 시험이 통과하는지 본다.** Run: `uv run pytest -v` / Expected: 7 passed.

- [ ] **Step 6: 커밋** — `feat(collector): KAMIS 응답 해석과 프로젝트 뼈대`

---

### Task 2: 조사 단위와 품종 목록 파일

**Files:**
- Create: `collector/units.py`, `collector/items.py`, `collector/tests/test_units.py`, `collector/tests/test_items.py`

**Interfaces:**
- Consumes: `models.Item`, `models.OverallRow`, `models.CATEGORIES`
- Produces:
  - `units.round_won(x: float) -> int`
  - `units.classify_unit(unit: str) -> tuple[str, float, str]` → `(measure, amount, unit_label)`. 읽을 수 없으면 `ValueError`.
  - `units.unit_price(price: int, measure: str, amount: float) -> int`
  - `items.build_items(rows: list[OverallRow], rank_code: str) -> list[Item]` — `rank == "상품"`인 줄만, `id` 순으로 정렬
  - `items.save_items(path: Path, items: list[Item]) -> None`, `items.load_items(path: Path) -> list[Item]`

- [ ] **Step 1: 실패하는 시험을 쓴다**

```python
def test_round_won_rounds_half_up():
    assert round_won(2.5) == 3 and round_won(3.5) == 4 and round_won(239.4) == 239

@pytest.mark.parametrize("unit, expected", [
    ("1kg", ("weight", 1000, "100g")), ("500g", ("weight", 500, "100g")),
    ("20kg", ("weight", 20000, "100g")), ("1.5kg", ("weight", 1500, "100g")),
    ("10개", ("count", 10, "개")), ("30구", ("count", 30, "개")),
    ("1포기", ("count", 1, "포기")), ("1마리", ("count", 1, "마리")),
    ("1단", ("count", 1, "단")), ("1봉", ("count", 1, "봉")),
])
def test_classify_unit(unit, expected):
    assert classify_unit(unit) == expected

def test_classify_unit_rejects_unreadable():
    with pytest.raises(ValueError):
        classify_unit("")

def test_unit_price():
    assert unit_price(2400, "weight", 1000) == 240     # 1kg 2,400원 → 100g당 240원
    assert unit_price(7500, "count", 30) == 250        # 30구 7,500원 → 1개당 250원
    assert unit_price(4000, "count", 1) == 4000        # 1포기

def test_build_items_keeps_top_grade_and_round_trips(tmp_path):
    rows = [make_row("411", "05", "상품", "10개"), make_row("411", "05", "중품", "10개")]
    items = build_items(rows, rank_code="04")
    assert [i.id for i in items] == ["411-05"]
    assert (items[0].measure, items[0].amount, items[0].unit_label) == ("count", 10, "개")
    save_items(tmp_path / "items.json", items)
    assert load_items(tmp_path / "items.json") == items
```

(`make_row`는 이 시험 파일 안에서 `OverallRow`를 만드는 작은 도우미다.)

- [ ] **Step 2: 실패를 본다.** Run: `uv run pytest collector/tests/test_units.py collector/tests/test_items.py -v` / Expected: FAIL.
- [ ] **Step 3: `units.py`, `items.py`를 쓴다.** `classify_unit`은 `^(\d+(?:\.\d+)?)?\s*(\D+)$`로 숫자와 단위를 나누고(숫자가 없으면 1), `kg`→×1000·`g`→×1은 무게, `구`는 `개`로 바꿔 개수, 그 밖의 글자는 그대로 개수 단위 이름. `amount`는 정수로 떨어지면 `int` 모양 그대로 비교되도록 `float`로 둔다(`1000 == 1000.0`).
- [ ] **Step 4: 통과를 본다.** Run: `uv run pytest -v` / Expected: 모두 PASS.
- [ ] **Step 5: 커밋** — `feat(collector): 조사 단위 해석과 품종 목록 파일`

---

### Task 3: 계산 규칙

**Files:**
- Create: `collector/compute.py`, `collector/tests/test_compute.py`

**Interfaces:**
- Consumes: `Item`, `OverallRow`, `StoreRow`, `units.round_won`, `units.unit_price`
- Produces:
  - `compute.THRESHOLD_PCT = 15.0`, `compute.LARGE_ONLY = True`(False면 모든 가게 값을 쓰는 "전국 평균"으로 바뀐다)
  - `compute.mean_won(values: list[int]) -> int`
  - `compute.price_range(values: list[int]) -> tuple[int, int]`
  - `compute.change_pct(today: int | None, past: int | None) -> float | None` (반올림하지 않은 값. 파일에는 `build_entry`가 소수 첫째 자리로 줄여 넣고, 신호는 줄이기 전 값으로 판단한다 — 설계 6절)
  - `compute.signal(pct: float | None, threshold: float = THRESHOLD_PCT) -> str | None`
  - `compute.build_entry(item: Item, overall: OverallRow | None, stores: list[StoreRow], as_of: date, large_only: bool = LARGE_ONLY) -> dict | None`

`build_entry`가 돌려주는 사전(설계 7절의 품종 항목)은 이 모양이다. 다른 Task가 이 키 이름을 그대로 쓴다.

```json
{"id": "411-05", "category": "과일류", "item": "사과", "kind": "홍로",
 "unit": "10개", "measure": "count", "unit_label": "개", "as_of": "2026-11-02",
 "price": 32000, "unit_price": 3200, "stores": 26,
 "range": [29500, 34000], "unit_range": [2950, 3400],
 "change": {"week": 3.2, "month": null, "year": 12.3, "normal": 18.1},
 "signal": "비싼 편", "trend": [["2026-10-02", 28000], ["2026-10-05", 28300]]}
```

품종의 기준일(`as_of`)은 `as_of`부터 거꾸로 31일 안에서 대형유통 값이 있는 가장 최근 날이다(그날 조사가 없던 품종도 가장 최근 값을 보여 주기 위한 해석이다). 31일 안에 값이 하나도 없으면 `None`을 돌려준다. `change`와 `signal`은 `overall`에서만 낸다(`overall`이 없으면 모두 `null`).

- [ ] **Step 1: 실패하는 시험을 쓴다**

```python
def test_mean_won():
    assert mean_won([3000, 3001]) == 3001

def test_price_range_uses_middle_half():
    assert price_range([1, 2, 3, 4, 5, 6, 7, 8]) == (3, 6)   # inclusive 방식 4분의 1 지점 2.75→3, 6.25→6

def test_price_range_under_four_uses_min_max():
    assert price_range([5, 1, 3]) == (1, 5)

def test_change_pct():
    assert change_pct(118, 100) == 18.0
    assert change_pct(100, None) is None and change_pct(None, 100) is None

@pytest.mark.parametrize("pct, expected", [(15.0, "비싼 편"), (14.9, "보통"), (-15.0, "싼 편"), (-14.9, "보통"), (None, None)])
def test_signal_boundaries(pct, expected):
    assert signal(pct) == expected

def test_build_entry_large_only():
    stores = [store("2026-11-02", "A-유통", 3000), store("2026-11-02", "B-유통", 3400),
              store("2026-11-02", "경동", 2000), store("2026-10-30", "A-유통", 2900)]
    e = build_entry(APPLE, overall(today=32000, week=31000, normal=27100), stores, date(2026, 11, 2))
    assert e["price"] == 3200 and e["stores"] == 2 and e["range"] == [3000, 3400]
    assert e["unit_price"] == 320 and e["as_of"] == "2026-11-02"   # APPLE은 1kg 단위 품종
    assert e["trend"] == [["2026-10-30", 2900], ["2026-11-02", 3200]]
    assert e["change"]["normal"] == 18.1 and e["signal"] == "비싼 편"

def test_build_entry_all_stores_when_not_large_only():
    ...  # 위와 같은 가게 값, large_only=False → stores == 3, price == 2800

def test_build_entry_uses_latest_day_within_31_days():
    e = build_entry(APPLE, None, [store("2026-10-20", "A-유통", 3000)], date(2026, 11, 2))
    assert e["as_of"] == "2026-10-20" and e["change"]["week"] is None and e["signal"] is None

def test_build_entry_none_when_no_value_in_31_days():
    assert build_entry(APPLE, None, [store("2026-10-01", "A-유통", 3000)], date(2026, 11, 2)) is None
```

(`APPLE`, `store`, `overall`은 이 시험 파일의 도우미다. `APPLE`은 `unit="1kg"`, `measure="weight"`, `amount=1000`.)

- [ ] **Step 2: 실패를 본다.** Run: `uv run pytest collector/tests/test_compute.py -v` / Expected: FAIL.
- [ ] **Step 3: `compute.py`를 쓴다.** `price_range`는 4곳 이상이면 `statistics.quantiles(values, n=4, method="inclusive")`의 첫째·셋째 값을 `round_won`. `trend`는 31일 안의 날짜마다 그날 가게 값 평균, 날짜 순.
- [ ] **Step 4: 통과를 본다.** Run: `uv run pytest -v` / Expected: 모두 PASS.
- [ ] **Step 5: 커밋** — `feat(collector): 대형유통 평균·범위·시기 신호 계산`

---

### Task 4: KAMIS 받기(실제와 샘플)

**Files:**
- Create: `collector/kamis.py`, `collector/tests/test_kamis.py`

**Interfaces:**
- Consumes: `Item`, `parse.KamisError`
- Produces:
  - `kamis.Source` (Protocol): `name: str`(`"KAMIS"` 또는 `"샘플"`), `category(self, category_code: str) -> dict`, `period(self, item: Item, start: date, end: date) -> dict`
  - `kamis.KamisSource(cert_key: str, cert_id: str, opener=urllib.request.urlopen, sleep=time.sleep)`
  - `kamis.SampleSource(sample_dir: Path)` — `category_<코드>.json`, `period/<item.id>.json`을 읽는다. 파일이 없으면 `{"data": ["001"]}`.
  - `kamis.make_source(env: Mapping[str, str], sample_dir: Path) -> Source` — `KAMIS_CERT_KEY`와 `KAMIS_CERT_ID`가 둘 다 있으면 `KamisSource`, 아니면 `SampleSource`
  - `kamis.BASE_URL = "https://www.kamis.or.kr/service/price/xml.do"` (문서에는 `http://`로 나온다. 키가 주소에 실려 가므로 `https://`를 쓰고, 키를 받은 첫 실행에서 되는지 확인한다 — `docs/decisions.md`의 "키를 받으면 확인할 것"에 더한다)

요청 변수: 전체 평균은 `action=dailyPriceByCategoryList, p_cert_key, p_cert_id, p_returntype=json, p_product_cls_code=01, p_item_category_code=<코드>, p_convert_kg_yn=N`. 가게별 값은 `action=periodRetailProductList, p_cert_key, p_cert_id, p_returntype=json, p_startday, p_endday(YYYY-MM-DD), p_itemcategorycode, p_itemcode, p_kindcode, p_productrankcode, p_convert_kg_yn=N`. 다시 시도는 처음 1번 + 3번, 기다림은 2·4·8초. 응답이 "데이터 없음"(`001`)이면 다시 시도하지 않고 그대로 돌려준다(해석은 Task 1의 몫).

- [ ] **Step 1: 실패하는 시험을 쓴다**

```python
def test_kamis_retries_then_succeeds():
    opener = FakeOpener([OSError(), OSError(), OSError(), b'{"data": {"error_code": "000", "item": []}}'])
    waits = []
    src = KamisSource("SECRETKEY", "me", opener=opener, sleep=waits.append)
    assert src.category("400")["data"]["error_code"] == "000"
    assert waits == [2, 4, 8]
    assert "p_item_category_code=400" in opener.urls[0] and "p_product_cls_code=01" in opener.urls[0]

def test_kamis_gives_up_without_leaking_key():
    src = KamisSource("SECRETKEY", "me", opener=FakeOpener([OSError()] * 4), sleep=lambda s: None)
    with pytest.raises(KamisError) as err:
        src.category("400")
    assert "SECRETKEY" not in str(err.value)

def test_kamis_does_not_retry_no_data():
    opener = FakeOpener([b'{"data": ["001"]}'])
    assert KamisSource("k", "me", opener=opener, sleep=lambda s: None).category("400") == {"data": ["001"]}
    assert len(opener.urls) == 1

def test_period_request_params():
    opener = FakeOpener([b'{"data": ["001"]}'])
    KamisSource("k", "me", opener=opener, sleep=lambda s: None).period(APPLE, date(2026, 10, 3), date(2026, 11, 2))
    for part in ["action=periodRetailProductList", "p_startday=2026-10-03", "p_endday=2026-11-02", "p_itemcode=411", "p_kindcode=05", "p_productrankcode=04"]:
        assert part in opener.urls[0]

def test_make_source_picks_by_env(tmp_path):
    assert make_source({}, tmp_path).name == "샘플"
    assert make_source({"KAMIS_CERT_KEY": "k"}, tmp_path).name == "샘플"
    assert make_source({"KAMIS_CERT_KEY": "k", "KAMIS_CERT_ID": "i"}, tmp_path).name == "KAMIS"

def test_sample_source_missing_period_is_no_data(tmp_path):
    assert SampleSource(tmp_path).period(APPLE, date(2026, 10, 3), date(2026, 11, 2)) == {"data": ["001"]}
```

(`FakeOpener`는 응답 목록을 차례로 돌려주거나 예외를 던지고, 받은 주소를 `urls`에 모으는 시험용 도우미다. 응답은 `io.BytesIO`를 감싼 문맥 관리자로 돌려준다.)

- [ ] **Step 2: 실패를 본다.** Run: `uv run pytest collector/tests/test_kamis.py -v` / Expected: FAIL.
- [ ] **Step 3: `kamis.py`를 쓴다.** 주소는 `urllib.parse.urlencode`로 만든다. 예외를 다시 던질 때 원래 예외를 붙이지 않는다(`raise KamisError("KAMIS 요청 실패: 전체 평균 400") from None`) — 원래 예외 글에 주소가 들어 있을 수 있다.
- [ ] **Step 4: 통과를 본다.** Run: `uv run pytest -v` / Expected: 모두 PASS.
- [ ] **Step 5: 커밋** — `feat(collector): KAMIS 받기와 샘플 받기`

---

### Task 5: 실제 코드로 품종 목록과 샘플 응답 만들기

**Files:**
- Create: `collector/make_items.py`, `collector/make_sample.py`, `collector/items.json`, `collector/sample/category_*.json`, `collector/sample/period/*.json`, `collector/tests/test_sample.py`

**Interfaces:**
- Consumes: `kamis.make_source`, `parse.parse_category`, `items.build_items/save_items/load_items`, `models.CATEGORIES`
- Produces:
  - `make_items.main(argv: list[str] | None = None) -> int` — 부류 6개를 받아 `items.json`을 다시 쓴다(키가 있으면 실제 응답으로)
  - `make_sample.build_sample(items: list[Item], as_of: date, seed: int = 20261102) -> tuple[dict[str, dict], dict[str, dict]]` — (부류 코드 → 전체 평균 응답, 품종 id → 가게별 값 응답)
  - `make_sample.main(argv: list[str] | None = None) -> int` — `collector/sample/`에 쓴다. 기준일 기본값 `2026-11-02`
  - 상품 등급 코드 상수 `make_items.TOP_RANK_CODE`(코드표에서 확인한 값)

- [ ] **Step 1: 코드표 내려받기 허락을 받는다.** KAMIS "농축수산물 품목 및 등급 코드표" 화면(`https://www.kamis.or.kr/customer/reference/openapi_list.do?action=detail&boardno=15`)에서 첨부 파일 이름과 크기를 확인해 사용자에게 알리고, 허락하면 Claude 임시 폴더의 새 빈 폴더에 내려받는다. 거절하면 KAMIS 소매가격 품목별 화면(`https://www.kamis.or.kr/customer/price/agricultureRetail/item.do`)의 선택 목록에서 코드를 읽는다.
- [ ] **Step 2: 처음 `items.json`을 만든다.** 설계 13·14절의 KAMIS 조사대상품목 화면에 있는 품종(약 50개)을 코드표의 실제 부류·품목·품종 코드와 상품 등급 코드로 적는다. 조사 단위는 지금 알 수 없으므로 품목마다 그럴듯한 단위를 넣는다(예: 사과 10개, 양파 1kg, 배추 1포기, 계란 30구). `docs/decisions.md`에 "샘플의 조사 단위는 지어낸 것이고, 키를 받으면 `make_items`로 다시 만든다"는 기록을 남긴다. 이 단계의 변환은 한 번 쓰고 버리는 스크립트로 하고 저장소에 넣지 않는다.
- [ ] **Step 3: 실패하는 시험을 쓴다** (`collector/tests/test_sample.py`)

```python
def test_sample_round_trips_items(tmp_path):
    items = load_items(ITEMS_PATH)
    categories, periods = build_sample(items, date(2026, 11, 2))
    rows = [r for code, raw in categories.items() for r in parse_category(raw, code, date(2026, 11, 2))]
    assert build_items(rows, TOP_RANK_CODE) == items

def test_sample_has_large_and_traditional_stores_over_31_days():
    items = load_items(ITEMS_PATH)
    _, periods = build_sample(items, date(2026, 11, 2))
    rows = parse_period(periods[items[0].id])
    assert len({r.market for r in rows if r.large}) >= 25 and any(not r.large for r in rows)
    assert min(r.day for r in rows) >= date(2026, 10, 3) and max(r.day for r in rows) == date(2026, 11, 2)
    assert all(r.day.weekday() < 5 for r in rows)

def test_sample_is_repeatable():
    items = load_items(ITEMS_PATH)
    assert build_sample(items, date(2026, 11, 2)) == build_sample(items, date(2026, 11, 2))
```

- [ ] **Step 4: 실패를 본다.** Run: `uv run pytest collector/tests/test_sample.py -v` / Expected: FAIL.
- [ ] **Step 5: `make_items.py`, `make_sample.py`를 쓴다.** 샘플은 `random.Random(seed)`로 품종마다 기준 가격을 정하고, 평일만 31일치, 대형유통 30곳(`"A-유통"`… 이름, 지역은 `p_countrycode` 목록의 도시 이름), 전통시장 5곳(`"경동"`, `"칠성"`, `"부전"`, `"양동"`, `"남부"`)에 ±10% 안의 흔들림을 준다. 전체 평균 응답의 `dpr3`·`dpr5`·`dpr6`·`dpr7`도 같은 난수로 만들어, 품종마다 신호가 고루 나오게 한다(비싼 편·보통·싼 편이 모두 있게).
- [ ] **Step 6: 샘플을 만들고 통과를 본다.** Run: `uv run python -m collector.make_sample && uv run pytest -v` / Expected: 모두 PASS, `collector/sample/`에 `category_100.json`~`category_600.json`과 품종 수만큼의 `period/*.json`.
- [ ] **Step 7: 커밋** — `feat(collector): 실제 KAMIS 코드로 품종 목록과 샘플 응답 만들기` (+ `docs/decisions.md` 기록)

---

### Task 6: 파일 쓰기와 수집 순서 전체

**Files:**
- Create: `collector/output.py`, `collector/__main__.py`, `collector/tests/test_output.py`, `collector/tests/test_main.py`, `data/prices.json`(샘플로 만든 결과)
- Modify: `CLAUDE.md`(실행 명령 절 추가)

**Interfaces:**
- Consumes: Task 1~5 전부
- Produces:
  - `output.SampleGuardError(Exception)`, `output.CollectError(Exception)`
  - `output.load_prices(path: Path) -> dict | None`
  - `output.should_skip(existing: dict | None, as_of: date, source: str) -> bool` — 기준일과 출처가 둘 다 같을 때만 참
  - `output.check_sample_guard(existing: dict | None, source: str) -> None` — 새 출처가 `"샘플"`이고 기존 출처가 `"KAMIS"`면 `SampleGuardError`
  - `output.carry_over(entries: list[dict], failed_ids: set[str], existing: dict | None) -> list[dict]` — 실패한 품종은 기존 항목을 그대로(없으면 뺌), 결과는 `id` 순
  - `output.write_prices(path: Path, data: dict) -> None` — 같은 폴더의 임시 파일에 다 쓴 뒤 `os.replace`
  - `__main__.run(source: Source, items: list[Item], out_path: Path, today: date) -> str` — `"updated"` 또는 `"skipped"`. 전체 평균이 모든 부류에서 실패하거나 모든 품종이 실패하면 `CollectError`
  - `__main__.main(argv: list[str] | None = None) -> int` — 성공·건너뜀 0, `CollectError`·`SampleGuardError` 1(이유를 한국어로 표준 오류에 쓴다)

`prices.json` 맨 위 항목: `{"as_of": "2026-11-02", "source": "KAMIS" | "샘플", "generated_at": "<한국 시각 ISO 8601>", "basis": {"compare": "전국 대형유통 평균" | "전국 평균", "season": "KAMIS 전체 평균"}, "threshold_pct": 15, "items": [...]}`. `basis.compare`는 `compute.LARGE_ONLY`로 정한다.

- [ ] **Step 1: 실패하는 시험을 쓴다**

```python
def test_should_skip_needs_same_date_and_source():
    existing = {"as_of": "2026-11-02", "source": "샘플"}
    assert should_skip(existing, date(2026, 11, 2), "샘플") is True
    assert should_skip(existing, date(2026, 11, 2), "KAMIS") is False   # Review Focus 4
    assert should_skip(existing, date(2026, 11, 3), "샘플") is False
    assert should_skip(None, date(2026, 11, 2), "샘플") is False

def test_sample_guard():
    with pytest.raises(SampleGuardError):
        check_sample_guard({"source": "KAMIS"}, "샘플")
    check_sample_guard({"source": "샘플"}, "샘플")
    check_sample_guard({"source": "KAMIS"}, "KAMIS")

def test_carry_over_keeps_old_entry_for_failed():
    existing = {"items": [{"id": "a", "price": 1}, {"id": "b", "price": 2}]}
    out = carry_over([{"id": "a", "price": 9}], {"b", "c"}, existing)
    assert out == [{"id": "a", "price": 9}, {"id": "b", "price": 2}]

def test_write_prices_replaces_whole_file(tmp_path):
    p = tmp_path / "prices.json"
    write_prices(p, {"as_of": "2026-11-02", "items": []})
    assert json.loads(p.read_text(encoding="utf-8"))["as_of"] == "2026-11-02"
    assert list(tmp_path.iterdir()) == [p]     # 임시 파일이 남지 않음

def test_run_with_sample_then_skip(tmp_path):
    out = tmp_path / "prices.json"
    src = SampleSource(SAMPLE_DIR)
    assert run(src, load_items(ITEMS_PATH), out, date(2026, 11, 3)) == "updated"
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["source"] == "샘플" and data["as_of"] == "2026-11-02" and data["items"]
    assert run(src, load_items(ITEMS_PATH), out, date(2026, 11, 3)) == "skipped"

def test_run_keeps_old_value_when_one_item_fails(tmp_path):
    ...  # 품종 하나의 period만 KamisError를 던지는 가짜 Source → 그 품종은 기존 항목 그대로, 나머지는 새 값

def test_run_total_failure_keeps_file(tmp_path):
    ...  # 모든 category가 KamisError → CollectError, 기존 파일 내용 그대로
```

- [ ] **Step 2: 실패를 본다.** Run: `uv run pytest collector/tests/test_output.py collector/tests/test_main.py -v` / Expected: FAIL.
- [ ] **Step 3: `output.py`, `__main__.py`를 쓴다.** `run`의 순서는 설계 5절 그대로: 기존 파일 읽기 → 샘플 덮어쓰기 검사 → 부류 6개 받기(부류 하나가 실패하면 그 부류 품종은 실패로) → 기준일 = 전체 평균 줄들의 `as_of` 가운데 가장 늦은 날 → 건너뛰기 판단 → 품종마다 가게별 값(`as_of - 30일` ~ `as_of`) → `build_entry` → `carry_over` → `write_prices`. `main`은 `make_source(os.environ, 샘플 폴더)`, `today`는 한국 시각(`ZoneInfo("Asia/Seoul")`) 기준.
- [ ] **Step 4: 통과를 본다.** Run: `uv run pytest -v` / Expected: 모두 PASS.
- [ ] **Step 5: 샘플로 화면용 파일을 만든다.** Run: `uv run python -m collector` / Expected: 종료 코드 0, `data/prices.json`의 `source`가 `"샘플"`. 크기를 재서(`wc -c data/prices.json`) 설계의 140KB 짐작과 비교해 보고에 적는다.
- [ ] **Step 6: `CLAUDE.md`에 실행 명령 절을 더한다.** 수집 `uv run python -m collector`, 시험 `uv run pytest`(하나만: `uv run pytest collector/tests/test_compute.py::test_signal_boundaries`), 품종 목록 다시 만들기 `uv run python -m collector.make_items`, 샘플 다시 만들기 `uv run python -m collector.make_sample`.
- [ ] **Step 7: 커밋** — `feat(collector): 화면용 파일 쓰기와 수집 순서 전체` (파일 `data/prices.json`은 `chore(data): 샘플 가격 파일 만들기`로 따로)

---

### Task 7: 화면(목록·검색·상세·총액)과 목록 저장

**Files:**
- Create: `index.html`, `style.css`, `app.js`, `store.js`
- Modify: `CLAUDE.md`(화면 확인 명령 추가)

**Interfaces:**
- Consumes: `data/prices.json`(Task 6의 모양)
- Produces:
  - `store.js` (ES 모듈): `getList(): Promise<{id: string, qty: number}[]>`, `addItem(id): Promise<void>`(개수 1, 이미 있으면 그대로), `removeItem(id): Promise<void>`, `setQty(id, qty): Promise<void>`(1 미만이면 1). 저장 키 `"mp.list.v1"`. localStorage가 오류를 내면 메모리 배열로 이어 간다.
  - `app.js`: 화면 상태는 주소의 `#` 뒤로 나눈다. `#/`(내 목록), `#/item/<id>`(상세). 검색어는 상태로만 둔다.

화면 구성은 설계 8절과 `.superpowers/brainstorm/`의 `layout.html`, `search-detail.html` 예시를 따른다.
- 맨 위: "{M}월 {D}일 기준 · 출처 {source}". `source`가 `"샘플"`이면 그 위에 샘플 띠. `navigator.onLine`이 거짓이면 "인터넷 연결 없음 · {M}월 {D}일 값" 띠.
- 내 목록 줄: 이름(`item · kind`, 품종이 하나뿐인 품목도 그대로), "×{qty}"(2 이상), `unit_price` + `unit_label`("1개당 3,200원", 무게는 "100g당 240원"), 신호. `prices.json`에 없는 id는 회색 "지금 값 없음". 품종 `as_of`가 파일 `as_of`와 다르면 "{M}월 {D}일 값" 작은 글씨.
- 총액 줄: 목록 품종마다 `range[0]×qty` 합 ~ `range[1]×qty` 합, "예상 총액 42,000~47,500원". 값 없는 품종이 있으면 "값 없는 품목 {N}개 제외".
- 검색: 입력값 앞뒤 공백을 지우고, 비어 있으면 내 목록. `item` 또는 `kind`에 검색어가 들어간 품종을 `item`으로 묶어 품목 제목 아래 줄로 보인다. 줄 오른쪽 "＋ 담기" / "✓ 담김".
- 상세: 설계 8절 순서. 30일 추이는 `trend`로 그린 SVG 선(최저·최고 값 글씨). "요즘 시기" 아래 "KAMIS 전체 평균 기준". 맨 아래 −/＋, "목록으로", "목록에서 빼기".
- 목록이 비면 "아래 검색창에서 품목을 찾아 ＋ 담기를 눌러 보세요".
- 숫자는 `toLocaleString("ko-KR")`, 퍼센트는 `Math.round`.

- [ ] **Step 1: `store.js`를 쓴다.**
- [ ] **Step 2: `index.html`, `style.css`, `app.js`를 쓴다.** `<script type="module" src="app.js">`. 누르는 영역은 44px 이상, 검색창은 화면 맨 아래 고정.
- [ ] **Step 3: 화면을 띄운다.** Run: `uv run python -m http.server 8000`(백그라운드) → 앱 안 브라우저로 `http://localhost:8000`을 휴대폰 크기(375×812)로 연다.
- [ ] **Step 4: 확인 목록대로 직접 해 보고 결과를 적는다.**
  - [ ] 첫 화면: 샘플 띠, 기준일, 빈 목록 안내가 보인다
  - [ ] "사과" 검색 → 사과 아래 품종 줄들, "＋ 담기" → "✓ 담김"
  - [ ] "파" 검색 → 대파·쪽파·양파 등 이름에 "파"가 들어간 품종이 모두 나온다
  - [ ] ✕ → 내 목록에 담은 품종, 총액 줄
  - [ ] 줄을 눌러 상세 → −/＋로 개수 2 → "목록으로" → 줄에 "×2", 총액이 바뀜
  - [ ] 브라우저 뒤로 가기로도 상세에서 목록으로 돌아온다
  - [ ] "목록에서 빼기" → 목록과 총액에서 빠짐
  - [ ] 새로고침해도 목록이 남는다
  - [ ] `localStorage.setItem`을 막은 상태(개발자 도구에서 `Storage.prototype.setItem = () => { throw new Error() }` 후 담기)에서도 화면이 멈추지 않는다(Review Focus 5)
  - [ ] `prices.json`에 없는 id를 저장 공간에 넣고 새로고침 → "지금 값 없음", 총액에 "값 없는 품목 1개 제외"
- [ ] **Step 5: `CLAUDE.md` 실행 명령에 화면 확인(`uv run python -m http.server 8000`, 375px)을 더한다.**
- [ ] **Step 6: 커밋** — `feat(screen): 목록·검색·상세·총액 화면과 목록 저장`

---

### Task 8: 오프라인과 홈 화면 추가

**Files:**
- Create: `sw.js`, `manifest.webmanifest`, `tools/make_icons.py`, `icons/icon-192.png`, `icons/icon-512.png`, `icons/apple-touch-icon.png`(180px)
- Modify: `index.html`(manifest·아이콘 링크, 서비스 워커 등록), `app.js`(홈 화면 추가 안내)

**Interfaces:**
- Consumes: Task 7의 화면 파일 이름
- Produces: 캐시 이름 상수 `CACHE = "mp-v1"`(`sw.js` 맨 위. 화면 파일을 고칠 때마다 숫자를 올린다 — `CLAUDE.md`에 한 줄 적는다)

- [ ] **Step 1: 아이콘을 만든다.** `tools/make_icons.py`는 `zlib`과 `struct`로 PNG를 직접 쓴다(단색 바탕에 흰 원 하나). Run: `uv run python tools/make_icons.py` / Expected: 세 파일 생성.
- [ ] **Step 2: `manifest.webmanifest`를 쓴다.** `name: "장보기 가격"`, `short_name: "장보기 가격"`, `start_url: "./"`, `scope: "./"`, `display: "standalone"`, `orientation: "portrait"`, 아이콘 192·512.
- [ ] **Step 3: `sw.js`를 쓴다.** 설치 때 화면 파일(`./`, `index.html`, `style.css`, `app.js`, `store.js`, `manifest.webmanifest`, 아이콘)을 미리 저장. 요청 처리: 주소가 `data/prices.json`으로 끝나면 네트워크 먼저(성공하면 저장본을 바꿈), 실패하면 저장본. 그 밖은 저장본 먼저. 활성화 때 `CACHE`가 아닌 옛 묶음을 지운다.
- [ ] **Step 4: 홈 화면 추가 안내를 더한다.** 처음 열 때 맨 위 "홈 화면에 추가하면 앱처럼 쓰고, 인터넷 없이도 열려요"와 닫기 버튼. 닫으면 localStorage `"mp.installHint.closed"`. 이미 앱 모양(`matchMedia("(display-mode: standalone)")`)이면 보이지 않는다.
- [ ] **Step 5: 확인 목록대로 직접 해 보고 결과를 적는다.**
  - [ ] 개발자 도구 Application(또는 `navigator.serviceWorker.controller`)에서 서비스 워커가 활성화
  - [ ] 서버를 끈 뒤 새로고침 → 화면과 마지막 가격으로 열리고, 오프라인 띠가 보인다(브라우저가 오프라인으로 알 때)
  - [ ] 서버를 다시 켜고 `prices.json`의 `as_of`를 바꿔 새로고침 → 새 기준일이 보인다(네트워크 먼저)
  - [ ] 안내를 닫고 새로고침 → 다시 안 나온다
- [ ] **Step 6: 커밋** — `feat(screen): 오프라인 저장과 홈 화면 추가`

---

### Task 9: 예약 실행과 Pages 배포

**Files:**
- Create: `.github/workflows/collect.yml`
- Modify: `CLAUDE.md`(예약 실행 설명), `docs/decisions.md`(지금 상태)

**Interfaces:**
- Consumes: `uv run python -m collector`의 종료 코드(0 성공·건너뜀, 1 실패)

워크플로 내용:
- 이름 `collect`. 실행 조건: `schedule: - cron: "0 10 * * 1-5"`(평일 한국 19시. 설계상 실행 시각은 키를 받은 뒤 KAMIS가 값을 올리는 시각을 보고 다시 정한다), `workflow_dispatch`("지금 실행" 버튼), `push: branches: [main]`.
- `concurrency: { group: collect, cancel-in-progress: false }`.
- 작업 `collect`(`push`가 아닐 때만): `permissions: contents: write`. 환경변수 `KAMIS_CERT_KEY: ${{ secrets.KAMIS_CERT_KEY }}`, `KAMIS_CERT_ID: ${{ secrets.KAMIS_CERT_ID }}`. 둘 중 하나라도 비면 `echo "키 없음: 수집을 건너뜁니다"` 후 나머지 단계를 건너뛴다. 키가 있으면 `actions/checkout@v4` → `astral-sh/setup-uv@v6` → `uv run python -m collector` → `data/prices.json`이 바뀌었을 때만 `github-actions[bot]` 이름으로 `chore(data): <기준일> 가격 갱신` 커밋·푸시.
- 작업 `deploy`(`collect`가 성공했거나 건너뛰었을 때, `always() && needs.collect.result != 'failure'`): `permissions: pages: write, id-token: write`, `environment: github-pages`. `actions/checkout@v4`(`ref: main`, 방금 커밋까지) → `_site/`에 `index.html style.css app.js store.js sw.js manifest.webmanifest icons/ data/`만 복사 → `actions/upload-pages-artifact@v3`(`path: _site`) → `actions/deploy-pages@v4`.

- [ ] **Step 1: `collect.yml`을 쓴다.**
- [ ] **Step 2: 문법을 확인한다.** Run: `uv run --with pyyaml python -c "import yaml,sys; d=yaml.safe_load(open('.github/workflows/collect.yml')); print(sorted(d['jobs']))"` / Expected: `['collect', 'deploy']`.
- [ ] **Step 3: `CLAUDE.md`에 예약 실행 한 단락**(언제 돌고, 키가 없으면 무엇을 하고, 배포가 어떻게 되는지)을 더하고, `docs/decisions.md` "지금 상태"를 "1차 구현 완료, 사람이 할 일 남음"으로 고친다.
- [ ] **Step 4: 커밋** — `feat(actions): 평일 저녁 수집과 Pages 배포`
- [ ] **Step 5: 사용자에게 할 일을 알리고 푸시 허락을 받는다.** (1) 저장소 설정 → Pages → 출처를 "GitHub Actions"로. (2) 푸시 허락. 푸시하면 `push`로 배포만 돈다. (3) Actions 탭에서 "Run workflow"로 "지금 실행" → "키 없음"이 찍히고 배포가 성공하는지. (4) 폰에서 `https://pakyong.github.io/MktPrice/`를 열어 샘플 띠, 홈 화면 추가, 비행기 모드로 열기(설계 11절 성공 기준 1). 성공 기준 2(가족 시험)는 사용자가 원할 때, 3(평일 사흘 자동 커밋)은 키를 받은 뒤 확인한다.
