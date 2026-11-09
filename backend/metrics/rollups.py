from django.db.models import Sum, Avg, Count, Q
from django.utils import timezone
from metrics.models import Event, DocQuality, JobSummary, UserDailyMetrics


def refresh_job_summary(job):
    funnel = {
        "processed": job.docs_processed,
        "failed": job.docs_failed,
        "total": job.docs_total,
    }
    failures = {}
    for row in Event.objects.filter(job=job, success=False).values("error_type").annotate(c=Count("id")):
        failures[row["error_type"] or "unknown"] = row["c"]

    per_method = {}
    for row in DocQuality.objects.filter(job=job).values("method").annotate(c=Count("id")):
        per_method[row["method"] or "unknown"] = row["c"]

    per_step_cost = {}
    for row in Event.objects.filter(job=job).values("step").annotate(s=Sum("cost_usd")):
        per_step_cost[row["step"]] = float(row["s"] or 0)

    agg = DocQuality.objects.filter(job=job).aggregate(
        ac=Avg("completeness"), conf=Avg("confidence")
    )
    JobSummary.objects.update_or_create(
        job=job,
        defaults={
            "funnel": funnel,
            "failures": failures,
            "per_method": per_method,
            "per_step_cost": per_step_cost,
            "avg_completeness": agg["ac"] or 0,
            "avg_confidence": agg["conf"] or 0,
        },
    )


def upsert_daily_metrics(job):
    today = timezone.now().date()
    agg = Event.objects.filter(job=job).aggregate(
        ti=Sum("tokens_in"), to=Sum("tokens_out"),
        sc=Sum("serper_queries"), cost=Sum("cost_usd"),
    )
    crawl_fetches = Event.objects.filter(job=job, action="crawl4ai").count()
    UserDailyMetrics.objects.update_or_create(
        tenant_id=job.tenant_id,
        user_id=job.datasource_owner_id,
        datasource_id=job.datasource_id,
        date=today,
        defaults={
            "docs_processed": job.docs_processed,
            "docs_failed": job.docs_failed,
            "tokens_in": agg["ti"] or 0,
            "tokens_out": agg["to"] or 0,
            "serper_calls": agg["sc"] or 0,
            "crawl_fetches": crawl_fetches,
            "cost_usd": agg["cost"] or 0,
        },
    )
