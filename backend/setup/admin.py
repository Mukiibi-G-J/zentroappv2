import html

from django.contrib import admin
from django.contrib import messages
from django.template.response import TemplateResponse
from django.urls import path
from django.http import HttpRequest, HttpResponseRedirect
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from setup.models import (
    EmailSetup,
    NoSeries,
    NoSeriesLines,
    InventorySetup,
    JournalSetup,
    BankAccountSetup,
    ResourceSetup,
    ManufacturingSetup,
    SeedManager,
)
from setup.utils import (
    discover_seed_commands,
    get_request_tenant_schema_name,
    run_all_seed_commands,
    run_seed_command,
)


def _admin_multiline_message(text: str):
    """Show seed logs in admin with line breaks (HTML-escaped)."""
    if not text:
        return ""
    return mark_safe(html.escape(text).replace("\n", "<br>"))


def _format_seed_command_output(
    output: str,
    *,
    max_lines: int = 40,
    max_chars: int = 8000,
) -> str:
    """Indent and cap stdout/stderr so admin messages stay readable."""
    text = (output or "").replace("\r\n", "\n").strip()
    if not text:
        return ""
    lines = text.split("\n")
    prefix = ""
    if len(lines) > max_lines:
        drop = len(lines) - max_lines
        prefix = f"… ({drop} earlier line(s) omitted)\n"
        lines = lines[-max_lines:]
    body = prefix + "\n".join(lines)
    if len(body) > max_chars:
        body = "… (truncated)\n" + body[-max_chars:]
    return "\n".join(f"   {line}" for line in body.split("\n"))


@admin.register(EmailSetup)
class EmailSetupAdmin(admin.ModelAdmin):
    list_display = ("subject", "email_category", "status")
    list_filter = ("email_category", "status")
    search_fields = ("subject", "from_email")

    fieldsets = (
        (None, {"fields": ("subject", "email_category", "status")}),
        (
            "SMTP Configuration",
            {
                "fields": (
                    "email_host",
                    "email_host_user",
                    "email_host_password",
                    "email_port",
                    "email_use_tls",
                )
            },
        ),
    )


@admin.register(NoSeries)
class NoSeriesAdmin(admin.ModelAdmin):
    list_display = ["code", "description"]
    search_fields = ["code", "description"]


@admin.register(NoSeriesLines)
class NoSeriesLinesAdmin(admin.ModelAdmin):
    list_display = [
        "no_series",
        "start_number",
        "end_number",
        "last_used_number",
        "last_used_date",
        "increment_by",
    ]


@admin.register(InventorySetup)
class InventorySetupAdmin(admin.ModelAdmin):
    list_display = ["item_no_series", "show_adjustment_history_before_after"]


@admin.register(JournalSetup)
class GeneralJournalTemplateAdmin(admin.ModelAdmin):
    list_display = ["journal_no_series", "journal_type"]
    list_filter = ["journal_type"]


@admin.register(BankAccountSetup)
class BankAccountSetupAdmin(admin.ModelAdmin):
    list_display = ["bank_account_no_series"]


@admin.register(ResourceSetup)
class ResourceSetupAdmin(admin.ModelAdmin):
    list_display = ["resource_no_series"]


@admin.register(ManufacturingSetup)
class ManufacturingSetupAdmin(admin.ModelAdmin):
    list_display = [
        "manufacturing_enabled",
        "bom_no_series",
        "production_order_no_series",
        "work_center_no_series",
        "machine_center_no_series",
        "routing_no_series",
    ]
    fields = [
        "manufacturing_enabled",
        "bom_no_series",
        "production_order_no_series",
        "work_center_no_series",
        "machine_center_no_series",
        "routing_no_series",
    ]


@admin.register(SeedManager)
class SeedManagerAdmin(admin.ModelAdmin):
    """
    Admin interface for Seed Manager.
    Provides actions to run all seed commands at once.
    """

    list_display = ["name", "created_at", "updated_at"]
    readonly_fields = ["created_at", "updated_at", "system_id", "seed_commands_list"]
    change_form_template = "admin/setup/seedmanager/change_form.html"
    fields = [
        "name",
        "description",
        "seed_commands_list",
        "created_at",
        "updated_at",
        "system_id",
    ]

    def has_add_permission(self, request):
        """Only allow adding if no instance exists"""
        return not SeedManager.objects.exists()

    def has_delete_permission(self, request, obj=None):
        """Prevent deletion of the seed manager"""
        return False

    def seed_commands_list(self, obj):
        """Display list of all discovered seed commands"""
        commands = discover_seed_commands()

        if not commands:
            return "No seed commands found."

        html = "<div style='max-height: 400px; overflow-y: auto;'>"
        html += "<table style='width: 100%; border-collapse: collapse;'>"
        html += "<thead><tr style='background-color: #f5f5f5;'>"
        html += "<th style='padding: 8px; text-align: left; border: 1px solid #ddd;'>Command</th>"
        html += "<th style='padding: 8px; text-align: left; border: 1px solid #ddd;'>App</th>"
        html += "<th style='padding: 8px; text-align: left; border: 1px solid #ddd;'>Description</th>"
        html += "</tr></thead><tbody>"

        for cmd in commands:
            html += "<tr>"
            html += f"<td style='padding: 8px; border: 1px solid #ddd;'><code>{cmd['command']}</code></td>"
            html += (
                f"<td style='padding: 8px; border: 1px solid #ddd;'>{cmd['app']}</td>"
            )
            html += f"<td style='padding: 8px; border: 1px solid #ddd;'>{cmd['description']}</td>"
            html += "</tr>"

        html += "</tbody></table></div>"
        return format_html(html)

    seed_commands_list.short_description = "Available Seed Commands"

    actions = ["run_all_seeds"]

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "<path:object_id>/run-selected/",
                self.admin_site.admin_view(self.run_selected_seeds_view),
                name="setup_seedmanager_run_selected",
            ),
        ]
        return custom_urls + urls

    def render_change_form(self, request, context, add=False, change=False, form_url="", obj=None):
        # Provide discovered commands to template for checkbox UI.
        context["seed_commands"] = discover_seed_commands()
        return super().render_change_form(
            request, context, add=add, change=change, form_url=form_url, obj=obj
        )

    def run_selected_seeds_view(self, request: HttpRequest, object_id: str, *args, **kwargs):
        """
        Custom admin endpoint to run only selected seed commands.
        """
        obj = self.get_object(request, object_id)
        if obj is None:
            self.message_user(request, "Seed Manager not found.", level=messages.ERROR)
            return HttpResponseRedirect("../../")

        if request.method != "POST":
            # Should only be used via the change form POST.
            return HttpResponseRedirect("../")

        selected = request.POST.getlist("seed_commands")
        all_cmds = {c["command"]: c for c in discover_seed_commands()}
        valid_selected = [name for name in selected if name in all_cmds]

        if not valid_selected:
            self.message_user(
                request,
                "No seed commands selected.",
                level=messages.WARNING,
            )
            return HttpResponseRedirect("../")

        schema_name = get_request_tenant_schema_name(request)

        from django_tenants.utils import schema_context

        results = {}
        with schema_context(schema_name):
            for command_name in valid_selected:
                info = all_cmds[command_name]
                success, output = run_seed_command(command_name, info["app"])
                results[command_name] = {
                    "success": success,
                    "output": output,
                    "app": info["app"],
                    "description": info.get("description", ""),
                }

        success_count = sum(1 for r in results.values() if r["success"])
        failure_count = len(results) - success_count

        message_parts = [
            f"Schema: {schema_name}",
            f"Ran {len(valid_selected)} selected seed command(s). "
            f"Successful: {success_count} · Failed: {failure_count}",
            "",
            "— Command log —",
        ]
        for command_name, result in results.items():
            status = "OK" if result["success"] else "FAILED"
            message_parts.append(
                f"[{status}] {command_name} ({result['app']})"
            )
            formatted = _format_seed_command_output(str(result.get("output", "")))
            if formatted:
                message_parts.append(formatted)
            else:
                message_parts.append("   (no output)")

        full_message = "\n".join(message_parts)
        if failure_count > 0:
            self.message_user(
                request, _admin_multiline_message(full_message), level=messages.WARNING
            )
        else:
            self.message_user(
                request, _admin_multiline_message(full_message), level=messages.SUCCESS
            )

        return HttpResponseRedirect("../")

    def get_actions(self, request):
        """Get available actions"""
        actions = super().get_actions(request)
        # Remove default delete action
        if "delete_selected" in actions:
            del actions["delete_selected"]
        return actions

    @admin.action(description="🌱 Run All Seed Commands")
    def run_all_seeds(self, request, queryset):
        """
        Run all discovered seed commands.
        This action will execute all seed commands found in the project.
        """
        commands = discover_seed_commands()

        if not commands:
            self.message_user(
                request,
                "No seed commands found in the project.",
                level=messages.WARNING,
            )
            return

        schema_name = get_request_tenant_schema_name(request)

        results = run_all_seed_commands(schema_name=schema_name)

        success_count = sum(1 for r in results.values() if r["success"])
        failure_count = len(results) - success_count

        message_parts = [
            f"Schema: {schema_name}",
            f"Ran {len(commands)} seed command(s). "
            f"Successful: {success_count} · Failed: {failure_count}",
            "",
            "— Command log (OK: last 6 lines; FAILED: up to 35 lines) —",
        ]

        for command_name, result in results.items():
            ok = result["success"]
            status = "OK" if ok else "FAILED"
            message_parts.append(f"[{status}] {command_name} ({result['app']})")
            out = str(result.get("output", ""))
            if ok:
                formatted = _format_seed_command_output(
                    out, max_lines=6, max_chars=1200
                )
            else:
                formatted = _format_seed_command_output(
                    out, max_lines=35, max_chars=6000
                )
            if formatted:
                message_parts.append(formatted)
            elif not ok:
                message_parts.append("   (no error output captured)")
            else:
                message_parts.append("   (no output)")

        full_message = "\n".join(message_parts)

        if failure_count > 0:
            self.message_user(
                request, _admin_multiline_message(full_message), level=messages.WARNING
            )
        else:
            self.message_user(
                request, _admin_multiline_message(full_message), level=messages.SUCCESS
            )

    run_all_seeds.short_description = "🌱 Run All Seed Commands"
