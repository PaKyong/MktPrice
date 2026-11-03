// 오프라인용 서비스 워커(브라우저가 파일을 폰에 저장해 두는 기능).
// 화면 파일은 저장해 둔 것을 먼저 쓰고, 가격 파일은 인터넷이 되면 새로 받는다.
// 화면 파일을 고치면 CACHE 숫자를 올린다. 안 올리면 폰에 옛 화면이 계속 남는다.

const CACHE = "mp-v9";
const PRICES = "data/prices.json";
// 신호가 약한 매장에서 가격 파일을 이만큼만 기다리고, 넘으면 저장본을 먼저 보여 준다.
const PRICES_WAIT_MS = 3000;
const SHELL = [
  "./",
  "index.html",
  "style.css",
  "app.js",
  "store.js",
  "manifest.webmanifest",
  "icons/icon-192.png",
  "icons/icon-512.png",
  "icons/apple-touch-icon.png",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    // cache: "reload"로 브라우저의 임시 저장본(HTTP 캐시)을 거치지 않고 새 파일을 받는다.
    caches.open(CACHE)
      .then((cache) => cache.addAll([...SHELL, PRICES].map((url) => new Request(url, { cache: "reload" }))))
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
async function pricesFirstFromNetwork(event) {
  const network = fetch(event.request).then(async (response) => {
    if (response.ok) {
      const cache = await caches.open(CACHE);
      await cache.put(PRICES, response.clone());
    }
    return response;
  });
  event.waitUntil(network.catch(() => {}));
  const cached = await caches.match(PRICES);
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
  if (url.pathname.endsWith(`/${PRICES}`)) {
    event.respondWith(pricesFirstFromNetwork(event));
    return;
  }
  event.respondWith(
    caches.match(request, { ignoreSearch: true }).then((hit) => hit || fetch(request)),
  );
});
