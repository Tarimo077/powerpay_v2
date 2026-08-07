from celery import shared_task
from django.utils import timezone

from .models import ReportRun, ReportSchedule
from .services import build_report_context, send_report_email


def run_schedule(schedule, source=ReportRun.SOURCE_SCHEDULED):
    """Build, render and email a report for one schedule. Returns the ReportRun."""
    now = timezone.now()
    end = now
    start = now - schedule.period_delta()

    context = build_report_context(
        user=schedule.user,
        start=start,
        end=end,
        sections=schedule.sections,
        organization=schedule.organization,
        allow_long=True,
    )

    run = ReportRun(
        schedule=schedule,
        user=schedule.user,
        source=source,
        period_start=start,
        period_end=end,
        recipients=schedule.recipients,
        sections_snapshot=schedule.sections,
    )

    try:
        send_report_email(context, schedule.recipient_list, schedule=schedule)
        run.status = ReportRun.STATUS_SUCCESS
    except Exception as exc:  # noqa: BLE001 - report the failure in history
        run.status = ReportRun.STATUS_FAILED
        run.error = str(exc)

    run.completed_at = timezone.now()
    run.save()
    schedule.advance(from_time=now)
    return run


@shared_task
def generate_manual_report(run_id):
    """Render a queued manual report in the background and email it."""
    try:
        run = ReportRun.objects.select_related("user").get(pk=run_id)
    except ReportRun.DoesNotExist:
        return False

    try:
        context = build_report_context(
            user=run.user,
            start=run.period_start,
            end=run.period_end,
            sections=run.sections_snapshot or None,
            allow_long=True,
        )
        recipients = [e.strip() for e in (run.recipients or "").split(",") if e.strip()]
        if not recipients and run.user.email:
            recipients = [run.user.email]

        if not recipients:
            raise ValueError("No email address to send the report to.")

        send_report_email(context, recipients)
        run.status = ReportRun.STATUS_SUCCESS
        run.error = ""
    except Exception as exc:  # noqa: BLE001 - report the failure in history
        run.status = ReportRun.STATUS_FAILED
        run.error = str(exc)

    run.completed_at = timezone.now()
    run.save(update_fields=["status", "error", "completed_at"])
    return run.status == ReportRun.STATUS_SUCCESS


@shared_task
def run_due_report_schedules():
    """Celery beat entry point - emails every schedule that is due."""
    now = timezone.now()

    schedules = (
        ReportSchedule.objects
        .select_related("user", "organization")
        .filter(active=True, next_run_at__lte=now)
    )

    processed = 0
    for schedule in schedules:
        run_schedule(schedule)
        processed += 1

    return processed


@shared_task
def run_report_schedule_now(schedule_id):
    try:
        schedule = ReportSchedule.objects.select_related("user", "organization").get(
            pk=schedule_id
        )
    except ReportSchedule.DoesNotExist:
        return False

    run_schedule(schedule, source=ReportRun.SOURCE_MANUAL)
    return True
