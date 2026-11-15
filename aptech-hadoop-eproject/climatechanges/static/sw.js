/* Global Warming Explorer — service worker
   Makes the site installable and usable offline on PC and mobile.
   Strategy:
     - App shell (HTML/CSS/JS/icons) -> cached, "stale while revalidate"
       so visits are instant but still pick up the newest build in the
       background.
     - Anything cross-origin (Open-Meteo weather, global-warming.org CO2 /
       temperature data, Google Fonts, Chart.js CDN) -> network only,
       NEVER cached, so "live" sections stay genuinely live and never show
       stale numbers. If the network is down, those widgets show their own
       "couldn't load" state instead of old data.
     - Unknown navigations while offline -> offline.html fallback.

   Bump CACHE_VERSION whenever site content changes so returning visitors
   get the update instead of a stale cached copy. */
"use strict";

const CACHE_VERSION = "gw-explorer-d0b995ba";
const APP_SHELL = [
  "./",
  "index.html",
  "about.html",
  "action-hub.html",
  "carbon-footprint.html",
  "causes.html",
  "certificate.html",
  "checkin.html",
  "class-dashboard.html",
  "clean-energy.html",
  "course.html",
  "data-explorer.html",
  "effects.html",
  "for-teachers.html",
  "glossary.html",
  "lesson-1.html",
  "lesson-2.html",
  "lesson-3.html",
  "lesson-4.html",
  "lesson-5.html",
  "lesson-6.html",
  "lesson-7.html",
  "lesson-8.html",
  "quiz.html",
  "recycle.html",
  "simulator.html",
  "what-is-global-warming.html",
  "why-care.html",
  "offline.html",
  "css/styles.css",
  "css/brand.css",
  "js/main.js",
  "js/premium.js",
  "js/calculator.js",
  "js/certificate.js",
  "js/charts.js",
  "js/checkin.js",
  "js/checklist.js",
  "js/dashboard.js",
  "js/live-data.js",
  "js/progress.js",
  "js/quiz.js",
  "js/simulator.js",
  "js/weather.js",
  "manifest.json",
  "favicon.svg",
  "images/icons/icon-192.png",
  "images/icons/icon-512.png",
  "images/icons/icon-maskable-512.png",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(CACHE_VERSION)
      .then((cache) =>
        Promise.all(
          APP_SHELL.map((url) =>
            cache.add(url).catch(() => {
              /* a single missing/renamed file shouldn't fail the whole install */
            })
          )
        )
      )
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((names) =>
        Promise.all(
          names
            .filter((name) => name !== CACHE_VERSION)
            .map((name) => caches.delete(name))
        )
      )
      .then(() => self.clients.claim())
  );
});

function isSameOrigin(url) {
  return url.origin === self.location.origin;
}

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;

  const url = new URL(req.url);

  // Cross-origin requests (live weather, live CO2/temperature data, fonts,
  // Chart.js CDN, etc.) always go straight to the network. Never cached,
  // so these sections stay genuinely dynamic.
  if (!isSameOrigin(url)) return;

  // Same-origin navigations: try the network first (freshest content),
  // fall back to cache, fall back to the offline page.
  if (req.mode === "navigate") {
    event.respondWith(
      fetch(req)
        .then((res) => {
          const copy = res.clone();
          caches.open(CACHE_VERSION).then((cache) => cache.put(req, copy));
          return res;
        })
        .catch(() =>
          caches.match(req).then((cached) => cached || caches.match("offline.html"))
        )
    );
    return;
  }

  // Same-origin static assets: stale-while-revalidate.
  event.respondWith(
    caches.match(req).then((cached) => {
      const network = fetch(req)
        .then((res) => {
          const copy = res.clone();
          caches.open(CACHE_VERSION).then((cache) => cache.put(req, copy));
          return res;
        })
        .catch(() => cached);
      return cached || network;
    })
  );
});
