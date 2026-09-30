// Saturday in Austin, offline: the page and planner come from the network when there is one,
// Python (Pyodide) and photos come from the cache after the first visit, so the app opens fast
// and still plans a Saturday with no signal.
const CACHE = 'saturday-v1';
const SHELL = ['./', 'index.html', 'web/app.js', 'manifest.webmanifest', 'icons/icon-192.png', 'icons/icon-512.png'];

self.addEventListener('install', e => {
    e.waitUntil(caches.open(CACHE).then(c => c.addAll(SHELL)).then(() => self.skipWaiting()));
});
self.addEventListener('activate', e => {
    e.waitUntil(caches.keys()
        .then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k))))
        .then(() => self.clients.claim()));
});

const keep = (request, response) => {
    if (response && (response.ok || response.type === 'opaque')) {
        const copy = response.clone();
        caches.open(CACHE).then(c => c.put(request, copy));
    }
    return response;
};

self.addEventListener('fetch', e => {
    const { request } = e;
    if (request.method !== 'GET') return;
    const url = new URL(request.url);
    // Pyodide and photos never change at a given address: cache first
    if (url.hostname === 'cdn.jsdelivr.net' || url.hostname === 'images.unsplash.com' || url.hostname === 'fonts.gstatic.com') {
        e.respondWith(caches.match(request).then(hit => hit || fetch(request).then(r => keep(request, r))));
        return;
    }
    // this site, fonts CSS, anything else: the newest version when online, the saved one when not
    if (url.origin === location.origin || url.hostname === 'fonts.googleapis.com') {
        e.respondWith(fetch(request).then(r => keep(request, r))
            .catch(() => caches.match(request, { ignoreSearch: url.origin === location.origin })));
    }
});
