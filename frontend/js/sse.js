export function subscribeJob(jobId, onUpdate) {
  const access = localStorage.getItem("access");
  // EventSource cannot set headers; use fetch stream fallback via polyfill pattern
  // For MVP: poll every 2s if SSE blocked, else try EventSource without auth cookie
  let stopped = false;
  const es = new EventSource(`/api/jobs/${jobId}/stream`);
  // Note: browser EventSource won't send Authorization; nginx/backend should accept query token or we poll
  es.onmessage = (ev) => {
    try { onUpdate(JSON.parse(ev.data)); } catch {}
  };
  es.onerror = () => {
    es.close();
    // fallback poll
    const tick = async () => {
      if (stopped) return;
      try {
        const { get } = await import("./api.js");
        const j = await get(`/jobs/${jobId}`);
        onUpdate({
          status: j.status,
          docs_processed: j.docs_processed,
          docs_failed: j.docs_failed,
          docs_total: j.docs_total,
          cost_usd: j.cost_usd,
        });
        if (["done", "failed", "cancelled"].includes(j.status)) return;
      } catch {}
      setTimeout(tick, 2000);
    };
    tick();
  };
  return () => { stopped = true; es.close(); };
}
