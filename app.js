// 장보기 가격 화면: 첫 화면(즐겨찾기, 전체 품목), 검색, 상세.
// 가격 계산은 수집 스크립트가 끝내 두었고, 여기서는 보여 주기만 한다.

import { getFavorites } from "./store.js";

// chip: 전체 품목에서 마지막으로 누른 부류 칸(다시 그려도 칠한 채로 둔다).
const state = { data: null, byId: new Map(), favorites: [], query: "", chip: null };
const $ = (id) => document.getElementById(id);

// ---- 글자 만들기 ----

const won = (n) => `${n.toLocaleString("ko-KR")}원`;
const md = (iso) => {
  const [, m, d] = iso.split("-");
  return `${Number(m)}월 ${Number(d)}일`;
};
const signedPct = (x) => `${x > 0 ? "+" : x < 0 ? "-" : ""}${Math.abs(Math.round(x))}%`;
// 품종 이름에 품목 이름이 들어 있으면 품종 이름만 쓴다("양파 · 양파" → "양파", "파 · 대파" → "대파").
const displayName = (e) => (e.kind.includes(e.item) ? e.kind : `${e.item} ${e.kind}`);
const perUnit = (e) => (e.measure === "weight" ? "100g당" : `1${e.unit_label}당`);
const signalClass = { "비싼 편": "sig--high", "보통": "sig--mid", "싼 편": "sig--low" };

// 평년 대비 같은 %: 내리면 빨강 ▼, 오르면 파랑 ▲. 반올림해 0이면 흐린 0%, 값이 없으면 흐린 -.
function pctText(x) {
  if (x === null || x === undefined) return { text: "-", cls: "muted" };
  const r = Math.round(x);
  if (r === 0) return { text: "0%", cls: "muted" };
  return r < 0 ? { text: `▼${-r}%`, cls: "down" } : { text: `▲${r}%`, cls: "up" };
}

function normalText(pct) {
  const r = Math.round(pct);
  if (r === 0) return "평년과 비슷";
  return r > 0 ? `평년보다 ${r}% 비쌈` : `평년보다 ${-r}% 쌈`;
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

function svgEl(tag, attrs, text) {
  const el = document.createElementNS("http://www.w3.org/2000/svg", tag);
  for (const [k, v] of Object.entries(attrs)) el.setAttribute(k, v);
  if (text) el.textContent = text;
  return el;
}

// ---- 기준일 줄 ----

function renderTop() {
  const { data } = state;
  $("asof").textContent = `${data.as_of.replaceAll("-", ".")} 기준 · 출처 ${data.source}`;
  $("print-sample").hidden = data.source !== "샘플";
  const offline = $("print-offline");
  offline.hidden = navigator.onLine;
  offline.textContent = `인터넷 연결 없음 · ${md(data.as_of)} 값`;
}

// ---- 한 줄 ----

// 줄 가운데의 30일 작은 그래프. 색은 오른쪽 % 하나에만 쓰므로 회색 선 하나. 값이 둘보다 적으면 그리지 않는다.
function sparkline(trend) {
  if (trend.length < 2) return null;
  const values = trend.map(([, v]) => v);
  const min = Math.min(...values);
  const span = Math.max(...values) - min || 1;
  const points = values
    .map((v, i) => `${((i / (values.length - 1)) * 56).toFixed(1)},${(22 - ((v - min) / span) * 20).toFixed(1)}`)
    .join(" ");
  const svg = svgEl("svg", { viewBox: "0 0 56 24", class: "spark", "aria-hidden": "true" });
  svg.append(svgEl("polyline", { points }));
  return svg;
}

// 즐겨찾기·전체 품목·검색 결과의 한 줄: 왼쪽 이름과 단위, 가운데 30일 그래프, 오른쪽 단위 가격과 평년 대비 %.
function rowNode(e) {
  const pct = pctText(e.change.normal);
  const tag = e.signal === "싼 편" ? "down" : e.signal === "비싼 편" ? "up" : null;
  return h("li", {},
    h("a", { class: "row", href: `#/item/${e.id}` },
      h("span", { class: "row__name" }, displayName(e),
        h("span", { class: "row__sub" }, perUnit(e),
          tag ? [" · ", h("span", { class: tag }, e.signal)] : null,
          // 일부 품종만 받지 못한 날은 그 품종이 옛 값이다.
          e.as_of !== state.data.as_of ? ` · ${md(e.as_of)} 값` : null)),
      sparkline(e.trend) || h("span", {}),
      h("span", { class: "row__price" }, won(e.unit_price),
        h("span", { class: `row__pct ${pct.cls}` }, pct.text))));
}

// 즐겨찾기에 있지만 철이 지나 가격 파일에서 빠진 품종.
function missingRowNode(fav) {
  return h("li", {},
    h("a", { class: "row", href: `#/item/${fav.id}` },
      h("span", { class: "row__name" }, fav.name || fav.id, h("span", { class: "row__sub" }, "지금 값 없음"))));
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
  // 다시 그려도 옆으로 밀어 둔 부류 칸 줄 위치를 그대로 둔다(지우기 전에 읽는다).
  const chipsLeft = view.querySelector(".chips")?.scrollLeft ?? 0;
  view.replaceChildren();
  const favRows = state.favorites.map((f) =>
    (state.byId.has(f.id) ? rowNode(state.byId.get(f.id)) : missingRowNode(f)));
  view.append(h("section", { class: "section" },
    h("h2", { class: "sec" }, "즐겨찾기"),
    favRows.length
      ? h("ul", { class: "rows" }, favRows)
      : h("p", { class: "empty" }, "상세 화면에서 ☆를 누르면 여기 모여요")));

  const byCategory = new Map();
  for (const e of browseOrder()) {
    if (!byCategory.has(e.category)) byCategory.set(e.category, []);
    byCategory.get(e.category).push(e);
  }
  view.append(h("section", { class: "section" },
    h("h2", { class: "sec" }, "전체 품목"),
    h("nav", { class: "chips", "aria-label": "부류" }, [...byCategory].map(([c, list]) =>
      h("button", { type: "button", class: c === state.chip ? "chip chip--on" : "chip", "data-category": c,
                    onclick: () => jumpTo(c) }, `${c} ${list.length}`))),
    [...byCategory].map(([c, list]) => h("section", { class: "cat-block", id: `cat-${c}` },
      h("h3", { class: "cat" }, c), h("ul", { class: "rows" }, list.map(rowNode))))));
  view.querySelector(".chips").scrollLeft = chipsLeft;
}

// 부류 칸을 누르면 그 부류로 건너뛰고 칸을 칠한다. 위에 붙은 막대와 칸 줄에 가리지 않게 그만큼 덜 내린다.
function jumpTo(category) {
  state.chip = category;
  $("search").blur();
  for (const chip of document.querySelectorAll(".chip")) {
    chip.classList.toggle("chip--on", chip.dataset.category === category);
    if (chip.dataset.category === category) chip.scrollIntoView({ block: "nearest", inline: "nearest" });
  }
  const section = document.getElementById(`cat-${category}`);
  const covered = $("bar-home").offsetHeight + document.querySelector(".chips").offsetHeight;
  window.scrollTo(0, section.getBoundingClientRect().top + window.scrollY - covered);
}

// ---- 검색 ----

function renderSearch() {
  const view = $("view");
  view.replaceChildren();
  const q = state.query;
  const found = browseOrder().filter((e) => e.item.includes(q) || e.kind.includes(q));
  if (!found.length) {
    view.append(h("p", { class: "found" }, `"${q}"에 맞는 품목이 없어요. 다른 이름으로 찾아 보세요.`));
    return;
  }
  view.append(h("p", { class: "found" }, `"${q}" 찾은 품종 ${found.length}개`),
    h("ul", { class: "rows" }, found.map(rowNode)));
}

// ---- 상세 ----

function trendChart(trend) {
  const values = trend.map(([, v]) => v);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const w = 320;
  const top = 14;
  const bottom = 70;
  const x = (i) => (trend.length === 1 ? w : (i / (trend.length - 1)) * w);
  const y = (v) => bottom - ((v - min) / span) * (bottom - top);
  const points = values.map((v, i) => `${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(" ");
  const svg = svgEl("svg", { viewBox: `0 0 ${w} 84`, class: "chart", role: "img",
                             "aria-label": `최근 30일 평균: 최저 ${won(min)}, 최고 ${won(max)}` });
  svg.append(
    svgEl("line", { x1: 0, y1: bottom, x2: w, y2: bottom, class: "chart__base" }),
    svgEl("polyline", { points, class: "chart__line" }),
    svgEl("circle", { cx: x(values.length - 1), cy: y(values.at(-1)), r: 3.5, class: "chart__dot" }),
    svgEl("text", { x: 0, y: 10, class: "chart__label" }, `최고 ${max.toLocaleString("ko-KR")}`),
    svgEl("text", { x: 0, y: 82, class: "chart__label" }, `최저 ${min.toLocaleString("ko-KR")}`));
  return svg;
}

// 왼쪽 글자와 오른쪽 값을 한 줄에 놓는다.
const pair = (cls, left, right) => h("p", { class: cls }, h("span", {}, left), right);

function renderDetail(id) {
  const view = $("view");
  view.replaceChildren();
  const e = state.byId.get(id);
  const fav = state.favorites.find((x) => x.id === id);
  if (!e) {
    view.append(h("section", { class: "detail" },
      h("h2", { class: "detail__name" }, fav?.name || id),
      h("p", { class: "empty" }, "지금 값 없음. 철이 지나 KAMIS 조사 값이 없는 품목이에요.")));
    return;
  }
  const basis = state.data.basis.compare === "전국 대형유통 평균" ? "대형유통" : "조사처";
  const num = (n) => n.toLocaleString("ko-KR");
  const changes = [["1주 전보다", e.change.week], ["1개월 전보다", e.change.month], ["1년 전보다", e.change.year]]
    .filter(([, v]) => v !== null);
  const pctClass = (v) => (v > 0 ? "sig--high" : v < 0 ? "sig--low" : "");
  view.append(h("section", { class: "detail" },
    h("div", { class: "detail__head" },
      h("h2", { class: "detail__name" }, displayName(e)), h("span", { class: "muted" }, e.category)),
    h("p", { class: "detail__meta" }, `${e.as_of.replaceAll("-", ".")} · ${basis} ${e.stores}곳 평균`),
    h("div", { class: "dl" }),
    h("p", { class: "detail__price" }, h("span", {}, perUnit(e)), h("strong", {}, won(e.unit_price))),
    pair("detail__row muted", e.unit, h("span", {}, won(e.price))),
    pair("detail__row muted", "가게마다(가운데 절반)",
      h("span", {}, `${num(e.unit_range[0])}~${num(e.unit_range[1])}/${e.unit_label}`)),
    h("div", { class: "dl" }),
    pair("detail__row", "30일 추이", h("span", { class: "muted" }, `${e.unit} 기준`)),
    e.trend.length ? trendChart(e.trend) : h("p", { class: "muted" }, "추이 값이 없어요"),
    h("div", { class: "dl" }),
    e.change.normal !== null
      ? h("p", { class: "stamp-wrap" },
          h("span", { class: `stamp ${signalClass[e.signal] || "sig--mid"}` }, normalText(e.change.normal)))
      : h("p", { class: "muted" }, "평년 값이 없어요"),
    changes.map(([label, v]) => pair("detail__row", label, h("span", { class: pctClass(v) }, signedPct(v)))),
    h("p", { class: "detail__foot" }, "* 요즘 시기는 KAMIS 전체 평균 기준")));
}

// ---- 화면 고르기 ----

function render() {
  if (!state.data) return;
  renderTop();
  const match = location.hash.match(/^#\/item\/(.+)$/);
  $("home-head").hidden = Boolean(match);
  $("search-clear").hidden = !state.query;
  if (match) renderDetail(decodeURIComponent(match[1]));
  else if (state.query) renderSearch();
  else renderHome();
}

async function refresh() {
  state.favorites = await getFavorites();
  render();
}

// 가격 파일을 받는다. 못 받으면 null.
async function fetchPrices() {
  try {
    const res = await fetch("data/prices.json", { cache: "no-cache" });
    return res.ok ? await res.json() : null;
  } catch {
    return null;
  }
}

function setData(data) {
  state.data = data;
  state.byId = new Map(data.items.map((e) => [e.id, e]));
}

// 화면이 다시 보일 때 가격 파일을 새로 받는다. 홈 화면 앱은 며칠 뒤 다시 띄워도
// 처음부터 열리지 않아서, 이렇게 안 하면 옛 가격이 남는다.
// 파일을 만든 시각이 같거나 못 받으면(오프라인) 지금 화면을 그대로 둔다.
async function reloadPrices() {
  if (document.visibilityState !== "visible") return;
  const data = await fetchPrices();
  if (!data || data.generated_at === state.data?.generated_at) return;
  setData(data);
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

async function init() {
  setupInstallHint();
  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("sw.js").catch(() => {});
  }
  $("search").addEventListener("input", (ev) => {
    state.query = ev.target.value.trim();
    if (location.hash.startsWith("#/item/")) location.hash = "#/";
    else render();
  });
  $("search-form").addEventListener("submit", (ev) => {
    ev.preventDefault();
    $("search").blur();
  });
  // ✕는 검색어를 지우고 첫 화면으로 돌아간다.
  $("search-clear").addEventListener("click", () => {
    state.query = "";
    $("search").value = "";
    $("search").blur();
    render();
  });
  // 목록을 손가락으로 내리기 시작하면 자판을 닫아 화면을 넓힌다.
  window.addEventListener("touchmove", () => {
    if (document.activeElement === $("search")) $("search").blur();
  }, { passive: true });
  window.addEventListener("hashchange", () => {
    render();
    window.scrollTo(0, 0);
  });
  window.addEventListener("online", render);
  window.addEventListener("offline", render);
  document.addEventListener("visibilitychange", reloadPrices);

  const data = await fetchPrices();
  if (!data) {
    $("view").replaceChildren(h("p", { class: "empty" },
      "가격 파일을 불러오지 못했어요. 인터넷에 연결한 뒤 다시 열어 주세요."));
    return;
  }
  setData(data);
  await refresh();
}

init();
