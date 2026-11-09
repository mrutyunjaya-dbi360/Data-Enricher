import uuid
from django.db import models
from accounts.models import Tenant, User


class Datasource(models.Model):
    STATUS_CHOICES = [("active", "Active"), ("disabled", "Disabled")]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="datasources")
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="datasources")
    label = models.CharField(max_length=120)
    encrypted_uri = models.BinaryField()
    encrypted_master_uri = models.BinaryField(null=True, blank=True)
    db_name = models.CharField(max_length=120)
    col_name = models.CharField(max_length=120)
    field_mapping = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active")
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="created_datasources")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.label} ({self.db_name}.{self.col_name})"
