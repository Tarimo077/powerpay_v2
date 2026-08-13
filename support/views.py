from django.shortcuts import render, redirect, get_object_or_404
from functools import wraps
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Count, Max, Case, When, IntegerField
from django.db.models.functions import Coalesce
from .models import Ticket, TicketMessage
from .forms import TicketForm
from django.core.paginator import Paginator
from notifications.utils import notify
from accounts.models import User
from django.contrib import messages


# ---------------------------------------------------------------- permissions
def is_admin(user):
    return bool(
        user
        and user.is_authenticated
        and (
            user.is_superuser
            or getattr(user, "role", None) in ["superadmin"]
        )
    )


def get_support_admins():
    """Platform superadmins who should be alerted about support activity."""
    return User.objects.filter(
        Q(is_superuser=True) | Q(role="superadmin"),
        is_active=True,
    ).distinct()


def notify_support_admins(ticket, title, message, type="info"):
    for admin in get_support_admins():
        if admin.id == ticket.user_id:
            continue
        notify(user=admin, title=title, message=message, type=type)


def support_admin_required(view_func):
    @login_required
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if is_admin(request.user):
            return view_func(request, *args, **kwargs)

        messages.error(request, "You do not have permission to manage support tickets.")
        return redirect("support:support_ticket_list")

    return _wrapped_view


# ---------------------------------------------------------------- helpers
def _ticket_stats(qs):
    agg = qs.aggregate(
        total=Count("id"),
        open=Count(Case(When(status="open", then=1), output_field=IntegerField())),
        in_progress=Count(Case(When(status="in_progress", then=1), output_field=IntegerField())),
        closed=Count(Case(When(status="closed", then=1), output_field=IntegerField())),
    )
    return agg


def _apply_filters(qs, request):
    q = (request.GET.get("q") or "").strip()
    status = request.GET.get("status") or ""
    priority = request.GET.get("priority") or ""

    if q:
        qs = qs.filter(
            Q(description__icontains=q)
            | Q(subject__icontains=q)
            | Q(id__icontains=q)
            | Q(user__email__icontains=q)
            | Q(user__username__icontains=q)
        )
    if status:
        qs = qs.filter(status=status)
    if priority:
        qs = qs.filter(priority=priority)

    return qs, q, status, priority


def _paginate(request, qs, default_per_page):
    try:
        per_page = int(request.GET.get("per_page", default_per_page))
    except (TypeError, ValueError):
        per_page = default_per_page
    per_page = per_page if per_page in (5, 10, 20, 50) else default_per_page
    return Paginator(qs, per_page).get_page(request.GET.get("page", 1)), per_page


# ---------------------------------------------------------------- user views
@login_required
def create_ticket(request):
    if request.method == "POST":
        form = TicketForm(request.POST)
        if form.is_valid():
            ticket = form.save(commit=False)
            ticket.user = request.user
            ticket.save()

            notify_support_admins(
                ticket,
                title=f"New Support Ticket #{ticket.id}",
                message=(
                    f"{request.user.email} opened a "
                    f"{ticket.get_priority_display().lower()} priority ticket: "
                    f"{ticket.get_subject_display()}"
                ),
                type="warning" if ticket.priority == "high" else "info",
            )

            messages.success(request, f"Ticket #{ticket.id} submitted. Our team will be in touch.")
            return redirect("support:ticket_detail", ticket_id=ticket.id)
    else:
        form = TicketForm()

    return render(request, "support/create_ticket.html", {"form": form})


@login_required
def ticket_list(request):
    base_qs = Ticket.objects.filter(user=request.user)
    stats = _ticket_stats(base_qs)

    qs, q, status, priority = _apply_filters(base_qs, request)
    qs = qs.annotate(
        last_activity=Coalesce(Max("messages__created_at"), "updated_at")
    ).order_by("-created_at")

    tickets, per_page = _paginate(request, qs, 5)

    return render(request, "support/ticket_list.html", {
        "tickets": tickets,
        "per_page": per_page,
        "stats": stats,
        "q": q,
        "status": status,
        "priority": priority,
        "status_choices": Ticket.STATUS_CHOICES,
        "priority_choices": Ticket.PRIORITY_CHOICES,
    })


@login_required
def ticket_detail(request, ticket_id):
    ticket = get_object_or_404(
        Ticket.objects.select_related("user"), id=ticket_id, user=request.user
    )

    if request.method == "POST" and ticket.status != "closed":
        reply = request.POST.get("reply")

        if reply and reply.strip():
            TicketMessage.objects.create(
                ticket=ticket,
                sender=request.user,
                message=reply.strip(),
            )
            ticket.save(update_fields=["updated_at"])

            notify_support_admins(
                ticket,
                title=f"New Message | Ticket #{ticket.id}",
                message=f"{request.user.email} responded to a support ticket.",
                type="warning",
            )
            messages.success(request, "Message sent.")

        return redirect("support:ticket_detail", ticket_id=ticket_id)

    return render(request, "support/ticket_detail.html", {
        "ticket": ticket,
        "ticket_messages": ticket.messages.select_related("sender").all(),
    })


# ---------------------------------------------------------------- admin views
@support_admin_required
def admin_ticket_list(request):
    base_qs = Ticket.objects.all()
    stats = _ticket_stats(base_qs)

    qs, q, status, priority = _apply_filters(base_qs, request)

    sort = request.GET.get("sort") or "-created_at"
    if sort not in ("created_at", "-created_at"):
        sort = "-created_at"

    qs = qs.select_related("user").annotate(
        last_activity=Coalesce(Max("messages__created_at"), "updated_at")
    ).order_by(sort)

    tickets, per_page = _paginate(request, qs, 10)

    return render(request, "support/admin_ticket_list.html", {
        "tickets": tickets,
        "per_page": per_page,
        "stats": stats,
        "q": q,
        "status": status,
        "priority": priority,
        "sort": sort,
        "status_choices": Ticket.STATUS_CHOICES,
        "priority_choices": Ticket.PRIORITY_CHOICES,
    })


@support_admin_required
def admin_ticket_detail(request, ticket_id):
    ticket = get_object_or_404(Ticket.objects.select_related("user"), id=ticket_id)

    if request.method == "POST":
        reply = request.POST.get("reply")
        status = request.POST.get("status")
        priority = request.POST.get("priority")

        valid_status = dict(Ticket.STATUS_CHOICES)
        valid_priority = dict(Ticket.PRIORITY_CHOICES)

        if status in valid_status and status != ticket.status:
            ticket.status = status
            ticket.save(update_fields=["status", "updated_at"])

            notify(
                user=ticket.user,
                title=f"Ticket #{ticket.id} Status Updated",
                message=f"Your support ticket status has changed to: {ticket.get_status_display()}",
                type="info",
            )

        if priority in valid_priority and priority != ticket.priority:
            ticket.priority = priority
            ticket.save(update_fields=["priority", "updated_at"])

        if reply and reply.strip():
            TicketMessage.objects.create(
                ticket=ticket,
                sender=request.user,
                message=reply.strip(),
            )

            notify(
                user=ticket.user,
                title=f"New Message | Ticket #{ticket.id}",
                message="The support team has responded to your ticket.",
                type="success",
            )

        messages.success(request, f"Ticket #{ticket.id} updated.")
        return redirect("support:admin_ticket_detail", ticket_id=ticket_id)

    return render(request, "support/admin_ticket_detail.html", {
        "ticket": ticket,
        "ticket_messages": ticket.messages.select_related("sender").all(),
    })
