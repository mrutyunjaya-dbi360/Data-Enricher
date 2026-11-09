import uuid
from django.db import models
from accounts.models import Tenant, User
from datasources.models import Datasource
from jobs.models import Job


class Event(models.Model):
    STEP_CHOICES = [("step1", "Step1"), ("step2", "Step2"), ("step3", "Step3")]
    ACTION_CHOICES = [
        ("serper", "Serper"),
        ("llm_select", "LLM Select"),
        ("llm_verify", "LLM Verify"),
        ("crewai", "CrewAI"),
        ("crawl4ai", "Crawl4AI"),
        ("doc_complete", "Doc Complete"),
        ("mongo_write", "Mongo Write"),
    ]

    id = models.BigAutoField(primary_key=True)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="events")
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name="events", db_index=True)
    datasource = models.ForeignKey(Datasource, on_delete=models.CASCADE, related_name="events", db_index=True)
    datasource_owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="owned_events", db_index=True)
    submitted_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name="submitted_events", db_index=True)
    doc_id = models.CharField(max_length=64, null=True, blank=True, db_index=True)
    step = models.CharField(max_length=16, choices=STEP_CHOICES)
    action = models.CharField(max_length=32, choices=ACTION_CHOICES)
    ts = models.DateTimeField(auto_now_add=True, db_index=True)
    latency_ms = models.IntegerField(null=True, blank=True)
    success = models.BooleanField(default=True)
    error_type = models.CharField(max_length=64, blank=True)
    model = models.CharField(max_length=64, blank=True)
    tokens_in = models.IntegerField(default=0)
    tokens_out = models.IntegerField(default=0)
    cost_usd = models.DecimalField(max_digits=14, decimal_places=8, default=0)
    serper_queries = models.IntegerField(default=0)
    crawl_bytes = models.IntegerField(default=0)
    method = models.CharField(max_length=32, blank=True)
    extra = models.JSONField(default=dict, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["job", "ts"]),
            models.Index(fields=["datasource_owner", "ts"]),
            models.Index(fields=["tenant", "ts"]),
            models.Index(fields=["job", "doc_id"]),
        ]


class DocQuality(models.Model):
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name="doc_qualities")
    datasource = models.ForeignKey(Datasource, on_delete=models.CASCADE)
    datasource_owner = models.ForeignKey(User, on_delete=models.CASCADE)
    doc_id = models.CharField(max_length=64)
    source = models.CharField(max_length=120, blank=True)
    domain = models.CharField(max_length=255, blank=True)
    method = models.CharField(max_length=32, blank=True)
    status = models.CharField(max_length=32, blank=True)
    completeness = models.DecimalField(max_digits=4, decimal_places=3, default=0)
    confidence = models.DecimalField(max_digits=4, decimal_places=3, default=0)
    fields = models.JSONField(default=dict, blank=True)
    validation_errors = models.JSONField(default=list, blank=True)

    class Meta:
        unique_together = [("job", "doc_id")]
        indexes = [models.Index(fields=["job", "doc_id"])]


class JobSummary(models.Model):
    job = models.OneToOneField(Job, on_delete=models.CASCADE, primary_key=True, related_name="summary")
    funnel = models.JSONField(default=dict, blank=True)
    failures = models.JSONField(default=dict, blank=True)
    per_method = models.JSONField(default=dict, blank=True)
    per_step_cost = models.JSONField(default=dict, blank=True)
    avg_completeness = models.DecimalField(max_digits=4, decimal_places=3, default=0)
    avg_confidence = models.DecimalField(max_digits=4, decimal_places=3, default=0)


class UserDailyMetrics(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    datasource = models.ForeignKey(Datasource, on_delete=models.CASCADE, null=True, blank=True)
    date = models.DateField()
    docs_processed = models.IntegerField(default=0)
    docs_matched = models.IntegerField(default=0)
    docs_failed = models.IntegerField(default=0)
    tokens_in = models.BigIntegerField(default=0)
    tokens_out = models.BigIntegerField(default=0)
    serper_calls = models.IntegerField(default=0)
    crawl_fetches = models.IntegerField(default=0)
    cost_usd = models.DecimalField(max_digits=14, decimal_places=6, default=0)

    class Meta:
        unique_together = [("tenant", "user", "datasource", "date")]
