import { get, getUser } from "../api.js";

export async function renderCost(root) {
  root.innerHTML = `<h2>Cost</h2><p class="skeleton" style="height:2rem;width:50%"></p>`;
  let jobs = [];
  try { jobs = await get("/jobs"); } catch (e) {
    root.innerHTML = `<p class="empty">${e.message}</p>`; return;
  }
  const jobId = sessionStorage.getItem("selectedJob") || (jobs[0] && jobs[0].id);
  const opts = jobs.map(j => `<option value="${j.id}" ${j.id===jobId?"selected":""}>${j.datasource_label||j.id.slice(0,8)}</option>`).join("");
  root.innerHTML = `
    <h2>Cost</h2>
    <label class="job-select">Job <select id="job-sel">${opts||"<option>None</option>"}</select></label>
    <div id="cost-body"></div>`;
  const body = document.getElementById("cost-body");
  document.getElementById("job-sel").onchange = (e) => load(e.target.value);
  async function load(id) {
    if (!id) { body.innerHTML = `<p class="empty">No data yet — run a job</p>`; return; }
    sessionStorage.setItem("selectedJob", id);
    try {
      const c = await get(`/jobs/${id}/cost`);
      const user = getUser();
      const budget = user?.monthly_budget || 50;
      const spendPct = Math.min(100, (c.total_usd / budget) * 100);
      body.innerHTML = `
        <div class="stat-row">
          <div class="stat-card"><div class="num">$${c.total_usd.toFixed(4)}</div><div class="label">Total</div></div>
          <div class="stat-card"><div class="num">$${(c.openai_usd||0).toFixed(4)}</div><div class="label">OpenAI</div></div>
          <div class="stat-card"><div class="num">$${(c.serper_usd||0).toFixed(4)}</div><div class="label">Serper</div></div>
          <div class="stat-card"><div class="num">$${(c.cost_per_success||0).toFixed(4)}</div><div class="label">Per success</div></div>
        </div>
        <p>Budget: $${budget} — spent ${spendPct.toFixed(1)}%</p>
        <progress value="${spendPct}" max="100"></progress>
        <h3>By step</h3><canvas id="step-chart" height="160"></canvas>
        <h3>Forecast</h3>
        <p>Remaining docs at current rate ≈ <strong>$${(c.forecast_usd||0).toFixed(2)}</strong></p>
        <h3>Top expensive docs</h3>
        <table><thead><tr><th>Doc</th><th>Cost</th></tr></thead>
        <tbody>${(c.top_expensive_docs||[]).map(d=>`<tr><td>${d.doc_id}</td><td>$${d.cost.toFixed(4)}</td></tr>`).join("")||"<tr><td colspan=2 class=empty>None</td></tr>"}</tbody></table>`;
      const steps = Object.keys(c.by_step||{});
      if (steps.length) {
        new Chart(document.getElementById("step-chart"), {
          type: "doughnut",
          data: { labels: steps, datasets: [{ data: steps.map(s => c.by_step[s]), backgroundColor: ["#60a5fa","#34d399","#fbbf24"] }] },
        });
      }
    } catch (e) { body.innerHTML = `<p class="empty">${e.message}</p>`; }
  }
  if (jobId) load(jobId);
}
