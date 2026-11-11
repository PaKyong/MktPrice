// 오프라인용 서비스 워커(브라우저가 파일을 폰에 저장해 두는 기능).
// 화면 파일은 저장해 둔 것을 먼저 쓰고, 가격 파일(KAMIS, 이마트)은 인터넷이 되면 새로 받는다.
// 화면 파일을 고치면 CACHE 숫자를 올린다. 안 올리면 폰에 옛 화면이 계속 남는다.

const CACHE = "mp-v30";
const PRICES = "data/prices.json";
// 이마트 파일은 키를 넣기 전에는 없어서 설치 목록에 넣지 않는다(하나라도 없으면 설치가 통째로 실패한다).
// 대신 설치할 때 따로 "있으면" 넣는다(keepEmart). 처음 받는 데 성공했을 때도 저장된다.
const EMART = "data/emart.json";
const LIVE = [PRICES, EMART];
// 신호가 약한 매장에서 가격 파일을 이만큼만 기다리고, 넘으면 저장본을 먼저 보여 준다.
const PRICES_WAIT_MS = 3000;
const SHELL = [
  "./",
  "index.html",
  "style.css",
  "app.js",
  "store.js",
  "manifest.webmanifest",
  "fonts/mkt-sans.woff2",
  "icons/icon-192.png",
  "icons/icon-512.png",
  "icons/apple-touch-icon.png",
];

// 새 묶음에 이마트 파일을 넣는다. 활성화 때 옛 묶음을 지우므로, 안 넣으면 화면을 고칠 때마다
// 폰의 이마트 저장본이 사라져 마트에서 인터넷 없이 열면 이마트 칸이 없다.
// 받으면(파일이 없으면 404라 실패) 그것을, 못 받으면 옛 묶음의 저장본을 옮겨 온다. 둘 다 없으면 그냥 둔다.
async function keepEmart(cache) {
  try {
    await cache.add(new Request(EMART, { cache: "reload" }));
  } catch {
    const old = await caches.match(EMART);
    if (old) await cache.put(EMART, old);
  }
}

self.addEventListener("install", (event) => {
  event.waitUntil(
    // cache: "reload"로 브라우저의 임시 저장본(HTTP 캐시)을 거치지 않고 새 파일을 받는다.
    caches.open(CACHE)
      .then((cache) => cache.addAll([...SHELL, PRICES].map((url) => new Request(url, { cache: "reload" })))
        .then(() => keepEmart(cache)))
      .then(() => self.skipWaiting()),
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((key) => key !== CACHE).map((key) => caches.delete(key))))
      .then(() => self.clients.claim()),
  );
});

// 가격 파일: 네트워크 먼저. 받으면 저장본을 바꾼다. 못 받거나(오류 응답 포함)
// PRICES_WAIT_MS 안에 오지 않으면 저장본을 보여 주고, 늦게 온 응답은 저장만 한다.
async function liveFirstFromNetwork(event, path) {
  const network = fetch(event.request).then(async (response) => {
    if (response.ok) {
      const cache = await caches.open(CACHE);
      await cache.put(path, response.clone());
    }
    return response;
  });
  event.waitUntil(network.catch(() => {}));
  const cached = await caches.match(path);
  if (!cached) return network;
  const timeout = new Promise((resolve) => setTimeout(() => resolve(null), PRICES_WAIT_MS));
  try {
    const response = await Promise.race([network, timeout]);
    return response && response.ok ? response : cached;
  } catch {
    return cached;
  }
}

self.addEventListener("fetch", (event) => {
  const { request } = event;
  if (request.method !== "GET") return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;
  const live = LIVE.find((path) => url.pathname.endsWith(`/${path}`));
  if (live) {
    event.respondWith(liveFirstFromNetwork(event, live));
    return;
  }
  event.respondWith(
    caches.match(request, { ignoreSearch: true }).then((hit) => hit || fetch(request)),
  );
});
