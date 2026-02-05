from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q

from .models import Organization
from .forms import OrganizationForm


def is_admin_user(user):
    return user.is_superuser or getattr(user, "role", None) == "admin"


@login_required
def organizations_page(request):
    if not is_admin_user(request.user):
        messages.error(request, "You are not allowed to view organizations.")
        return redirect("index")

    q = request.GET.get("q", "")

    organizations = Organization.objects.all().order_by("name")

    if q:
        organizations = organizations.filter(
            Q(name__icontains=q) |
            Q(phone_number__icontains=q) |
            Q(email__icontains=q)
        )

    paginator = Paginator(organizations, 10)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "page_obj": page_obj,
        "search_query": q,
        "is_admin": True,
    }

    # ✅ HTMX partial response
    if request.headers.get("HX-Request"):
        return render(request, "partials/organizations_table.html", context)

    return render(request, "organizations/organizations_list.html", context)


@login_required
def organization_create(request):
    if not is_admin_user(request.user):
        messages.error(request, "You are not allowed to add organizations.")
        return redirect("organizations_page")

    if request.method == "POST":
        form = OrganizationForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, "Organization created successfully.")
            return redirect("organizations_page")
    else:
        form = OrganizationForm()

    return render(request, "organizations/organization_form.html", {"form": form, "title": "Add Organization"})


@login_required
def organization_update(request, pk):
    if not is_admin_user(request.user):
        messages.error(request, "You are not allowed to edit organizations.")
        return redirect("organizations_page")

    org = get_object_or_404(Organization, pk=pk)

    if request.method == "POST":
        form = OrganizationForm(request.POST, request.FILES, instance=org)
        if form.is_valid():
            form.save()
            messages.success(request, "Organization updated successfully.")
            return redirect("organizations_page")
    else:
        form = OrganizationForm(instance=org)

    return render(request, "organizations/organization_form.html", {"form": form, "title": "Edit Organization"})


@login_required
def organization_delete(request, pk):
    if not is_admin_user(request.user):
        return JsonResponse({"success": False}, status=403)

    org = get_object_or_404(Organization, pk=pk)
    org.delete()

    return JsonResponse({"success": True})
