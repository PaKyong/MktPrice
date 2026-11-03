# 이마트 상품(참가격) 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 한국소비자원 참가격에서 이마트 값을 받아 `data/emart.json`을 만들고, 화면에 "이마트" 칸(평소 값·행사 때 최저 값)과 이마트 상세 화면을 더한다.

**Architecture:** 수집은 받기(`collector/champrice.py`: 설명서의 달 목록, API 나눠 받기)와 계산·파일 쓰기(`collector/emart.py`: 이마트 줄 고르기, 대표값·평소 값·행사 최저, `uv run python -m collector.emart`)로 나눈다. 파일 쓰기는 지금 `collector/output.py`의 `load_prices`·`write_prices`를 그대로 쓴다. 화면(`app.js`)은 `data/emart.json`을 따로 받아 KAMIS 품종과 같은 지도(`state.byId`)에 넣고, 줄과 상세만 이마트용으로 그린다. 예약 실행은 KAMIS 커밋 다음에 참가격을 돌리고, 실패해도 배포한 뒤 맨 끝 작업에서 실패로 끝낸다.

**Tech Stack:** Python 3.12+ 표준 라이브러리만(urllib, json, re, collections), uv, pytest. 화면은 빌드 없는 HTML·CSS·JS(ES 모듈). GitHub Actions.

**Spec:** `docs/design.md` 15절(이유는 `docs/decisions.md`의 2026-11-03 참가격 기록 다섯 건)

## Global Constraints

- 파이썬은 `uv run`으로 돌린다. 새 패키지는 더하지 않는다. 함수마다 타입 힌트와 Google 스타일 한국어 docstring(`anthropic-skills:python-style-guide`), 주변 코드(`collector/kamis.py`)의 모양을 따른다.
- 키는 환경변수 `DATA_GO_KR_KEY`(Secrets 같은 이름). 요청에는 머리말 `Authorization: Infuser <키>`로 싣고, 주소·오류 메시지·출력에 키를 넣지 않는다.
- 주소: 설명서 `https://infuser.odcloud.kr/oas/docs?namespace=15083256/v1`(키 없이 읽힌다), API `https://api.odcloud.kr/api` + 설명서의 경로(예: `/15083256/v1/uddi:4f684682-d8a2-446e-be30-adfffdaae05a`). 요청 변수 `page`(1부터), `perPage`, `returnType=JSON`. 응답은 `{"page", "perPage", "totalCount", "currentCount", "matchCount", "data": [줄, …]}`이고 줄의 칸은 `상품명`, `조사일`(`YYYY-MM-DD`), `판매가격`(정수), `판매업소`, `제조사`, `세일여부`, `원플러스원`.
- 숫자: 한 번에 받는 줄 수 `PER_PAGE = 10000`, 기간 `MONTHS = 3`(가장 새 달과 그 앞 두 달), 다시 시도 간격은 `collector.kamis.RETRY_WAITS`(2·4·8초), 기다림 `collector.kamis.TIMEOUT_SECONDS`.
- 이마트 가게: 이름이 `"이마트"`로 시작하고 `"이마트24"`로 시작하지 않는 곳.
- `data/emart.json` 모양(Task 2가 만들고 Task 3·4가 읽는다):
  ```json
  {"source": "참가격", "generated_at": "2026-11-13T19:05:12+09:00",
   "months": ["2026-07-24", "2026-08-28", "2026-09-25"], "as_of": "2026-09-25",
   "items": [{"name": "오뚜기 크런치 치킨너겟(480g)", "usual": 10980,
              "low": {"price": 4970, "day": "2026-09-11", "pct": -55},
              "last_day": "2026-09-25", "stores": 118,
              "history": [["2026-09-25", 10980, 118], ["2026-09-11", 4970, 113]]}]}
  ```
  `months`는 받은 달의 기준일(설명서 이름 끝 날짜), `as_of`는 받은 줄의 가장 늦은 조사일, `low`는 행사가 없었으면 `null`, `stores`는 `last_day`의 이마트 지점 수, `history`는 최근 날부터. `items`는 상품명 순. 쓰기는 `collector.output.write_prices`(BOM 없는 UTF-8, 줄바꿈 없음, 통째로 바꿔 넣기).
- 화면 문구(정확히 이대로). `{M}.{D}`는 앞 0 없이("9.25"), 숫자는 `toLocaleString("ko-KR")`.
  - 부류 칸 "이마트 {N}"(다른 부류 뒤, 맨 끝)
  - 줄 왼쪽 아래: "평소 값" / "평소 값 · 행사 없음", 상품의 `last_day`가 파일 `as_of`와 다르면 뒤에 " · {M}월 {D}일 값". 검색 결과와 즐겨찾기에서만 맨 앞에 작은 표시 "이마트"
  - 줄 오른쪽: 굵게 "{평소 값}원", 그 아래 빨강 "행사 {값}"(원 없음) 또는 흐린 "-"
  - 기준일 줄 끝에 " · 이마트 {M}.{D} 조사"(`data/emart.json`이 있을 때만)
  - 상세: "이마트 · {M}.{D} 조사 · 이마트 {N}곳" / "{평소 값}원" + 흐린 "평소 값" / 빨강 "행사 때 {값}원 ({M}.{D}) · 평소보다 ▼{N}%" 또는 흐린 "3개월 동안 행사 없음" / 제목 "최근 3개월 조사" / 줄마다 "{M}.{D}"와 "{값}원"(행사 최저 날은 빨강) / "* 한국소비자원 참가격. 행사 표시가 없어서, 3개월 동안 조사한 이마트 값 중 가장 높은 값을 평소 값으로 봤어요."
  - 파일에 없는 이마트 상품의 상세: "지금 값 없음. 최근 3개월 동안 이마트 조사 값이 없는 상품이에요." **(이 계획에서 처음 정함, 보고에서 알린다)**
- 이마트 상품의 즐겨찾기 id는 `"이마트:" + 상품명`, 이름은 상품명. 상세 주소는 모든 품종에서 `#/item/${encodeURIComponent(id)}`.
- 화면 파일을 고치는 Task마다 `sw.js`의 `CACHE`를 하나씩 올린다: Task 3 `mp-v12`, Task 4 `mp-v13`.
- 화면 확인은 앱 안 브라우저(`.claude/launch.json`의 "web")를 375×812로 열고, 확인 전에 늘 저장본을 지운다:
  ```js
  for (const r of await navigator.serviceWorker.getRegistrations()) await r.unregister();
  for (const k of await caches.keys()) await caches.delete(k);
  location.reload();
  ```
- 키가 오기 전 화면 확인용 `data/emart.json`은 9월 CSV(`/tmp/claude-1000/-home-ym-workspace-market-price/3500b051-4017-4afb-955c-1ae8388e54ac/scratchpad/champrice/price_2026_09.csv`, cp949)로 Task 3에서 만든다. 이 파일과 `scratch/`는 커밋하지 않고 Task 4 끝에서 지운다. `data/prices.json`은 손대지 않는다.
- 커밋은 CLAUDE.md 4절(한국어, 배경·바꾼 것·검증, Co-Authored-By 한 줄). 푸시는 사용자가 말할 때만.

## Review Focus

1. 상품명에 `%`가 든 상품(이마트 416개 중 4개, 예: "롯데 드림카카오 82%(86g)"): 줄을 누르면 상세가 열리고 ☆/★가 되며 그 주소로 새로고침해도 열려야 한다. 지금 `render()`의 `decodeURIComponent`는 인코딩하지 않은 `%`에서 오류를 낸다 → Task 3 Step 3, Task 4 Step 4.
2. `data/emart.json`이 없는 사이트(키를 넣기 전 지금 배포): 서비스 워커 설치가 실패하지 않고 오프라인으로 열리며, 화면은 이마트 칸과 이마트 조사일 없이 지금과 같아야 한다 → Task 3 Step 6, Task 4 Step 2·4.
3. 첫 실행에서 `data/emart.json`이 처음 생길 때: git이 아직 모르는 파일이라 `git diff --quiet`로는 "바뀐 것 없음"이 되어 커밋이 안 된다 → Task 5 Step 1(`git status --porcelain`).
4. 서버가 한 번에 주는 줄 수가 요청(`PER_PAGE`)보다 적을 때(상한이 있을 때): 모든 줄을 받아야 한다 → Task 1 Step 1 `test_rows_pages_until_total_even_if_server_gives_fewer`.
5. 즐겨찾기에 넣은 이마트 상품이 다음 달 파일에서 빠질 때: 첫 화면에 "이마트" 표시와 "지금 값 없음" 줄, 상세에 이마트용 안내, ★로 빼기 → Task 3 Step 6, Task 4 Step 4.

---

### Task 1: 참가격 받기

**Files:**
- Create: `collector/champrice.py`
- Test: `collector/tests/test_champrice.py`

**Interfaces:**
- Consumes: `collector.kamis.RETRY_WAITS`, `collector.kamis.TIMEOUT_SECONDS`
- Produces:
  - `DOCS_URL: str`, `API_BASE: str`, `PER_PAGE: int = 10000`
  - `class ChampriceError(Exception)` — 받기가 끝내 실패함(메시지에 키 없음).
  - `@dataclass(frozen=True) class Month: path: str; as_of: date` — 설명서의 달 하나(경로와 이름 끝 기준일).
  - `parse_months(doc: Dict[str, Any]) -> List[Month]` — 설명서 JSON의 `paths`에서 `get.summary` 끝이 `_YYYYMMDD` 또는 `_MM/DD/YYYY`인 것만, 기준일 오래된 것부터.
  - `class MonthSource(Protocol)`: `months() -> List[Month]`, `rows(month: Month) -> Iterator[Dict[str, Any]]`
  - `class ChampriceSource` (`MonthSource`를 따름): `__init__(self, key: str, opener: Callable[..., Any] = urllib.request.urlopen, sleep: Callable[[float], None] = time.sleep)`. `months()`는 설명서를 키 없이 받아 `parse_months`. `rows(month)`는 `page=1`부터 받아 `data`의 줄을 하나씩 내주고, 지금까지 받은 줄 수가 `totalCount` 이상이거나 `data`가 비면 멈춘다.

- [ ] **Step 1: 실패하는 시험 쓰기** — `test_kamis.py`의 `FakeOpener`처럼 응답을 차례로 돌려주는 도우미를 두되, 받은 것이 `urllib.request.Request`이므로 `req.full_url`과 `req.get_header("Authorization")`를 모은다.
  - `test_parse_months_reads_both_date_shapes`: `paths`에 summary `"…_20260925"`, `"…_09/24/2021"`, `"…_20260828"`, 날짜 없는 `"…정보"` 넷 → `[Month(path2, date(2021,9,24)), Month(path3, date(2026,8,28)), Month(path1, date(2026,9,25))]`.
  - `test_months_reads_docs_without_key`: 응답 하나(설명서 JSON) → 결과가 `parse_months`와 같고, 주소가 `DOCS_URL`, `Authorization` 머리말이 없다.
  - `test_rows_pages_until_total_count`: 1쪽 `{"totalCount": 3, "data": [a, b]}`, 2쪽 `{"totalCount": 3, "data": [c]}` → `list(rows(m)) == [a, b, c]`. 주소에 `page=1`, `page=2`, `perPage=10000`, `returnType=JSON`이 있고 앞부분이 `API_BASE + m.path`, 머리말은 `"Infuser SECRETKEY"`, 주소에 `SECRETKEY`가 없다.
  - `test_rows_pages_until_total_even_if_server_gives_fewer`: `totalCount` 5에 쪽마다 2·2·1줄 → 5줄, 요청 3번.
  - `test_rows_stops_on_empty_page`: `totalCount` 10인데 2쪽 `data`가 `[]` → 1쪽 줄만 내주고 멈춘다(무한히 돌지 않는다).
  - `test_retries_then_gives_up_without_leaking_key`: `OSError("…SECRETKEY…")` 네 번 → `ChampriceError`, 메시지에 `SECRETKEY` 없음, 기다린 간격 `[2, 4, 8]`. 세 번 실패 뒤 성공하면 그 응답을 쓴다.
- [ ] **Step 2: 시험이 실패하는지 보기** — `uv run pytest collector/tests/test_champrice.py -v` → `ModuleNotFoundError: collector.champrice`.
- [ ] **Step 3: `collector/champrice.py` 쓰기** — 위 Interfaces. 머리 docstring에 무엇을 받는지와 키를 머리말로 싣는 까닭(주소가 기록에 남지 않게)을 쓴다. 다시 시도는 `KamisSource._get`과 같은 모양(응답을 읽으면 그대로 돌려주고, `OSError`·`ValueError`면 기다렸다 다시, 끝내 실패하면 예외 이름만 담아 `ChampriceError`).
- [ ] **Step 4: 시험 통과 보기** — `uv run pytest collector/tests/test_champrice.py -v` → 모두 PASS. `uv run pytest` → 모두 PASS.
- [ ] **Step 5: 커밋** — `feat(collector): 참가격 달 목록과 한 달 치 줄을 나눠 받는 부분을 더함`.

### Task 2: 이마트 계산과 `collector.emart` 명령

**Files:**
- Create: `collector/emart.py`
- Test: `collector/tests/test_emart.py`

**Interfaces:**
- Consumes: Task 1의 `Month`, `MonthSource`, `ChampriceSource`, `ChampriceError`; `collector.output.load_prices`, `collector.output.write_prices`
- Produces:
  - `EMART_PATH = Path(__file__).parent.parent / "data" / "emart.json"`, `SOURCE_NAME = "참가격"`, `MONTHS = 3`, `KST = ZoneInfo("Asia/Seoul")`
  - `@dataclass(frozen=True) class ShopRow: name: str; day: date; price: int; store: str`
  - `is_emart(store: str) -> bool`
  - `parse_rows(raw: Iterable[Mapping[str, Any]]) -> List[ShopRow]` — 이마트 줄만. 상품명이 비었거나, 조사일이 `YYYY-MM-DD`가 아니거나, 판매가격이 0보다 큰 정수(또는 정수 글자)가 아닌 줄은 그 줄만 건너뛴다.
  - `representative(prices: List[int]) -> int` — 가장 많이 나온 값, 횟수가 같으면 높은 값.
  - `build_products(rows: List[ShopRow]) -> List[Dict[str, Any]]` — Global Constraints의 상품 항목, 상품명 순.
  - `build_emart(raw: Iterable[Mapping[str, Any]], months: List[Month], now: datetime) -> Dict[str, Any]` — 파일 전체. 상품이 하나도 없으면 `ChampriceError("이마트 줄이 하나도 없습니다. 응답 칸 이름(상품명, 조사일, 판매가격, 판매업소)이나 가게 이름 모양을 확인하세요. 기존 파일은 그대로 둡니다.")`.
  - `run(source: MonthSource, out_path: Path, now: datetime) -> str` — `"updated"` 또는 `"skipped"`.
  - `main() -> int` — `uv run python -m collector.emart`.

- [ ] **Step 1: 실패하는 시험 쓰기** — 줄 만드는 도우미 `raw(name, day, price, store)`(칸 이름은 응답과 같은 한글).
  - `test_is_emart`: `"이마트강릉점"` 참, `"이마트24(본사)"`·`"롯데슈퍼전농점"`·`"신세계백화점본점"` 거짓.
  - `test_parse_rows_keeps_emart_and_skips_bad_rows`: 이마트 좋은 줄 2개(판매가격 하나는 정수 `4970`, 하나는 글자 `"10980"`), 이마트24 줄, 롯데슈퍼 줄, 이마트인데 가격 `""`·`None`·`"abc"`·`0`, 조사일 `"2026/09/25"`, 상품명 `""` → 2개만 남는다.
  - `test_representative_most_common_then_higher`: `[10980]*3 + [4970]*2 → 10980`, `[4970, 10980] → 10980`, `[3950, 3950, 4150] → 3950`.
  - `test_products_usual_low_and_history`: 치킨너겟 8-28 10980(1곳), 9-11 4970(2곳), 9-25 10980(3곳) → `usual 10980`, `low {"price": 4970, "day": "2026-09-11", "pct": -55}`, `last_day "2026-09-25"`, `stores 3`, `history [["2026-09-25",10980,3],["2026-09-11",4970,2],["2026-08-28",10980,1]]`.
  - `test_products_no_sale_when_all_same`: 고향만두 두 날 모두 7980 → `low is None`.
  - `test_products_low_tie_takes_latest_day`: 7-24 3950, 8-28 4150, 9-11 3950 → `low.day == "2026-09-11"`.
  - `test_build_emart_file`: 두 상품("신라면(5개입)", "고향만두(900g)") → `source "참가격"`, `months` = 받은 `Month`들의 기준일 글자, `as_of` = 가장 늦은 조사일, `generated_at` = `now.isoformat(timespec="seconds")`, `items`의 이름이 `["고향만두(900g)", "신라면(5개입)"]`.
  - `test_build_emart_raises_without_emart_rows`: 롯데슈퍼 줄뿐 → `ChampriceError`.
  - `run` 시험은 `months()`와 `rows()`를 흉내 내고 부른 달을 모으는 `FakeSource`로, 파일은 `tmp_path`에:
    - `test_run_writes_latest_three_months`: 달 4개 → `rows`를 부른 달이 뒤의 3개, 결과 `"updated"`, 파일이 생긴다.
    - `test_run_skips_when_newest_month_already_in_file`: 기존 파일 `months`에 가장 새 달 기준일이 있음 → `"skipped"`, `rows`를 부르지 않고 파일이 그대로.
    - `test_run_keeps_file_on_failure`: `rows`가 `ChampriceError`를 던지거나 이마트 줄이 없음 → 예외가 나오고 기존 파일 내용이 그대로.
  - `main` 시험(`monkeypatch`로 환경변수와 `EMART_PATH`, `ChampriceSource`를 바꾼다):
    - `test_main_without_key_skips`: `DATA_GO_KR_KEY` 없음 → `0`, 출력에 "참가격 키 없음", 파일이 생기지 않는다.
    - `test_main_returns_1_on_failure`: 받기가 `ChampriceError` → `1`, 오류 출력에 "참가격 수집 실패".
- [ ] **Step 2: 시험이 실패하는지 보기** — `uv run pytest collector/tests/test_emart.py -v` → `ModuleNotFoundError: collector.emart`.
- [ ] **Step 3: `collector/emart.py` 쓰기** — 위 Interfaces. `pct`는 `round((low - usual) / usual * 100)`. `run`은 (1) `source.months()`의 뒤 `MONTHS`개, 없으면 `ChampriceError("설명서에 달 목록이 없습니다.")`, (2) 기존 파일(`load_prices`)의 `months`에 가장 새 달 기준일이 있으면 `"skipped"`, (3) 세 달의 `rows`를 이어 `build_emart`, (4) `write_prices`, (5) 한 줄 요약 `참가격 {as_of}: 이마트 상품 {N}개, 이마트 줄 {M}개, 달 {기준일들}`. `main`은 키가 없으면 `참가격 키 없음: 이마트 값을 건너뜁니다`를 찍고 0, `ChampriceError`면 `참가격 수집 실패: {err}`를 오류 출력에 찍고 1, 건너뛰면 `참가격: 새 달이 없어 건너뜁니다`, 쓰면 `참가격: {EMART_PATH}를 새로 썼습니다`. 머리 docstring에 명령과 키 이름을 쓴다(`collector/__main__.py` 모양).
- [ ] **Step 4: 시험 통과 보기** — `uv run pytest collector/tests/test_emart.py -v` → 모두 PASS. `uv run pytest` → 모두 PASS. `env -u DATA_GO_KR_KEY uv run python -m collector.emart` → "참가격 키 없음…", 종료 코드 0, `data/emart.json` 없음.
- [ ] **Step 5: 커밋** — `feat(collector): 이마트 평소 값·행사 때 최저 값을 계산해 data/emart.json을 쓰는 명령을 더함`.

### Task 3: 화면 — 이마트 줄, 전체 품목의 "이마트" 칸, 검색, 즐겨찾기

**Files:**
- Modify: `app.js`(상태, 파일 받기, 기준일 줄, 줄 그리기, 첫 화면, 검색, 주소 인코딩), `style.css`(이마트 표시 한 줄), `sw.js`(`CACHE` → `mp-v12`)
- Create(확인용, 커밋하지 않음): `scratch/emart_from_csv.py`

**Interfaces:**
- Consumes: Task 2의 `data/emart.json` 모양, `collector.emart.build_emart`, `collector.output.write_prices`, `collector.champrice.Month`
- Produces(Task 4가 씀):
  - `state.emart`: `data/emart.json` 내용 또는 `null`. `state.byId`에 이마트 상품도 `{...항목, id: "이마트:" + name, emart: true}`로 들어 있다.
  - `EMART_ID = "이마트:"`
  - `mdot(iso: string): string` — `"2026-09-25"` → `"9.25"`
  - `fetchJson(path: string): Promise<object | null>` — 지금 `fetchPrices`를 경로를 받게 바꾼 것(`cache: "no-cache"`, 실패하면 `null`).
  - `setData(data, emart): void`

- [ ] **Step 1: 확인용 파일 만들기** — `scratch/emart_from_csv.py`: 인자로 받은 CSV를 `csv.DictReader(open(path, encoding="cp949"))`로 읽어 `build_emart(rows, [Month("csv", date(2026, 9, 25))], datetime.now(KST))`를 `write_prices(EMART_PATH, …)`로 쓴다. `uv run python -m scratch.emart_from_csv "<Global Constraints의 CSV 경로>"` → `data/emart.json`이 생기고 요약에 이마트 상품 416개. 보고에서 "확인용"이라고 밝힌다.
- [ ] **Step 2: 받기와 기준일 줄** — `init()`과 `reloadPrices()`가 `fetchJson("data/prices.json")`과 `fetchJson("data/emart.json")`을 함께 받는다. 가격 파일을 못 받으면 지금 안내 그대로(이마트 파일이 있어도). `reloadPrices`는 두 파일 중 하나라도 `generated_at`이 바뀌었을 때만 다시 그린다. `renderTop()`은 `state.emart`가 있으면 기준일 줄 끝에 `" · 이마트 {mdot(as_of)} 조사"`.
- [ ] **Step 3: 줄 그리기와 주소** — 
  - `emartRowNode(e, showTag: boolean): HTMLLIElement` — `rowNode`와 같은 `<a class="row">` 세 칸: 왼쪽 상품명과 흐린 줄(`showTag`면 맨 앞 `<span class="tag">이마트</span>`, "평소 값"/"평소 값 · 행사 없음", 날짜 다르면 " · {M}월 {D}일 값"), 가운데 빈 `<span>`, 오른쪽 `won(e.usual)`과 그 아래 `row__pct down` "행사 {값}" 또는 `row__pct muted` "-".
  - `itemRow(e, showTag: boolean)` — `e.emart`면 `emartRowNode`, 아니면 `rowNode(e)`.
  - `missingRowNode(fav)` — id가 `EMART_ID`로 시작하면 흐린 줄 맨 앞에 "이마트" 표시.
  - 모든 줄의 `href`를 `#/item/${encodeURIComponent(e.id)}`로 바꾼다(`render()`의 `decodeURIComponent`는 그대로).
  - `style.css`: `.tag { margin-right: 4px; padding: 1px 5px; border-radius: 4px; background: var(--soft); color: var(--muted); font-size: 11px; }`
- [ ] **Step 4: 첫 화면과 검색** — `renderHome()`: 즐겨찾기 줄은 `itemRow(e, true)`. 전체 품목은 지금 부류들 뒤에 `state.emart`가 있으면 "이마트" 부류를 더하고(상품명 `localeCompare(…, "ko")` 순, `itemRow(e, false)`), 칸은 "이마트 {N}". `renderSearch()`: 지금 결과 뒤에 이마트 상품 가운데 상품명에 검색어가 든 것(같은 순서)을 `itemRow(e, true)`로 붙인다. 찾은 개수 문구는 둘을 합친 수. `CACHE`를 `mp-v12`로.
- [ ] **Step 5: 시험** — `uv run pytest` → 모두 PASS.
- [ ] **Step 6: 확인** (375×812, 저장본을 지운 뒤). 이마트 상세는 Task 4에서 그리므로 이 Task에서는 이마트 줄을 누르지 않는다.
  - 기준일 줄이 "… 기준 · 출처 … · 이마트 9.25 조사". 부류 칸 맨 끝 "이마트 416"을 누르면 이마트 제목으로 건너뛴다. "오뚜기 크런치 치킨너겟(480g)" 줄은 "10,980원"과 빨간 "행사 4,970", "고향만두(900g)"는 "7,980원", "평소 값 · 행사 없음", 흐린 "-". 이마트 칸 안 줄에는 "이마트" 표시가 없다.
  - "배추"를 치면 KAMIS 배추 품종들 뒤에 "이마트" 표시가 붙은 "배추(1.5~2kg)"(5,980원, 행사 3,480)가 나온다. 개수 문구가 둘을 합친 수다.
  - 폭 320에서 가장 긴 이름 "쿤달 허니 앤 마카다미아 헤어 트리트먼트 베이비파우더향(718ml)"이 줄바꿈되고 가격과 겹치지 않는다.
  - 콘솔에서 `localStorage.setItem("mp.fav.v1", JSON.stringify([{id: "이마트:없어진 상품(1kg)", name: "없어진 상품(1kg)"}])); location.reload();` → 즐겨찾기에 "이마트" 표시와 "지금 값 없음" 줄.
  - `data/emart.json`을 잠시 다른 이름으로 바꾸고 다시 열면 이마트 칸과 " · 이마트 … 조사"가 없고 나머지는 지금과 같다(확인 뒤 되돌린다).
  - 콘솔 오류가 없다. 화면을 찍어 둔다.
- [ ] **Step 7: 커밋** — `feat(screen): 전체 품목에 이마트 칸을 더하고 검색·즐겨찾기에 이마트 상품을 섞음`. `data/emart.json`과 `scratch/`는 넣지 않는다(`git status`로 확인).

### Task 4: 화면 — 이마트 상세 화면과 오프라인

**Files:**
- Modify: `app.js`(상세), `style.css`(필요하면 상세 한두 줄), `sw.js`(이마트 파일 다루기, `CACHE` → `mp-v13`), `tools/tests/test_site_files.py`

**Interfaces:**
- Consumes: Task 3의 `state.emart`, `state.byId`의 `emart: true` 항목, `EMART_ID`, `mdot`, `won`, `info`, `renderStar`
- Produces: `renderEmartDetail(e): void`. `sw.js`에 `const EMART = "data/emart.json";`

- [ ] **Step 1: 상세 그리기** — `renderDetail(id)`에서 `displayName(e)`를 부르기 전에 `e?.emart`면 `renderEmartDetail(e)`로 넘긴다(이마트 항목에는 품목·품종 이름이 없다. ☆ 이름은 상품명). Global Constraints의 상세 문구 순서대로: `detail__name`, `detail__meta`, `detail__price`(평소 값 + `detail__unit` "평소 값"), `detail__normal`에 행사 줄(빨강) 또는 흐린 "3개월 동안 행사 없음", 제목(`cat` 모양) "최근 3개월 조사", `info` 줄들(`info(mdot(day), won(price))`, 행사 최저 날 값은 `down`), `detail__foot`. 값이 없는 id가 `EMART_ID`로 시작하면 이름과 "지금 값 없음. 최근 3개월 동안 이마트 조사 값이 없는 상품이에요."만(KAMIS 안내 대신).
- [ ] **Step 2: 서비스 워커** — `pricesFirstFromNetwork(event)`를 `liveFirstFromNetwork(event, path)`로 바꿔 `PRICES`와 `EMART` 둘 다 같은 방식(네트워크 먼저, 3초, 저장본)으로 다룬다. `install`의 저장 목록에는 `EMART`를 넣지 않는다(파일이 없으면 설치가 통째로 실패한다). 처음 받는 데 성공하면 그때 저장된다. `CACHE`를 `mp-v13`으로.
- [ ] **Step 3: 배포 파일 시험** — `test_deploy_copies_every_offline_file`이 `EMART`도 읽어 배포 복사 목록(`data`)에 있는지 본다. `uv run pytest` → 모두 PASS.
- [ ] **Step 4: 확인** (375×812, 저장본을 지운 뒤)
  - 치킨너겟 상세: "이마트 · 9.25 조사 · 이마트 {N}곳", "10,980원 평소 값", 빨간 "행사 때 4,970원 (9.11) · 평소보다 ▼55%", 목록 "9.25 10,980원", "9.11 4,970원"(빨강), 맨 아래 각주. 고향만두 상세는 흐린 "3개월 동안 행사 없음".
  - "롯데 드림카카오 82%(86g)" 줄을 누르면 상세가 열리고, ☆를 누르면 ★가 되고, 그 주소로 새로고침해도 열린다. ←로 돌아오면 첫 화면 즐겨찾기에 "이마트" 표시와 함께 보인다. ★로 빼면 사라진다.
  - Task 3 Step 6의 "없어진 상품" 즐겨찾기를 누르면 이마트용 안내가 보이고 ★로 뺄 수 있다.
  - 한 번 연 뒤 네트워크를 끊고(오프라인) 다시 열면 이마트 칸과 상세가 그대로 열린다. `data/emart.json`을 잠시 치우고 저장본을 지운 뒤 열면 서비스 워커가 설치되고(`navigator.serviceWorker.controller`가 생김) 오프라인으로도 열린다(확인 뒤 되돌린다).
  - 어두운 화면에서 이마트 표시와 빨간 행사 글씨가 읽힌다. 콘솔 오류가 없다. 화면을 찍어 둔다.
- [ ] **Step 5: 확인용 파일 지우기** — `data/emart.json`과 `scratch/`를 지운다(이번 작업에서 만든 임시 파일). `git status`에 둘이 없다.
- [ ] **Step 6: 커밋** — `feat(screen): 이마트 상품 상세 화면을 더하고 이마트 파일도 오프라인으로 열리게 함`.

### Task 5: 예약 실행과 문서

**Files:**
- Modify: `.github/workflows/collect.yml`, `CLAUDE.md`(실행 명령, 예약 실행과 배포), `docs/decisions.md`(지금 상태)

**Interfaces:**
- Consumes: Task 2의 `uv run python -m collector.emart`(키 없으면 0, 실패하면 1)
- Produces: `collect` 작업의 출력 `emart`(참가격 단계의 결과 `success`/`failure`/`skipped`)

- [ ] **Step 1: 예약 실행 고치기**
  - 머리 주석에 참가격을 더한다. `collect` 작업 `env`에 `DATA_GO_KR_KEY: ${{ secrets.DATA_GO_KR_KEY }}`.
  - `actions/checkout`과 `setup-uv`의 `if:`를 지워 늘 돌게 한다(KAMIS 키가 없어도 참가격은 돈다). KAMIS 단계들의 `if:`는 그대로.
  - KAMIS "바뀌었으면 커밋·푸시" 다음에 `id: emart`, `continue-on-error: true`인 "이마트 값(참가격) 받기" 단계(`uv run python -m collector.emart`). 주석: 실패해도 KAMIS 커밋과 배포는 하고 맨 끝에서 실패로 끝낸다. KAMIS가 실패한 날은 이 단계까지 가지 않고 다음 실행에서 받는다.
  - 그다음 `if: steps.emart.outcome == 'success'`인 "이마트 파일 바뀌었으면 커밋·푸시": `git status --porcelain -- data/emart.json`이 비면 "이마트 파일이 그대로라 커밋하지 않습니다"로 끝. 아니면 `as_of`를 읽어 `chore(data): 이마트 ${as_of} 값 갱신`으로 커밋하고(봇 이름·주소는 KAMIS 단계와 같게 다시 설정), `git pull --rebase` 뒤 푸시. `git diff`가 아니라 `git status`를 쓰는 까닭(처음 생기는 파일)을 주석에 쓴다.
  - `collect`에 `outputs: emart: ${{ steps.emart.outcome }}`.
  - 새 작업 `emart-check`: `needs: [collect, deploy]`, `if: always() && needs.collect.outputs.emart == 'failure'`, 한 단계에서 `echo "이마트 값(참가격)을 받지 못했습니다. 기존 data/emart.json은 그대로입니다. collect 작업의 '이마트 값(참가격) 받기' 기록을 보세요."` 뒤 `exit 1`.
- [ ] **Step 2: 시험** — `uv run pytest` → 모두 PASS(배포 복사 목록 시험 포함). 바뀐 `collect.yml`을 다시 읽어 들여쓰기와 `if:` 식을 확인한다.
- [ ] **Step 3: CLAUDE.md** — "실행 명령"에 `- 이마트 값(참가격) 받기: \`uv run python -m collector.emart\` — 키(환경변수 \`DATA_GO_KR_KEY\`)가 없으면 건너뛴다. 새 달이 있을 때만 최근 3개 달을 받아 \`data/emart.json\`을 쓴다.` 한 줄. "예약 실행과 배포"에 Secrets `DATA_GO_KR_KEY`, 참가격은 KAMIS 커밋 다음에 돌고 바뀌었을 때만 `chore(data): 이마트 <조사일> 값 갱신`으로 커밋하며, 실패하면 배포 뒤 `emart-check`가 실패로 끝낸다는 것을 한두 문장으로. `data/emart.json`도 손으로 고치지 않는다.
- [ ] **Step 4: 결정 기록 "지금 상태"** — 2026-11-03 참가격 줄을 "`docs/plan-emart.md`(Task 1~5)대로 구현했다(서비스 워커 `mp-v13`). 남은 사람 할 일: 공공데이터포털 가입과 활용 신청, Secrets에 `DATA_GO_KR_KEY`, 푸시 뒤 \"Run workflow\"로 첫 실행 확인"으로 고친다.
- [ ] **Step 5: 커밋** — `feat(collect): 평일 예약 실행에서 참가격 이마트 값도 받아 커밋함`. 문서 고친 것도 같은 커밋.
- [ ] **Step 6: 푸시 뒤 확인(사용자가 푸시를 허락한 뒤, 사람과 함께)**
  - 키를 넣기 전 "Run workflow": `collect` 기록에 "참가격 키 없음", 실행 전체가 성공, 사이트는 지금과 같다.
  - 키를 넣은 뒤 "Run workflow": 봇 커밋 `chore(data): 이마트 2026-09-25 값 갱신`(또는 그 뒤 날짜)이 생기고 사이트에 이마트 칸이 보인다. 요약 줄의 이마트 상품 수가 400개 안팎인지 본다.
  - 첫 실행에서 401이 오면(머리말 인증이 안 됨) 요청 방식을 `serviceKey` 주소 변수로 바꿀지 사용자와 정한다. 받은 줄 수가 23만 줄보다 크게 적으면 `PER_PAGE` 상한을 의심한다. 둘 다 설계 15절 "아직 모르는 것"이다.
