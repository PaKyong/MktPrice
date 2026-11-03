# 시세 찾아보기 + 즐겨찾기 화면 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 화면을 `docs/design.md` 8절대로 "맨 위 검색창 + 즐겨찾기 + 부류별 전체 품목 + 증권 앱 모양 상세"로 바꾸고, 장보기 목록·개수·예상 총액·영수증 생김새와 영수증 글꼴을 뺀다.

**Architecture:** 화면은 지금처럼 빌드 없는 HTML·CSS·JS다. `store.js`는 목록 대신 즐겨찾기(품종 코드와 이름)를 저장하고 옛 목록을 한 번 옮긴다. `index.html`은 "맨 위 막대(검색창 또는 ←/☆) + 기준일 줄 + 본문" 뼈대로, `style.css`는 새 색으로 다시 쓰고, `app.js`는 줄 하나를 만드는 함수 하나로 즐겨찾기·전체 품목·검색 결과를 모두 그린다. 수집 쪽(`collector/`, `data/`)은 건드리지 않는다.

**Tech Stack:** HTML·CSS·JS(ES 모듈, 라이브러리 없음). 시험은 Python 3.14 + uv + pytest(배포 파일 목록 시험만 해당).

**Spec:** `docs/design.md` 8·9·11절 (정한 이유는 `docs/decisions.md`의 2026-11-03 기록 마지막 네 건)

## Global Constraints

- 색은 `docs/design.md` 8절 표의 값을 그대로 CSS 변수로 쓴다: `--bg` 바탕, `--text` 글씨, `--muted` 흐린 글씨, `--soft` 옅은 바탕, `--line` 옅은 선, `--down` 내림(빨강), `--up` 오름(파랑), `--band` 샘플 띠. 어두운 화면 값은 `@media (prefers-color-scheme: dark)`에서 바꾼다.
- 값이 내리면 `--down`(빨강)과 ▼, 오르면 `--up`(파랑)과 ▲. "싼 편"은 빨강, "비싼 편"은 파랑.
- %는 정수로 보인다(`Math.round`). 부호 대신 화살표를 쓴다("▼14%", "▲5%"). 반올림해 0이면 흐린 "0%", 값이 없으면 흐린 "-".
- 글꼴은 폰 기본 글꼴(`-apple-system, BlinkMacSystemFont, "Apple SD Gothic Neo", "Noto Sans KR", "Malgun Gothic", sans-serif`), 굵기는 400과 700, 숫자는 `font-variant-numeric: tabular-nums`.
- 그림자와 그러데이션은 쓰지 않는다. 누르는 곳은 모두 44px 이상. 키보드 초점 테두리(`:focus-visible`)는 남긴다.
- 화면 문구(정확히 이대로):
  - 검색창: 안내 "품목 검색 (예: 양파)", 읽어 주기 이름 "품목 검색", ✕의 이름 "검색 지우기"
  - 기준일 줄 "{YYYY.MM.DD} 기준 · 출처 {출처}" / 샘플 띠 "샘플 데이터 · 실제 가격 아님" / "인터넷 연결 없음 · {M}월 {D}일 값" / "홈 화면에 추가하면 앱처럼 쓰고, 인터넷 없이도 열려요" + "닫기"
  - "즐겨찾기" / "상세 화면에서 ☆를 누르면 여기 모여요" / "전체 품목" / 부류 칸 "{부류} {N}"
  - `"{검색어}" 찾은 품종 {N}개` / `"{검색어}"에 맞는 품목이 없어요. 다른 이름으로 찾아 보세요.`
  - 줄: "100g당" · "1{단위}당" / "싼 편" · "비싼 편" / "{M}월 {D}일 값" / "지금 값 없음"
  - 상세: ← 이름 "뒤로", ☆ 이름 "즐겨찾기에 넣기", ★ 이름 "즐겨찾기에서 빼기" / "{부류} · {MM.DD} 기준 · 대형유통 {N}곳 평균"(비교 기준이 전국 평균이면 "조사처 {N}곳 평균") / "{단위 가격}원" + "/{단위}" / "평년보다 ▼14% · 보통" · "평년 값 없음" / "최고 {값}" · "최저 {값}" / "30일 · {조사 단위} 기준" · "추이 값이 없어요" / 정보 줄 "{조사 단위}", "가게마다(가운데 절반)", "1주 전보다", "1개월 전보다", "1년 전보다" / "* 평년·지난 값 비교는 KAMIS 전체 평균 기준" / "지금 값 없음. 철이 지나 KAMIS 조사 값이 없는 품목이에요."
  - 가격 파일을 못 받았을 때 "가격 파일을 불러오지 못했어요. 인터넷에 연결한 뒤 다시 열어 주세요."(지금 그대로)
- 화면 파일을 고치는 Task마다 `sw.js`의 `CACHE`를 하나씩 올린다: Task 1 `mp-v7`, Task 2 `mp-v8`, Task 3 `mp-v9`, Task 4 `mp-v10`.
- 화면에는 자동 시험이 없다(설계 2·11절). 앱 안 브라우저(`.claude/launch.json`의 "web")를 375×812로 열어 직접 확인한다. 확인 전에는 늘 서비스 워커와 저장본을 지우고 다시 연다(옛 화면이 보이지 않게):
  ```js
  for (const r of await navigator.serviceWorker.getRegistrations()) await r.unregister();
  for (const k of await caches.keys()) await caches.delete(k);
  location.reload();
  ```
- `data/prices.json`과 `collector/`는 손대지 않는다. 커밋은 CLAUDE.md 4절(한국어, Co-Authored-By 한 줄). 푸시는 사용자가 말할 때만.

## Review Focus

1. 옛 장보기 목록이 있는 폰: 처음 열 때 한 번만, 담은 순서대로 즐겨찾기로 옮겨지고 옛 저장 칸(`mp.list.v1`)이 지워져야 한다. 저장 공간을 못 쓰는 브라우저에서도 화면은 열려야 한다 → Task 2 Step 5.
2. 즐겨찾기에 있지만 가격 파일에 없는 품종(철이 지남): 첫 화면에 "지금 값 없음" 줄로 보이고, 누르면 상세가 열리고, ★로 뺄 수 있어야 한다 → Task 2 Step 5, Task 3 Step 4.
3. 값이 모자란 품종: 추이가 하루치(`216-00` 갓), 평년 값 없음(30개, 예 `111-10`), 반올림하면 0이 되는 %(`280-00` 브로콜리 -0.2%) → 작은 그래프는 비고, % 자리는 흐린 "-", 0은 "▼0%"가 아니라 흐린 "0%" → Task 2 Step 6, Task 3 Step 4.
4. 가장 긴 이름 "물오징어 연근해(신선 냉장)"(`619-03`)을 폭 320px에서: 이름이 줄바꿈되고 그래프·가격·%와 겹치지 않아야 한다 → Task 2 Step 6.
5. 상세 주소로 바로 열었을 때(새로고침, 받은 링크): ←가 앱 밖으로 나가지 않고 첫 화면으로 가야 한다. 검색 결과에서 들어갔다 오면 검색어와 결과가, 전체 품목 중간에서 들어갔다 오면 보던 자리가 그대로여야 한다 → Task 3 Step 4.

---

### Task 1: 영수증 글꼴 파일과 글꼴 도구 지우기

**Files:**
- Delete: `fonts/receipt-regular.woff2`, `fonts/receipt-bold.woff2`, `fonts/OFL.txt`, `tools/make_font.py`, `tools/tests/test_make_font.py`
- Modify: `style.css`(맨 위 `@font-face` 두 개와 `MktReceipt`를 쓰는 `font-family`), `index.html`(글꼴 `preload` 줄), `sw.js`(`SHELL`의 글꼴 두 줄, `CACHE`), `.github/workflows/collect.yml:103`(`cp -r` 줄의 `fonts`), `pyproject.toml`·`uv.lock`, `.gitignore`(`/tools/fonts-src/` 설명), `CLAUDE.md`(실행 명령의 글꼴 줄들)
- Test: `tools/tests/test_site_files.py`(그대로 둔다)

**Interfaces:**
- Produces: 화면은 폰 기본 글꼴로 보인다. 다음 Task가 `style.css`를 통째로 다시 쓰므로 여기서는 글꼴 부분만 고친다.

- [ ] **Step 1: 파일 지우기** — `git rm` 으로 위 다섯 파일을 지운다. `tools/__init__.py`, `tools/make_icons.py`, `tools/tests/test_site_files.py`는 남긴다. `tools/fonts-src/`(git 밖 원본)는 손대지 않는다.
- [ ] **Step 2: 개발용 패키지 빼기** — `uv remove --dev fonttools brotli`. 둘 다 글꼴 도구만 쓰던 것이다. → 확인: `pyproject.toml`의 `dev`에 `pytest`만 남는다.
- [ ] **Step 3: 글꼴을 부르던 곳 고치기** — `style.css`의 `@font-face` 두 개를 지우고 `MktReceipt`를 Global Constraints의 폰 기본 글꼴 목록으로 바꾼다. `index.html`의 `<link rel="preload" href="fonts/receipt-regular.woff2" …>` 줄, `sw.js` `SHELL`의 `fonts/…` 두 줄, `collect.yml` `cp -r` 줄의 `fonts`를 지운다. `CACHE`를 `mp-v7`로 올린다. `.gitignore`의 설명은 "예전 영수증 글꼴의 원본. 지금은 쓰지 않지만 내 컴퓨터에 남아 있어 git에 들어가지 않게 둔다"로 바꾼다.
- [ ] **Step 4: CLAUDE.md 고치기** — "영수증 글꼴 만들기" 줄을 지우고, "품종 목록 다시 만들기"(실행 명령) 줄 끝의 "바꾼 뒤에는 글꼴도 다시 만든다(아래)."와 예약 실행 절의 "그 뒤 받아 와서 `tools/make_font.py`로 … 내 컴퓨터에만 있다)." 문장을 지운다.
- [ ] **Step 5: 시험** — `uv run pytest` → 모두 통과(글꼴 시험은 지웠고, `test_deploy_copies_every_offline_file`이 `SHELL`과 배포 복사 목록이 맞는지 본다). `grep -rn "font\|글꼴" index.html app.js sw.js .github CLAUDE.md` → 폰 기본 글꼴 목록 말고는 나오지 않는다.
- [ ] **Step 6: 화면 확인** — 앱 안 브라우저에서 저장본을 지우고 다시 연다. 네트워크 요청 목록에 `fonts/`가 없고, 콘솔 오류가 없고, 화면이 폰 기본 글꼴로 보인다.
- [ ] **Step 7: 커밋** — `chore(screen): 영수증 글꼴 파일과 글꼴 만들기 도구를 지움`. 본문에 왜 지웠는지(폰 기본 글꼴로 바꿈, 품종 목록을 바꿀 때마다 글꼴을 다시 만들 일이 없어짐)를 쓴다.

### Task 2: 즐겨찾기 저장, 맨 위 검색창, 첫 화면과 검색

**Files:**
- Modify(통째로 다시 씀): `store.js`, `index.html`의 `<body>`, `style.css`
- Modify: `app.js`(머리 주석, 상태, 글자 도우미, 목록·검색·훑어보기·합계 그리기를 첫 화면·검색·줄 그리기로 바꿈, 상세의 아래 고정 영역 단추를 지움), `sw.js`(`CACHE` → `mp-v8`)

**Interfaces:**
- Produces(`store.js`): 저장 칸 이름 `"mp.fav.v1"`, 옛 칸 `"mp.list.v1"`.
  - `getFavorites(): Promise<Array<{id: string, name: string}>>` — 넣은 순서, 복사본.
  - `addFavorite(id: string, name: string): Promise<void>` — 이미 있으면 그대로, 없으면 맨 뒤에.
  - `removeFavorite(id: string): Promise<void>`
- Produces(`app.js`, Task 3이 씀):
  - `state = { data, byId, favorites, query, chip }` — `favorites`는 `getFavorites()` 결과, `chip`은 마지막으로 누른 부류 칸.
  - `pctText(x: number | null): { text: string, cls: "down" | "up" | "muted" }` — Global Constraints의 % 규칙.
  - `refresh(): Promise<void>` — 즐겨찾기를 다시 읽고 `render()`.
  - `render(): void` — 주소가 `#/item/{id}`이면 상세(`renderDetail`), 아니면 검색어가 있으면 검색 결과, 없으면 첫 화면.
- Produces(`index.html`): 맨 위 `<header id="bar-home" class="bar">` 안에 지금의 `search-form`·`search`·`search-clear`, 그 아래 `<div id="home-head">` 안에 `asof`, `print-sample`, `print-offline`, `banner-install`(+`install-close`), 그 아래 `<main id="view">`. `dock`, `total`, `dock-list`, `dock-detail`, 톱니 그림, 영수증 제목은 없앤다.

- [ ] **Step 1: `store.js` 다시 쓰기** — 위 세 함수. `load()`는 메모리에 있으면 그것을, 없으면 `mp.fav.v1`을 읽고, 그 칸이 비어 있고 `mp.list.v1`이 있으면 그 항목들의 `{id, name}`을 같은 순서로(같은 `id`는 한 번만) 옮겨 `mp.fav.v1`에 저장하고 `mp.list.v1`을 지운다. 저장 공간이 오류를 내면 지금처럼 이 화면을 연 동안만 메모리로 이어 간다. 머리 주석의 "장보기 목록"을 "즐겨찾기"로 바꾸고, Promise 방식인 이유(나중에 가족 공유) 설명은 남긴다.
- [ ] **Step 2: `index.html` 뼈대와 `style.css` 다시 쓰기** — 위 Produces의 뼈대. `.bar`는 `position: sticky; top: 0`, 높이 `--bar-h: 60px`. 부류 칸 줄 `.chips`는 `position: sticky; top: var(--bar-h)`, 한 줄에 옆으로 밀기(지금처럼). 샘플 띠는 `--band` 바탕. 줄 `.row`는 `display: grid; grid-template-columns: minmax(0, 1fr) 56px auto; gap: 12px; min-height: 56px`이고, 이름은 줄바꿈되며(말줄임 없음) 가격 칸은 `white-space: nowrap; text-align: right`. 묶음 사이에만 `1px solid var(--line)`. 검색창과 부류 칸은 `--soft` 바탕에 둥근 모서리, 칠한 부류 칸은 `--text` 바탕에 `--bg` 글씨. 색은 Global Constraints의 변수.
- [ ] **Step 3: 줄 그리기** — `app.js`에 아래 함수를 두고, 지금의 `signedPct`, `signalLine`, `normalText`, `unitPriceText`, `signalClass`, `signalMark`, `renderList`, `renderTotal`, `groupNodes`, `renderBrowse` 가운데 안 쓰게 되는 것은 지운다. 아직 옛 상세 본문이 쓰는 `normalText`, `signedPct`, `signalClass`, `pair`, `trendChart`는 Task 3까지 남긴다. `state.browseCategory`는 `state.chip`으로 이름을 바꾼다.
  - `sparkline(trend: Array<[string, number]>): SVGSVGElement | null` — `viewBox="0 0 56 24"`, 회색(`--muted`) 선 하나, 축·글자 없음, 값이 둘보다 적으면 `null`.
  - `rowNode(e): HTMLLIElement` — `<a class="row" href="#/item/{id}">` 안에 왼쪽(이름 `displayName(e)`, 그 아래 작게 `perUnit(e)`, 신호가 싼 편·비싼 편이면 그 말을 `down`·`up` 색으로, 품종 기준일이 파일 기준일과 다르면 "{M}월 {D}일 값"), 가운데(`sparkline`이 `null`이면 빈 칸), 오른쪽(`won(e.unit_price)` 굵게, 그 아래 `pctText(e.change.normal)`).
  - `missingRowNode(fav: {id: string, name: string}): HTMLLIElement` — 같은 링크 모양에 이름(`fav.name || fav.id`)과 흐린 "지금 값 없음"만.
  - `browseOrder(): Array<품종>` — 부류 순서 `BROWSE_ORDER`(지금 값 그대로) → 품목 가나다(`localeCompare(…, "ko")`) → 파일 순서.
- [ ] **Step 4: 첫 화면과 검색 그리기**
  - `renderTop(): void` — 기준일 줄, 샘플 띠, 인터넷 없음 줄(지금 함수를 새 문구로).
  - `renderHome(): void` — 제목 "즐겨찾기"와 즐겨찾기 줄(가격 파일에 있으면 `rowNode`, 없으면 `missingRowNode`) 또는 빈 안내, 그 아래 제목 "전체 품목", 부류 칸 줄, 부류마다 제목과 `rowNode` 줄들. 부류 칸 누르기는 지금 `jumpTo`를 쓰되 내리는 거리에서 `--bar-h`와 칸 줄 높이를 함께 뺀다. 칸 줄의 옆 위치를 다시 그려도 지키는 것은 지금처럼.
  - `renderSearch(): void` — `browseOrder()`에서 품목 이름이나 품종 이름에 검색어가 든 것만, 위에 `"{q}" 찾은 품종 {N}개`, 없으면 안내 문구.
  - 검색창: 입력하면 `state.query`를 바꿔 `render()`. ✕는 검색어가 있을 때만 보이고, 누르면 검색어를 지우고 자판을 닫는다. "아무것도 안 친 채로 누르면 훑어보기"는 지운다(전체 품목이 늘 보이므로). 손가락으로 내리기 시작하면 자판을 닫는 것은 남긴다.
  - 상세 화면에서는 `home-head`를 숨긴다. 상세 본문(`renderDetail`)은 이 Task에서 아래 고정 영역 단추(개수, 목록으로, 빼기, 담기)와 `renderDetailDock`만 지우고 나머지는 둔다(Task 3에서 다시 쓴다).
  - `sw.js`의 `CACHE`를 `mp-v8`로.
- [ ] **Step 5: 확인 — 옮기기와 즐겨찾기 줄** — 저장본을 지운 뒤 콘솔에서:
  ```js
  localStorage.clear();
  localStorage.setItem("mp.list.v1", JSON.stringify([
    { id: "245-00", name: "양파", qty: 2 }, { id: "999-99", name: "옛 품종", qty: 1 }, { id: "245-00", name: "양파", qty: 1 }]));
  location.reload();
  ```
  → 즐겨찾기에 "양파"(가격·그래프·%)와 "옛 품종"(흐린 "지금 값 없음") 두 줄이 이 순서로 보인다. `localStorage.getItem("mp.list.v1")`은 `null`, `JSON.parse(localStorage.getItem("mp.fav.v1"))`은 `[{id:"245-00",name:"양파"},{id:"999-99",name:"옛 품종"}]`. 한 번 더 다시 열어도 같다. `localStorage.clear()` 뒤 다시 열면 빈 안내 문구가 보인다.
- [ ] **Step 6: 확인 — 첫 화면과 검색** (375×812)
  - 검색창이 맨 위에 있고 끝까지 내려도 붙어 있다. 부류 칸 줄은 검색창 바로 아래에 붙는다. "수산물" 칸을 누르면 수산물 제목이 칸 줄 아래에 가리지 않고 보인다.
  - "파"를 치면 `"파" 찾은 품종 5개`와 줄 다섯 개, 즐겨찾기·전체 품목은 사라진다. ✕를 누르면 돌아온다. "가나다"를 치면 없다는 안내.
  - 줄 색: 양파(`245-00`, 평년 -14.4%)는 빨간 "▼14%", 고등어 국산(염장)은 파란 "▲51%"와 파란 "비싼 편", 사과 후지는 빨간 "싼 편". 브로콜리(`280-00`, -0.2%)는 흐린 "0%". `111-10`(평년 없음)은 흐린 "-". 갓(`216-00`, 추이 하루치)은 그래프 칸이 비어 있다.
  - 폭 320으로 바꿔 "물"을 쳐서 "물오징어 연근해(신선 냉장)" 줄을 본다: 이름이 두 줄로 내려가고 그래프·가격과 겹치지 않는다.
  - 콘솔 오류가 없다. 화면을 찍어 둔다.
- [ ] **Step 7: 커밋** — `feat(screen): 맨 위 검색창과 즐겨찾기·전체 품목 첫 화면으로 바꿈`. 본문에 배경(담기·총액을 빼고 시세 찾기 중심으로), 바꾼 것(저장, 뼈대, 줄, 옛 목록 옮기기), 검증(위 확인)을 쓴다.

### Task 3: 상세 화면 (←, ☆, 증권 앱 모양 본문, 보던 자리로 돌아오기)

**Files:**
- Modify: `index.html`(상세용 맨 위 막대), `style.css`(막대 단추, 상세 본문), `app.js`(`renderDetail` 다시 씀, 돌아가기, 주소 바뀜 처리), `sw.js`(`CACHE` → `mp-v9`)

**Interfaces:**
- Consumes: Task 2의 `addFavorite`, `removeFavorite`, `state`, `pctText`, `refresh`, `render`.
- Produces(`index.html`): `<header id="bar-detail" class="bar" hidden>` 안에 `<button id="back" aria-label="뒤로">←</button>`와 `<button id="star" aria-pressed="false">☆</button>`. 상세에서는 `bar-home`을 숨기고 `bar-detail`을 보인다.
- Produces(`app.js`): `renderDetail(id: string): void`, `goBack(): void`, 상태에 `cameFromApp: boolean`, `homeScroll: number`.

- [ ] **Step 1: 맨 위 막대** — ☆는 즐겨찾기가 아니면 "☆"(이름 "즐겨찾기에 넣기", `aria-pressed="false"`), 즐겨찾기면 "★"(이름 "즐겨찾기에서 빼기", `aria-pressed="true"`). 누르면 `addFavorite(id, 이름)` 또는 `removeFavorite(id)` 뒤 `refresh()`. 이름은 가격 파일에 있으면 `displayName(e)`, 없으면 즐겨찾기에 저장된 이름.
- [ ] **Step 2: 돌아가기** — `history.scrollRestoration = "manual"`. `hashchange`에서 첫 화면(`#/` 또는 빈 주소)에서 `#/item/…`로 갈 때 `state.homeScroll = window.scrollY`, `state.cameFromApp = true`로 두고 맨 위로 올린다. 상세에서 첫 화면으로 올 때는 그린 뒤 `window.scrollTo(0, state.homeScroll)` 하고 `cameFromApp`을 `false`로. `goBack()`은 `cameFromApp`이면 `history.back()`, 아니면 `location.hash = "#/"`. 검색어는 `state.query`와 검색창 값에 남아 있으므로 돌아오면 검색 결과가 그대로 보인다.
- [ ] **Step 3: 본문 다시 쓰기** — 8절 "상세 화면" 순서대로: 이름(굵게), 흐린 줄 "{부류} · {MM.DD} 기준 · 대형유통 {N}곳 평균", 큰 굵은 `won(e.unit_price)`와 흐린 "/{e.unit_label}", "평년보다 {pctText} · {e.signal}"(평년 없으면 흐린 "평년 값 없음"), 30일 그래프(지금 `trendChart`를 쓰되 선과 점은 `--text`, 바닥선은 `--line` 점선, 그 아래 흐린 "30일 · {e.unit} 기준". 추이가 없으면 "추이 값이 없어요"), 정보 줄(왼쪽 흐린 이름, 오른쪽 값: `e.unit`/`won(e.price)`, "가게마다(가운데 절반)"/"{lo}~{hi}/{unit_label}", 지난 값 % 셋 가운데 `null`이 아닌 것만 `pctText`로), 맨 아래 흐린 각주. 가격 파일에 없는 품종은 이름과 "지금 값 없음. 철이 지나 …" 안내만. 다 쓴 뒤 안 쓰게 된 `normalText`, `signedPct`, `signalClass`를 지운다. `sw.js`의 `CACHE`를 `mp-v9`로.
- [ ] **Step 4: 확인** (375×812, 저장본을 지운 뒤)
  - 첫 화면에서 양파 줄을 누른다 → 위 막대에 ←와 ☆, 본문이 위 순서로 보이고 "평년보다 ▼14% · 보통"이 빨갛다. ☆를 누르면 ★로 바뀌고, ←로 돌아오면 즐겨찾기 맨 뒤에 양파가 있다. 다시 들어가 ★를 누르고 돌아오면 빠져 있다.
  - 전체 품목의 수산물 칸을 눌러 내려간 자리에서 줄 하나를 열고 ← → 같은 자리로 돌아온다. "파" 검색 결과에서 대파를 열고 ← → `"파" 찾은 품종 5개`가 그대로.
  - 주소창에 `#/item/245-00`을 직접 넣고 새로고침 → ←를 누르면 첫 화면(앱 밖으로 나가지 않음).
  - `#/item/999-99`(Task 2 Step 5의 옛 품종을 즐겨찾기에 넣어 둔 상태) → "지금 값 없음" 안내와 ★, ★를 누르면 빠진다.
  - `#/item/216-00`(추이 하루치)과 `#/item/111-10`(평년 없음) → 오류 없이 열리고, 111-10은 "평년 값 없음".
  - 콘솔 오류가 없다. 화면을 찍어 둔다.
- [ ] **Step 5: 커밋** — `feat(screen): 상세 화면을 증권 앱 모양으로 바꾸고 즐겨찾기 단추를 둠`.

### Task 4: 홈 화면 앱 설정, 문서, 전체 확인

**Files:**
- Modify: `manifest.webmanifest`(`background_color`, `theme_color` → `"#FFFFFF"`), `index.html`(`theme-color` 두 줄: 밝은 화면 `#ffffff`, 어두운 화면 `#121417`), `sw.js`(`CACHE` → `mp-v10`), `CLAUDE.md`(화면 확인 줄), `docs/decisions.md`("지금 상태")

- [ ] **Step 1: 설정 색 바꾸기** — 위 값으로. `CACHE`를 `mp-v10`으로.
- [ ] **Step 2: CLAUDE.md** — "화면 확인" 줄의 "검색 → 담기 → 개수 → 총액 → 상세 → 빼기"를 "검색 → 상세 → ☆ → 첫 화면 즐겨찾기 → ★로 빼기"로 바꾼다.
- [ ] **Step 3: 설계 11절 화면 확인 전부** — 저장본을 지운 뒤 375×812에서 11절 목록을 하나씩 본다. Task 2·3에서 본 것 말고 여기서 새로 보는 것:
  - 어두운 화면(`resize_window`의 `colorScheme: "dark"`): 바탕 `#121417`, 글씨가 읽히고, 빨강·파랑이 어두운 화면 값으로 바뀐다. 샘플 띠 글씨가 읽힌다.
  - 인터넷 끊기: 한 번 연 뒤 네트워크를 끊고(`navigator.onLine`을 바꿀 수 없으면 `preview_stop`으로 서버를 멈추고) 다시 열면 마지막 가격으로 열리고 "인터넷 연결 없음 · 11월 2일 값"이 보인다.
  - 홈 화면 안내 쪽지와 "닫기": 닫고 다시 열면 나오지 않는다.
  - `uv run pytest` → 모두 통과.
- [ ] **Step 4: 결정 기록 "지금 상태"** — 2026-11-03 줄에 "`docs/plan-stock.md`(Task 1~4)대로 구현했다(서비스 워커 `mp-v10`)"를 붙인다.
- [ ] **Step 5: 커밋** — `feat(screen): 홈 화면 앱 색을 새 바탕에 맞추고 구현을 마침`. 문서 고친 것도 같은 커밋.
