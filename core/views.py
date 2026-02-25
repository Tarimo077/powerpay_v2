from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from devices.models import DeviceInfo, DeviceData
from organizations.models import Organization
from devices.services.energy import (
    kwh_today_for_devices,
    kwh_this_month_for_devices,
)
from django.db.models import Sum
from datetime import datetime, timedelta
from transactions.models import Transaction  
import csv
from django.http import HttpResponse, JsonResponse
from openpyxl import Workbook
from .forms import ExportForm
from inventory.models import InventoryItem, Warehouse
from customers.models import Customer
from sales.models import Sale
from support.models import Ticket
from accounts.models import User
from django.db.models import Model
from django.utils.timezone import is_aware
import pandas as pd
from django.views.decorators.http import require_POST
from django.db import transaction
from django.utils.dateparse import parse_date
from .forms import CustomerSalesImportForm


@login_required
def index(request):
    user = request.user
    is_superadmin = user.is_superuser or getattr(user, "role", "") == "admin"

    context = {"is_superadmin": is_superadmin}

    # ---------------- Organizations ----------------
    if is_superadmin:
        organizations = Organization.objects.all()
    else:
        organizations = [user.organization]

    # ---------------- Devices ----------------
    if is_superadmin:
        devices = DeviceInfo.objects.all()
    else:
        devices = DeviceInfo.objects.filter(organization=user.organization)
        

    # ---------------- Transactions ----------------
    if is_superadmin:
        transactions = Transaction.objects.all()
    else:
        transactions = Transaction.objects.filter(org=user.organization)

    # ---------------- Summary Cards ----------------
    context.update({
        "org_count": len(organizations),
        "device_count": devices.count(),
        "kwh_today": kwh_today_for_devices(devices),
        "kwh_month": kwh_this_month_for_devices(devices),
        "total_money": transactions.aggregate(total=Sum("amount"))["total"] or 0,
        "total_transactions": transactions.count(),
    })

    # ---------------- Device Status ----------------
    context["device_status_counts"] = {
        "ON": devices.filter(active=True).count(),
        "OFF": devices.filter(active=False).count(),
    }

    # ---------------- kWh Line Chart ----------------
    today = datetime.today().date()
    days = [today - timedelta(days=i) for i in reversed(range(7))]
    context["line_chart_labels"] = [d.strftime("%a %d") for d in days]

    line_chart_data = {}
    for device in devices:
        device_kwh = []
        for day in days:
            total = DeviceData.objects.filter(
                deviceid=device.deviceid,
                time__date=day
            ).aggregate(sum_kwh=Sum("kwh"))["sum_kwh"] or 0
            device_kwh.append(round(total, 2))
        if any(v > 0 for v in device_kwh):
            line_chart_data[device.deviceid] = device_kwh
    context["line_chart_data"] = line_chart_data

    # ---------------- Money by Org (superusers only) ----------------
    if is_superadmin:
        money_by_org = Transaction.objects.values('org__name').annotate(total=Sum('amount'))
        context['money_by_org_labels'] = [x['org__name'] for x in money_by_org]
        context['money_by_org_data'] = [float(x['total']) for x in money_by_org]

        # Money over last 7 days per org
        money_line_data = {}
        for org in organizations:
            daily_totals = []
            for day in days:
                total = Transaction.objects.filter(
                    org=org,
                    time__date=day
                ).aggregate(total=Sum('amount'))['total'] or 0
                daily_totals.append(float(total))
            money_line_data[org.name] = daily_totals
        context['money_line_data'] = money_line_data
        context['money_line_labels'] = [d.strftime("%a %d") for d in days]

    return render(request, "core/index.html", context)


def export_csv(queryset, is_superadmin, model, filename):
    response = HttpResponse(content_type="text/csv")
    filename = filename + ".csv"
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response.set_cookie('download_started', 'true', max_age=60)
    writer = csv.writer(response)

    # 🔥 If aggregated (DeviceData)
    if model == "devicedata":
        fields = ["deviceid", "total_kwh"]
        writer.writerow(fields)

        for row in queryset:
            writer.writerow([row["deviceid"], row["total_kwh"]])

        return response

    # 🔥 Normal model exports
    fields = [f.name for f in queryset.model._meta.fields]

    # Remove time for DeviceInfo
    if model == "deviceinfo" and "time" in fields:
        fields.remove("time")

    # Hide organization if not superadmin
    if not is_superadmin and "organization" in fields:
        fields.remove("organization")

    if not is_superadmin and "org" in fields:
        fields.remove("org")

    if not is_superadmin and "id" in fields:
        fields.remove("id")

    writer.writerow(fields)

    for obj in queryset:
        row = []
        for field in fields:
            value = getattr(obj, field)

            if isinstance(value, Model):
                value = str(value)

            # 🔥 Remove timezone from datetime
            if hasattr(value, "tzinfo") and value.tzinfo is not None:
                value = value.replace(tzinfo=None)

            row.append(value)

        writer.writerow(row)

    return response


def export_excel(queryset, is_superadmin, model, filename):

    wb = Workbook()
    ws = wb.active

    # 🔥 Aggregated case (DeviceData)
    if model == "devicedata":
        fields = ["deviceid", "total_kwh"]
        ws.append(fields)

        for row in queryset:
            ws.append([row["deviceid"], row["total_kwh"]])

        response = HttpResponse(
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        filename = filename + ".xlsx"
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        wb.save(response)
        return response

    # Normal model export
    fields = [f.name for f in queryset.model._meta.fields]

    if model == "deviceinfo" and "time" in fields:
        fields.remove("time")

    if not is_superadmin and "organization" in fields:
        fields.remove("organization")

    if not is_superadmin and "org" in fields:
        fields.remove("org")

    ws.append(fields)

    for obj in queryset:
        row = []
        for field in fields:
            value = getattr(obj, field)

            # 🔥 Convert ForeignKey objects safely
            if isinstance(value, Model):
                value = str(value)

            # 🔥 Remove timezone from datetime
            if hasattr(value, "tzinfo") and value.tzinfo is not None:
                value = value.replace(tzinfo=None)

            row.append(value)

        ws.append(row)

    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    filename = filename + ".xlsx"
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response.set_cookie('download_started', 'true', max_age=60)
    wb.save(response)
    return response

@login_required
def export_data_view(request):
    form = ExportForm(request.GET or None)

    if not form.is_valid():
        return render(request, "core/export_data.html", {"form": form})

    model = form.cleaned_data["model"]
    devices = form.cleaned_data["devices"]
    start = form.cleaned_data["start_date"]
    end = form.cleaned_data["end_date"]
    export_format = form.cleaned_data["format"]

    user = request.user
    is_superadmin = user.role == "superadmin"

    queryset = None

    # ---------------------------
    # DEVICE INFO
    # ---------------------------
    if model == "deviceinfo":
        queryset = DeviceInfo.objects.all()

        if not is_superadmin:
            queryset = queryset.filter(organization=user.organization)

        if devices:
            queryset = queryset.filter(id__in=devices.values_list("id", flat=True))

    # ---------------------------
    # DEVICE DATA
    # ---------------------------
    elif model == "devicedata":
        queryset = DeviceData.objects.all()

        # Restrict to user org
        if not is_superadmin:
            user_devices = DeviceInfo.objects.filter(
                organization=user.organization
            ).values_list("deviceid", flat=True)

            queryset = queryset.filter(deviceid__in=user_devices)

        # Filter selected devices
        if devices:
            selected_ids = devices.values_list("deviceid", flat=True)
            queryset = queryset.filter(deviceid__in=selected_ids)

        # Time filter
        if start and end:
            queryset = queryset.filter(time__range=(start, end))

        # 🔥 AGGREGATE kWh per device
        queryset = (
            queryset
            .values("deviceid")
            .annotate(total_kwh=Sum("kwh"))
            .order_by("deviceid")
        )

    # ---------------------------
    # CUSTOMERS
    # ---------------------------
    elif model == "customers":
        queryset = Customer.objects.all()

        if not is_superadmin:
            queryset = queryset.filter(organization=user.organization)

        if start and end:
            queryset = queryset.filter(date__range=(start, end))

    # ---------------------------
    # SALES
    # ---------------------------
    elif model == "sales":
        queryset = Sale.objects.all()

        if not is_superadmin:
            queryset = queryset.filter(organization=user.organization)

        if start and end:
            queryset = queryset.filter(date__range=(start, end))

    # ---------------------------
    # TRANSACTIONS
    # ---------------------------
    elif model == "transactions":
        queryset = Transaction.objects.all()

        if not is_superadmin:
            queryset = queryset.filter(org=user.organization)

        if start and end:
            queryset = queryset.filter(time__range=(start, end))

    # ---------------------------
    # SUPERADMIN ONLY MODELS
    # ---------------------------
    elif model == "inventory":
        if not is_superadmin:
            return HttpResponse("Unauthorized", status=403)
        queryset = InventoryItem.objects.all()

        if start and end:
            queryset = queryset.filter(date_added__range=(start, end))

    elif model == "warehouses":
        if not is_superadmin:
            return HttpResponse("Unauthorized", status=403)
        queryset = Warehouse.objects.all()

    elif model == "organizations":
        if not is_superadmin:
            return HttpResponse("Unauthorized", status=403)
        queryset = Organization.objects.all()

    elif model == "support":
        if not is_superadmin:
            return HttpResponse("Unauthorized", status=403)
        queryset = Ticket.objects.all()

    elif model == "users":
        if not is_superadmin:
            return HttpResponse("Unauthorized", status=403)
        queryset = User.objects.all()

    # ---------------------------
    # EXPORT
    # ---------------------------
    if start and end:
        filename = model+"_"+str(start)+"_"+"to"+"_"+str(end)
    else:
        filename = model
    if export_format == "csv":
        return export_csv(queryset, is_superadmin, model, filename)

    return export_excel(queryset, is_superadmin, model, filename)

@login_required
def export_count_view(request):
    model = request.GET.get("model")
    device_ids = request.GET.getlist("devices")
    start = request.GET.get("start_date")
    end = request.GET.get("end_date")

    user = request.user
    is_superadmin = user.role == "superadmin"

    queryset = None
    count = 0

    # ---------------------------
    # DEVICE INFO
    # ---------------------------
    if model == "deviceinfo":
        queryset = DeviceInfo.objects.all()
        if not is_superadmin:
            queryset = queryset.filter(organization=user.organization)
        
        if device_ids:
            # Match the data view: filter by the primary key (id)
            queryset = queryset.filter(id__in=device_ids)
        
        count = queryset.count()

    # ---------------------------
    # DEVICE DATA (AGGREGATED)
    # ---------------------------
    elif model == "devicedata":
        queryset = DeviceData.objects.all()

        # 1. Restrict to user's org
        if not is_superadmin:
            user_device_ids = DeviceInfo.objects.filter(
                organization=user.organization
            ).values_list("deviceid", flat=True)
            queryset = queryset.filter(deviceid__in=user_device_ids)

        # 2. Filter selected devices
        if device_ids:
            # We fetch the actual deviceid strings/ints from the DeviceInfo table
            # to ensure the data types match what DeviceData expects.
            selected_device_vals = DeviceInfo.objects.filter(
                id__in=device_ids
            ).values_list("deviceid", flat=True)
            
            queryset = queryset.filter(deviceid__in=selected_device_vals)

        # 3. Time filter
        if start and end and start.strip() and end.strip():
            queryset = queryset.filter(time__range=(start, end))

        # 4. CAPTURE RECORD COUNT
        count = queryset.count()

    # ---------------------------
    # CUSTOMERS
    # ---------------------------
    elif model == "customers":
        queryset = Customer.objects.all()
        if not is_superadmin:
            queryset = queryset.filter(organization=user.organization)
        if start and end:
            queryset = queryset.filter(date__range=(start, end))
        count = queryset.count()

    # ---------------------------
    # SALES
    # ---------------------------
    elif model == "sales":
        queryset = Sale.objects.all()
        if not is_superadmin:
            queryset = queryset.filter(organization=user.organization)
        if start and end:
            queryset = queryset.filter(date__range=(start, end))
        count = queryset.count()

    # ---------------------------
    # TRANSACTIONS
    # ---------------------------
    elif model == "transactions":
        queryset = Transaction.objects.all()
        if not is_superadmin:
            queryset = queryset.filter(org=user.organization)
        if start and end:
            queryset = queryset.filter(time__range=(start, end))
        count = queryset.count()

    # ---------------------------
    # SUPERADMIN ONLY MODELS
    # ---------------------------
    elif model in ["inventory", "warehouses", "organizations", "support", "users"]:
        if not is_superadmin:
            return JsonResponse({"error": "Unauthorized"}, status=403)

        if model == "inventory":
            queryset = InventoryItem.objects.all()
            if start and end:
                queryset = queryset.filter(date_added__range=(start, end))
        elif model == "warehouses":
            queryset = Warehouse.objects.all()
        elif model == "organizations":
            queryset = Organization.objects.all()
        elif model == "support":
            queryset = Ticket.objects.all()
        elif model == "users":
            queryset = User.objects.all()
        
        count = queryset.count() if queryset else 0

    return JsonResponse({"count": count})


@login_required
def customer_sales_import_page(request):
    form = CustomerSalesImportForm()
    return render(request, "core/customer_sales_import.html", {"form": form})


@login_required
@require_POST
def import_customers_sales(request):
    form = CustomerSalesImportForm(request.POST, request.FILES)

    if not form.is_valid():
        return JsonResponse({"success": False, "error": form.errors})

    file = form.cleaned_data["file"]

    try:
        if file.name.endswith(".csv"):
            df = pd.read_csv(file)
        else:
            df = pd.read_excel(file)
    except Exception as e:
        return JsonResponse({"success": False, "error": f"File read error: {str(e)}"})

    required_columns = [
        "customer_external_id",
        "name",
        "id_number",
        "phone_number",
        "country",
        "location",
        "gender",
        "household_type",
        "household_size",
        "preferred_language",
        "registration_date",
        "product_type",
        "product_name",
        "product_model",
        "product_serial_number",
        "purchase_mode",
        "sales_rep",
        "type_of_use",
    ]

    for col in required_columns:
        if col not in df.columns:
            return JsonResponse({"success": False, "error": f"Missing column: {col}"})

    user = request.user
    organization = user.organization

    errors = []
    external_customer_map = {}

    try:
        with transaction.atomic():

            # CREATE CUSTOMERS
            for index, row in df.iterrows():
                ext_id = str(row["customer_external_id"]).strip()

                if ext_id in external_customer_map:
                    continue

                if Customer.objects.filter(id_number=row["id_number"]).exists():
                    errors.append(f"Duplicate id_number at row {index + 2}")
                    continue

                if row["gender"] not in dict(Customer.GENDER_CHOICES):
                    errors.append(f"Invalid gender at row {index + 2}")
                    continue

                customer = Customer.objects.create(
                    name=row["name"],
                    id_number=row["id_number"],
                    phone_number=row["phone_number"],
                    alternate_phone_number=row.get("alternate_phone_number"),
                    email=row.get("email"),
                    country=row["country"],
                    location=row["location"],
                    gender=row["gender"],
                    household_type=row["household_type"],
                    household_size=int(row["household_size"]),
                    preferred_language=row["preferred_language"],
                    county=row.get("county"),
                    sub_county=row.get("sub_county"),
                    organization=organization,
                )

                external_customer_map[ext_id] = customer

            # CREATE SALES
            for index, row in df.iterrows():
                ext_id = str(row["customer_external_id"]).strip()
                referred_ext = str(row.get("referred_by_external_id", "")).strip()

                customer = external_customer_map.get(ext_id)

                if not customer:
                    errors.append(f"Customer mapping missing at row {index + 2}")
                    continue

                referred_by = external_customer_map.get(referred_ext) if referred_ext else None

                if row["product_type"] not in dict(Sale.PRODUCT_TYPE_CHOICES):
                    errors.append(f"Invalid product_type at row {index + 2}")
                    continue

                Sale.objects.create(
                    customer=customer,
                    registration_date=parse_date(str(row["registration_date"])),
                    product_type=row["product_type"],
                    product_name=row["product_name"],
                    product_model=row["product_model"],
                    product_serial_number=row["product_serial_number"],
                    purchase_mode=row["purchase_mode"],
                    sales_rep=row["sales_rep"],
                    type_of_use=row["type_of_use"],
                    payment_plan=row.get("payment_plan"),
                    referred_by=referred_by,
                    organization=organization,
                )

        if errors:
            return JsonResponse({"success": False, "error": errors})

        return JsonResponse({
            "success": True,
            "message": f"{len(external_customer_map)} customers and {len(df)} sales imported successfully."
        })

    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)})