// A basic service worker to make the app installable.
// This file can be expanded later with caching strategies.

self.addEventListener('install', (event) => {
  console.log('Service Worker: Installing...');
  // Skip waiting to activate the new service worker immediately.
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  console.log('Service Worker: Activating...');
  // Take control of all clients (open tabs) immediately.
  event.waitUntil(clients.claim());
});

self.addEventListener('fetch', (event) => {
  // For now, just pass through all network requests.
  // This is where you would add caching logic.
  event.respondWith(fetch(event.request));
});
