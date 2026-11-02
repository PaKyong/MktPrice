// 오프라인용 서비스 워커(브라우저가 파일을 폰에 저장해 두는 기능).
// 화면 파일은 저장해 둔 것을 먼저 쓰고, 가격 파일은 인터넷이 되면 새로 받는다.
// 화면 파일을 고치면 CACHE 숫자를 올린다. 안 올리면 폰에 옛 화면이 계속 남는다.

const CACHE = "mp-v1";
const PRICES = "data/prices.json";
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
    caches.open(CACHE)
      .then((cache) => cache.addAll([...SHELL, PRICES]))
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

// 가격 파일: 네트워크 먼저, 받으면 저장본을 바꾸고, 못 받으면 저장본.
async function pricesFirstFromNetwork(request) {
  try {
    const response = await fetch(request);
    if (response.ok) {
      const cache = await caches.open(CACHE);
      await cache.put(PRICES, response.clone());
    }
    return response;
  } catch {
    const cached = await caches.match(PRICES);
    if (cached) return cached;
    throw new Error("가격 파일을 받을 수 없고 저장본도 없음");
  }
}

self.addEventListener("fetch", (event) => {
  const { request } = event;
  if (request.method !== "GET") return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;
  if (url.pathname.endsWith(`/${PRICES}`)) {
    event.respondWith(pricesFirstFromNetwork(request));
    return;
  }
  event.respondWith(
    caches.match(request, { ignoreSearch: true }).then((hit) => hit || fetch(request)),
  );
});
