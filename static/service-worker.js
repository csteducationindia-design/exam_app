const CACHE_NAME = 'cst-exam-v4'; // Changed version to force update
const ASSETS_TO_CACHE = [
  '/',
  '/exam',
  '/manifest.json',
  '/static/css/tailwind.css',
  '/static/icon.png',
  '/static/seal.svg',
  '/static/student_exam_client.html',
  '/static/admin_teacher_portal.html'
];

// Install: Cache files immediately
self.addEventListener('install', (event) => {
  self.skipWaiting(); // Force new worker to active immediately
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(ASSETS_TO_CACHE);
    })
  );
});

// Activate: Clean up old caches
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames.map((cache) => {
          if (cache !== CACHE_NAME) {
            return caches.delete(cache);
          }
        })
      );
    })
  );
  self.clients.claim(); // Take control of page immediately
});

// Fetch: The Safe Logic
self.addEventListener('fetch', (event) => {
  // CRITICAL FIX: Ignore chrome-extensions and anything that isn't HTTP
  if (!event.request.url.startsWith('http')) {
    return;
  }

  event.respondWith(
    caches.match(event.request).then((cachedResponse) => {
      // 1. Return from cache if found
      if (cachedResponse) {
        return cachedResponse;
      }

      // 2. Fetch from network if not in cache
      return fetch(event.request).then((networkResponse) => {
        // Check if response is valid
        if (!networkResponse || networkResponse.status !== 200 || networkResponse.type !== 'basic') {
          return networkResponse;
        }

        // Cache the new file
        const responseToCache = networkResponse.clone();
        caches.open(CACHE_NAME).then((cache) => {
          cache.put(event.request, responseToCache);
        });

        return networkResponse;
      }).catch(() => {
         // 3. Fallback for offline errors (prevents "Promise rejected" crash)
         return new Response('Offline: Resource not found');
      });
    })
  );
});