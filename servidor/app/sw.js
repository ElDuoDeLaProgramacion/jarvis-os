// Guarda la app para que abra al instante. Las respuestas de /api/* nunca se guardan.
const CACHE = 'jarvis-app-1'
const ARCHIVOS = ['./', 'manifest.json', 'icono.svg', 'icono-192.png']

self.addEventListener('install', (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(ARCHIVOS)).then(() => self.skipWaiting()))
})
self.addEventListener('activate', (e) => {
  e.waitUntil(caches.keys().then((ks) => Promise.all(ks.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
    .then(() => self.clients.claim()))
})
self.addEventListener('fetch', (e) => {
  const url = new URL(e.request.url)
  if (e.request.method !== 'GET' || !url.pathname.startsWith('/app/')) return
  // Primero la red (para ver siempre la última versión); sin red, lo guardado.
  e.respondWith(fetch(e.request).then((r) => {
    const copia = r.clone()
    caches.open(CACHE).then((c) => c.put(e.request, copia))
    return r
  }).catch(() => caches.match(e.request)))
})
