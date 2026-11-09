import uuid
from django.db import models
from django.utils import timezone
from accounts.models import Tenant, User
from datasources.models import Datasource


class Job(models.Model):
    STATUS_CHOICES = [
        ("queued", "Queued"),
        ("running", "Running"),
        ("paused", "Paused"),
        ("done", "Done"),
        ("failed", "Failed"),
        ("cancelled", "Cancelled"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="jobs")
    datasource = models.ForeignKey(Datasource, on_delete=models.CASCADE, related_name="jobs")
    datasource_owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="owned_jobs")
    submitted_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name="submitted_jobs")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="queued")
    output_mode = models.CharField(max_length=40, default="separate_collection")
    config = models.JSONField(default=dict, blank=True)
    cancel_requested = models.BooleanField(default=False)
    docs_total = models.IntegerField(default=0)
    docs_processed = models.IntegerField(default=0)
    docs_failed = models.IntegerField(default=0)
    cost_usd = models.DecimalField(max_digits=14, decimal_places=6, default=0)
    error = models.TextField(blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def mark_running(self):
        self.status = "running"
        self.started_at = timezone.now()
        self.save(update_fields=["status", "started_at"])

    def finish(self, result: str):
        self.status = result if result in ("done", "cancelled", "paused") else "done"
        self.finished_at = timezone.now()
        self.save(update_fields=["status", "finished_at"])

    def pause(self, reason: str = ""):
        self.status = "paused"
        self.error = reason
        self.finished_at = timezone.now()
        self.save(update_fields=["status", "error", "finished_at"])

    def fail(self, reason: str):
        self.status = "failed"
        self.error = reason
        self.finished_at = timezone.now()
        self.save(update_fields=["status", "error", "finished_at"])
