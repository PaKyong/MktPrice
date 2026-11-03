// 장보기 가격 화면: 내 목록, 검색, 상세, 예상 총액.
// 가격 계산은 수집 스크립트가 끝내 두었고, 여기서는 보여 주기와 목록 합계만 한다.

import { addItem, getList, removeItem, setQty } from "./store.js";

const state = { data: null, byId: new Map(), list: [], query: "" };
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
// 영수증 줄의 단위 가격: "1,267/100g", "1,709/개"
const unitPriceText = (e) => `${e.unit_price.toLocaleString("ko-KR")}/${e.unit_label}`;
const signalClass = { "비싼 편": "sig--high", "보통": "sig--mid", "싼 편": "sig--low" };
const signalMark = { "비싼 편": "▲ ", "싼 편": "▼ ", "보통": "" };

// 품목 줄 둘째 줄의 신호: "▲ 비싼 편 +19%", "보통 +4%". 평년 값이 없으면 신호 말만.
function signalLine(e) {
  if (!e.signal) return null;
  const pct = e.change.normal !== null ? ` ${signedPct(e.change.normal)}` : "";
  return { text: `${signalMark[e.signal] ?? ""}${e.signal}${pct}`, cls: signalClass[e.signal] || "sig--mid" };
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

// ---- 영수증 머리 ----

function renderTop() {
  const { data } = state;
  $("asof").textContent = `${data.as_of.replaceAll("-", ".")} 기준 · 출처 ${data.source}`;
  $("print-sample").hidden = data.source !== "샘플";
  const offline = $("print-offline");
  offline.hidden = navigator.onLine;
  offline.textContent = `* 인터넷 연결 없음 · ${md(data.as_of)} 값 *`;
}

// ---- 내 목록 ----

function renderList() {
  const view = $("view");
  view.replaceChildren();
  if (!state.list.length) {
    view.append(h("p", { class: "empty" }, "아래 검색창에서 품목을 찾아 + 담기를 눌러 보세요"));
    return;
  }
  // 영수증 품목 줄: 첫 줄에 이름과 단위 가격, 들여 쓴 둘째 줄에 신호와 평년 대비 %.
  const rows = state.list.map((entry) => {
    const e = state.byId.get(entry.id);
    const qty = entry.qty >= 2 ? ` x${entry.qty}` : "";
    const line = (name, price) => h("span", { class: "item__line" },
      h("span", { class: "item__name" }, name), h("span", { class: "item__price" }, price));
    if (!e) {
      return h("li", {},
        h("a", { class: "item", href: `#/item/${entry.id}` },
          line(`${entry.name || entry.id}${qty}`, "-"),
          h("span", { class: "item__sig" }, "지금 값 없음")));
    }
    const sig = signalLine(e);
    const stale = e.as_of !== state.data.as_of ? `${sig ? " · " : ""}${md(e.as_of)} 값` : "";
    return h("li", {},
      h("a", { class: "item", href: `#/item/${e.id}` },
        line(`${displayName(e)}${qty}`, unitPriceText(e)),
        sig || stale
          ? h("span", { class: "item__sig" },
              sig ? h("span", { class: sig.cls }, sig.text) : null,
              stale ? h("span", { class: "muted" }, stale) : null)
          : null));
  });
  view.append(h("ul", { class: "items" }, rows));
}

// 합계는 검색 중에도 보이고, 상세 화면에서는 숨긴다.
function renderTotal(detail) {
  const total = $("total");
  const priced = state.list.filter((x) => state.byId.has(x.id));
  const missing = state.list.length - priced.length;
  if (!state.list.length || detail) {
    total.hidden = true;
    return;
  }
  let low = 0;
  let high = 0;
  for (const x of priced) {
    const e = state.byId.get(x.id);
    low += e.range[0] * x.qty;
    high += e.range[1] * x.qty;
  }
  total.replaceChildren(...[
    h("span", { class: "total__label" }, "합계(예상)"),
    h("strong", { class: "total__value" }, priced.length ? `${low.toLocaleString("ko-KR")}~${won(high)}` : "—"),
    missing ? h("span", { class: "total__note" }, `값 없는 품목 ${missing}개 제외`) : null,
  ].filter(Boolean));
  total.hidden = false;
}

// ---- 검색 ----

function renderSearch() {
  const view = $("view");
  view.replaceChildren();
  const q = state.query;
  const qtyOf = new Map(state.list.map((x) => [x.id, x.qty]));
  const groups = new Map();
  for (const e of state.data.items) {
    if (!e.item.includes(q) && !e.kind.includes(q)) continue;
    if (!groups.has(e.item)) groups.set(e.item, []);
    groups.get(e.item).push(e);
  }
  if (!groups.size) {
    view.append(h("p", { class: "empty" }, `"${q}"에 맞는 품목이 없어요. 다른 이름으로 찾아 보세요.`));
    return;
  }
  view.append(h("p", { class: "found" }, `"${q}" 찾은 품목 ${groups.size}개`));
  [...groups].forEach(([item, entries], i) => {
    if (i) view.append(h("div", { class: "dl" }));
    view.append(h("h2", { class: "group" }, item,
      entries.length > 1 ? h("span", { class: "group__count" }, ` ${entries.length}`) : null));
    view.append(h("ul", { class: "items" }, entries.map((e) => {
      const qty = qtyOf.get(e.id);
      // 싼 편·비싼 편일 때만 짧게 붙인다("▼싼 편"). 보통은 비워 둔다.
      const short = e.signal === "비싼 편" || e.signal === "싼 편"
        ? h("span", { class: signalClass[e.signal] }, ` ${signalMark[e.signal].trim()}${e.signal}`) : null;
      return h("li", { class: "result" },
        h("a", { class: "item", href: `#/item/${e.id}` },
          h("span", { class: "result__name" }, e.kind, short),
          h("span", { class: "result__price" }, unitPriceText(e))),
        h("button", {
          type: "button", class: qty ? "add add--done" : "add", "aria-pressed": qty ? "true" : "false",
          onclick: async () => {
            if (!qty) {
              await addItem(e.id, displayName(e));
              await refresh();
            }
          },
        }, qty ? `담음 x${qty}` : "+ 담기"));
    })));
  });
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
  const svgEl = (tag, attrs, text) => {
    const el = document.createElementNS("http://www.w3.org/2000/svg", tag);
    for (const [k, v] of Object.entries(attrs)) el.setAttribute(k, v);
    if (text) el.textContent = text;
    return el;
  };
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

// 왼쪽 글자와 오른쪽 값을 한 줄에 놓는다(영수증 줄).
const pair = (cls, left, right) => h("p", { class: cls }, h("span", {}, left), right);

function renderDetail(id) {
  const view = $("view");
  view.replaceChildren();
  const e = state.byId.get(id);
  const entry = state.list.find((x) => x.id === id);
  if (!e) {
    view.append(h("section", { class: "detail" },
      h("h2", { class: "detail__name" }, entry?.name || id),
      h("p", { class: "empty" }, "지금 값 없음. 철이 지나 KAMIS 조사 값이 없는 품목이에요.")));
    renderDetailDock(id, entry);
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
  renderDetailDock(id, entry, e);
}

function renderDetailDock(id, entry, e) {
  const dock = $("dock-detail");
  const back = h("button", { type: "button", class: "btn btn--primary", onclick: goList }, "목록으로");
  if (entry) {
    dock.replaceChildren(
      h("div", { class: "dock__row" },
        h("div", { class: "stepper", role: "group", "aria-label": "개수" },
          h("button", { type: "button", "aria-label": "하나 빼기", disabled: entry.qty <= 1,
                        onclick: async () => { await setQty(id, entry.qty - 1); await refresh(); } }, "−"),
          h("output", { "aria-live": "polite" }, String(entry.qty)),
          h("button", { type: "button", "aria-label": "하나 더",
                        onclick: async () => { await setQty(id, entry.qty + 1); await refresh(); } }, "+")),
        back),
      h("button", { type: "button", class: "btn btn--text",
                    onclick: async () => { await removeItem(id); state.list = await getList(); goList(); } },
        "목록에서 빼기"));
  } else {
    dock.replaceChildren(h("div", { class: "dock__row" },
      h("button", { type: "button", class: "btn",
                    onclick: async () => { await addItem(id, e ? displayName(e) : id); await refresh(); } }, "+ 담기"),
      back));
  }
}

// ---- 화면 고르기 ----

function goList() {
  state.query = "";
  $("search").value = "";
  if (location.hash === "#/" || location.hash === "") render();
  else location.hash = "#/";
}

function render() {
  if (!state.data) return;
  renderTop();
  const match = location.hash.match(/^#\/item\/(.+)$/);
  const detail = Boolean(match);
  $("dock-list").hidden = detail;
  $("dock-detail").hidden = !detail;
  $("search-clear").hidden = !state.query;
  if (detail) renderDetail(decodeURIComponent(match[1]));
  else if (state.query) renderSearch();
  else renderList();
  renderTotal(detail);
}

async function refresh() {
  state.list = await getList();
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
  $("search-clear").addEventListener("click", () => {
    goList();
    $("search").focus();
  });
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
