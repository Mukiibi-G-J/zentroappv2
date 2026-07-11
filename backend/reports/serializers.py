from rest_framework import serializers
from .models import ScheduledReport, ReportLog


class ScheduledReportSerializer(serializers.ModelSerializer):
    """Serializer for Scheduled Reports"""

    created_by_name = serializers.CharField(
        source="created_by.full_name", read_only=True
    )

    class Meta:
        model = ScheduledReport
        fields = [
            "id",
            "name",
            "report_type",
            "frequency",
            "recipients",
            "export_format",
            "filters",
            "is_active",
            "last_run",
            "next_run",
            "created_by",
            "created_by_name",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "created_by_name",
            "created_at",
            "updated_at",
            "last_run",
        ]


class ReportLogSerializer(serializers.ModelSerializer):
    """Serializer for Report Logs"""

    generated_by_name = serializers.CharField(
        source="generated_by.full_name", read_only=True
    )
    scheduled_report_name = serializers.CharField(
        source="scheduled_report.name", read_only=True
    )

    class Meta:
        model = ReportLog
        fields = [
            "id",
            "report_type",
            "generated_by",
            "generated_by_name",
            "generated_at",
            "filters_applied",
            "export_format",
            "execution_time_ms",
            "cached",
            "scheduled_report",
            "scheduled_report_name",
            "ip_address",
        ]
        read_only_fields = [
            "id",
            "generated_at",
            "generated_by_name",
            "scheduled_report_name",
        ]
