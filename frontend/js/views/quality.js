import { get } from "../api.js";

export async function renderQuality(root) {
  root.innerHTML = `<h2>Quality</h2><p class="skeleton"></p>`;
  let jobs = [];
  try { jobs = await get("/jobs"); } catch (e) {
    root.innerHTML = `<p class="empty">${e.message}</p>`; return;
  }
  const jobId = sessionStorage.getItem("selectedJob") || (jobs[0] && jobs[0].id);
  const opts = jobs.map(j => `<option value="${j.id}" ${j.id===jobId?"selected":""}>${j.datasource_label||j.id.slice(0,8)}</option>`).join("");
  root.innerHTML = `
    <h2>Quality</h2>
    <label class="job-select">Job <select id="job-sel">${opts||"<option>None</option>"}</select></label>
    <div id="q-body"></div>`;
  const body = document.getElementById("q-body");
  document.getElementById("job-sel").onchange = (e) => load(e.target.value);
  async function load(id) {
    if (!id) return;
    sessionStorage.setItem("selectedJob", id);
    try {
      const q = await get(`/jobs/${id}/quality`);
      const ff = q.field_fill || {};
      const rows = Object.entries(ff).map(([k,v]) => {
        const pct = (v.pct||0)*100;
        const cls = pct >= 80 ? "g" : pct >= 40 ? "a" : "r";
        return `<tr><td>${k}</td><td class="${cls}">${pct.toFixed(0)}% (${v.filled}/${v.total})</td></tr>`;
      }).join("");
      body.innerHTML = `
        <div class="stat-row">
          <div class="stat-card"><div class="num">${(q.avg_completeness*100).toFixed(0)}%</div><div class="label">Avg completeness</div></div>
          <div class="stat-card"><div class="num">${(q.avg_confidence*100).toFixed(0)}%</div><div class="label">Avg confidence</div></div>
          <div class="stat-card"><div class="num">${(q.validation_pass_rate*100).toFixed(0)}%</div><div class="label">Validation pass</div></div>
          <div class="stat-card"><div class="num">${(q.duplicate_domains||[]).length}</div><div class="label">Dup domains</div></div>
        </div>
        <h3>Field fill</h3>
        <table class="heatmap"><thead><tr><th>Field</th><th>Fill</th></tr></thead><tbody>${rows||"<tr><td colspan=2 class=empty>No data yet</td></tr>"}</tbody></table>
        <h3>Completeness histogram</h3><canvas id="comp-chart" height="120"></canvas>`;
      const h = q.completeness_hist || {};
      new Chart(document.getElementById("comp-chart"), {
        type: "bar",
        data: { labels: Object.keys(h), datasets: [{ data: Object.values(h), backgroundColor: "#60a5fa" }] },
        options: { plugins: { legend: { display: false } } },
      });
    } catch (e) { body.innerHTML = `<p class="empty">${e.message}</p>`; }
  }
  if (jobId) load(jobId);
}
