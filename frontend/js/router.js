const routes = {};

export function route(path, handler) {
  routes[path] = handler;
}

export function start(root) {
  const go = async () => {
    const hash = location.hash || "#/report";
    const path = hash.replace(/^#/, "").split("?")[0] || "/report";
    const user = JSON.parse(localStorage.getItem("user") || "null");
    if (path !== "/login" && !user) {
      location.hash = "#/login";
      return;
    }
    if (path === "/users" && user && user.role !== "admin") {
      location.hash = "#/report";
      toast("Admins only");
      return;
    }
    const fn = routes[path] || routes["/report"];
    root.innerHTML = "";
    await fn(root);
  };
  window.addEventListener("hashchange", go);
  go();
}

export function toast(msg) {
  const el = document.getElementById("toast");
  if (!el) return;
  el.textContent = msg;
  el.hidden = false;
  setTimeout(() => { el.hidden = true; }, 3000);
}
