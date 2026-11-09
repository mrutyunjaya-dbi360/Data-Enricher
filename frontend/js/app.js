import { route, start, toast } from "./router.js";
import { getUser, clearTokens, setUser } from "./api.js";
import { renderLogin } from "./views/login.js";
import { renderReport } from "./views/report.js";
import { renderCost } from "./views/cost.js";
import { renderQuality } from "./views/quality.js";
import { renderUsers } from "./views/users.js";
import { renderDatasources } from "./views/datasources.js";

route("/login", renderLogin);
route("/report", renderReport);
route("/cost", renderCost);
route("/quality", renderQuality);
route("/users", renderUsers);
route("/datasources", renderDatasources);

function updateChrome() {
  const user = getUser();
  const top = document.getElementById("topbar");
  const badge = document.getElementById("user-badge");
  const navUsers = document.getElementById("nav-users");
  if (!user || location.hash === "#/login") {
    top.hidden = true;
    return;
  }
  top.hidden = false;
  badge.textContent = `${user.email} · ${user.role}`;
  badge.className = "badge" + (user.role === "admin" ? " admin" : "");
  navUsers.hidden = user.role !== "admin";
}

document.getElementById("logout-btn")?.addEventListener("click", (e) => {
  e.preventDefault();
  clearTokens();
  location.hash = "#/login";
});

window.addEventListener("hashchange", updateChrome);
start(document.getElementById("main"));
updateChrome();
export { toast };
