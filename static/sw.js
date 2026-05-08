// Service Worker — Mon Potager PWA
// Cache les assets statiques pour un chargement hors-ligne rapide.
const CACHE_NAME = 'potager-v1';
const STATIC_ASSETS = [
  '/',
  '/static/index.html',
  '/static/manifest.json',
  '/static/icon.png',
];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => cache.addAll(STATIC_ASSETS))
  );
  self.skipWaiting();
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);

  // Les requêtes API (/voice, /parse, /ask, etc.) passent toujours par le réseau
  if (url.pathname.startsWith('/voice') ||
      url.pathname.startsWith('/parse') ||
      url.pathname.startsWith('/ask')   ||
      url.pathname.startsWith('/stats') ||
      url.pathname.startsWith('/historique') ||
      url.pathname.startsWith('/health')) {
    return; // pas de cache pour l'API
  }

  // Assets statiques : cache-first
  if (event.request.method !== 'GET') return;
  event.respondWith(
    caches.match(event.request).then(cached => cached || fetch(event.request))
  );
});
