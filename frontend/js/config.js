// Local (no Docker): frontend :8080 → Django :8000
// Docker/nginx: same origin, use "/api"
window.SCRAPEOPS_API = window.SCRAPEOPS_API || "http://127.0.0.1:8000/api";
