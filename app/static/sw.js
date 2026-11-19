
const CACHE_NAME = "home-finance-v3";

// Cache only public static resources.
// Never cache financial pages or private account information.
const STATIC_FILES = [
    "/static/style.css",
    "/static/home-finance-kd-icon-192.png",
    "/static/home-finance-kd-icon-512.png"
];

self.addEventListener("install", (event) => {
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then((cache) => cache.addAll(STATIC_FILES))
            .then(() => self.skipWaiting())
    );
});

self.addEventListener("activate", (event) => {
    event.waitUntil(
        caches.keys().then((cacheNames) => {
            return Promise.all(
                cacheNames
                    .filter((name) =>
                        name.startsWith("home-finance-") &&
                        name !== CACHE_NAME
                    )
                    .map((name) => caches.delete(name))
            );
        }).then(() => self.clients.claim())
    );
});

self.addEventListener("fetch", (event) => {
    const request = event.request;
    const url = new URL(request.url);

    if (
        request.method !== "GET" ||
        url.origin !== self.location.origin
    ) {
        return;
    }

    // Static resources can be loaded from cache.
    if (url.pathname.startsWith("/static/")) {
        event.respondWith(
            caches.match(request).then((cachedResponse) => {
                return cachedResponse || fetch(request);
            })
        );
        return;
    }

    // Never cache dashboard, login, or financial pages.
    // Show an offline message if a page cannot be reached.
    if (request.mode === "navigate") {
        event.respondWith(
            fetch(request).catch(() => {
                return new Response(
                    `<!doctype html>
                    <html lang="en">
                    <head>
                        <meta charset="utf-8">
                        <meta name="viewport" content="width=device-width, initial-scale=1">
                        <title>Home Finance - Offline</title>
                    </head>
                    <body style="font-family:Arial;text-align:center;padding:50px;background:#f5f7f5;color:#172554">
                        <h1>Home Finance</h1>
                        <h2>You are offline</h2>
                        <p>Please connect to the internet to access your financial information.</p>
                    </body>
                    </html>`,
                    {
                        headers: {
                            "Content-Type": "text/html; charset=utf-8"
                        }
                    }
                );
            })
        );
    }
});
