import { get } from "../api.js";
import { subscribeJob } from "../sse.js";

let unsub = null;

async function loadJobs() {
  return get("/jobs");
}

export async function renderReport(root) {
  if (unsub) { unsub(); unsub = null; }
  root.innerHTML = `<p class="skeleton" style="height:2rem;width:60%"></p>`;
  let jobs = [];
  try { jobs = await loadJobs(); } catch (e) {
    root.innerHTML = `<p class="empty">${e.message}</p>`;
    return;
  }
  const jobId = sessionStorage.getItem("selectedJob") || (jobs[0] && jobs[0].id);
  if (jobId) sessionStorage.setItem("selectedJob", jobId);

  const opts = jobs.map(j =>
    `<option value="${j.id}" ${j.id === jobId ? "selected" : ""}>${j.datasource_label || j.id.slice(0,8)} · ${j.status}</option>`
  ).join("");

  root.innerHTML = `
    <h2>Report</h2>
    <label class="job-select">Job
      <select id="job-sel">${opts || "<option>No jobs</option>"}</select>
    </label>
    <div id="report-body">${jobId ? "" : '<p class="empty">No data yet — run a job</p>'}</div>`;

  const sel = document.getElementById("job-sel");
  const body = document.getElementById("report-body");

  async function renderJob(id) {
    if (!id) return;
    sessionStorage.setItem("selectedJob", id);
    body.innerHTML = `<div class="skeleton" style="height:120px"></div>`;
    try {
      const [rep, job] = await Promise.all([get(`/jobs/${id}/report`), get(`/jobs/${id}`)]);
      const f = rep.funnel || {};
      const stages = ["unprocessed","find_domain","domain_not_found","matched","unmatched","processed","scrape_failed"];
      const colors = ["#94a3b8","#60a5fa","#f87171","#34d399","#fbbf24","#22c55e","#ef4444"];
      const total = Math.max(1, Object.values(f).reduce((a,b)=>a+(b||0),0) || job.docs_total || 1);
      const funnelHtml = stages.map((s,i) => {
        const n = f[s] || 0;
        const pct = Math.max(2, (n / total) * 100);
        return n ? `<div style="width:${pct}%;background:${colors[i]}" title="${s}: ${n}">${s} ${n}</div>` : "";
      }).join("");
      body.innerHTML = `
        <div class="funnel">${funnelHtml || '<div style="width:100%;background:#e5e7eb;color:#333">No funnel data</div>'}</div>
        <div class="stat-row">
          <div class="stat-card"><div class="num" id="c-proc">${job.docs_processed}</div><div class="label">Processed</div></div>
          <div class="stat-card"><div class="num">${f.matched || 0}</div><div class="label">Matched</div></div>
          <div class="stat-card"><div class="num" id="c-fail">${job.docs_failed}</div><div class="label">Failed</div></div>
          <div class="stat-card"><div class="num"><span class="status ${job.status}">${job.status}</span></div><div class="label">Status · ETA ${rep.eta_seconds ? Math.round(rep.eta_seconds/60)+'m' : '—'}</div></div>
        </div>
        <h3>Failures</h3>
        <canvas id="fail-chart" height="120"></canvas>
        <h3>Docs</h3>
        <div id="docs-table"><p class="skeleton"></p></div>`;
      const labels = Object.keys(rep.failures || {});
      const vals = Object.values(rep.failures || {});
      if (labels.length) {
        new Chart(document.getElementById("fail-chart"), {
          type: "bar",
          data: { labels, datasets: [{ label: "Count", data: vals, backgroundColor: "#f87171" }] },
          options: { indexAxis: "y", plugins: { legend: { display: false } } },
        });
      }
      try {
        const docs = await get(`/jobs/${id}/report/docs?page_size=20`);
        const rows = (docs.results || []).map(d =>
          `<tr><td>${(d.doc_id||"").slice(0,8)}</td><td>${d.domain||""}</td><td>${d.method||""}</td>
           <td><span class="status ${d.status}">${d.status}</span></td><td>${d.completeness||""}</td></tr>`
        ).join("");
        document.getElementById("docs-table").innerHTML = rows
          ? `<table><thead><tr><th>Doc</th><th>Domain</th><th>Method</th><th>Status</th><th>Comp.</th></tr></thead><tbody>${rows}</tbody></table>`
          : `<p class="empty">No docs yet</p>`;
      } catch {}
      if (unsub) unsub();
      unsub = subscribeJob(id, (p) => {
        const el = document.getElementById("c-proc");
        if (el) el.textContent = p.docs_processed;
        const fl = document.getElementById("c-fail");
        if (fl) fl.textContent = p.docs_failed;
      });
    } catch (e) {
      body.innerHTML = `<p class="empty">${e.message}</p>`;
    }
  }

  sel.onchange = () => renderJob(sel.value);
  if (jobId) renderJob(jobId);
}
