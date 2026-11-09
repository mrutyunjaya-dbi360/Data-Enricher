import { get, post, del } from "../api.js";
import { toast } from "../router.js";

export async function renderDatasources(root) {
  root.innerHTML = `<h2>Datasources</h2><p class="skeleton"></p>`;
  let list = [];
  try { list = await get("/datasources"); } catch (e) {
    root.innerHTML = `<p class="empty">${e.message}</p>`; return;
  }
  const rows = list.map(d => `
    <tr>
      <td>${d.label}</td><td>${d.db_name}.${d.col_name}</td>
      <td><code>${d.uri_masked}</code></td><td>${d.status}</td>
      <td><button class="outline secondary btn-del" data-id="${d.id}">Delete</button></td>
    </tr>`).join("");
  root.innerHTML = `
    <h2>Datasources <button id="btn-add" class="outline" style="float:right">Add</button></h2>
    <table>
      <thead><tr><th>Label</th><th>DB.Col</th><th>URI</th><th>Status</th><th></th></tr></thead>
      <tbody>${rows||"<tr><td colspan=5 class=empty>No datasources</td></tr>"}</tbody>
    </table>
    <dialog id="add-dlg">
      <article>
        <header>New datasource</header>
        <form id="add-form">
          <label>Label <input name="label" required /></label>
          <label>Mongo URI <input name="mongo_uri" required placeholder="mongodb+srv://..." /></label>
          <label>Database <input name="db_name" required /></label>
          <label>Collection <input name="col_name" required /></label>
          <label>Field mapping (JSON) <textarea name="field_mapping" rows="4">{}</textarea></label>
          <button type="submit">Create</button>
        </form>
      </article>
    </dialog>`;
  document.getElementById("btn-add").onclick = () => document.getElementById("add-dlg").showModal();
  document.getElementById("add-form").onsubmit = async (e) => {
    e.preventDefault();
    const fd = new FormData(e.target);
    let mapping = {};
    try { mapping = JSON.parse(fd.get("field_mapping") || "{}"); } catch {
      toast("Invalid JSON for field mapping"); return;
    }
    try {
      await post("/datasources", {
        label: fd.get("label"),
        mongo_uri: fd.get("mongo_uri"),
        db_name: fd.get("db_name"),
        col_name: fd.get("col_name"),
        field_mapping: mapping,
      });
      toast("Datasource created");
      document.getElementById("add-dlg").close();
      renderDatasources(root);
    } catch (err) { toast(err.message); }
  };
  root.querySelectorAll(".btn-del").forEach(btn => {
    btn.onclick = async () => {
      if (!confirm("Delete?")) return;
      try { await del(`/datasources/${btn.dataset.id}`); renderDatasources(root); }
      catch (e) { toast(e.message); }
    };
  });
}
