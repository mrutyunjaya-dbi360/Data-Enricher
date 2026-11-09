from decimal import Decimal
from django.db.models import Sum, Avg, Count, Q
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from jobs.models import Job
from metrics.models import Event, DocQuality, JobSummary, UserDailyMetrics
from accounts.permissions import IsAdmin
from accounts.models import User


def _job_scope(user, pk=None):
    qs = Job.objects.filter(tenant=user.tenant)
    if user.role != "admin":
        qs = qs.filter(datasource_owner=user)
    if pk:
        return qs.filter(pk=pk).first()
    return qs


class JobReportView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        job = _job_scope(request.user, pk)
        if not job:
            return Response({"detail": "Not found"}, status=404)
        summary, _ = JobSummary.objects.get_or_create(job=job)
        funnel = summary.funnel or {}
        # enrich funnel with status counts if empty
        if not funnel.get("processed"):
            funnel = {
                "unprocessed": 0, "find_domain": 0, "domain_not_found": 0,
                "matched": 0, "unmatched": 0,
                "processed": job.docs_processed,
                "scrape_failed": job.docs_failed,
            }
        elapsed = 0
        if job.started_at:
            from django.utils import timezone
            end = job.finished_at or timezone.now()
            elapsed = max(0, (end - job.started_at).total_seconds())
        throughput = (job.docs_processed / elapsed) if elapsed > 0 else 0
        remaining = max(0, (job.docs_total or 0) - job.docs_processed)
        eta = (remaining / throughput) if throughput > 0 else None
        return Response({
            "funnel": funnel,
            "failures": summary.failures or {},
            "per_method": summary.per_method or {},
            "throughput": round(throughput, 4),
            "eta_seconds": round(eta) if eta else None,
            "docs_processed": job.docs_processed,
            "docs_failed": job.docs_failed,
            "docs_total": job.docs_total,
            "status": job.status,
        })


class JobReportDocsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        job = _job_scope(request.user, pk)
        if not job:
            return Response({"detail": "Not found"}, status=404)
        qs = DocQuality.objects.filter(job=job).order_by("-id")
        status_f = request.query_params.get("status")
        if status_f:
            qs = qs.filter(status=status_f)
        page = int(request.query_params.get("page", 1))
        size = min(int(request.query_params.get("page_size", 25)), 200)
        total = qs.count()
        items = list(qs[(page - 1) * size: page * size])
        return Response({
            "count": total,
            "results": [
                {
                    "doc_id": d.doc_id, "domain": d.domain, "method": d.method,
                    "status": d.status, "completeness": str(d.completeness),
                    "confidence": str(d.confidence), "source": d.source,
                    "validation_errors": d.validation_errors,
                }
                for d in items
            ],
        })


class JobCostView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        job = _job_scope(request.user, pk)
        if not job:
            return Response({"detail": "Not found"}, status=404)
        total = Event.objects.filter(job=job).aggregate(s=Sum("cost_usd"))["s"] or Decimal("0")
        by_step = {}
        for r in Event.objects.filter(job=job).values("step").annotate(s=Sum("cost_usd")):
            by_step[r["step"]] = float(r["s"] or 0)
        by_action = {}
        for r in Event.objects.filter(job=job).values("action").annotate(s=Sum("cost_usd")):
            by_action[r["action"]] = float(r["s"] or 0)
        tokens = {}
        for r in Event.objects.filter(job=job).exclude(model="").values("model").annotate(
            ti=Sum("tokens_in"), to=Sum("tokens_out"), c=Sum("cost_usd")
        ):
            tokens[r["model"]] = {"tokens_in": r["ti"] or 0, "tokens_out": r["to"] or 0, "cost": float(r["c"] or 0)}
        success = max(job.docs_processed, 1)
        top = list(
            Event.objects.filter(job=job, doc_id__isnull=False)
            .values("doc_id").annotate(c=Sum("cost_usd")).order_by("-c")[:10]
        )
        remaining = max(0, (job.docs_total or 0) - job.docs_processed)
        per_doc = float(total) / success if success else 0
        return Response({
            "total_usd": float(total),
            "by_step": by_step,
            "by_action": by_action,
            "tokens_by_model": tokens,
            "cost_per_doc": per_doc,
            "cost_per_success": per_doc,
            "top_expensive_docs": [{"doc_id": t["doc_id"], "cost": float(t["c"] or 0)} for t in top],
            "forecast_usd": remaining * per_doc,
            "openai_usd": by_action.get("llm_select", 0) + by_action.get("llm_verify", 0) + by_action.get("crewai", 0),
            "serper_usd": by_action.get("serper", 0),
        })


class JobCostTimeseriesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        job = _job_scope(request.user, pk)
        if not job:
            return Response({"detail": "Not found"}, status=404)
        # simple: group by minute
        rows = (
            Event.objects.filter(job=job)
            .extra(select={"bucket": "date_trunc('minute', ts)"})
            .values("bucket")
            .annotate(cost_usd=Sum("cost_usd"))
            .order_by("bucket")
        )
        # sqlite fallback: just return all events aggregated coarsely
        try:
            data = [{"ts": r["bucket"].isoformat() if r["bucket"] else None, "cost_usd": float(r["cost_usd"] or 0)} for r in rows]
        except Exception:
            data = [{"ts": job.created_at.isoformat(), "cost_usd": float(job.cost_usd or 0)}]
        return Response(data)


class JobQualityView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        job = _job_scope(request.user, pk)
        if not job:
            return Response({"detail": "Not found"}, status=404)
        docs = list(DocQuality.objects.filter(job=job))
        field_fill = {}
        if docs:
            keys = set()
            for d in docs:
                keys.update((d.fields or {}).keys())
            for k in keys:
                filled = sum(1 for d in docs if (d.fields or {}).get(k))
                field_fill[k] = {"filled": filled, "total": len(docs), "pct": filled / len(docs)}
        hist = {"0-0.2": 0, "0.2-0.4": 0, "0.4-0.6": 0, "0.6-0.8": 0, "0.8-1.0": 0}
        conf_by_method = {}
        for d in docs:
            c = float(d.completeness or 0)
            if c < 0.2: hist["0-0.2"] += 1
            elif c < 0.4: hist["0.2-0.4"] += 1
            elif c < 0.6: hist["0.4-0.6"] += 1
            elif c < 0.8: hist["0.6-0.8"] += 1
            else: hist["0.8-1.0"] += 1
            m = d.method or "unknown"
            conf_by_method.setdefault(m, []).append(float(d.confidence or 0))
        conf_dist = {m: (sum(v) / len(v) if v else 0) for m, v in conf_by_method.items()}
        val_errors = {}
        for d in docs:
            for e in (d.validation_errors or []):
                val_errors[e] = val_errors.get(e, 0) + 1
        avg_c = sum(float(d.completeness or 0) for d in docs) / len(docs) if docs else 0
        avg_conf = sum(float(d.confidence or 0) for d in docs) / len(docs) if docs else 0
        pass_rate = sum(1 for d in docs if not d.validation_errors) / len(docs) if docs else 0
        domains = {}
        for d in docs:
            if d.domain:
                domains[d.domain] = domains.get(d.domain, 0) + 1
        dups = [{"domain": k, "count": v} for k, v in domains.items() if v > 1]
        return Response({
            "field_fill": field_fill,
            "completeness_hist": hist,
            "confidence_hist": conf_dist,
            "validation_pass_rate": pass_rate,
            "worst_fields": sorted(field_fill.items(), key=lambda x: x[1]["pct"])[:10],
            "duplicate_domains": dups,
            "avg_completeness": avg_c,
            "avg_confidence": avg_conf,
        })


class JobQualityDocsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        job = _job_scope(request.user, pk)
        if not job:
            return Response({"detail": "Not found"}, status=404)
        qs = DocQuality.objects.filter(job=job).order_by("completeness")
        page = int(request.query_params.get("page", 1))
        size = min(int(request.query_params.get("page_size", 25)), 200)
        total = qs.count()
        items = list(qs[(page - 1) * size: page * size])
        return Response({
            "count": total,
            "results": [
                {
                    "doc_id": d.doc_id, "completeness": str(d.completeness),
                    "confidence": str(d.confidence), "fields": d.fields,
                    "validation_errors": d.validation_errors, "method": d.method,
                    "domain": d.domain, "status": d.status,
                }
                for d in items
            ],
        })


class UsersMetricsView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request):
        tenant = request.user.tenant
        users = User.objects.filter(tenant=tenant)
        out = []
        for u in users:
            agg = Event.objects.filter(datasource_owner=u).aggregate(
                ti=Sum("tokens_in"), to=Sum("tokens_out"), sc=Sum("serper_queries"), cost=Sum("cost_usd")
            )
            from datasources.models import Datasource
            out.append({
                "user_id": str(u.id),
                "email": u.email,
                "role": u.role,
                "status": u.status,
                "datasources_count": Datasource.objects.filter(owner=u).count(),
                "docs_processed": Job.objects.filter(datasource_owner=u).aggregate(s=Sum("docs_processed"))["s"] or 0,
                "tokens_in": agg["ti"] or 0,
                "tokens_out": agg["to"] or 0,
                "serper_calls": agg["sc"] or 0,
                "cost_usd": float(agg["cost"] or 0),
                "last_active": u.updated_at.isoformat() if u.updated_at else None,
            })
        return Response(out)


class UserMetricsDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        if request.user.role != "admin" and str(request.user.id) != str(pk):
            return Response({"detail": "Forbidden"}, status=403)
        try:
            user = User.objects.get(pk=pk, tenant=request.user.tenant)
        except User.DoesNotExist:
            return Response({"detail": "Not found"}, status=404)
        agg = Event.objects.filter(datasource_owner=user).aggregate(
            ti=Sum("tokens_in"), to=Sum("tokens_out"), sc=Sum("serper_queries"), cost=Sum("cost_usd")
        )
        return Response({
            "user_id": str(user.id),
            "email": user.email,
            "tokens_in": agg["ti"] or 0,
            "tokens_out": agg["to"] or 0,
            "serper_calls": agg["sc"] or 0,
            "cost_usd": float(agg["cost"] or 0),
            "docs_processed": Job.objects.filter(datasource_owner=user).aggregate(s=Sum("docs_processed"))["s"] or 0,
        })


class UserDatasourcesMetricsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        if request.user.role != "admin" and str(request.user.id) != str(pk):
            return Response({"detail": "Forbidden"}, status=403)
        from datasources.models import Datasource
        rows = []
        for ds in Datasource.objects.filter(owner_id=pk, tenant=request.user.tenant):
            cost = Event.objects.filter(datasource=ds).aggregate(s=Sum("cost_usd"))["s"] or 0
            rows.append({
                "datasource_id": str(ds.id),
                "label": ds.label,
                "cost_usd": float(cost),
                "jobs": Job.objects.filter(datasource=ds).count(),
            })
        return Response(rows)


class ReportSummaryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = Event.objects.filter(tenant=request.user.tenant)
        if request.user.role != "admin":
            qs = qs.filter(datasource_owner=request.user)
        return Response({
            "events": qs.count(),
            "cost_usd": float(qs.aggregate(s=Sum("cost_usd"))["s"] or 0),
        })


class CostSummaryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = Event.objects.filter(tenant=request.user.tenant)
        if request.user.role != "admin":
            qs = qs.filter(datasource_owner=request.user)
        return Response({"total_usd": float(qs.aggregate(s=Sum("cost_usd"))["s"] or 0)})


class QualitySummaryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = DocQuality.objects.filter(job__tenant=request.user.tenant)
        if request.user.role != "admin":
            qs = qs.filter(datasource_owner=request.user)
        return Response({
            "docs": qs.count(),
            "avg_completeness": float(qs.aggregate(a=Avg("completeness"))["a"] or 0),
        })
