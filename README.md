# 장보기 가격

대형마트에서 가격표를 보고 "이 값이 적당한가?"를 폰으로 바로 확인하는 페이지입니다.

**주소: https://pakyong.github.io/MktPrice/**

## 무엇을 보여 주나

- **농산물·수산물 110여 개** (채소, 과일, 수산물, 곡물 등, KAMIS 조사. 철에 따라 개수가 바뀝니다)
  - 전국 대형마트 평균을 가격표와 같은 단위(100g당, 1개당)로 보여 줍니다.
  - "평년보다 39% 싸요"처럼 평년과 견준 말을 보여 주고, 15% 넘게 차이 나면 빨강(싼 편)·파랑(비싼 편)으로 칠합니다.
  - 최근 30일 값의 작은 그래프를 보여 줍니다.
- **이마트 상품 430개** (라면, 과자, 우유, 고기, 생활용품 등, 한국소비자원 참가격 조사)
  - "평소 값"은 최근 3개월 조사 가운데 가장 높은 값입니다(행사 값이 표시 없이 섞여 있어서).
  - "행사 때 최저 값"은 그 3개월 가운데 가장 낮은 값과 그날입니다.
  - 라면·면, 과자·빵·빙과 같은 11개 묶음으로 나눠 보여 줍니다.
- **즐겨찾기**: 자주 보는 품목을 첫 화면에 모아 둡니다. 폰마다 따로 저장됩니다.

## 쓰는 법

1. 주소를 열고 홈 화면에 추가합니다(아이폰 Safari: 공유 → 홈 화면에 추가, 안드로이드 Chrome: 메뉴 → 홈 화면에 추가).
2. 화면 아래 검색창에 품목 이름을 치거나, "전체 품목"의 칸(싼 편, 채소류, 이마트 라면·면 …)을 눌러 찾습니다.
3. 품목을 누르면 상세 화면이 나옵니다. 오른쪽 위 ☆를 누르면 즐겨찾기에 들어가고, 목록에서 이름 뒤에 노란 ★가 붙습니다.
4. 상세 화면 아래 검은 받침의 칸에 가격표 값을 넣으면, 대형마트 값 막대 위에 노란 핀이 꽂히고 "대형마트에서 흔한 값이에요"처럼 한 마디로 알려 줍니다.
5. 마트 안에서 인터넷이 안 돼도 마지막으로 받은 값으로 열립니다.

값이 바뀌는 때

- KAMIS 품목: 평일 저녁 7시쯤 하루 한 번 바뀝니다. 주말과 공휴일에는 새 값이 없습니다.
- 이마트 상품: 한 달에 한 번 바뀝니다. 참가격 자료가 늦게 올라와서 늘 3~7주 전 조사 값입니다. 첫 화면 제목 아래에 조사일("이마트 9월 25일 조사")이 보입니다.

## 어떻게 돌아가나

서버 없이 GitHub만으로 돌아갑니다.

```
[GitHub Actions: 평일 한국 시각 19시, Actions 탭의 "Run workflow"로도 돌릴 수 있음]
  KAMIS API  → collector(파이썬) → data/prices.json
  참가격 API → collector(파이썬) → data/emart.json   (새 달이 있을 때만)
  → 바뀐 파일만 커밋 → GitHub Pages에 배포

[GitHub Pages]
  index.html, app.js, style.css (빌드 없음) → data/*.json을 읽어 보여 주기만 함

[폰]
  서비스 워커가 화면 파일과 마지막 가격 파일을 저장 → 인터넷 없이도 열림
  즐겨찾기는 폰 안 저장 공간(localStorage)에
```

- 계산(평균, 단위 가격, 평년 대비, 평소 값 등)은 모두 수집 스크립트에서 끝냅니다. 화면은 보여 주기만 합니다.
- 브라우저는 API를 직접 부르지 않습니다. 키가 화면 코드에 드러나지 않게 하려는 것입니다.

## 데이터 출처

- [KAMIS 농산물유통정보](https://www.kamis.or.kr/customer/main/main.do) Open API의 일별 소매가격(한국농수산식품유통공사)
- [한국소비자원 생필품 가격 정보(참가격)](https://www.data.go.kr/data/15083256/fileData.do) (공공데이터포털)

## 직접 돌려 보기

파이썬 3.12와 [uv](https://docs.astral.sh/uv/)가 필요합니다. 시험은 인터넷 없이 돕니다.

```bash
uv run python -m collector.make_sample   # 키 없이 쓸 샘플 응답 만들기(collector/sample/, git에 넣지 않음)
uv run python -m collector               # KAMIS 값 받기 → data/prices.json (키가 없으면 샘플로)
uv run python -m collector.emart         # 이마트 값 받기 → data/emart.json (키가 없으면 건너뜀)
uv run pytest                            # 시험
uv run python -m http.server 8000        # 화면 보기: http://localhost:8000
```

키는 환경변수로 넣습니다.

| 환경변수 | 무엇 |
|---|---|
| `KAMIS_CERT_KEY`, `KAMIS_CERT_ID` | KAMIS Open API 인증키와 아이디 |
| `DATA_GO_KR_KEY` | 공공데이터포털 인증키(참가격 API 활용 신청 뒤 받음) |

## 저장소를 처음 설정할 때

- 저장소 Settings → Secrets and variables → Actions에 위 세 키를 넣습니다. 없는 키는 그 부분만 건너뜁니다.
- Settings → Pages의 출처(Source)를 "GitHub Actions"로 고릅니다.
- KAMIS 품종 목록을 실제 응답으로 다시 만들려면 "Run workflow" 창에서 "품종 목록도 다시 만들기"를 켜고 돌립니다.

## 손볼 때 알아 둘 것

- 화면 파일(HTML·CSS·JS·아이콘)을 고치면 `sw.js` 맨 위 `CACHE`의 숫자를 올립니다(예: `mp-v17` → `mp-v18`). 안 올리면 폰에 옛 화면이 남습니다. 올리면 폰은 새 화면을 받는 대로 저절로 한 번 다시 엽니다.
- 이마트 묶음은 [collector/emart_groups.json](collector/emart_groups.json)을 손으로 고칩니다(묶음 이름 → 상품명 목록, 적은 순서가 칸 순서). 목록에 없는 새 상품은 "이마트 기타" 칸에 모이고 Actions 기록에 이름이 남습니다.
- `data/prices.json`과 `data/emart.json`은 손으로 고치지 않습니다. Actions가 평일마다 커밋하므로 푸시 전에 `git pull --rebase`로 먼저 받아 옵니다.
- 아이콘은 `uv run python tools/make_icons.py`로 다시 만듭니다.
- 가격 숫자 글꼴(Geist에서 숫자만 자른 `fonts/geist-num.woff2`)은 `uv run python tools/make_font.py`로 다시 만듭니다. 원본은 git 밖 `tools/fonts-src/`에 둡니다(받는 곳은 도구 맨 위 설명).

## 폴더

| 경로 | 내용 |
|---|---|
| `index.html`, `app.js`, `store.js`, `style.css`, `sw.js`, `manifest.webmanifest`, `icons/`, `fonts/` | 화면(정적 사이트). `store.js`는 즐겨찾기 저장, `sw.js`는 오프라인용 서비스 워커, `fonts/`는 가격 숫자 글꼴 |
| `collector/` | 수집 스크립트. KAMIS(`kamis.py`, `compute.py`), 참가격(`champrice.py`, `emart.py`), 품종 목록 `items.json`, 이마트 묶음 `emart_groups.json` |
| `data/` | 화면이 읽는 파일. Actions가 만든다 |
| `tools/` | 아이콘·숫자 글꼴 만들기와 그 시험, 배포 파일 점검 시험 |
| `.github/workflows/collect.yml` | 예약 수집, 커밋, 배포 |
| `docs/` | 설계(`design.md`), 결정 기록(`decisions.md`), 구현 계획(`plan*.md`) |
