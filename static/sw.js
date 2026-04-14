// sw.js - Service Worker Básico
const CACHE_NAME = 'agenda-dental-v1';

self.addEventListener('install', (event) => {
    self.skipWaiting();
});

self.addEventListener('activate', (event) => {
    event.waitUntil(clients.claim());
});

self.addEventListener('fetch', (event) => {
    // Para el panel en tiempo real, siempre buscamos la versión más nueva en internet
    event.respondWith(fetch(event.request).catch(() => caches.match(event.request)));
});