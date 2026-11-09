import json
import time
from django.http import StreamingHttpResponse
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import Job
from .serializers import JobSerializer, JobCreateSerializer
from .cancellation import RedisCancelFlag
from .tasks import run_job
from datasources.models import Datasource


def _scope(qs, user):
    qs = qs.filter(tenant=user.tenant)
    if user.role != "admin":
        qs = qs.filter(datasource_owner=user)
    return qs


class JobListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = _scope(Job.objects.select_related("datasource", "submitted_by"), request.user)
        return Response(JobSerializer(qs[:50], many=True).data)

    def post(self, request):
        ser = JobCreateSerializer(data=request.data, context={"request": request})
        ser.is_valid(raise_exception=True)
        data = ser.validated_data
        ds = Datasource.objects.get(pk=data["datasource_id"])
        job = Job.objects.create(
            tenant=request.user.tenant,
            datasource=ds,
            datasource_owner=ds.owner,
            submitted_by=request.user,
            status="queued",
            config={
                "max_docs": data.get("max_docs", 0),
                "max_cycles": data.get("max_cycles", 10),
                "domain_threads": data.get("domain_threads", 10),
                "crewai_threads": data.get("crewai_threads", 5),
            },
        )
        run_job.delay(str(job.id))
        return Response(JobSerializer(job).data, status=status.HTTP_201_CREATED)


class JobDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            job = _scope(Job.objects.select_related("datasource", "submitted_by"), request.user).get(pk=pk)
        except Job.DoesNotExist:
            return Response({"detail": "Not found"}, status=404)
        return Response(JobSerializer(job).data)


class JobCancelView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            job = _scope(Job.objects.all(), request.user).get(pk=pk)
        except Job.DoesNotExist:
            return Response({"detail": "Not found"}, status=404)
        if job.status not in ("queued", "running", "paused"):
            return Response({"detail": f"Cannot cancel status={job.status}"}, status=400)
        job.cancel_requested = True
        job.save(update_fields=["cancel_requested"])
        RedisCancelFlag(str(job.id)).set()
        if job.status == "queued":
            job.status = "cancelled"
            job.save(update_fields=["status"])
        return Response(JobSerializer(job).data)


class JobResumeView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            job = _scope(Job.objects.all(), request.user).get(pk=pk)
        except Job.DoesNotExist:
            return Response({"detail": "Not found"}, status=404)
        if job.status != "paused":
            return Response({"detail": "Only paused jobs can be resumed"}, status=400)
        job.cancel_requested = False
        job.status = "queued"
        job.error = ""
        job.save(update_fields=["cancel_requested", "status", "error"])
        RedisCancelFlag(str(job.id)).clear()
        run_job.delay(str(job.id))
        return Response(JobSerializer(job).data)


class JobStreamView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            job = _scope(Job.objects.all(), request.user).get(pk=pk)
        except Job.DoesNotExist:
            return Response({"detail": "Not found"}, status=404)

        def event_stream():
            last = None
            for _ in range(900):  # ~30 min at 2s
                try:
                    job.refresh_from_db()
                except Exception:
                    break
                payload = {
                    "status": job.status,
                    "docs_processed": job.docs_processed,
                    "docs_failed": job.docs_failed,
                    "docs_total": job.docs_total,
                    "cost_usd": str(job.cost_usd),
                }
                data = json.dumps(payload)
                if data != last:
                    yield f"data: {data}\n\n"
                    last = data
                if job.status in ("done", "failed", "cancelled"):
                    break
                time.sleep(2)

        resp = StreamingHttpResponse(event_stream(), content_type="text/event-stream")
        resp["Cache-Control"] = "no-cache"
        resp["X-Accel-Buffering"] = "no"
        return resp
