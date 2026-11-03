# 영수증 화면 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 화면 생김새를 `docs/design.md` 8절 "생김새"(장보기 예상 영수증)대로 바꾼다. 하는 일(목록·검색·상세·총액·오프라인)은 그대로 두고 모양과 문구, 정한 내용 변경 네 가지만 바꾼다.

**Architecture:** 화면은 지금처럼 빌드 없는 HTML·CSS·JS다. `index.html`의 뼈대를 "받침 위 영수증 종이 + 아래 고정 영역"으로 바꾸고, `style.css`를 새 색·글꼴로 다시 쓰고, `app.js`의 그리기 함수들을 새 줄 모양에 맞춘다. 글꼴은 `tools/make_font.py`가 원본 나눔고딕코딩에서 앱이 쓰는 글자만 남겨 `fonts/`에 만들고, 서비스 워커가 화면 파일과 함께 저장한다.

**Tech Stack:** HTML·CSS·JS(ES 모듈, 라이브러리 없음). 글꼴 도구는 Python 3.14 + uv, 개발용 `fonttools`·`brotli`(woff2 압축에 필요).

**Spec:** `docs/design.md` 8절 "생김새", 9·11·12절 (정한 이유는 `docs/decisions.md`의 2026-11-03 기록들)

## Global Constraints

- 색은 `docs/design.md` 8절 표의 값을 그대로 CSS 변수로 쓴다. 어두운 화면에서는 받침·흐린 글씨·점선·신호색만 바뀌고 종이는 `#e6e2d6`, 잉크는 `#2b2925`로 밝은 종이를 유지한다.
- 그림자와 그러데이션은 쓰지 않는다. 구분선은 모두 `1.5px dashed` 점선이다. 단추·상자 모서리는 4px.
- 글꼴 굵기는 400과 700 두 가지만 쓴다(글꼴 파일이 두 개).
- 누르는 곳은 모두 44px 이상. 키보드 초점 테두리(`:focus-visible`)는 지금처럼 남긴다.
- 원본 글꼴 이름에는 사용 조건상 쓸 수 없는 이름(Reserved Font Name: "Nanum", "NanumGothic" 등)이 있다. 만든 글꼴의 이름은 `MktReceipt`로 바꾸고, CSS `font-family`와 파일 이름에도 "Nanum"을 쓰지 않는다. 저작권 문구와 `OFL.txt`는 남긴다.
- 원본 글꼴 파일은 git에 넣지 않는다(`/tools/fonts-src/`). 만든 `fonts/*.woff2`와 `fonts/OFL.txt`만 넣는다.
- 화면 파일을 바꾸므로 `sw.js`의 `CACHE`를 `mp-v4`로 한 번 올린다(Task 2). 이 계획 안에서는 더 올리지 않는다.
- 화면에는 자동 시험이 없다(설계 2·11절). 화면 확인은 앱 안 브라우저 375×812로 직접 한다. 글꼴 도구는 pytest로 시험한다.
- 화면 문구(정확히 이대로): "장보기 예상 영수증" / "{YYYY.MM.DD} 기준 · 출처 {출처}" / "** 샘플 데이터 · 실제 가격 아님 **" / "* 인터넷 연결 없음 · {M}월 {D}일 값 *" / "홈 화면에 추가하면 앱처럼 쓰고, 인터넷 없이도 열려요" + "닫기" / "아래 검색창에서 품목을 찾아 + 담기를 눌러 보세요" / "합계(예상)" / "값 없는 품목 {N}개 제외" / "지금 값 없음" / "{M}월 {D}일 값" / `"{검색어}" 찾은 품목 {N}개` / "+ 담기" · "담음 x{N}" / "{YYYY.MM.DD} · 대형유통 {N}곳 평균"(비교 기준이 전국 평균이면 "조사처 {N}곳 평균") / "가게마다(가운데 절반)" / "30일 추이" · "최고 {값}" · "최저 {값}" / "1주 전보다", "1개월 전보다", "1년 전보다"(뒤에 "+3%"처럼 퍼센트) / "* 요즘 시기는 KAMIS 전체 평균 기준" / "목록으로" · "목록에서 빼기".
- 신호 줄: 보통 "보통 +4%", 싼 편 "▼ 싼 편 -18%", 비싼 편 "▲ 비싼 편 +19%". 퍼센트 부호는 ASCII `+`·`-`(지금 `signedPct`의 `−`(U+2212)를 바꾼다).
- 파이썬은 `anthropic-skills:python-style-guide`(타입 힌트, 한국어 docstring). 커밋은 CLAUDE.md 4절. 푸시는 사용자가 말할 때만.

## Review Focus

1. 글꼴에 없는 글자(검색창에 친 "가나다", 앞으로 생길 새 품종 이름): 그 글자만 폰 기본 글꼴로 보이고 네모(□)로 깨지지 않아야 한다 → Task 4 확인 단계.
2. 가장 긴 이름("포도 레드글로브 칠레(~23.5) x12", "가리비 해만가리비(홍가리비)")을 폭 320px에서: 이름이 줄바꿈되고 가격과 겹치지 않아야 한다 → Task 2·3 확인 단계.
3. 목록이 길 때(15줄 이상): 마지막 줄이 아래 고정 영역에 가려지지 않고, 합계와 톱니가 늘 보여야 한다. "값 없는 품목 1개 제외" 줄이 생겨 고정 영역이 높아져도 마찬가지 → 아래 고정 영역을 `position: fixed` + 고정 높이 대신 `position: sticky; bottom: 0`으로 해 높이 계산을 없앤다(Task 2).
4. 인터넷 없이 처음 다시 열 때(새 서비스 워커 설치 뒤): 영수증 글꼴로 보여야 한다. 글꼴 파일은 `SHELL` 목록에 들어 있어야 한다 → Task 2·4.
5. 합계가 큰 수("1,234,560~1,345,670원")일 때 폭 320px에서 한 줄을 넘으면 줄바꿈되고 잘리지 않아야 한다 → Task 2 확인 단계.

---

### Task 1: 글꼴 만들기 도구와 글꼴 파일

**Files:**
- Create: `tools/make_font.py`, `tools/__init__.py`(빈 파일), `tools/tests/__init__.py`, `tools/tests/test_make_font.py`
- Create(만든 결과): `fonts/receipt-regular.woff2`, `fonts/receipt-bold.woff2`, `fonts/OFL.txt`
- Modify: `pyproject.toml`(개발용 의존성, `testpaths`에 `"tools/tests"` 추가), `uv.lock`, `.gitignore`(`/tools/fonts-src/`), `CLAUDE.md`(실행 명령에 글꼴 만들기 한 줄, 품종 목록 다시 만들기 줄에 "그 뒤 글꼴도 다시 만든다")

**Interfaces:**
- Produces: `used_chars(items_path: Path, screen_files: List[Path]) -> str`, `subset_font(src: Path, dst: Path, chars: str, family: str, style: str) -> None`, `main() -> int`. 상수 `FAMILY = "MktReceipt"`, `SRC_DIR = tools/fonts-src`, `OUT_DIR = fonts`, `SCREEN_FILES = [index.html, app.js]`.
- Produces(Task 2가 씀): `fonts/receipt-regular.woff2`(굵기 400), `fonts/receipt-bold.woff2`(굵기 700), 글꼴 이름 `MktReceipt`.

- [ ] **Step 1: 개발용 패키지 더하기** — `uv add --dev fonttools brotli`. fonttools는 글자 덜어내기와 이름 바꾸기, brotli는 woff2로 줄이는 데 필요하다.

- [ ] **Step 2: 원본 글꼴 내려받기(사용자 허락 받은 뒤)** — Google Fonts 공식 저장소(`https://raw.githubusercontent.com/google/fonts/main/ofl/nanumgothiccoding/`)에서 `NanumGothicCoding-Regular.ttf`(2,315,924바이트), `NanumGothicCoding-Bold.ttf`(2,246,240바이트), `OFL.txt`(4,534바이트)를 `tools/fonts-src/`에 받는다. 크기가 위와 같은지 확인한다. `.gitignore`에 `/tools/fonts-src/`를 더한다.

- [ ] **Step 3: 실패하는 시험 쓰기** — `tools/tests/test_make_font.py`. 시험용 글꼴은 `fontTools.fontBuilder.FontBuilder`로 그 자리에서 만든다(글리프 `.notdef`, `A`, `B`, `가`; 이름표의 가족 이름 "NanumGothicCoding", 저작권(이름 0번) "Copyright NHN NanumGothic").

```python
def test_used_chars_collects_item_names_and_screen_text(tmp_path):
    # items.json에 {"item_name": "양파", "kind_name": "햇양파", "unit": "1kg", "category_name": "채소류"} 하나,
    # 화면 파일 하나에 "합계(예상)".
    chars = used_chars(items_path, [screen_path])
    for c in "양파햇채소류합계예상":
        assert c in chars
    for c in "0123456789,~/+-%()*x":
        assert c in chars          # 출력 가능한 ASCII(0x20~0x7E)는 늘 들어간다
    assert len(chars) == len(set(chars))
    assert list(chars) == sorted(chars)

def test_subset_font_keeps_only_requested_chars(tmp_path):
    subset_font(src, dst, "A가", FAMILY, "Regular")
    font = TTFont(dst)
    assert font.flavor == "woff2"
    assert set(font.getBestCmap()) == {ord("A"), ord("가")}

def test_subset_font_renames_reserved_font_name(tmp_path):
    subset_font(src, dst, "A", FAMILY, "Bold")
    names = TTFont(dst)["name"]
    assert names.getDebugName(1) == "MktReceipt"
    assert names.getDebugName(2) == "Bold"
    for rec in names.names:
        if rec.nameID not in (0, 13, 14):          # 저작권과 사용 조건 문구만 원래대로 둔다
            assert "Nanum" not in rec.toUnicode()
    assert "NHN" in names.getDebugName(0)
```

- [ ] **Step 4: 시험이 실패하는지 보기** — `uv run pytest tools/tests -v` → `ModuleNotFoundError`(또는 이름 없음)로 실패.

- [ ] **Step 5: `tools/make_font.py` 쓰기**
  - `used_chars`: items.json 각 품종의 글자 값(`item_name`, `kind_name`, `unit`, `unit_label`, `category_name`)과 화면 파일 전체 글자, 그리고 출력 가능한 ASCII 전부를 모아 겹치지 않게 정렬한 문자열. 줄바꿈 같은 제어 문자는 뺀다.
  - `subset_font`: `fontTools.subset`(`Subsetter`, `Options(flavor="woff2", hinting=False)`)로 글자를 덜어낸 뒤 이름표를 고친다. 이름 1번=가족, 2번=굵기 이름, 4번=`"{family} {style}"`, 6번=`"{family}-{style}"`, 3번=`"{family}-{style}"`. 그 밖에 0·13·14번이 아니면서 "Nanum"이 든 이름 기록은 지운다.
  - `main`: 원본 두 개가 없으면 받는 주소를 알려 주고 1을 돌려준다. 있으면 `receipt-regular.woff2`(Regular), `receipt-bold.woff2`(Bold)를 만들고 `OFL.txt`를 `fonts/`로 복사하고, 글자 수와 파일 크기를 찍고 0을 돌려준다.
  - 실행: `uv run python tools/make_font.py`

- [ ] **Step 6: 시험이 통과하는지 보기** — `uv run pytest -q` → 기존 72개 + 새 3개 모두 통과.

- [ ] **Step 7: 글꼴 만들기** — `uv run python tools/make_font.py` → `fonts/`에 파일 세 개. woff2 둘을 합쳐 200KB를 넘으면 멈추고 크기를 보고한다(설계에서 "수십~100KB쯤"으로 말해 둔 값).

- [ ] **Step 8: 커밋** — `feat(screen): 영수증 글꼴을 쓰는 글자만 남겨 만드는 도구와 글꼴 파일`. CLAUDE.md 실행 명령 두 줄도 같은 커밋.

### Task 2: 영수증 바탕, 머리, 목록, 합계

**Files:**
- Modify: `index.html`, `style.css`(다시 씀), `app.js`(맨 위 도우미, `renderTop`, `renderList`, `renderTotal`, `setupInstallHint`가 쓰는 요소), `manifest.webmanifest`, `sw.js`

**Interfaces:**
- Consumes: Task 1의 `fonts/receipt-regular.woff2`, `fonts/receipt-bold.woff2`, 글꼴 이름 `MktReceipt`.
- Produces(Task 3이 씀): `displayName(e) -> string`(품종 이름이 품목 이름과 같으면 품목 이름만, 아니면 `"{품목} {품종}"`), `unitPriceText(e) -> string`(`"1,267/100g"`, `"1,709/개"`: 무게면 `/100g`, 개수면 `/{unit_label}`, 숫자에는 "원"을 붙이지 않음), `signalLine(e) -> {text, cls} | null`(위 Global Constraints의 신호 줄 문구, `cls`는 `sig--high`·`sig--low`·`sig--mid`, 평년 값이 없으면 신호 말만, 신호가 없으면 null), ASCII 부호를 쓰는 `signedPct(x)`. CSS 클래스 `.paper`, `.dl`(점선), `.btn`, `.btn--primary`, `.btn--text`, `.stepper`, `.muted`, `.empty`, 색 변수 `--base`, `--paper`, `--ink`, `--muted`, `--dash`, `--high`, `--low`, `--marker`.

- [ ] **Step 1: `index.html` 뼈대 바꾸기**
  - 맨 위: 홈 화면 안내 쪽지 `#banner-install`(문구와 "닫기" 단추 `#install-close`는 그대로, 클래스 `note`).
  - 종이 `<div class="paper">` 안에 머리 `<header class="head">`: `<h1>장보기 예상 영수증</h1>`, `<p id="asof">`, `<p id="print-sample" class="print print--sample" hidden>** 샘플 데이터 · 실제 가격 아님 **</p>`, `<p id="print-offline" class="print" hidden>`. 그 아래 `.dl`, 그 아래 `<main id="view">`.
  - 아래 고정 영역 `<footer id="dock" class="dock">`: `#dock-list` 안에 종이 색 끝부분 `<div class="paper paper--end">`(그 안에 `.dl`과 `#total`), 그 아래 톱니 `<svg class="tear" viewBox="0 0 100 4" preserveAspectRatio="none" aria-hidden="true">`(지그재그 `polygon`, `fill: var(--paper)`), 그 아래 검색 폼(지금 그대로). `#dock-detail`은 그대로.
  - `<meta name="theme-color">`를 밝은 화면 `#d8d3c6`, 어두운 화면 `#161614` 두 줄로(`media="(prefers-color-scheme: dark)"`).
- [ ] **Step 2: `style.css` 다시 쓰기** — `@font-face` 두 개(`MktReceipt` 400·700, `font-display: swap`), `body`의 글꼴은 `"MktReceipt", -apple-system, "Apple SD Gothic Neo", "Noto Sans KR", sans-serif`. 색 변수는 설계 8절 표 그대로. 받침 `--base` 위 종이는 좌우 12px 여백. 아래 고정 영역은 `position: sticky; bottom: 0`(Review Focus 3), 아래쪽 `env(safe-area-inset-bottom)` 여백. 검색창은 종이색 바탕, 잉크색 1.5px 테두리, 모서리 4px, 높이 48px. `word-break: keep-all`과 `overflow-wrap: anywhere`로 긴 이름을 줄바꿈한다.
- [ ] **Step 3: `app.js` 머리와 목록 그리기**
  - `renderTop`: `#asof`에 `"2026.11.02 기준 · 출처 KAMIS"`(날짜의 `-`를 `.`로). `#print-sample`은 출처가 "샘플"일 때만, `#print-offline`은 `navigator.onLine`이 거짓일 때 `"* 인터넷 연결 없음 · 11월 2일 값 *"`.
  - `renderList`: 품목 줄은 `<a class="item" href="#/item/{id}">` 안에 첫 줄(이름 `displayName(e)` + 개수 2 이상이면 `" x{N}"`, 오른쪽 `unitPriceText(e)`)과 들여 쓴 둘째 줄(`signalLine(e)`, 품종 기준일이 파일 기준일과 다르면 끝에 `" · 11월 1일 값"`). 값 없는 품종은 이름(저장해 둔 이름), 가격 자리 `-`, 둘째 줄 흐린 글씨 "지금 값 없음". 빈 목록 문구는 Global Constraints대로. 목록에 담을 때 저장하는 이름도 `displayName(e)`.
  - `renderTotal`: 목록이 비어 있지 않으면 검색 중에도 보인다. "합계(예상)"와 `"85,310~92,035원"`, 값 없는 품목이 있으면 그 아래 "값 없는 품목 {N}개 제외".
- [ ] **Step 4: `manifest.webmanifest`** — `background_color`와 `theme_color`를 `#D8D3C6`로.
- [ ] **Step 5: `sw.js`** — `CACHE = "mp-v4"`, `SHELL`에 `fonts/receipt-regular.woff2`, `fonts/receipt-bold.woff2`를 더한다.
- [ ] **Step 6: 화면 확인(앱 안 브라우저 375×812, `web` 서버)** — 양파·대파·사과 후지 x3·감자 수미·값 없는 품종 하나를 담은 상태로: 머리 두 줄과 샘플 형광펜 줄, 줄 모양(이름 겹침 없음, 신호 줄 색), "지금 값 없음" 줄, 합계와 "값 없는 품목 1개 제외", 톱니와 검색창. 목록 15줄로 늘려 스크롤 끝까지 내려도 마지막 줄이 가려지지 않는지. 폭 320px로 줄여 가장 긴 이름과 큰 합계가 줄바꿈되는지(Review Focus 2·3·5). 어두운 화면(`colorScheme: "dark"`)에서 받침만 어둡고 종이는 밝은지. 검색어를 쳐도 합계가 보이는지. 확인용으로 바꾼 저장 공간 값은 끝나고 되돌린다.
- [ ] **Step 7: 커밋** — `feat(screen): 목록 화면을 장보기 예상 영수증 모양으로`

### Task 3: 검색과 상세 화면

**Files:**
- Modify: `app.js`(`renderSearch`, `renderDetail`, `renderDetailDock`, `trendChart`), `style.css`(검색·상세 부분)

**Interfaces:**
- Consumes: Task 2의 `displayName`, `unitPriceText`, `signalLine`, `signedPct`, CSS 클래스와 색 변수.

- [ ] **Step 1: 검색** — 종이 머리 자리에 흐린 글씨 `"파" 찾은 품목 4개`(품목 묶음 수). 묶음마다 품목 이름(굵게, 품종이 2개 이상이면 뒤에 흐린 글씨로 개수), 그 아래 품종 줄: 왼쪽에 이름(품종 이름, 품목 이름과 같으면 품목 이름)과 싼 편·비싼 편일 때만 짧은 신호("▼싼 편", "▲비싼 편"), 그 아래 흐린 글씨 `unitPriceText(e)`; 오른쪽 단추 "+ 담기"(잉크색 테두리) 또는 담은 품종이면 잉크색으로 칠한 `"담음 x{N}"`(눌러도 아무 일 없음, `aria-pressed="true"`). 묶음 사이는 `.dl`. 결과가 없을 때 문구는 지금 그대로.
- [ ] **Step 2: 상세** — 위에서 아래로: 이름(`displayName`, 굵게)과 오른쪽 흐린 부류, 흐린 `"2026.11.02 · 대형유통 30곳 평균"`, `.dl`, 한 줄에 왼쪽 `perUnit(e)`("1개당")와 오른쪽 가장 큰 굵은 `won(e.unit_price)`, 흐린 줄 `"{조사 단위} {값}원"`(예: "10개 17,085원")과 `"가게마다(가운데 절반)"` / `"1,642~1,774/개"`, `.dl`, "30일 추이"와 그래프, `.dl`, 도장(`normalText(e.change.normal)`, 테두리만, `rotate(-4deg)`, 클래스 `stamp sig--high|sig--low|sig--mid`; 평년 값이 없으면 흐린 "평년 값이 없어요"), 1주·1개월·1년 줄(`"1주 전보다"` + `signedPct`, 0보다 크면 빨강, 작으면 초록, 값이 없는 줄은 뺀다), 맨 아래 흐린 `"* 요즘 시기는 KAMIS 전체 평균 기준"`. 값 없는 품종 상세는 지금 문구 그대로 영수증 안에. 노란 가격표(`.tag`)는 없앤다.
- [ ] **Step 3: 그래프** — 바닥선은 점선(`stroke-dasharray`), 선과 마지막 날 점은 잉크색, 글자는 흐린 색. 계산은 지금 그대로.
- [ ] **Step 4: 상세 아래 고정 영역** — 개수 상자(잉크색 테두리), "목록으로"(잉크색 칠한 단추), "목록에서 빼기"(빨간 글씨). 목록에 없는 품종이면 지금처럼 "+ 담기"와 "목록으로".
- [ ] **Step 5: 화면 확인(375×812, 그리고 320px)** — "파" 검색: 묶음 4개, 담은 양파는 "담음 x2", "+ 담기"를 누르면 그 자리가 "담음 x1"로 바뀌고 합계가 바뀌는지. 사과 후지 상세: 시안 순서대로인지, 도장 색(비싼 편 빨강), 개수 −/+와 "목록으로", "목록에서 빼기". 싼 편·보통 품종 상세의 도장 색. 가장 긴 이름 상세가 320px에서 줄바꿈되는지. 어두운 화면.
- [ ] **Step 6: 커밋** — `feat(screen): 검색과 상세 화면을 영수증 모양으로`

### Task 4: 오프라인·글꼴 확인과 문서

**Files:**
- Modify: `docs/decisions.md`("지금 상태"), 필요하면 `CLAUDE.md`

- [ ] **Step 1: 오프라인 확인** — `web` 서버로 한 번 연 뒤(새 서비스 워커 `mp-v4` 설치, 캐시에 woff2 두 개가 있는지 `caches` 확인), 서버를 끄고 새로 고침: 영수증 글꼴로 열리고 오프라인 인쇄 줄이 보이는지(Review Focus 4). 서버를 끈 상태 확인은 `curl`로 한다.
- [ ] **Step 2: 없는 글자 확인** — 검색창에 "가나다"를 쳐서 네모로 깨지지 않고 기본 글꼴로 보이는지, `"가나다"에 맞는 품목이 없어요` 문구가 읽히는지(Review Focus 1).
- [ ] **Step 3: 시험 전체** — `uv run pytest -q` → 75개 통과.
- [ ] **Step 4: 문서** — `docs/decisions.md` "지금 상태"에 영수증 화면 구현을 적는다. 커밋 `docs: 영수증 화면 구현을 지금 상태에 적음`.
