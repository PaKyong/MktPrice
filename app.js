// 장보기 가격 화면: 첫 화면(즐겨찾기, 전체 품목), 검색, 상세.
// 가격 계산은 수집 스크립트가 끝내 두었고, 여기서는 보여 주기만 한다.

import { addFavorite, getFavorites, moveFavorite, removeFavorite } from "./store.js";

// chip: 전체 품목에서 고른 칸 이름(부류, 이마트 묶음, "싼 편"·"비싼 편"). null이면 첫 부류(채소류)다.
// 앱을 닫을 때까지 기억한다. chipsLeft: 칸 줄을 옆으로 민 위치.
// cameFromApp, homeScroll: 상세로 들어오기 전 화면과 그 화면의 스크롤 위치(←로 돌아갈 때 쓴다).
// emart: data/emart.json(참가격 이마트 값, 없으면 null), emartItems: 그 상품들을 묶음 순서로, 묶음 안은 상품명 가나다순으로.
const state = { data: null, emart: null, emartItems: [], byId: new Map(), favorites: [], query: "", chip: null,
                chipsLeft: 0, cameFromApp: false, homeScroll: 0 };
const $ = (id) => document.getElementById(id);
// 이마트 상품의 id(즐겨찾기 열쇠, 상세 주소)는 상품명 앞에 이것을 붙인다.
const EMART_ID = "이마트:";
// 전체 품목에서 이마트 상품이 들어갈 칸 이름. 묶음이 안 붙은 옛 파일이면 "이마트" 칸 하나다.
const emartCategory = (e) => (e.group ? `이마트 ${e.group}` : "이마트");

// ---- 글자 만들기 ----

const won = (n) => `${n.toLocaleString("ko-KR")}원`;
const md = (iso) => {
  const [, m, d] = iso.split("-");
  return `${Number(m)}월 ${Number(d)}일`;
};
// 상품명에 %가 든 이마트 상품이 있어 주소에 넣을 때는 늘 인코딩한다.
const itemHref = (id) => `#/item/${encodeURIComponent(id)}`;
// 메신저가 주소를 풀어서 보내면 "82%(86g)"처럼 뒤에 16진수 두 자리가 없는 %가 와서 풀기가 실패한다.
// 그런 %만 "%25"로 바꿔 풀고, 그래도 안 되면 받은 글자를 그대로 쓴다.
function decodeId(raw) {
  try {
    return decodeURIComponent(raw.replace(/%(?![0-9a-f]{2})/gi, "%25"));
  } catch {
    return raw;
  }
}
// 품종 이름에 품목 이름이 들어 있으면 품종 이름만 쓴다("양파 · 양파" → "양파", "파 · 대파" → "대파").
const displayName = (e) => (e.kind.includes(e.item) ? e.kind : `${e.item} ${e.kind}`);
const perUnit = (e) => (e.measure === "weight" ? "100g당" : `1${e.unit_label}당`);

// 평년 비교 한 마디. 색은 신호가 싼 편이면 빨강(down), 비싼 편이면 파랑(up), 보통이면 없음.
function normalText(e) {
  const x = e.change.normal;
  if (x === null || x === undefined) return { text: "평년 값 없음", cls: "" };
  const cls = e.signal === "싼 편" ? "down" : e.signal === "비싼 편" ? "up" : "";
  const r = Math.round(Math.abs(x));
  if (r === 0) return { text: "평년과 같아요", cls };
  return { text: `평년보다 ${r}% ${x < 0 ? "싸요" : "비싸요"}`, cls };
}

// 검색어 뒤에 붙일 "로"·"으로". 마지막 글자가 한글이고 받침이 있으면(ㄹ 받침은 빼고) "으로".
function ro(word) {
  const code = word.charCodeAt(word.length - 1) - 0xac00;
  if (code < 0 || code >= 11172) return "로";
  const final = code % 28;
  return final === 0 || final === 8 ? "로" : "으로";
}

// 지난 값 비교 한 마디: "15% 올랐어요"(파랑), "48% 내렸어요"(빨강), 반올림해 0이면 "같아요".
function changeText(v) {
  const r = Math.round(Math.abs(v));
  if (r === 0) return { text: "같아요", cls: "" };
  return v < 0 ? { text: `${r}% 내렸어요`, cls: "down" } : { text: `${r}% 올랐어요`, cls: "up" };
}

// 작은 요소 만들기 도우미. 글자는 textContent로만 넣는다.
function h(tag, attrs = {}, ...children) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v === null || v === undefined || v === false) continue;
    if (k === "class") el.className = v;
    else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
    else el.setAttribute(k, v === true ? "" : v);
  }
  for (const c of children.flat()) {
    if (c === null || c === undefined || c === false) continue;
    el.append(c instanceof Node ? c : document.createTextNode(String(c)));
  }
  return el;
}

// 가격: Geist 숫자에 한 단계 작은 "원"을 붙인다(<b class="num">1,234<small>원</small></b>).
const wonNode = (n, cls) => h("b", { class: cls ? `num ${cls}` : "num" }, n.toLocaleString("ko-KR"), h("small", {}, "원"));
// 줄 아래의 작은 표시("이마트", "이마트 2곳", "11월 2일 값").
const mini = (text) => h("span", { class: "mini" }, text);

function svgEl(tag, attrs, text) {
  const el = document.createElementNS("http://www.w3.org/2000/svg", tag);
  for (const [k, v] of Object.entries(attrs)) el.setAttribute(k, v);
  if (text) el.textContent = text;
  return el;
}

// ---- 기준일 줄 ----

// 기준일 다음 날부터 오늘 전날까지의 평일 수(한국 날짜). 오늘 값은 저녁에 오므로 세지 않는다.
function missedWeekdays(asOf) {
  const today = new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Seoul" }).format(new Date());
  const day = new Date(`${asOf}T00:00:00Z`);
  const end = new Date(`${today}T00:00:00Z`);
  let n = 0;
  for (day.setUTCDate(day.getUTCDate() + 1); day < end; day.setUTCDate(day.getUTCDate() + 1)) {
    if (day.getUTCDay() !== 0 && day.getUTCDay() !== 6) n += 1;
  }
  return n;
}

function renderTop() {
  const { data } = state;
  $("asof").textContent = `${data.source} ${md(data.as_of)} 값`
    + (state.emart ? `, 이마트 ${md(state.emart.as_of)} 조사` : "");
  $("print-sample").hidden = data.source !== "샘플";
  const offline = $("print-offline");
  offline.hidden = navigator.onLine;
  offline.textContent = `인터넷 연결 없음. ${md(data.as_of)} 값이에요.`;
  // 평일 이틀 치 넘게 새 값이 없으면 예약 실행이 멈췄을 수 있다. 인터넷이 없을 때는 위 띠로 충분하다.
  const stale = $("print-stale");
  stale.hidden = !navigator.onLine || data.source === "샘플" || missedWeekdays(data.as_of) <= 2;
  stale.textContent = `가격이 ${md(data.as_of)} 뒤로 안 바뀌었어요`;
}

// ---- 한 줄 ----

// 줄 가운데의 30일 작은 그래프. 색은 평년 비교 한 마디에만 쓰므로 흐린 선 하나. 값이 둘보다 적으면 그리지 않는다.
// 세로 폭은 적어도 평균의 위아래 10%로 잡는다. 꽉 채워 그리면 30일 동안 1%만 움직여도 절벽처럼 보인다.
function sparkline(trend) {
  if (trend.length < 2) return null;
  const values = trend.map(([, v]) => v);
  const low = Math.min(...values);
  const high = Math.max(...values);
  const mean = values.reduce((a, b) => a + b, 0) / values.length;
  const half = Math.max((high - low) / 2, mean * 0.1);
  const min = (low + high) / 2 - half;
  const points = values
    .map((v, i) => `${((i / (values.length - 1)) * 48).toFixed(1)},${(21 - ((v - min) / (half * 2)) * 20).toFixed(1)}`)
    .join(" ");
  const svg = svgEl("svg", { viewBox: "0 0 48 22", class: "spark", "aria-hidden": "true" });
  svg.append(svgEl("polyline", { points }));
  return svg;
}

// 즐겨찾기에 든 품목 이름 뒤에 붙이는 노란 ★.
const favMark = (e) => (state.favorites.some((f) => f.id === e.id)
  ? h("span", { class: "fav-mark", role: "img", "aria-label": "즐겨찾기" }, "★") : null);

// 즐겨찾기·전체 품목·검색 결과의 한 줄: 왼쪽 이름과 평년 비교 한 마디, 가운데 30일 그래프, 오른쪽 단위 가격과 단위.
// markFav: 전체 품목과 검색 결과에서 즐겨찾기에 든 품목이면 이름 뒤에 ★를 붙인다(즐겨찾기 칸 안은 모두 즐겨찾기라 뺀다).
function rowNode(e, markFav) {
  const normal = normalText(e);
  return h("li", {},
    h("a", { class: "row", href: itemHref(e.id) },
      h("span", { class: "row__name" }, displayName(e), markFav ? favMark(e) : null,
        h("span", { class: "row__sub" }, h("span", { class: normal.cls || null }, normal.text),
          // 일부 품종만 받지 못한 날은 그 품종이 옛 값이다.
          e.as_of !== state.data.as_of ? mini(`${md(e.as_of)} 값`) : null)),
      sparkline(e.trend) || h("span", {}),
      h("span", { class: "row__price" }, wonNode(e.unit_price), h("span", { class: "row__unit" }, perUnit(e)))));
}

// 이마트 상품의 한 줄: 왼쪽 상품명과 행사 때 최저 값, 오른쪽 평소 값. 그래프 칸은 없다(조사가 6번뿐).
// showTag: 검색 결과와 즐겨찾기처럼 KAMIS 품종과 섞이는 곳에서 "이마트" 표시를 붙인다.
function emartRowNode(e, showTag, markFav) {
  return h("li", {},
    h("a", { class: "row row--emart", href: itemHref(e.id) },
      h("span", { class: "row__name" }, e.name, markFav ? favMark(e) : null,
        h("span", { class: "row__sub" }, showTag ? mini("이마트") : null,
          e.low ? h("span", { class: "down" }, `행사 때 ${won(e.low.price)}`) : "행사 없음",
          // 지점이 한두 곳뿐인 값은 덜 믿을 만해서 알린다.
          e.stores <= 2 ? mini(`이마트 ${e.stores}곳`) : null,
          // 마지막 조사일에 값이 없던 상품은 그 전 값이다.
          e.last_day !== state.emart.as_of ? mini(`${md(e.last_day)} 값`) : null)),
      h("span", { class: "row__price" }, wonNode(e.usual), h("span", { class: "row__unit" }, "평소 값"))));
}

const itemRow = (e, showTag, markFav) => (e.emart ? emartRowNode(e, showTag, markFav) : rowNode(e, markFav));

// 즐겨찾기에 있지만 가격 파일에서 빠진 품종(철이 지남)이나 이마트 상품(조사가 끊김).
// 이마트 파일을 아직 못 받았으면(4초 넘게 늦음) 빠진 것이 아니라 받는 중이다.
function missingRowNode(fav) {
  const emart = fav.id.startsWith(EMART_ID);
  return h("li", {},
    h("a", { class: "row row--missing", href: itemHref(fav.id) },
      h("span", { class: "row__name" }, fav.name || fav.id,
        h("span", { class: "row__sub" }, emart ? mini("이마트") : null,
          emart && !state.emart ? "이마트 값 받는 중" : "지금 값 없음"))));
}

// 장 볼 때 자주 찾는 부류 순서. 여기 없는 부류는 뒤에 붙는다.
const BROWSE_ORDER = ["채소류", "과일류", "수산물", "식량작물", "특용작물"];
const orderOf = (c) => (BROWSE_ORDER.includes(c) ? BROWSE_ORDER.indexOf(c) : BROWSE_ORDER.length);

// 전체 품목과 검색 결과의 순서: 부류 → 품목 가나다 → 파일 순서(정렬은 같은 값끼리 원래 순서를 지킨다).
function browseOrder() {
  return [...state.data.items].sort((a, b) =>
    orderOf(a.category) - orderOf(b.category) || a.item.localeCompare(b.item, "ko"));
}

// ---- 첫 화면: 즐겨찾기와 전체 품목 ----

function renderHome() {
  const view = $("view");
  view.replaceChildren();
  const favRows = state.favorites.map((f) => {
    const li = state.byId.has(f.id) ? itemRow(state.byId.get(f.id), true, false) : missingRowNode(f);
    li.dataset.id = f.id;
    return li;
  });
  const favList = favRows.length ? h("ul", { class: "rows rows--fav" }, favRows) : null;
  if (favList) setupFavGestures(favList);
  view.append(h("section", { class: "section" },
    h("h2", { class: "sec" }, "즐겨찾기"),
    favList ?? h("p", { class: "empty" }, "상세 화면에서 ☆를 누르면 여기 모여요"),
    favRows.length > 1 ? h("p", { class: "fav-hint" }, "길게 눌러 끌면 순서를 바꾸고, 옆으로 밀면 빠져요") : null));

  const byCategory = new Map();
  for (const e of browseOrder()) {
    if (!byCategory.has(e.category)) byCategory.set(e.category, []);
    byCategory.get(e.category).push(e);
  }
  // 이마트 상품은 KAMIS 부류들 뒤에 묶음마다 칸을 둔다(emartItems가 이미 묶음 순서다).
  for (const e of state.emartItems) {
    const c = emartCategory(e);
    if (!byCategory.has(c)) byCategory.set(c, []);
    byCategory.get(c).push(e);
  }
  // 칸 줄: 맨 앞에 "싼 편", "비싼 편", 그 뒤에 부류와 이마트 묶음. 늘 칸 하나를 골라 그 칸의 품목만 보인다.
  // 고른 칸이 없어졌으면(새 가격 파일에 싼 편이 하나도 없는 날 등) 첫 부류로 돌아간다.
  const tabs = new Map([...signalLists(), ...byCategory]);
  const chosen = tabs.has(state.chip) ? state.chip : byCategory.keys().next().value;
  const title = chosen === "싼 편" || chosen === "비싼 편"
    ? `평년보다 ${Math.round(state.data.threshold_pct)}% 넘게 ${chosen === "싼 편" ? "싼" : "비싼"} 품종`
    : chosen;
  // 칸과 칸 제목은 이름 뒤에 흐린 개수를 따로 붙인다("채소류 43").
  const count = (n) => h("span", { class: "chip__n" }, n);
  view.append(h("section", { class: "section" },
    h("h2", { class: "sec" }, "전체 품목"),
    h("nav", { class: "chips", "aria-label": "부류" },
      [...tabs].map(([c, list]) => h("button", { type: "button", class: c === chosen ? "chip chip--on" : "chip",
                                                 "aria-pressed": String(c === chosen), onclick: () => choose(c) },
        c, count(list.length)))),
    h("section", { class: "cat-block" },
      h("h3", { class: "cat" }, title, count(tabs.get(chosen).length)),
      h("ul", { class: "rows" }, tabs.get(chosen).map((e) => itemRow(e, false, true))))));
  // 다시 그려도, 상세에 갔다 와도 옆으로 밀어 둔 부류 칸 줄 위치를 그대로 둔다(render가 지우기 전에 적어 둔다).
  view.querySelector(".chips").scrollLeft = state.chipsLeft;
}

// ---- 즐겨찾기 끌어 옮기기, 밀어 빼기 ----

// 길게 누르면(그동안 거의 안 움직이면) 줄을 들어 위아래로 끌어 순서를 바꾼다.
// 옆으로 밀면 줄이 따라오고, 줄 폭의 40% 넘게 밀고 떼면 바로 빠진다(아래에 "되돌리기" 띠).
// 위아래로 먼저 움직이면 보통처럼 목록이 내려간다. 끌거나 민 뒤에는 눌림이 상세로 가지 않는다.
const HOLD_MS = 450;
const MOVE_PX = 10;
function setupFavGestures(ul) {
  let g = null;
  const reset = () => {
    if (!g) return;
    clearTimeout(g.timer);
    g.li.classList.remove("row--lifted");
    g.li.style.transform = "";
    g = null;
  };
  ul.addEventListener("touchstart", (ev) => {
    const li = ev.target.closest("li[data-id]");
    if (!li || ev.touches.length > 1) return;
    const t = ev.touches[0];
    g = { li, x0: t.clientX, y0: t.clientY, dx: 0, mode: "wait", start: [...ul.children].indexOf(li) };
    g.timer = setTimeout(() => {
      if (g?.mode !== "wait") return;
      g.mode = "drag";
      li.classList.add("row--lifted");
      navigator.vibrate?.(10);
    }, HOLD_MS);
  }, { passive: true });
  ul.addEventListener("touchmove", (ev) => {
    if (!g) return;
    const t = ev.touches[0];
    const dx = t.clientX - g.x0;
    const dy = t.clientY - g.y0;
    if (g.mode === "wait") {
      if (Math.abs(dx) > MOVE_PX && Math.abs(dx) > Math.abs(dy)) g.mode = "swipe";
      else if (Math.abs(dy) > MOVE_PX) g.mode = "scroll";
      if (g.mode !== "wait") clearTimeout(g.timer);
    }
    if (g.mode === "scroll") return;
    if (g.mode === "wait") return;
    ev.preventDefault();
    if (g.mode === "swipe") {
      g.dx = dx;
      g.li.style.transform = `translateX(${dx}px)`;
      return;
    }
    // 끄는 중: 손가락이 옆 줄의 절반을 넘으면 그 줄과 자리를 바꾼다. 줄이 옮겨 간 만큼 기준점도 옮긴다.
    const prev = g.li.previousElementSibling;
    const next = g.li.nextElementSibling;
    if (next && dy > next.offsetHeight / 2) {
      next.after(g.li);
      g.y0 += next.offsetHeight;
    } else if (prev && dy < -prev.offsetHeight / 2) {
      prev.before(g.li);
      g.y0 -= prev.offsetHeight;
    }
    g.li.style.transform = `translateY(${t.clientY - g.y0}px)`;
  }, { passive: false });
  ul.addEventListener("touchend", async () => {
    if (!g) return;
    const { li, mode, dx, start } = g;
    const id = li.dataset.id;
    // 끌거나 민 다음의 눌림(click)은 상세로 가지 않게 한 번 막는다.
    if (mode === "drag" || mode === "swipe") ul.dataset.blockClick = "1";
    reset();
    if (mode === "drag") {
      const to = [...ul.children].indexOf(li);
      if (to !== start) {
        await moveFavorite(id, to);
        await refresh();
      }
    } else if (mode === "swipe" && Math.abs(dx) > li.offsetWidth * 0.4) {
      const fav = state.favorites.find((f) => f.id === id);
      await removeFavorite(id);
      await refresh();
      // 5초 동안 되돌릴 수 있다. 되돌리면 원래 자리로 넣는다.
      showToast(`${fav.name || fav.id}, 즐겨찾기에서 뺐어요`, async () => {
        await addFavorite(fav.id, fav.name);
        await moveFavorite(fav.id, start);
        await refresh();
      });
    }
  });
  ul.addEventListener("touchcancel", reset);
  ul.addEventListener("click", (ev) => {
    if (ul.dataset.blockClick) {
      ev.preventDefault();
      delete ul.dataset.blockClick;
    }
  }, true);
  // 길게 누르면 뜨는 링크 메뉴(안드로이드)를 막는다. 아이폰 미리보기는 CSS로 막는다.
  ul.addEventListener("contextmenu", (ev) => ev.preventDefault());
}

// 아래에 잠깐 띄우는 띠. onUndo가 있으면 "되돌리기" 단추를 붙여 5초, 없으면 2초 보인다.
let toastTimer = null;
function showToast(text, onUndo) {
  const toast = $("toast");
  const undo = $("toast-undo");
  $("toast-text").textContent = text;
  undo.hidden = !onUndo;
  undo.onclick = onUndo ? async () => {
    clearTimeout(toastTimer);
    toast.hidden = true;
    await onUndo();
  } : null;
  toast.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { toast.hidden = true; }, onUndo ? 5000 : 2000);
}

// 신호가 "싼 편"·"비싼 편"인 KAMIS 품종. 평년 대비 차이가 큰 것부터. 없는 쪽은 칸을 두지 않는다.
function signalLists() {
  const lists = new Map();
  for (const [signal, sign] of [["싼 편", 1], ["비싼 편", -1]]) {
    const list = state.data.items.filter((e) => e.signal === signal)
      .sort((a, b) => sign * (a.change.normal - b.change.normal));
    if (list.length) lists.set(signal, list);
  }
  return lists;
}

// 칸을 누르면 그 칸의 품목으로 바꿔 그린다. 목록을 내려 칸 줄이 맨 위에 붙어 있었으면 새 목록의 첫 줄이
// 칸 줄 바로 아래 오게 올리고, 즐겨찾기가 보이던 자리면 그대로 둔다(즐겨찾기가 위로 밀려 가지 않게).
function choose(name) {
  $("search").blur();
  state.chip = name;
  render();
  const chips = document.querySelector(".chips");
  const covered = chips.offsetHeight + parseFloat(getComputedStyle(chips).top);
  const top = $("view").querySelector(".cat-block").getBoundingClientRect().top + window.scrollY - covered;
  window.scrollTo(0, Math.min(window.scrollY, top));
}

// ---- 검색 ----

// 영어 대소문자와 띄어쓰기를 가리지 않게 맞춘다("cj" → CJ, "고향 만두" → 고향만두).
const norm = (s) => s.toLowerCase().replace(/\s+/g, "");
// 검색어마다 더 찾을 낱말. 이름에 없는 말로 찾기 쉬운 것만 둔다(예: "계란"인데 상품명은 "유정란").
const MORE_WORDS = {
  계란: ["유정란", "달걀"],
  달걀: ["계란", "유정란"],
  라면: ["너구리", "탕면", "왕뚜껑", "큰사발"],
  소고기: ["쇠고기"],
  쇠고기: ["소고기"],
  생수: ["삼다수", "아이시스"],
  물: ["삼다수", "아이시스"],
  휴지: ["화장지", "3겹"],
  맥주: ["카스", "하이트", "에일"],
  소주: ["참이슬", "처음처럼"],
  커피: ["맥심", "카누", "맥스웰", "네스프레소", "돌체구스토", "라떼", "콜드브루"],
  아이스크림: ["메로나", "월드콘", "부라보콘", "투게더", "싸만코", "돼지바", "바밤바"],
  치약: ["2080", "페리오토탈7오리지널"],
  생리대: ["쏘피", "좋은느낌", "화이트수퍼"],
};
// 한글 낱자의 초성("신" → "ㅅ"). 한글 낱자가 아니면 그대로 둔다.
const CHOSEONG = "ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ";
const initials = (s) => [...s].map((ch) => {
  const code = ch.charCodeAt(0) - 0xac00;
  return code >= 0 && code < 11172 ? CHOSEONG[Math.floor(code / 588)] : ch;
}).join("");

// 검색어로 이름을 고르는 함수를 만든다. 초성만 쳤으면 이름의 초성으로("ㅅㄹㅁ" → 신라면) 찾는다.
function matcher(query) {
  const q = norm(query);
  if (/^[ㄱ-ㅎ]+$/.test(q)) return (name) => initials(norm(name)).includes(q);
  const words = [q, ...(MORE_WORDS[q] ?? [])];
  return (name) => {
    const n = norm(name);
    return words.some((w) => n.includes(w));
  };
}

function renderSearch() {
  const view = $("view");
  view.replaceChildren();
  const q = state.query;
  const match = matcher(q);
  // KAMIS 품종 뒤에 이마트 상품(전체 품목과 같은 순서).
  const found = [...browseOrder().filter((e) => match(e.item) || match(e.kind)),
                 ...state.emartItems.filter((e) => match(e.name))];
  if (!found.length) {
    view.append(h("p", { class: "found" }, `"${q}"에 맞는 품목이 없어요. 다른 이름으로 찾아 보세요.`));
    return;
  }
  view.append(h("p", { class: "found" }, `"${q}"${ro(q)} 찾은 품종 ${found.length}개`),
    h("ul", { class: "rows" }, found.map((e) => itemRow(e, true, true))));
}

// ---- 상세 ----

// 상세의 30일 그래프. 큰 글씨와 같은 단위 가격(100g당, 1개당)으로 그린다. 마지막 값 높이에 점선을 긋고,
// 가장 높은·낮은 점 곁에 값을, 아래 양 끝에 처음·끝 날짜를 쓴다. 값이 둘 이상일 때만 부른다.
// 조사 단위 값에 (단위 가격 ÷ 조사 단위 값)을 곱해 바꾼다. 오늘 값은 큰 글씨와 똑같고, 다른 날은 1원 안쪽으로 맞다.
function trendChart(e) {
  const values = e.trend.map(([, v]) => Math.round((v * e.unit_price) / e.price));
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const w = 335;
  const top = 24;
  const bottom = 92;
  const x = (i) => 2 + (i / (values.length - 1)) * (w - 8);
  const y = (v) => bottom - ((v - min) / span) * (bottom - top);
  const points = values.map((v, i) => `${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(" ");
  // "최고 659"·"최저 559": 글자가 그림 밖으로 나가지 않게 양옆 30px 안쪽에, 날짜 줄과 겹치지 않게 110 위에 둔다.
  const mark = (word, v, dy) => {
    const cx = Math.min(Math.max(x(values.indexOf(v)), 30), w - 30);
    const text = svgEl("text", { x: cx, y: Math.min(y(v) + dy, 110), "text-anchor": "middle", class: "chart__label" },
      `${word} `);
    text.append(svgEl("tspan", { class: "chart__value num" }, v.toLocaleString("ko-KR")));
    return text;
  };
  const last = values.at(-1);
  const svg = svgEl("svg", { viewBox: `0 0 ${w} 132`, class: "chart", role: "img",
                             "aria-label": `최근 30일 ${perUnit(e)} 평균: 최저 ${won(min)}, 최고 ${won(max)}` });
  svg.append(
    svgEl("line", { x1: 0, y1: y(last), x2: w, y2: y(last), class: "chart__base" }),
    svgEl("polyline", { points, class: "chart__line" }),
    svgEl("circle", { cx: x(values.length - 1), cy: y(last), r: 3.5, class: "chart__dot" }),
    mark("최고", max, -9),
    mark("최저", min, 19),
    svgEl("text", { x: 0, y: 128, class: "chart__label" }, md(e.trend[0][0])),
    svgEl("text", { x: w, y: 128, "text-anchor": "end", class: "chart__label" }, md(e.trend.at(-1)[0])));
  return svg;
}

// 가게 범위 막대. 가게 절반 칸(band), 평균 눈금(avg), 점(dots: [값, 칠할 class]), 아래 글자(labels: [값, 숫자, 흐린 말]).
// 가격표와의 비교는 사람이 막대를 보고 한다(값을 입력받지 않는다).
function priceRuler({ min, max, band, avg, dots = [], labels }) {
  const at = (v) => ((v - min) / (max - min)) * 100;
  return h("div", { class: "ruler", "aria-hidden": "true" },
    h("div", { class: "ruler__track" }),
    h("div", { class: "ruler__band", style: `left:${at(band[0])}%;width:${at(band[1]) - at(band[0])}%` }),
    avg !== undefined ? h("div", { class: "ruler__avg", style: `left:${at(avg)}%` }) : null,
    dots.map(([v, cls]) => h("div", { class: `ruler__dot ${cls}`, style: `left:${at(v)}%` })),
    labels.map(([v, text, sub]) => h("div", { class: "ruler__lab num", style: `left:${at(v)}%` },
      text, sub ? h("span", {}, sub) : null)));
}

// 상세 정보 줄: 왼쪽 보조 글씨 이름, 오른쪽 값.
const info = (label, value) => h("li", { class: "info__row" }, h("span", {}, label), h("span", {}, value));

// 상세 위 막대의 ☆/★. 누르면 즐겨찾기에 넣거나 빼고 아래에 잠깐 띠를 띄운다. 별 모양은 CSS가 aria-pressed로 칠한다.
// 본문은 다시 그리지 않는다. 철 지난 품종은 즐겨찾기에서 빼면 이름을 알 곳이 없어 제목이 코드로 바뀌기 때문이다.
function renderStar(id, name, on) {
  const star = $("star");
  star.setAttribute("aria-pressed", String(on));
  star.setAttribute("aria-label", on ? "즐겨찾기에서 빼기" : "즐겨찾기에 넣기");
  star.onclick = async () => {
    if (on) await removeFavorite(id);
    else await addFavorite(id, name);
    state.favorites = await getFavorites();
    renderStar(id, name, !on);
    showToast(on ? "즐겨찾기에서 뺐어요" : "즐겨찾기에 넣었어요");
  };
}

// 큰 가격 아래 범위 묶음: 소제목, 막대, 한 줄 설명.
const rangeBlock = (title, ruler, caption) =>
  h("section", { class: "range" }, h("h2", { class: "sec" }, title), ruler, h("p", { class: "range__cap" }, caption));

// 이마트 상품 상세: 평소 값, 행사 때 최저 값, 행사와 평소 값 막대, 최근 3개월 조사일별 대표값.
// 행사가 없었으면 조사 값이 모두 평소 값이라 막대에 보일 것이 없어 막대 묶음을 뺀다.
function renderEmartDetail(e) {
  const low = e.low;
  const num = (n) => n.toLocaleString("ko-KR");
  const range = low && rangeBlock("행사와 평소 값", priceRuler({
    min: low.price - (e.usual - low.price) / 2, max: e.usual + (e.usual - low.price) / 2,
    band: [low.price, e.usual],
    dots: e.history.map(([, price]) => [price, price === low.price ? "ruler__dot--low" : ""]),
    labels: [[low.price, num(low.price), "행사"], [e.usual, num(e.usual), "평소"]] }),
  `3개월 동안 이마트에서 ${won(low.price)}부터 ${won(e.usual)} 사이였어요`);
  // 행사 때 몇십 원만 내린 상품은 %가 반올림해 0이 되어 원으로 말한다.
  const off = low ? Math.round(-low.pct) : 0;
  const lowNote = low && `${md(low.day)}, 평소보다 ${off > 0 ? `${off}%` : won(e.usual - low.price)} 싸요`;
  $("view").append(
    h("section", { class: "detail" },
      h("p", { class: "detail__cat" }, e.group ? `이마트 ${e.group}` : "이마트"),
      h("h1", { class: "detail__name" }, e.name),
      h("p", { class: "detail__cap" }, `이마트 ${e.stores}곳 평소 값, ${md(e.last_day)} 조사`),
      wonNode(e.usual, "detail__price"),
      h("p", { class: "detail__sig" }, low
        ? [h("span", { class: "pill pill--down" }, `행사 때 ${won(low.price)}`), h("span", {}, lowNote)]
        : h("span", { class: "pill" }, "3개월 동안 행사 없음")),
      range,
      h("h2", { class: "sec" }, "최근 3개월 조사"),
      h("ul", { class: "info" }, e.history.map(([day, price]) =>
        info(md(day), h("span", { class: day === low?.day ? "num down" : "num" }, won(price))))),
      h("p", { class: "detail__foot" },
        "한국소비자원 참가격. 행사 표시가 없어서 3개월 동안 본 값 가운데 가장 높은 값을 평소 값으로 봤어요.")));
}

function renderDetail(id) {
  const view = $("view");
  view.replaceChildren();
  const e = state.byId.get(id);
  const fav = state.favorites.find((x) => x.id === id);
  // 이마트 항목에는 품목·품종 이름이 없어 displayName을 부르기 전에 가른다.
  if (e?.emart) {
    renderStar(id, e.name, Boolean(fav));
    renderEmartDetail(e);
    return;
  }
  const name = e ? displayName(e) : fav?.name || id;
  renderStar(id, name, Boolean(fav));
  if (!e) {
    view.append(h("section", { class: "detail detail--empty" },
      h("h1", { class: "detail__name" }, name),
      h("p", { class: "empty" }, !id.startsWith(EMART_ID)
        ? "지금 값이 없어요. 철이 지나 KAMIS 조사 값이 없는 품목이에요."
        : state.emart
          ? "지금 값 없음. 최근 3개월 동안 이마트 조사 값이 없는 상품이에요."
          : "이마트 값을 아직 받지 못했어요. 받으면 바로 보여요.")));
    return;
  }
  // 비교 기준이 대형유통 평균이면 "대형마트 33곳 평균", 전국 평균으로 바뀌었으면 "조사처 33곳 평균".
  const who = state.data.basis.compare === "전국 대형유통 평균" ? "대형마트" : "조사처";
  const num = (n) => n.toLocaleString("ko-KR");
  const normal = normalText(e);
  const changes = [["1주 전보다", e.change.week], ["1개월 전보다", e.change.month], ["1년 전보다", e.change.year]]
    .filter(([, v]) => v !== null);
  // 가격 막대: 가게 가운데 절반을 칸, 평균을 눈금으로. 양옆 여백은 칸 폭의 절반, 적어도 평균의 12%.
  // 칸 양 끝 숫자가 너무 가까우면(막대 폭의 18% 안쪽) 가운데에 "153~199"로 하나만 쓴다.
  const [lo, hi] = e.unit_range;
  const avg = e.unit_price;
  const pad = Math.max((hi - lo) / 2, avg * 0.12);
  const min = Math.min(lo, avg) - pad;
  const max = Math.max(hi, avg) + pad;
  const at = (v) => (v - min) / (max - min);
  const labels = lo === hi ? [[lo, num(lo)]]
    : at(hi) - at(lo) < 0.18 ? [[(lo + hi) / 2, `${num(lo)}~${num(hi)}`]]
      : [[lo, num(lo)], [hi, num(hi)]];
  // 평균 눈금 아래 "평균": 양 끝 숫자와 막대 폭의 14% 넘게 떨어져 있을 때만 붙인다(겹치지 않게).
  if (labels.length === 2 && labels.every(([v]) => Math.abs(at(v) - at(avg)) > 0.14)) labels.push([avg, "", "평균"]);
  const span = lo === hi ? won(lo) : `${num(lo)}~${won(hi)}`;
  const caption = e.stores >= 4 ? `${who} 절반은 ${span}이에요` : `조사한 ${e.stores}곳은 ${span}이에요`;
  view.append(
    h("section", { class: "detail" },
      h("p", { class: "detail__cat" }, e.category),
      h("h1", { class: "detail__name" }, name),
      h("p", { class: "detail__cap" }, `${who} ${e.stores}곳 평균, ${perUnit(e)}`),
      wonNode(e.unit_price, "detail__price"),
      h("p", { class: "detail__sig" },
        h("span", { class: normal.cls ? `pill pill--${normal.cls}` : "pill" }, normal.text), h("span", {}, `${md(e.as_of)} 값`)),
      rangeBlock("가게마다", priceRuler({ min, max, band: [lo, hi], avg, labels }), caption),
      h("h2", { class: "sec" }, "30일"),
      e.trend.length >= 2 ? trendChart(e) : h("p", { class: "empty" }, "추이 값이 하루치뿐이에요"),
      h("h2", { class: "sec" }, "지난 값과 비교"),
      h("ul", { class: "info" },
        changes.map(([label, v]) => {
          const c = changeText(v);
          return info(label, h("span", { class: c.cls || null }, c.text));
        }),
        info(`${e.unit} 값`, h("span", { class: "num" }, won(e.price)))),
      h("p", { class: "detail__foot" }, "평년과 지난 값은 KAMIS 전체 평균으로 견줘요.")));
}

// ←: 앱 안에서 들어왔으면 브라우저 뒤로 가기(검색어와 보던 자리가 그대로 남는다).
// 상세 주소로 바로 열었으면 뒤로 가면 앱 밖으로 나가므로 첫 화면으로 간다. 이때 상세 기록을
// 첫 화면으로 바꿔치기해, 폰의 뒤로 가기로 상세에 다시 들어와 ←가 앱 밖으로 나가는 일을 막는다.
function goBack() {
  if (state.cameFromApp) history.back();
  else location.replace("#/");
}

// ---- 화면 고르기 ----

function render() {
  if (!state.data) return;
  // 첫 화면을 지우기 전에 칸 줄을 옆으로 민 위치를 적어 둔다.
  const chips = document.querySelector(".chips");
  if (chips) state.chipsLeft = chips.scrollLeft;
  renderTop();
  const match = location.hash.match(/^#\/item\/(.+)$/);
  $("search-form").hidden = Boolean(match);
  $("bar-detail").hidden = !match;
  $("home-head").hidden = Boolean(match);
  $("search-clear").hidden = !state.query;
  // 검색 중에는 제목과 안내 쪽지를 숨기고 띠만 남긴다(CSS).
  document.body.classList.toggle("searching", Boolean(state.query) && !match);
  // 상세에서는 띠를 가격표 받침 위에 띄운다(CSS).
  document.body.classList.toggle("detail", Boolean(match));
  if (match) renderDetail(decodeId(match[1]));
  else if (state.query) renderSearch();
  else renderHome();
}

async function refresh() {
  state.favorites = await getFavorites();
  render();
}

// 가격 파일(data/prices.json, data/emart.json)을 받는다. 못 받으면(이마트 파일은 키를 넣기 전에는 없다) null.
async function fetchJson(path) {
  try {
    const res = await fetch(path, { cache: "no-cache" });
    return res.ok ? await res.json() : null;
  } catch {
    return null;
  }
}

// 이마트 파일은 폰에 저장본이 없을 때(키를 넣기 전, 화면을 고친 뒤 처음 연 날) 서비스 워커의 3초 제한이
// 걸리지 않는다. 신호가 약한 매장에서 첫 화면이 이 파일을 기다리며 비지 않게 따로 자른다.
// 서비스 워커의 3초보다 길게 잡아, 저장본이 있으면 그것을 받는다. 늦게 온 답은 lateEmart로 그때 다시 그린다.
const EMART_WAIT_MS = 4000;
function fetchEmart() {
  const file = fetchJson("data/emart.json");
  const timeout = new Promise((resolve) => setTimeout(() => resolve(null), EMART_WAIT_MS));
  return Promise.race([file, timeout]).then((first) => {
    if (first === null) file.then((late) => late && lateEmart(late));
    return first;
  });
}
const fetchBoth = () => Promise.all([fetchJson("data/prices.json"), fetchEmart()]);

// 4초 넘게 늦게 온 이마트 파일. KAMIS 파일이 아직이면 받아 두었다가 처음 그릴 때 쓴다.
let pendingEmart = null;
function lateEmart(emart) {
  if (!state.data) {
    pendingEmart = emart;
    return;
  }
  if (emart.generated_at === state.emart?.generated_at) return;
  setData(state.data, emart);
  refresh();
}

// 이마트 상품은 id를 붙여 KAMIS 품종과 같은 지도에 넣는다(즐겨찾기와 상세 주소가 같은 길을 쓴다).
function setData(data, emart) {
  state.data = data;
  state.emart = emart;
  const groups = emart?.groups ?? [];
  state.emartItems = (emart?.items ?? []).map((x) => ({ ...x, id: EMART_ID + x.name, emart: true }))
    .sort((a, b) => groups.indexOf(a.group) - groups.indexOf(b.group) || a.name.localeCompare(b.name, "ko"));
  state.byId = new Map([...data.items, ...state.emartItems].map((e) => [e.id, e]));
}

// 화면이 다시 보일 때 가격 파일을 새로 받는다. 홈 화면 앱은 며칠 뒤 다시 띄워도
// 처음부터 열리지 않아서, 이렇게 안 하면 옛 가격이 남는다.
// 두 파일 다 만든 시각이 같거나 못 받으면(오프라인) 지금 화면을 그대로 둔다.
async function reloadPrices() {
  if (document.visibilityState !== "visible") return;
  const [data, fetched] = await fetchBoth();
  if (!data) return;
  const emart = fetched ?? state.emart;
  if (data.generated_at === state.data?.generated_at && emart?.generated_at === state.emart?.generated_at) return;
  setData(data, emart);
  await refresh();
}

// 처음 열었을 때 한 번 홈 화면 추가를 안내한다. 닫으면 다시 나오지 않고, 이미 앱 모양이면 보이지 않는다.
function setupInstallHint() {
  const KEY = "mp.installHint.closed";
  const standalone = window.matchMedia("(display-mode: standalone)").matches || navigator.standalone === true;
  let closed = false;
  try {
    closed = localStorage.getItem(KEY) === "1";
  } catch {
    // 저장 공간을 못 쓰면 안내를 그대로 보인다.
  }
  const hint = $("banner-install");
  hint.hidden = standalone || closed;
  $("install-close").addEventListener("click", () => {
    hint.hidden = true;
    try {
      localStorage.setItem(KEY, "1");
    } catch {
      // 저장하지 못하면 다음에 다시 보인다.
    }
  });
}

// 자판이 가린 높이를 --kb에 넣는다. 아래 검색창, 가격표 받침, 띠가 그만큼 올라가 자판 바로 위에 붙는다.
// 아이폰은 자판이 올라와도 창 높이(innerHeight)가 그대로라, 지금 보이는 영역(visualViewport)과의 차이가 자판 높이다.
// 안드로이드는 viewport 메타의 interactive-widget=resizes-content로 창이 자판만큼 줄어 이 값이 0에 가깝다.
function setupKeyboardInset() {
  const vv = window.visualViewport;
  if (!vv) return;
  let queued = false;
  const update = () => {
    queued = false;
    const inset = Math.max(0, Math.round(window.innerHeight - vv.height - vv.offsetTop));
    document.documentElement.style.setProperty("--kb", `${inset}px`);
  };
  // 한 화면을 그릴 때 한 번만 잰다.
  const queue = () => {
    if (queued) return;
    queued = true;
    requestAnimationFrame(update);
  };
  vv.addEventListener("resize", queue);
  vv.addEventListener("scroll", queue);
  document.addEventListener("focusin", queue);
  document.addEventListener("focusout", queue);
}

async function init() {
  setupInstallHint();
  setupKeyboardInset();
  if ("serviceWorker" in navigator) {
    // 새 화면 파일을 다 받은 서비스 워커가 자리를 잡으면 한 번 다시 연다. 안 그러면 다음에 열 때까지 옛 화면이 남는다.
    // 처음 설치할 때(전에 맡은 서비스 워커가 없을 때)는 이미 새 화면이라 다시 열지 않는다.
    const hadWorker = Boolean(navigator.serviceWorker.controller);
    navigator.serviceWorker.addEventListener("controllerchange", () => {
      if (hadWorker) window.location.reload();
    });
    navigator.serviceWorker.register("sw.js").catch(() => {});
  }
  // 검색 결과나 첫 화면은 맨 위부터 보인다. 목록을 내린 채로 치면 결과 앞쪽이 위 막대 뒤에 가려지기 때문이다.
  $("search").addEventListener("input", (ev) => {
    state.query = ev.target.value.trim();
    render();
    window.scrollTo(0, 0);
  });
  $("search-form").addEventListener("submit", (ev) => {
    ev.preventDefault();
    $("search").blur();
  });
  // 지우기 단추(×)는 검색어를 지우고 첫 화면으로 돌아간다.
  $("search-clear").addEventListener("click", () => {
    state.query = "";
    $("search").value = "";
    $("search").blur();
    render();
    window.scrollTo(0, 0);
  });
  // 목록을 손가락으로 내리기 시작하면 자판을 닫아 화면을 넓힌다.
  window.addEventListener("touchmove", () => {
    if (document.activeElement === $("search")) $("search").blur();
  }, { passive: true });
  $("back").addEventListener("click", goBack);
  // 상세로 들어갈 때 보던 자리를 적어 두고, 돌아오면 그 자리로 내린다(다시 그리므로 브라우저에 맡기지 않는다).
  history.scrollRestoration = "manual";
  window.addEventListener("hashchange", (ev) => {
    const toDetail = location.hash.startsWith("#/item/");
    const fromDetail = new URL(ev.oldURL).hash.startsWith("#/item/");
    if (toDetail && !fromDetail) {
      state.homeScroll = window.scrollY;
      state.cameFromApp = true;
    }
    render();
    if (toDetail) {
      window.scrollTo(0, 0);
    } else if (fromDetail) {
      window.scrollTo(0, state.homeScroll);
      state.cameFromApp = false;
    }
  });
  // 인터넷이 다시 되면 띠를 지우고 가격 파일도 새로 받는다(오프라인으로 연 동안 바뀌었을 수 있다).
  window.addEventListener("online", () => {
    render();
    reloadPrices();
  });
  window.addEventListener("offline", render);
  document.addEventListener("visibilitychange", reloadPrices);

  const [data, emart] = await fetchBoth();
  if (!data) {
    $("view").replaceChildren(h("p", { class: "empty" },
      "가격 파일을 불러오지 못했어요. 인터넷에 연결한 뒤 다시 열어 주세요."));
    return;
  }
  setData(data, emart ?? pendingEmart);
  await refresh();
}

init();
