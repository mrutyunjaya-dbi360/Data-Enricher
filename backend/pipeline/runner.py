"""Job runner — one cycle loop ported from run_forever / run_pipeline_once."""
import logging
from pipeline.step1 import run_step1
from pipeline.step2 import run_step2
from pipeline.step3 import run_step3
from pipeline.exceptions import CreditExpired

logger = logging.getLogger(__name__)


def reset_stuck(col):
    try:
        result = col.update_many(
            {
                "status": "unprocessed",
                "company_url": {"$exists": True, "$nin": [None, ""]},
                "domain_status_method": {"$exists": True},
            },
            {"$unset": {
                "company_url": "", "domain_status_method": "",
                "domain_status_error": "", "domain_context_used": "",
            }},
        )
        if result.modified_count:
            logger.warning(f"[RESET] {result.modified_count} partial docs cleaned")
    except Exception as e:
        logger.error(f"[RESET] {e}")


def has_pending(cfg, local_client):
    col = local_client[cfg.local_db][cfg.local_col]
    unprocessed = col.count_documents({"status": "unprocessed"})
    find_domain = col.count_documents({"status": "find_domain"})
    unmatched = col.count_documents({
        "status": "unmatched",
        "$or": [
            {"step3_attempts": {"$exists": False}},
            {"step3_attempts": {"$lt": cfg.max_step3_attempts}},
        ],
    })
    no_status = col.count_documents({
        "$and": [
            {"$or": [{"status": {"$exists": False}}, {"status": None}]},
            {"company_url": {"$exists": True, "$nin": ["", None]}},
        ]
    })
    total = unprocessed + find_domain + unmatched + no_status
    logger.info(f"[POLL] pending={total} (unproc={unprocessed} find={find_domain} unmatched={unmatched})")
    return total > 0


def run_job(cfg, local_client, master_client, cancel, emitter, progress_cb=None) -> str:
    col = local_client[cfg.local_db][cfg.local_col]
    for cycle in range(cfg.max_cycles):
        if cancel and cancel.is_set():
            return "cancelled"
        logger.info(f"=== CYCLE {cycle + 1}/{cfg.max_cycles} ===")
        reset_stuck(col)
        try:
            run_step1(cfg, local_client, cancel, emitter, progress_cb)
            if cancel and cancel.is_set():
                return "cancelled"
            run_step2(cfg, local_client, master_client, cancel, emitter)
            if cancel and cancel.is_set():
                return "cancelled"
            run_step3(cfg, local_client, cancel, emitter, progress_cb)
        except CreditExpired:
            raise
        if not has_pending(cfg, local_client):
            return "done"
    return "done"
