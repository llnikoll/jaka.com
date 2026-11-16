/**
 * Service Worker para Jaka Bicicletería - PWA Support
 * Cache primario: recursos principales, Cache red: solo datos
 */

const CACHE_PRINCIPAL = 'jaka-tienda-v1';
const CACHE_DATOS = 'jaka-datos-v1';

// Recursos a cachear en tiempo de instalación
const URLs_CACHE = [
  '/',
  '/tienda.html',
  '/index.html',
  '/assets/estilos.css',
  '/assets/config.js',
  '/assets/app.js',
  '/assets/jaka-icono.png',
  '/assets/favicon-32.png',
  '/assets/favicon-192.png',
  '/assets/apple-touch-icon.png',
  '/assets/jaka-og.png'
];

// Instalación - cachear recursos principales
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_PRINCIPAL)
      .then((cache) => cache.addAll(URLs_CACHE))
      .then(() => self.skipWaiting())
  );
});

// Activación - limpiar caches antiguos
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys.map((key) => {
          if (key !== CACHE_PRINCIPAL && key !== CACHE_DATOS) {
            return caches.delete(key);
          }
        })
      );
    }).then(() => self.clients.claim())
  );
});

// Fetch - Network First para HTML, Cache First para assets, Network Only para datos
self.addEventListener('fetch', (event) => {
  const url = event.request.url;
  const request = event.request;

  // Ignorar métodos no GET
  if (request.method !== 'GET') return;

  // Para peticiones de datos (JSON)
  if (url.includes('/data/') || url.includes('ciclovia.com.py') || url.includes('chacomer.com.py')) {
    event.respondWith(
      fetch(request)
        .then((response) => {
          // Cachear respuestas exitosas
          if (response && response.status === 200 && response.type === 'basic') {
            const responseClone = response.clone();
            caches.open(CACHE_DATOS).then((cache) => cache.put(request, responseClone));
          }
          return response;
        })
        .catch(() => {
          // Fallback al cache cuando no hay conexión
          return caches.match(request);
        })
    );
    return;
  }

  // Para HTML - Network First
  if (request.destination === 'document' || url.endsWith('.html') || url.endsWith('/')) {
    event.respondWith(
      fetch(request)
        .then((response) => {
          if (response && response.status === 200) {
            const responseClone = response.clone();
            caches.open(CACHE_PRINCIPAL).then((cache) => cache.put(request, responseClone));
          }
          return response;
        })
        .catch(() => caches.match(request))
    );
    return;
  }

  // Para otros assets - Cache First
  event.respondWith(
    caches.match(request)
      .then((response) => {
        if (response) return response;
        return fetch(request).then((networkResponse) => {
          if (networkResponse && networkResponse.status === 200) {
            const responseClone = networkResponse.clone();
            caches.open(CACHE_PRINCIPAL).then((cache) => cache.put(request, responseClone));
          }
          return networkResponse;
        });
      })
  );
});

// Mensaje para forzar actualización
self.addEventListener('message', (event) => {
  if (event.data && event.data.type === 'CACHE_UPDATE') {
    caches.open(CACHE_PRINCIPAL).then((cache) => cache.keys().then((keys) => {
      keys.forEach((key) => cache.delete(key));
    }));
  }
});