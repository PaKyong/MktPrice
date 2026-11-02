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
const signedPct = (x) => `${x > 0 ? "+" : x < 0 ? "−" : ""}${Math.abs(Math.round(x))}%`;
const nameOf = (e) => `${e.item} · ${e.kind}`;
const perUnit = (e) => (e.measure === "weight" ? "100g당" : `1${e.unit_label}당`);
const signalClass = { "비싼 편": "sig--high", "보통": "sig--mid", "싼 편": "sig--low" };

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

const signalChip = (e) => (e.signal ? h("span", { class: `sig ${signalClass[e.signal]}` }, e.signal) : null);

// ---- 맨 위 띠와 기준일 ----

function renderTop() {
  const { data } = state;
  $("asof").textContent = `${md(data.as_of)} 기준 · 출처 KAMIS`;
  $("banner-sample").hidden = data.source !== "샘플";
  const offline = $("banner-offline");
  offline.hidden = navigator.onLine;
  offline.textContent = `인터넷 연결 없음 · ${md(data.as_of)} 값`;
}

// ---- 내 목록 ----

function renderList() {
  const view = $("view");
  view.replaceChildren();
  if (!state.list.length) {
    view.append(h("p", { class: "empty" }, "아래 검색창에서 품목을 찾아 ＋ 담기를 눌러 보세요"));
    return;
  }
  const rows = state.list.map((entry) => {
    const e = state.byId.get(entry.id);
    const qty = entry.qty >= 2 ? h("span", { class: "row__qty" }, `×${entry.qty}`) : null;
    if (!e) {
      return h("li", {},
        h("a", { class: "row row--gone", href: `#/item/${entry.id}` },
          h("span", { class: "row__name" }, entry.name || entry.id, qty),
          h("span", { class: "row__price" }, "지금 값 없음")));
    }
    const stale = e.as_of !== state.data.as_of ? h("span", { class: "row__stale" }, `${md(e.as_of)} 값`) : null;
    return h("li", {},
      h("a", { class: "row", href: `#/item/${e.id}` },
        h("span", { class: "row__name" }, nameOf(e), qty, stale),
        h("span", { class: "row__price" },
          h("span", { class: "row__unit" }, perUnit(e)), " ", won(e.unit_price)),
        signalChip(e)));
  });
  view.append(h("ul", { class: "rows" }, rows));
}

function renderTotal() {
  const total = $("total");
  const priced = state.list.filter((x) => state.byId.has(x.id));
  const missing = state.list.length - priced.length;
  if (!state.list.length || state.query) {
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
    h("span", { class: "total__label" }, "예상 총액"),
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
  const inList = new Set(state.list.map((x) => x.id));
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
  for (const [item, entries] of groups) {
    view.append(h("h2", { class: "group" }, item, h("span", { class: "group__count" }, `품종 ${entries.length}개`)));
    view.append(h("ul", { class: "rows" }, entries.map((e) => {
      const added = inList.has(e.id);
      return h("li", { class: "result" },
        h("a", { class: "row", href: `#/item/${e.id}` },
          h("span", { class: "row__name" }, e.kind),
          h("span", { class: "row__price" }, h("span", { class: "row__unit" }, perUnit(e)), " ", won(e.unit_price)),
          signalChip(e)),
        h("button", {
          type: "button", class: added ? "add add--done" : "add", "aria-pressed": added ? "true" : "false",
          onclick: async () => {
            if (!added) {
              await addItem(e.id, nameOf(e));
              await refresh();
            }
          },
        }, added ? "✓ 담김" : "＋ 담기"));
    })));
  }
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
  const changes = [["1주 전", e.change.week], ["1개월 전", e.change.month], ["1년 전", e.change.year]]
    .filter(([, v]) => v !== null)
    .map(([label, v]) => `${label} ${signedPct(v)}`)
    .join(" · ");
  view.append(h("section", { class: "detail" },
    h("div", { class: "detail__head" },
      h("h2", { class: "detail__name" }, nameOf(e)), signalChip(e)),
    h("p", { class: "detail__meta" }, `${e.category} · ${md(e.as_of)} 기준`),
    h("div", { class: "tag" },
      h("span", { class: "tag__unit" }, perUnit(e)),
      h("strong", { class: "tag__price" }, won(e.unit_price))),
    h("p", { class: "detail__sub" }, `${e.unit} ${won(e.price)} · ${basis} ${e.stores}곳 평균`),
    h("h3", {}, "대형마트 범위"),
    h("p", { class: "detail__range" }, `${perUnit(e)} ${won(e.unit_range[0])}~${won(e.unit_range[1])}`),
    h("h3", {}, "30일 추이 ", h("small", {}, `(${basis} 평균, ${e.unit})`)),
    e.trend.length ? trendChart(e.trend) : h("p", { class: "muted" }, "추이 값이 없어요"),
    h("h3", {}, "요즘 시기 ", h("small", {}, "KAMIS 전체 평균 기준")),
    e.change.normal !== null
      ? h("p", { class: `detail__season ${signalClass[e.signal] || ""}` }, normalText(e.change.normal))
      : h("p", { class: "muted" }, "평년 값이 없어요"),
    changes ? h("p", { class: "muted" }, changes) : null));
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
                        onclick: async () => { await setQty(id, entry.qty + 1); await refresh(); } }, "＋")),
        back),
      h("button", { type: "button", class: "btn btn--text",
                    onclick: async () => { await removeItem(id); state.list = await getList(); goList(); } },
        "목록에서 빼기"));
  } else {
    dock.replaceChildren(h("div", { class: "dock__row" },
      h("button", { type: "button", class: "btn",
                    onclick: async () => { await addItem(id, e ? nameOf(e) : id); await refresh(); } }, "＋ 담기"),
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
  renderTotal();
}

async function refresh() {
  state.list = await getList();
  render();
}

async function init() {
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

  try {
    const res = await fetch("data/prices.json", { cache: "no-cache" });
    if (!res.ok) throw new Error(String(res.status));
    state.data = await res.json();
  } catch {
    $("view").replaceChildren(h("p", { class: "empty" },
      "가격 파일을 불러오지 못했어요. 인터넷에 연결한 뒤 다시 열어 주세요."));
    return;
  }
  state.byId = new Map(state.data.items.map((e) => [e.id, e]));
  await refresh();
}

init();
