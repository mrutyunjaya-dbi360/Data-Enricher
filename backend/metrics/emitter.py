import threading
import time
import logging
from decimal import Decimal
from django.utils import timezone

logger = logging.getLogger(__name__)


class EventEmitter:
    """Thread-safe batched event writer. Never raises into the pipeline."""

    def __init__(self, job, cfg, flush_interval=2.0):
        self.job = job
        self.cfg = cfg
        self.flush_interval = flush_interval
        self._buffer = []
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._flush_loop, daemon=True)
        self._thread.start()
        self._doc_costs = {}

    def emit(self, *, doc_id=None, step, action, success=True, latency_ms=None,
             error_type="", model="", tokens_in=0, tokens_out=0, cost_usd=0,
             serper_queries=0, crawl_bytes=0, method="", extra=None):
        try:
            cost = Decimal(str(cost_usd or 0))
            row = {
                "tenant_id": self.cfg.tenant_id,
                "job_id": self.cfg.job_id,
                "datasource_id": self.cfg.datasource_id,
                "datasource_owner_id": self.cfg.datasource_owner_id,
                "submitted_by_id": self.cfg.submitted_by_id,
                "doc_id": str(doc_id) if doc_id else None,
                "step": step,
                "action": action,
                "latency_ms": latency_ms,
                "success": bool(success),
                "error_type": (error_type or "")[:64],
                "model": (model or "")[:64],
                "tokens_in": int(tokens_in or 0),
                "tokens_out": int(tokens_out or 0),
                "cost_usd": cost,
                "serper_queries": int(serper_queries or 0),
                "crawl_bytes": int(crawl_bytes or 0),
                "method": (method or "")[:32],
                "extra": extra or {},
                "ts": timezone.now(),
            }
            with self._lock:
                self._buffer.append(row)
                if doc_id and cost:
                    did = str(doc_id)
                    self._doc_costs[did] = self._doc_costs.get(did, Decimal("0")) + cost
        except Exception as e:
            logger.warning(f"emit failed: {e}")

    def doc_cost(self, doc_id) -> Decimal:
        return self._doc_costs.get(str(doc_id), Decimal("0"))

    def _flush_loop(self):
        while not self._stop.wait(self.flush_interval):
            self.flush()

    def flush(self):
        with self._lock:
            batch = self._buffer
            self._buffer = []
        if not batch:
            return
        try:
            from metrics.models import Event
            Event.objects.bulk_create([Event(**r) for r in batch], ignore_conflicts=True)
        except Exception as e:
            logger.error(f"Event flush failed ({len(batch)} events): {e}")

    def close(self):
        self._stop.set()
        self.flush()
