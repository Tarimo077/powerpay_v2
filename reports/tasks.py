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
    )

    run = ReportRun(
        schedule=schedule,
        user=schedule.user,
        source=source,
        period_start=start,
        period_end=end,
        recipients=schedule.recipients,
    )

    try:
        send_report_email(context, schedule.recipient_list, schedule=schedule)
        run.status = ReportRun.STATUS_SUCCESS
    except Exception as exc:  # noqa: BLE001 - report the failure in history
        run.status = ReportRun.STATUS_FAILED
        run.error = str(exc)

    run.save()
    schedule.advance(from_time=now)
    return run


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
