from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from .forms import ReportRequestForm, ReportScheduleForm
from .models import ReportRun, ReportSchedule
from .services import (
    build_report_context,
    period_needs_background,
    render_report_pdf,
    report_filename,
    resolve_period,
)
from .tasks import generate_manual_report, run_report_schedule_now


def _queue_report(request, start, end, sections):
    """Create a queued run, hand it to the worker and flash a confirmation."""
    run = ReportRun.objects.create(
        user=request.user,
        source=ReportRun.SOURCE_MANUAL,
        period_start=start,
        period_end=end,
        recipients=request.user.email or "",
        sections_snapshot=sections,
        status=ReportRun.STATUS_QUEUED,
    )
    generate_manual_report.delay(run.id)
    messages.success(
        request,
        "This report covers a long period, so it is being prepared in the "
        f"background and will be emailed to {request.user.email or 'you'} "
        "when it is ready.",
    )
    return run


def _context_from_request(request):
    """
    Build a report context from GET parameters.

    Returns (form, context, too_long). Long periods are never built here - the
    caller queues them for the background worker instead.
    """
    has_params = bool(request.GET.get("period"))
    form = ReportRequestForm(request.GET or None) if has_params else ReportRequestForm()

    if has_params and form.is_valid():
        start, end = resolve_period(
            form.cleaned_data["period"],
            form.cleaned_data.get("start_date"),
            form.cleaned_data.get("end_date"),
        )
        if period_needs_background(start, end):
            return form, None, True

        context = build_report_context(request.user, start, end, form.sections())
        return form, context, False

    return form, None, False


@login_required
def report_center(request):
    form, report, too_long = _context_from_request(request)

    if too_long:
        start, end = resolve_period(
            form.cleaned_data["period"],
            form.cleaned_data.get("start_date"),
            form.cleaned_data.get("end_date"),
        )
        _queue_report(request, start, end, form.sections())
        return redirect("reports:run_history")

    return render(
        request,
        "reports/report_center.html",
        {
            "form": form,
            "report": report,
            "too_long": too_long,
            "query_string": request.GET.urlencode(),
            "schedule_count": ReportSchedule.objects.filter(user=request.user).count(),
        },
    )


@login_required
def report_download(request):
    form = ReportRequestForm(request.GET or None)

    if not form.is_valid():
        messages.error(request, "Choose a valid period before downloading the report.")
        return redirect("reports:report_center")

    start, end = resolve_period(
        form.cleaned_data["period"],
        form.cleaned_data.get("start_date"),
        form.cleaned_data.get("end_date"),
    )
    # Long periods can contain tens of thousands of rows - render them in the
    # background and email the PDF instead of timing out the request.
    if period_needs_background(start, end):
        _queue_report(request, start, end, form.sections())
        return redirect("reports:run_history")

    context = build_report_context(request.user, start, end, form.sections())
    pdf = render_report_pdf(context)

    if not pdf:
        messages.error(request, "The report PDF could not be generated. Please try again.")
        return redirect("reports:report_center")

    ReportRun.objects.create(
        user=request.user,
        source=ReportRun.SOURCE_MANUAL,
        period_start=start,
        period_end=end,
        status=ReportRun.STATUS_SUCCESS,
    )

    response = HttpResponse(pdf, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{report_filename(context)}"'
    return response


# ==========================================================
# SCHEDULES
# ==========================================================
@login_required
def schedule_list(request):
    schedules = ReportSchedule.objects.filter(user=request.user)

    return render(
        request,
        "reports/schedule_list.html",
        {"schedules": schedules},
    )


@login_required
def schedule_create(request):
    form = ReportScheduleForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        schedule = form.save(commit=False)
        schedule.user = request.user
        schedule.organization = request.user.organization
        schedule.save()
        messages.success(request, f"Schedule '{schedule.name}' was created.")
        return redirect("reports:schedule_list")

    return render(
        request,
        "reports/schedule_form.html",
        {"form": form, "mode": "create"},
    )


@login_required
def schedule_edit(request, pk):
    schedule = get_object_or_404(ReportSchedule, pk=pk, user=request.user)
    form = ReportScheduleForm(request.POST or None, instance=schedule)

    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, f"Schedule '{schedule.name}' was updated.")
        return redirect("reports:schedule_list")

    return render(
        request,
        "reports/schedule_form.html",
        {"form": form, "mode": "edit", "schedule": schedule},
    )


@login_required
def schedule_delete(request, pk):
    schedule = get_object_or_404(ReportSchedule, pk=pk, user=request.user)

    if request.method == "POST":
        name = schedule.name
        schedule.delete()
        messages.success(request, f"Schedule '{name}' was deleted.")
        return redirect("reports:schedule_list")

    return render(
        request,
        "reports/schedule_confirm_delete.html",
        {"schedule": schedule},
    )


@login_required
def schedule_toggle(request, pk):
    schedule = get_object_or_404(ReportSchedule, pk=pk, user=request.user)
    schedule.active = not schedule.active
    schedule.save(update_fields=["active", "updated_at"])

    messages.success(
        request,
        f"Schedule '{schedule.name}' is now {'active' if schedule.active else 'paused'}.",
    )
    return redirect("reports:schedule_list")


@login_required
def schedule_run_now(request, pk):
    schedule = get_object_or_404(ReportSchedule, pk=pk, user=request.user)
    run_report_schedule_now.delay(schedule.id)

    messages.success(
        request,
        f"'{schedule.name}' is being generated in the background and will be "
        f"emailed to {schedule.recipients}.",
    )
    return redirect("reports:schedule_list")


@login_required
def run_history(request):
    runs = (
        ReportRun.objects
        .filter(user=request.user)
        .select_related("schedule")
    )

    page = Paginator(runs, 25).get_page(request.GET.get("page"))

    return render(request, "reports/run_history.html", {"page_obj": page})
