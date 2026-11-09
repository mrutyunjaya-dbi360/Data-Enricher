import { get, post } from "../api.js";
import { toast } from "../router.js";

export async function renderUsers(root) {
  root.innerHTML = `<h2>Users</h2><p class="skeleton"></p>`;
  let users = [];
  try { users = await get("/metrics/users"); } catch (e) {
    root.innerHTML = `<p class="empty">${e.message}</p>`; return;
  }
  const rows = users.map(u => `
    <tr data-id="${u.user_id}">
      <td>${u.email}</td><td>${u.role}</td><td>${u.status}</td>
      <td>${u.datasources_count}</td><td>${u.docs_processed}</td>
      <td>$${(u.cost_usd||0).toFixed(4)}</td>
    </tr>`).join("");
  root.innerHTML = `
    <h2>Users <button id="btn-create" class="outline" style="float:right">Create user</button></h2>
    <table>
      <thead><tr><th>Email</th><th>Role</th><th>Status</th><th>DS</th><th>Docs</th><th>Cost</th></tr></thead>
      <tbody>${rows||"<tr><td colspan=6 class=empty>No users</td></tr>"}</tbody>
    </table>
    <dialog id="create-dlg">
      <article>
        <header>Create user</header>
        <form id="create-form">
          <label>Email <input name="email" type="email" required /></label>
          <label>Full name <input name="full_name" /></label>
          <label>Role <select name="role"><option value="member">member</option><option value="admin">admin</option></select></label>
          <button type="submit">Create</button>
        </form>
        <p id="gen-pw" hidden></p>
      </article>
    </dialog>`;
  document.getElementById("btn-create").onclick = () => document.getElementById("create-dlg").showModal();
  document.getElementById("create-form").onsubmit = async (e) => {
    e.preventDefault();
    const fd = new FormData(e.target);
    try {
      const u = await post("/admin/users", {
        email: fd.get("email"), full_name: fd.get("full_name"), role: fd.get("role"),
      });
      document.getElementById("gen-pw").hidden = false;
      document.getElementById("gen-pw").textContent = `Password (copy once): ${u.generated_password}`;
      toast("User created");
    } catch (err) { toast(err.message); }
  };
}
