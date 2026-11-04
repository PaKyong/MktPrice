# 화면 새로 그리기(선반 앞에서 한 손으로) 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 화면을 `docs/design.md` 8절대로 다시 그린다. 아래에 떠 있는 검색창, 큰 제목, 조용한 목록, 상세 아래 먹색 가격표 받침, Geist 숫자. 기능과 동작은 그대로다.

**Architecture:** 빌드 없는 HTML·CSS·JS 그대로다. 스크롤은 지금처럼 창 전체가 하고, 검색창(첫 화면)과 가격표 받침(상세)만 화면 아래에 고정한다. 자판이 올라오면 CSS 변수 `--kb`(자판 높이)만큼 둘을 올린다. 숫자 글꼴은 Geist에서 숫자만 잘라 `fonts/`에 넣고 서비스 워커가 저장한다. 수집 쪽(`collector/`, `data/`)은 건드리지 않는다.

**Tech Stack:** HTML·CSS·JS(ES 모듈, 라이브러리 없음). 글꼴 도구와 시험은 Python 3 + uv + pytest + fontTools.

**Spec:** `docs/design.md` 8절(15·16·17절의 동작은 그대로). 정한 이유는 `docs/decisions.md`의 2026-11-04 "화면을 새로 그린다" 기록 세 건. 시안은 `.superpowers/brainstorm/redesign-v3.html`(git 밖, 받침 색 단추에서 "먹색"이 정한 모습).

## Global Constraints

- 색은 설계 8절 표 그대로 CSS 변수로 둔다(밝은 / 어두운). `--bg` `#ffffff`/`#000000`, `--text` `#000000`/`#ffffff`, `--sub` `#4a515b`/`#aab1ba`, `--muted` `#6b737d`/`#8d949e`, `--soft` `#f3f4f6`/`#17191d`, `--line` `#e6e8eb`/`#26292e`, `--down` `#d9201c`/`#ff5a52`, `--down-soft` `#fef0ef`/`#3b1514`, `--up` `#1c5bd0`/`#6aa1ff`, `--up-soft` `#ecf1fc`/`#142039`, `--star` `#b07a00`/`#ffd23f`, `--dock` `#000000`/`#1e2024`, `--dock-down` `#ff6b63`, `--dock-up` `#7fb0ff`, `--tag` `#ffe14d`. 어두운 값은 `@media (prefers-color-scheme: dark)`에서 바꾼다.
- 글꼴: 한글과 "원"은 `-apple-system, BlinkMacSystemFont, "Apple SD Gothic Neo", "Noto Sans KR", "Malgun Gothic", sans-serif`. 가격 숫자만 `.num`(Geist, 600, `tabular-nums`, `letter-spacing: -0.02em`). 굵기는 400·600, 제목만 700. "원"은 `<small>`로 한 단계 작게(22→15, 26→17, 64→30).
- 크기(px): 제목 30, 묶음 제목 20, 줄 이름 17, 줄 아래 14, 줄 가격 22, 단위·날짜 13, 작은 표시 12, 상세 이름 26, 상세 가격 64, 소제목 17, 판정 19, 가격표 값 26.
- 테두리 상자를 쓰지 않는다. 누르는 곳은 44px 이상. `:focus-visible` 테두리는 남긴다. `prefers-reduced-motion: reduce`면 움직임을 끈다.
- 화면 문구(정확히 이대로. `{M}월 {D}일`은 지금의 `md()`):
  - 첫 화면: "장보기 가격" / "{출처} {M}월 {D}일 값, 이마트 {M}월 {D}일 조사"(이마트 파일이 없으면 쉼표 앞까지, 출처는 `data.source` 그대로 "KAMIS"·"샘플") / "샘플 값이에요. 실제 가격이 아니에요." / "인터넷 연결 없음. {M}월 {D}일 값이에요." / "가격이 {M}월 {D}일 뒤로 안 바뀌었어요" / "홈 화면에 추가하면 앱처럼 쓰고, 인터넷 없이도 열려요" + "닫기" / "즐겨찾기" / "길게 눌러 끌면 순서를 바꾸고, 옆으로 밀면 빠져요" / "상세 화면에서 ☆를 누르면 여기 모여요" / "전체 품목" / 칸·부류 제목은 이름과 흐린 개수를 따로 / 모아 보기 제목 "평년보다 {기준}% 넘게 싼 품종"·"…비싼 품종"
  - 검색: 안내 "품목 검색 (예: 양파)", 읽어 주기 "품목 검색", ✕ "검색 지우기" / `"{q}"{로|으로} 찾은 품종 {N}개` / `"{q}"에 맞는 품목이 없어요. 다른 이름으로 찾아 보세요.`
  - 줄: "평년보다 {n}% 싸요" · "평년보다 {n}% 비싸요" · "평년과 같아요" · "평년 값 없음" / "{M}월 {D}일 값" / "100g당" · "1{단위}당" / "행사 때 {값}원" · "행사 없음" · "이마트" · "이마트 {N}곳" · "평소 값" / "지금 값 없음" · "이마트 값 받는 중"
  - 상세: "뒤로", "즐겨찾기에 넣기", "즐겨찾기에서 빼기" / "{단위}당, 대형마트 {N}곳 평균"(전국 평균 기준이면 "조사처 {N}곳 평균") / "{M}월 {D}일 값" / "30일" · "최고 {값}" · "최저 {값}" · "추이 값이 하루치뿐이에요" / "지난 값과 비교" · "1주 전보다"·"1개월 전보다"·"1년 전보다" + "{n}% 올랐어요"·"{n}% 내렸어요"·"같아요" · "{조사 단위} 값" / "평년과 지난 값은 KAMIS 전체 평균으로 견줘요." / "지금 값이 없어요. 철이 지나 KAMIS 조사 값이 없는 품목이에요."(이마트 두 문구는 지금 그대로) / 띠 "즐겨찾기에 넣었어요" · "즐겨찾기에서 뺐어요" · "{이름}, 즐겨찾기에서 뺐어요" + "되돌리기"
  - 이마트 상세: "이마트 {묶음}"(없으면 "이마트") / "이마트 {N}곳 평소 값, {M}월 {D}일 조사" / "행사 때 {값}원" + "{M}월 {D}일, 평소보다 {n}% 싸요" · "3개월 동안 행사 없음" / "최근 3개월 조사" / "한국소비자원 참가격. 행사 표시가 없어서 3개월 동안 본 값 가운데 가장 높은 값을 평소 값으로 봤어요."
  - 받침: "가격표와 견주기" / "진한 칸은 대형마트 가운데 절반" · "진한 칸은 조사한 {N}곳" · "진한 칸은 행사 최저부터 평소 값까지" / "평균" · "행사 최저" · "평소 값" / "가격표 {단위}당" · "가격표 값" / 안내 "값 넣기" / "가격표에 적힌 값을 넣으면 바로 알려 줘요" / 판정 말은 지금 `judgeKamis`·`judgeEmart` 그대로이되 덧말 끝 "비쌈"→"비싸요", "쌈"→"싸요"
- 화면 파일을 고치는 Task마다 `sw.js`의 `CACHE`를 올린다: Task 1 `mp-v20`, Task 2 `mp-v21`, Task 3 `mp-v22`, Task 4 `mp-v23`, Task 5 `mp-v24`.
- 화면은 자동 시험이 없다(설계 11절). 앱 안 브라우저로 `http://localhost:8000`을 375×812에서 연다(`.claude/launch.json`의 "web". 8000이 이미 떠 있으면 그 주소를 바로 연다). 확인 전에는 서비스 워커와 저장본을 지우고 다시 연다:
  ```js
  for (const r of await navigator.serviceWorker.getRegistrations()) await r.unregister();
  for (const k of await caches.keys()) await caches.delete(k);
  location.reload();
  ```
- 패키지를 더할 때는 무엇을 왜 더하는지 먼저 사용자에게 말한다(CLAUDE.md 3절). 파일을 내려받기 전에는 이름·출처·크기를 말하고 허락을 받는다.
- 커밋은 CLAUDE.md 4절(한국어, 배경·바꾼 것·검증, Co-Authored-By 한 줄). 푸시는 사용자가 말할 때만.

## Review Focus

1. 아이폰에서 자판이 올라올 때: 아래 검색창과 가격표 받침이 자판 바로 위에 붙고, 받침이 올라온 채로 이름·큰 가격·막대·판정·칸이 보여야 한다. 자판을 닫으면 제자리로 돌아와야 한다. 앱 안 브라우저에는 자판이 없으므로 `--kb`를 손으로 넣어 보고, 진짜 폰은 사용자에게 부탁한다 → Task 4 Step 3, Task 5 Step 4.
2. 받침이 본문 끝을 가리지 않아야 한다: 맺음말까지 내려 볼 수 있어야 하고, 받침 높이가 다른 세 경우(KAMIS 막대, 아래말이 두 줄인 이마트 막대 `너구리(5개입)`, 막대 없는 이마트 `신라면(5개입)`)에서 모두 그래야 한다 → Task 3 Step 5.
3. 검색 결과 줄의 조사: "파"로, "쌀"로, "당근"으로, "cj"로(한글이 아니면 "로") → Task 2 Step 5.
4. 값이 모자라거나 0이 되는 경우: 평년 값 없음(`111-01` 등 20개), 평년 %가 반올림해 0(`243-00` 붉은고추 -0.4 → "평년과 같아요"), 지난 값 줄이 빠진 날(오늘 파일은 1개월 전이 모두 없다), 이마트 행사 %가 0(`삼양라면(5개입)` 3,070 → 덧말을 원으로 "평소보다 {차이}원 싸요"), 품종 기준일이 다른 줄(`111-10` 쌀 "10월 29일 값") → Task 2 Step 5, Task 3 Step 5.
5. 긴 이름과 큰 값이 320px 폭에서 겹치지 않아야 한다: "물오징어 연근해(신선 냉장)"(`619-03`), "쿤달 허니 앤 마카다미아 헤어 트리트먼트 베이비파우더향(718ml)", 상세 가격 18,886원(`221-00` 수박), 이마트 52,980원(`철원 오대쌀(10kg)`), 가격표 값 7자리 → Task 2 Step 5, Task 3 Step 5.

---

### Task 1: 숫자 글꼴(Geist) 파일과 만드는 도구

**Files:**
- Create: `tools/make_font.py`, `tools/tests/test_make_font.py`, `fonts/geist-num.woff2`, `fonts/OFL.txt`
- Modify: `style.css`(맨 위에 `@font-face`와 `.num`), `sw.js`(`SHELL`에 글꼴, `CACHE`), `.github/workflows/collect.yml:141`(`cp -r` 줄에 `fonts`), `.gitignore`(`/tools/fonts-src/` 설명), `pyproject.toml`·`uv.lock`, `CLAUDE.md`(실행 명령)
- Test: `tools/tests/test_make_font.py`, `tools/tests/test_site_files.py`(그대로, 이제 글꼴을 검사한다)

**Interfaces:**
- Produces: `make_font(src: Path, out: Path) -> None`, 상수 `CHARS = "0123456789,.%~"`. 화면용 CSS 클래스 `.num`(Task 2·3이 가격 숫자에 붙인다). 글꼴 이름 `"Geist Num"`.

- [ ] **Step 1: 원본 받기(허락 먼저)** — 사용자에게 "Google Fonts 저장소(github.com/google/fonts)의 `ofl/geist/Geist[wght].ttf`와 `ofl/geist/OFL.txt`를 `tools/fonts-src/`에 받겠다(크기는 받기 전에 `curl -sIL`로 확인해 알린다)"고 말하고 허락을 받는다. 경로가 바뀌었으면 저장소에서 찾아 다시 묻는다. `tools/fonts-src/`는 git 밖이다.
- [ ] **Step 2: 개발용 패키지 더하기(먼저 말하기)** — "글꼴을 자르고 woff2로 묶는 데 fontTools와 brotli가 필요하다(개발용만, 화면과 수집에는 안 들어간다)"고 말한 뒤 `uv add --dev fonttools brotli`.
- [ ] **Step 3: 실패하는 시험 쓰기** — `tools/tests/test_make_font.py`에 저장소에 든 결과물을 보는 시험 셋(원본이 없는 컴퓨터에서도 돈다):
  ```python
  def test_number_font_has_only_number_glyphs():
      font = TTFont(ROOT / "fonts" / "geist-num.woff2")
      cmap = font.getBestCmap()
      assert all(ord(c) in cmap for c in "0123456789,.%~")
      assert ord("원") not in cmap and ord("A") not in cmap
      assert (ROOT / "fonts" / "geist-num.woff2").stat().st_size < 30_000

  def test_number_font_keeps_tabular_figures():
      tags = {r.FeatureTag for r in TTFont(ROOT / "fonts" / "geist-num.woff2")["GSUB"].table.FeatureList.FeatureRecord}
      assert "tnum" in tags

  def test_number_font_keeps_license():
      names = TTFont(ROOT / "fonts" / "geist-num.woff2")["name"]
      assert "Open Font License" in str(names.getDebugName(13))
      assert (ROOT / "fonts" / "OFL.txt").exists()
  ```
- [ ] **Step 4: 시험이 실패하는지 보기** — `uv run pytest tools/tests/test_make_font.py -v` → 3개 FAIL(파일 없음).
- [ ] **Step 5: `make_font(src: Path, out: Path) -> None` 쓰기** — `tools/make_font.py`. 가변 글꼴을 `fontTools.varLib.instancer.instantiateVariableFont(font, {"wght": 600})`로 굵기 600 하나로 고정하고, `fontTools.subset`으로 `CHARS`만 남긴다. 옵션: `layout_features=["tnum", "kern"]`, `name_IDs=["*"]`(빼면 사용 조건 문구가 사라진다. 2026-11-03 영수증 글꼴 때 겪었다), `flavor="woff2"`. `python tools/make_font.py`로 돌리면 `tools/fonts-src/Geist[wght].ttf` → `fonts/geist-num.woff2`, `tools/fonts-src/OFL.txt` → `fonts/OFL.txt`. 함수마다 타입 힌트와 한국어 docstring.
- [ ] **Step 6: 만들고 시험 통과 보기** — `uv run python tools/make_font.py && uv run pytest tools/tests/test_make_font.py -v` → 3개 PASS.
- [ ] **Step 7: 화면에 글꼴 싣기** — `style.css` 맨 위에 `@font-face { font-family: "Geist Num"; src: url("fonts/geist-num.woff2") format("woff2"); font-weight: 600; font-display: swap; }`와 `.num`(Global Constraints). `index.html`에 `<link rel="preload" href="fonts/geist-num.woff2" as="font" type="font/woff2" crossorigin>`를 넣어 숫자가 늦게 바뀌어 보이지 않게 한다. `sw.js`의 `SHELL`에 `"fonts/geist-num.woff2"`를 넣고 `CACHE`를 `mp-v20`으로. `uv run pytest tools/tests/test_site_files.py` → FAIL(배포가 `fonts`를 안 싣는다) 확인 뒤 `collect.yml` `cp -r` 줄에 `fonts`를 더해 PASS.
- [ ] **Step 8: 설명 고치기** — `.gitignore`의 설명을 "글꼴 원본(Geist, 예전 영수증 글꼴). 만든 글꼴(fonts/)만 넣고 원본은 넣지 않는다"로. `CLAUDE.md` 실행 명령에 "숫자 글꼴 다시 만들기: `uv run python tools/make_font.py` — 원본은 `tools/fonts-src/`(git 밖)" 한 줄.
- [ ] **Step 9: 전체 시험과 커밋** — `uv run pytest` → 모두 PASS. 커밋 `feat(screen): 가격 숫자에 쓸 Geist 글꼴을 숫자만 잘라 넣고 오프라인으로 저장함`.

### Task 2: 색·글꼴 바탕과 첫 화면(제목, 띠, 칸 줄, 한 줄, 아래 검색창, 검색 결과)

**Files:**
- Modify: `index.html`, `style.css`(상세·가격 막대·판정 부분만 남기고 다시 씀), `app.js`(`renderTop`, `rowNode`, `emartRowNode`, `missingRowNode`, `renderHome`, `renderSearch`, `coveredHeight`, `render`), `sw.js`(`CACHE` `mp-v21`)

**Interfaces:**
- Consumes: Task 1의 `.num`.
- Produces: `wonNode(n: number, cls?: string) -> HTMLElement`(`<b class="num …">1,234<small>원</small></b>`), `normalText(e) -> { text: string, cls: "down" | "up" | "" }`(평년 비교 한 마디. 신호가 싼 편이면 `down`, 비싼 편이면 `up`), `mini(text: string) -> HTMLElement`(작은 표시), `ro(word: string) -> "로" | "으로"`. Task 3이 `wonNode`·`normalText`를 쓴다.

- [ ] **Step 1: `index.html` 뼈대 바꾸기** — 맨 위 검색 막대(`#bar-home`)를 없애고, 같은 `form#search-form`(그 안 `input#search`, `button#search-clear`, 앞에 돋보기 SVG)을 `<main>` 뒤로 옮겨 아래 검색창으로 쓴다. `#home-head`는 `div#home-title`(`h1` "장보기 가격", `p#asof`) → 띠 셋 → 쪽지 순서. 띠 셋은 같은 `class="band"` 하나로(노란 띠 class를 없앤다), 샘플 띠 글자를 새 문구로. 어두운 `theme-color`를 `#000000`으로. `#bar-detail`은 Task 3에서 바꾸므로 그대로.
- [ ] **Step 2: `style.css` 다시 쓰기** — Task 1의 글꼴 두 덩이와 상세 부분(`/* ---- 상세 ---- */`부터 판정까지, Task 3이 다시 쓴다)만 남기고 다시 쓴다. 상세 부분이 쓰는 `--band`, `--range`는 Task 3까지 남겨 둔다. 정할 것:
  - 제목 30/700, `#asof` 14 `--sub`. 띠는 `--soft` 바탕, 둥근 12, 15/600. 쪽지는 `--soft`, 둥근 16. 묶음 사이(`.section + .section`)는 선 대신 높이 8 `--soft` 띠(화면 폭 가득).
  - 칸 줄은 `position: sticky; top: env(safe-area-inset-top, 0px)`. 칸은 높이 40 둥근 알약 `--soft`, 이름 15/600, 개수는 `.chip__n`(400, `--muted`), 칠한 칸은 `--text` 바탕 `--bg` 글씨. 누르는 곳은 위아래 `margin`으로 44 이상.
  - 줄은 `grid-template-columns: minmax(0,1fr) 48px auto`, 높이 72 이상, 줄 사이 선 없음, 누르는 동안 흐려짐(`.row:active`)과 즐겨찾기를 들어 올린 줄의 둥근 모서리·그림자(`.row--lifted`)는 남긴다. 이마트·값 없음 줄은 두 칸. 작은 그래프 48×22, `--muted` 선.
  - 검색창은 `position: fixed; left: 12px; right: 12px; bottom: calc(12px + env(safe-area-inset-bottom, 0px) + var(--kb, 0px))`, 높이 54, 둥근 18, 바탕 `--soft`를 88% 비치게, `backdrop-filter: blur(16px)`, 그림자 `0 10px 30px -8px rgb(0 0 0 / 28%)`, 글씨 17, `bottom`이 바뀔 때 0.22초 `transition`. 첫 화면·검색의 `.view`는 아래에 검색창 높이만큼 빈자리. 상세에서는 검색창을 숨긴다.
  - 되돌리기 띠는 검색창 바로 위(`bottom`에 검색창 높이 + 12), `--text` 바탕에 `--bg` 글씨, 둥근 14.
  - `body.searching`이면 `#home-title`과 `#banner-install`을 숨긴다(띠는 남는다).
- [ ] **Step 3: 글자 도우미와 줄 바꾸기** — `wonNode`, `normalText`, `mini`, `ro`를 더한다. `ro`는 마지막 글자가 한글이고 받침이 있으면(ㄹ 받침은 빼고) "으로", 아니면 "로"다. `rowNode`: 왼쪽 위 이름(+★), 왼쪽 아래 `normalText`를 그 `cls`로, 기준일이 다르면 뒤에 `mini("{M}월 {D}일 값")`. 오른쪽은 `wonNode(e.unit_price)`와 흐린 단위. `emartRowNode`: 왼쪽 아래 `[showTag ? mini("이마트")] + ("행사 때 {값}원" down | "행사 없음") + [지점 2곳 이하면 mini("이마트 {N}곳")] + [조사일 다르면 mini("{M}월 {D}일 값")]`, 오른쪽 `wonNode(e.usual)`과 "평소 값". `missingRowNode`는 새 class만 맞춘다.
- [ ] **Step 4: 첫 화면·검색 그리기 바꾸기** — `renderTop`: `#asof`와 띠 둘의 글자를 Global Constraints 문구로. `renderHome`: 칸 글자를 이름 + `.chip__n` 개수로, 부류 제목도 같은 모양으로, 모아 보기 제목을 새 문구로. `renderSearch`: `"{q}"${ro(q)} 찾은 품종 {N}개`. `render()`: `#bar-home` 대신 `#search-form.hidden = 상세`, `document.body.classList.toggle("searching", 검색어 있음 && !상세)`. `coveredHeight()`는 칸 줄 높이 + 칸 줄의 `top` 값(`parseFloat(getComputedStyle(chips).top)`). `CACHE` → `mp-v21`.
- [ ] **Step 5: 화면으로 확인** — 저장본을 지우고 375×812로 연다.
  - 첫 화면: 제목·날짜 줄, 즐겨찾기 줄과 끌기 안내, 칸 줄이 내려도 맨 위에 붙고 내리는 대로 칠해지는지, 부류 칸 건너뛰기가 칸 줄에 가리지 않는지, "싼 편" 모아 보기 제목.
  - 줄: `243-00` 붉은고추 "평년과 같아요"(회색), 평년 없음 `111-01` "평년 값 없음", 쌀 `111-10` 뒤 "10월 29일 값" 표시, 이마트 줄의 "행사 때"·"이마트 2곳"(`갈치(냉동, 100g)`), 가격 숫자가 Geist인지(`document.fonts.check('600 22px "Geist Num"')`).
  - 검색: "파"→`"파"로 찾은 품종`, "쌀"→`"쌀"로`, "당근"→`"당근"으로`, "cj"→`"cj"로`. 검색 중 제목·쪽지가 숨고 띠는 남는지(개발자 도구에서 오프라인으로 바꿔 띠를 띄운다). ✕로 첫 화면.
  - 폭 320에서 `619-03`과 가장 긴 이마트 상품명이 겹치지 않는지. 어두운 화면.
  - 상세는 Task 3 전이라 옛 모양이어도 된다(열리기만 하면 된다).
- [ ] **Step 6: 커밋** — `feat(screen): 첫 화면을 큰 제목과 조용한 목록으로 바꾸고 검색창을 아래로 내림`.

### Task 3: 상세 화면과 가격표 받침

**Files:**
- Modify: `index.html`(`#bar-detail`의 ←·☆를 SVG로), `style.css`(상세·받침 부분 다시 씀, `--band`·`--range` 지움), `app.js`(`renderStar`, `showUndo`→`showToast`, `trendChart`, `priceRuler`, `priceTagBox`→`priceDock`, `judgeKamis`, `judgeEmart`, `renderEmartDetail`, `renderDetail`, `pctText`·`info` 정리), `sw.js`(`CACHE` `mp-v22`)

**Interfaces:**
- Consumes: Task 2의 `wonNode`, `normalText`, `mini`.
- Produces: `showToast(text: string, onUndo?: () => Promise<void>) -> void`(되돌리기 단추는 `onUndo`가 있을 때만), `changeText(v: number) -> { text, cls }`("15% 올랐어요" up / "48% 내렸어요" down / "같아요" ""), `priceDock({ cap: string, ruler?: { node, movePin }, label: string, judge }) -> HTMLElement`(`section.dock`). CSS 변수 `--dock-h`(받침 높이, Task 4가 쓴다).

- [ ] **Step 1: 맨 위 막대** — 높이 52, 지금처럼 위에 붙는다. `index.html`의 ←·☆를 24px SVG(시안의 꺾쇠와 별 모양)로. `renderStar`는 글자 대신 `aria-pressed`만 바꾸고, CSS가 `[aria-pressed="true"]`일 때 별을 `--star`로 채운다. 누르면 `showToast("즐겨찾기에 넣었어요" | "즐겨찾기에서 뺐어요")`. `showUndo`는 `showToast("{이름}, 즐겨찾기에서 뺐어요", 되돌리기)`로 바꾼다.
- [ ] **Step 2: KAMIS 본문** — `renderDetail`: 부류 → 이름 → 큰 가격 묶음(`"{단위}당, 대형마트 {N}곳 평균"`, `wonNode(e.unit_price, "detail__price")`, 평년 칸 `.pill--down|--up|--plain`에 `normalText(e).text`와 옆 "{M}월 {D}일 값") → "30일"과 `trendChart`(추이가 2개보다 적으면 "추이 값이 하루치뿐이에요") → "지난 값과 비교"(`changeText`로, 값 없는 줄은 빼고, 마지막에 "{조사 단위} 값" `{값}원`) → 맺음말. `trendChart`의 세로 범위 계산은 그대로 두고, 마지막 값 높이에 점선, 가장 높은·낮은 점 곁에 "최고 {값}"·"최저 {값}"(숫자 `tspan.num`, 글자가 그림 밖으로 안 나가게 양옆 34px 안으로), 아래 양 끝에 `md()` 날짜. 값이 없는 품종은 이름과 새 문구만, 받침 없음.
- [ ] **Step 3: 가격표 받침** — `priceTagBox`를 `priceDock`으로 바꾼다. 안은 머리 줄(제목 + 흐린 뜻 한 줄) → 막대(있으면) → 판정(`p` `aria-live="polite"`) → `form` 안 흰 칸(`label` 안에 이름 `span`, `input` `type="text" inputmode="numeric" enterkeyhint="done" placeholder="값 넣기"`, 뒤에 `small.won` "원"). 숫자만 받는 것과 핀·판정을 바꾸는 흐름은 지금 그대로. 받침은 `#view` 안 마지막 자식이고 CSS로 `position: fixed; left: 0; right: 0; bottom: var(--kb, 0px)`(바뀔 때 0.22초 `transition`, 움직임 줄이기면 끔), 위 두 모서리 26, 바탕 `--dock`, 글씨 흰색. 막대의 진한 칸은 흰색 55%, 바탕 선 흰색 16%, 평균 눈금 흰색, 핀은 `--tag` 바탕 검은 숫자(`.num`), 칸을 누르면(`:focus-within`) 테두리 `--tag` 2px, 값이 비면 "원"을 숨긴다(`input:placeholder-shown + .won`). 판정의 `.up`/`.down`은 받침 안에서 `--dock-up`/`--dock-down`. `ResizeObserver`로 받침 높이를 `--dock-h`에 넣고 `.detail`의 아래 빈자리를 `calc(var(--dock-h) + 24px)`로. `judgeKamis`·`judgeEmart`의 덧말 끝을 "비싸요"·"싸요"로.
- [ ] **Step 4: 이마트 상세** — 부류 자리 "이마트 {묶음}", 큰 가격 위 "이마트 {N}곳 평소 값, {M}월 {D}일 조사"(`last_day`), 평년 칸 자리에 빨강 칸 "행사 때 {값}원"과 "{M}월 {D}일, 평소보다 {n}% 싸요"(반올림해 0%면 "평소보다 {차이}원 싸요"), 없으면 회색 칸 "3개월 동안 행사 없음". "최근 3개월 조사" 줄(행사 최저는 빨강), 맺음말, 받침(막대는 행사가 있을 때만). 다 쓴 `pctText`, `mdot`, 옛 CSS(`--band`, `--range`, `.detail__normal` 등)를 지운다. `CACHE` → `mp-v22`.
- [ ] **Step 5: 화면으로 확인** — 저장본을 지우고 375×812로.
  - `223-02` 오이: 큰 가격 635원, 붉은 평년 칸, 그래프의 최고·최저·날짜, 지난 값 줄과 "10개 값", 받침에 690 → 핀과 "대형마트에서 흔한 값이에요 / 평균 635원보다 55원(9%) 비싸요", 1000 → 파랑 "…넷 중 셋보다 비싸요", 10 → 왼쪽 끝 ◀ 핀.
  - 조사처 3곳 `420-02` 파인애플 "진한 칸은 조사한 3곳", 1곳 `615-04` 명태(칸 폭 0, 숫자 하나).
  - 이마트 `너구리(5개입)`(막대·점·아래말 두 줄), `신라면(5개입)`(막대 없음, "3개월 동안 행사 없음"), `삼양라면(5개입)`("평소보다 {차이}원 싸요").
  - 세 경우 모두 맨 아래 맺음말까지 내려 받침 위로 보이는지. ☆→띠 "즐겨찾기에 넣었어요"→첫 화면에 줄 생김, ★로 빼기. 검색 결과에서 들어갔다 ←로 검색어가 남는지, 전체 품목 중간에서 들어갔다 ←로 자리가 남는지.
  - 폭 320에서 `221-00` 수박 18,886원, 이마트 52,980원, 가격표 칸에 7자리. 어두운 화면(받침 `#1e2024`).
- [ ] **Step 6: 커밋** — `feat(screen): 상세 아래에 먹색 가격표 받침을 붙이고 상세를 큰 가격 하나로 정리함`.

### Task 4: 자판과 함께 올라가기(검색창, 받침)

**Files:**
- Modify: `index.html`(viewport 메타에 `interactive-widget=resizes-content`), `app.js`(`setupKeyboardInset` 더하기, `init`에서 부르기), `style.css`(필요하면 자판이 열렸을 때 받침 아래 여백), `sw.js`(`CACHE` `mp-v23`)

**Interfaces:**
- Consumes: Task 2·3이 `bottom`에 쓰는 `var(--kb, 0px)`.
- Produces: `setupKeyboardInset() -> void`. 문서 뿌리(`document.documentElement`)의 `--kb`에 자판이 가린 높이(px)를 넣는다.

- [ ] **Step 1: 자판 높이 재기** — `setupKeyboardInset()`: `visualViewport`가 없으면 아무것도 안 한다. 있으면 `resize`·`scroll`과 `focusin`·`focusout` 때 `Math.max(0, Math.round(innerHeight - visualViewport.height - visualViewport.offsetTop))`를 `--kb`에 넣는다(아이폰은 자판이 올라와도 `innerHeight`가 그대로라 이 값이 자판 높이다. 안드로이드는 메타 덕에 `innerHeight`가 줄어 0에 가깝다). 한 화면을 그릴 때 한 번만 재도록 `requestAnimationFrame`으로 모은다.
- [ ] **Step 2: viewport 메타와 부르기** — `index.html` viewport에 `interactive-widget=resizes-content`를 더하고 `init()`에서 `setupKeyboardInset()`을 부른다. `CACHE` → `mp-v23`.
- [ ] **Step 3: 화면으로 확인** — 앱 안 브라우저에는 자판이 없으므로 `document.documentElement.style.setProperty("--kb", "290px")`를 넣어 본다: 첫 화면 검색창과 되돌리기 띠가 290px 올라가고, 오이 상세에서 받침이 올라간 채로 맨 위 막대·이름·큰 가격·막대·판정·칸이 한 화면(375×812)에 보이는지. `"0px"`로 되돌리면 제자리. 칸을 눌렀다 떼도(초점 들고 남) `--kb`가 0으로 남는지(자판 없는 브라우저).
- [ ] **Step 4: 커밋** — `feat(screen): 자판이 올라오면 아래 검색창과 가격표 받침이 자판 위로 같이 올라감`.

### Task 5: 문서와 전체 확인

**Files:**
- Modify: `README.md`(검색창 자리, 조사일 자리, 화면 설명), `docs/decisions.md`(지금 상태, 구현 중 Claude가 정한 것), `sw.js`(`CACHE` `mp-v24`, 앞 Task에서 다 올렸으면 그대로)

- [ ] **Step 1: README 고치기** — "맨 위 검색창" → "아래 검색창", "화면 맨 위에 조사일("이마트 9.25 조사")" → "제목 아래에 조사일("이마트 9월 25일 조사")", 상세 설명에 "아래 가격표 받침의 칸에 가격표 값을 넣으면 막대 위에 노란 핀이 꽂히고 한 마디로 알려 준다"를 맞게 넣는다.
- [ ] **Step 2: 전체 확인** — 저장본을 지우고 설계 11절 화면 확인 목록 전부와 위 Review Focus 1~5를 밝은·어두운 화면에서 다시 본다. 개발자 도구에서 오프라인으로 바꿔 다시 열어 가격과 Geist 숫자가 그대로 보이는지. `uv run pytest` 모두 PASS.
- [ ] **Step 3: 결정 기록** — `docs/decisions.md` 지금 상태에 구현을 마친 것(서비스 워커 버전 포함)을 적고, 구현하며 Claude가 정한 세부(예: 이마트 행사 0%일 때 원으로 말하기, 가격표 값에 쉼표를 넣지 않음, 30일 그래프 세로 범위는 그대로)를 한 기록으로 남긴다.
- [ ] **Step 4: 사람에게 부탁할 것 알리기** — 푸시 전이라 진짜 폰 확인은 사용자 몫이다. 보고에 적는다: 아이폰과 안드로이드에서 (1) 아래 검색창을 누르면 자판 위로 붙는지, (2) 상세 받침 칸을 누르면 받침이 자판 위로 올라오고 막대·판정이 보이는지, (3) 자판을 닫으면 제자리인지, (4) 홈 화면 앱으로 비행기 모드에서 열리는지.
- [ ] **Step 5: 커밋** — `docs: 화면 새로 그리기를 구현한 지금 상태와 구현 중 정한 세부를 적음`.
