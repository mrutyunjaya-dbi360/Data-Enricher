from celery import shared_task
import logging

logger = logging.getLogger(__name__)


@shared_task(bind=True, name="jobs.run_job")
def run_job(self, job_id: str):
    from jobs.models import Job
    from datasources.crypto import decrypt
    from jobs.cancellation import RedisCancelFlag
    from metrics.emitter import EventEmitter
    from pipeline.config import JobConfig
    from pipeline.runner import run_job as pipeline_run
    from pipeline.exceptions import CreditExpired, SSRFBlocked
    from pymongo import MongoClient

    try:
        job = Job.objects.select_related(
            "datasource", "datasource_owner", "submitted_by", "tenant"
        ).get(pk=job_id)
    except Job.DoesNotExist:
        logger.error(f"Job {job_id} not found")
        return

    local = None
    master = None
    emitter = None
    try:
        ds = job.datasource
        local_uri = decrypt(bytes(ds.encrypted_uri))
        master_uri = decrypt(bytes(ds.encrypted_master_uri)) if ds.encrypted_master_uri else None
        cfg = JobConfig.from_job(job, local_uri, master_uri)
        cancel = RedisCancelFlag(str(job.id))
        emitter = EventEmitter(job, cfg)

        local = MongoClient(cfg.local_uri, serverSelectionTimeoutMS=10000)
        master = MongoClient(cfg.master_uri, serverSelectionTimeoutMS=10000) if cfg.master_uri else None

        def progress_cb(processed=None, failed=None, total=None, cost=None):
            updates = {}
            if processed is not None:
                updates["docs_processed"] = processed
            if failed is not None:
                updates["docs_failed"] = failed
            if total is not None:
                updates["docs_total"] = total
            if cost is not None:
                updates["cost_usd"] = cost
            if updates:
                Job.objects.filter(pk=job.id).update(**updates)

        job.mark_running()
        result = pipeline_run(cfg, local, master, cancel, emitter, progress_cb)
        job.refresh_from_db()
        if job.cancel_requested or cancel.is_set():
            job.finish("cancelled")
        else:
            job.finish(result if result in ("done", "cancelled", "paused") else "done")
        try:
            from metrics.rollups import refresh_job_summary, upsert_daily_metrics
            refresh_job_summary(job)
            upsert_daily_metrics(job)
        except Exception as e:
            logger.warning(f"Rollup failed: {e}")
    except CreditExpired as e:
        job.pause(reason=str(e))
    except SSRFBlocked as e:
        job.fail(f"SSRF: {e}")
    except Exception as e:
        logger.exception(f"Job {job_id} failed")
        job.fail(str(e))
        raise
    finally:
        if emitter:
            emitter.flush()
        if local is not None:
            local.close()
        if master is not None:
            master.close()
