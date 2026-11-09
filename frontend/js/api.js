// Import config before this in app, or set window.SCRAPEOPS_API
const API = (typeof window !== "undefined" && window.SCRAPEOPS_API) || "/api";

function tokens() {
  return {
    access: localStorage.getItem("access"),
    refresh: localStorage.getItem("refresh"),
  };
}

export function setTokens(access, refresh) {
  localStorage.setItem("access", access);
  if (refresh) localStorage.setItem("refresh", refresh);
}

export function clearTokens() {
  localStorage.removeItem("access");
  localStorage.removeItem("refresh");
  localStorage.removeItem("user");
}

export function getUser() {
  try { return JSON.parse(localStorage.getItem("user") || "null"); } catch { return null; }
}

export function setUser(u) {
  localStorage.setItem("user", JSON.stringify(u));
}

async function refreshAccess() {
  const { refresh } = tokens();
  if (!refresh) throw new Error("No refresh token");
  const r = await fetch(`${API}/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh }),
  });
  if (!r.ok) throw new Error("Refresh failed");
  const data = await r.json();
  setTokens(data.access, data.refresh || refresh);
  return data.access;
}

export async function api(path, opts = {}) {
  const headers = { "Content-Type": "application/json", ...(opts.headers || {}) };
  let { access } = tokens();
  if (access) headers.Authorization = `Bearer ${access}`;
  let res = await fetch(`${API}${path}`, { ...opts, headers });
  if (res.status === 401 && tokens().refresh) {
    try {
      access = await refreshAccess();
      headers.Authorization = `Bearer ${access}`;
      res = await fetch(`${API}${path}`, { ...opts, headers });
    } catch {
      clearTokens();
      location.hash = "#/login";
      throw new Error("Session expired");
    }
  }
  const text = await res.text();
  let data = null;
  try { data = text ? JSON.parse(text) : null; } catch { data = text; }
  if (!res.ok) {
    const msg = (data && (data.detail || data.mongo_uri || JSON.stringify(data))) || res.statusText;
    throw new Error(typeof msg === "string" ? msg : JSON.stringify(msg));
  }
  return data;
}

export const get = (p) => api(p);
export const post = (p, body) => api(p, { method: "POST", body: JSON.stringify(body) });
export const patch = (p, body) => api(p, { method: "PATCH", body: JSON.stringify(body) });
export const del = (p) => api(p, { method: "DELETE" });
