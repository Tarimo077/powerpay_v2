from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from .models import Ticket, TicketMessage
from .forms import TicketForm
from django.core.paginator import Paginator
from notifications.utils import notify
from accounts.models import User

# Admin views
def is_admin(user):
    return user.is_staff

@login_required
def create_ticket(request):
    if request.method == 'POST':
        form = TicketForm(request.POST)
        if form.is_valid():
            ticket = form.save(commit=False)
            ticket.user = request.user
            ticket.save()
            return redirect('support_ticket_list')
    else:
        form = TicketForm()
    return render(request, 'support/create_ticket.html', {'form': form})

@login_required
def ticket_list(request):
    per_page = int(request.GET.get("per_page", 5))  # default 6 per page
    page_number = request.GET.get("page", 1)

    tickets_qs = Ticket.objects.filter(user=request.user).order_by('-created_at')

    paginator = Paginator(tickets_qs, per_page)
    tickets = paginator.get_page(page_number)

    return render(request, "support/ticket_list.html", {
        "tickets": tickets,
        "per_page": per_page,
    })


@login_required
def ticket_detail(request, ticket_id):
    ticket = get_object_or_404(Ticket, id=ticket_id, user=request.user)

    if request.method == 'POST' and ticket.status != 'closed':
        reply = request.POST.get("reply")

        if reply and reply.strip():
            TicketMessage.objects.create(
                ticket=ticket,
                sender=request.user,
                message=reply
            )

            # Send notification to all admins (or specific staff)
            admins = User.objects.filter(is_staff=True)
            for admin in admins:
                notify(
                    user=admin,
                    title=f"New Message | Ticket #{ticket.id}",
                    message=f"{request.user.email} responded to a support ticket.",
                    type="warning"
                )

        return redirect('ticket_detail', ticket_id=ticket_id)

    return render(request, "support/ticket_detail.html", {
        "ticket": ticket
    })


@user_passes_test(is_admin)
def admin_ticket_list(request):
    tickets = Ticket.objects.all().order_by("-created_at")

    paginator = Paginator(tickets, 10)
    page = request.GET.get("page")
    tickets_page = paginator.get_page(page)

    return render(request, "support/admin_ticket_list.html", {"tickets_page": tickets_page})


@user_passes_test(is_admin)
def admin_ticket_list(request):
    per_page = int(request.GET.get("per_page", 10))
    page = request.GET.get("page", 1)

    tickets_qs = Ticket.objects.all().order_by('-created_at')
    paginator = Paginator(tickets_qs, per_page)
    tickets = paginator.get_page(page)

    return render(request, "support/admin_ticket_list.html", {
        "tickets": tickets,
        "per_page": per_page,
    })


@user_passes_test(is_admin)
def admin_ticket_detail(request, ticket_id):
    ticket = get_object_or_404(Ticket, id=ticket_id)
    
    if request.method == "POST":
        reply = request.POST.get("reply")
        status = request.POST.get("status")

        # Handle status update
        if status and status != ticket.status:
            ticket.status = status
            ticket.save()

            notify(
                user=ticket.user,
                title=f"Ticket #{ticket.id} Status Updated",
                message=f"Your support ticket status has changed to: {ticket.get_status_display()}",
                type="info"
            )

        # Handle admin reply
        if reply and reply.strip():
            TicketMessage.objects.create(
                ticket=ticket,
                sender=request.user,
                message=reply
            )

            notify(
                user=ticket.user,
                title=f"New Message | Ticket #{ticket.id}",
                message=f"The support team has responded to your ticket.",
                type="success"
            )

        return redirect("admin_ticket_detail", ticket_id=ticket_id)

    messages_page = ticket.messages.all()
    return render(request, "support/admin_ticket_detail.html", {
        "ticket": ticket,
        "messages_page": messages_page
    })
