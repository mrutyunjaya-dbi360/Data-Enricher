from rest_framework import serializers
from .models import Job
from datasources.models import Datasource


class JobSerializer(serializers.ModelSerializer):
    datasource_label = serializers.CharField(source="datasource.label", read_only=True)
    submitted_by_email = serializers.CharField(source="submitted_by.email", read_only=True)

    class Meta:
        model = Job
        fields = [
            "id", "status", "output_mode", "config", "cancel_requested",
            "docs_total", "docs_processed", "docs_failed", "cost_usd", "error",
            "started_at", "finished_at", "created_at",
            "datasource", "datasource_label", "datasource_owner",
            "submitted_by", "submitted_by_email",
        ]
        read_only_fields = fields


class JobCreateSerializer(serializers.Serializer):
    datasource_id = serializers.UUIDField()
    max_docs = serializers.IntegerField(required=False, default=0, min_value=0)
    max_cycles = serializers.IntegerField(required=False, default=10, min_value=1, max_value=100)
    domain_threads = serializers.IntegerField(required=False, default=10, min_value=1, max_value=50)
    crewai_threads = serializers.IntegerField(required=False, default=5, min_value=1, max_value=20)

    def validate_datasource_id(self, value):
        request = self.context["request"]
        qs = Datasource.objects.filter(pk=value, tenant=request.user.tenant, status="active")
        if request.user.role != "admin":
            qs = qs.filter(owner=request.user)
        if not qs.exists():
            raise serializers.ValidationError("Datasource not found or not active")
        return value
