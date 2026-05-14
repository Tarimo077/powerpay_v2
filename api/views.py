from rest_framework import viewsets, mixins, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, BasePermission
from django.db.models import Sum, Max, Q
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter
from devices.models import DeviceInfo, DeviceData, DeviceWalletMap, DeviceCommandSchedule, TrackKwh
from customers.models import Customer
from sales.models import Sale
from transactions.models import Transaction
from organizations.models import Organization, OrganizationAccess, OrganizationAppAccess
from inventory.models import Warehouse, InventoryItem, InventoryMovement
from billing.models import Invoice, InvoiceItem, Receipt, SaaSBillingRule
from paygo.models import PayGoSettings
from support.models import Ticket, TicketMessage
from api.serializers import (
    DeviceInfoSerializer,
    DeviceStatusSerializer,
    DeviceDataSerializer,
    CustomerSerializer,
    SaleSerializer,
    TransactionSerializer,
    DeviceWalletSerializer,
    DeviceCommandScheduleSerializer,
    OrganizationSerializer,
    OrganizationAccessSerializer,
    OrganizationAppAccessSerializer,
    WarehouseSerializer,
    InventoryItemSerializer,
    InventoryMovementSerializer,
    InvoiceSerializer,
    InvoiceItemSerializer,
    ReceiptSerializer,
    SaaSBillingRuleSerializer,
    PayGoSettingsSerializer,
    TicketSerializer,
    TicketMessageSerializer,
    TrackKwhSerializer,
)
from rest_framework.views import APIView
import requests




API_ENDPOINT_INSTRUCTIONS = [
    {
        "method": "GET",
        "path": "/api/instructions/",
        "name": "API instructions",
        "description": "Returns a human-readable list of the available API endpoints, their purpose, access rules, and useful query parameters.",
        "access": "Authenticated users.",
    },
    {
        "method": "GET",
        "path": "/api/schema/",
        "name": "OpenAPI schema",
        "description": "Returns the machine-readable OpenAPI schema used by Swagger UI.",
        "access": "Authenticated users if global API authentication requires it; otherwise public depending on project settings.",
    },
    {
        "method": "GET",
        "path": "/api/docs/",
        "name": "Swagger API docs",
        "description": "Interactive browser documentation where users can inspect endpoints, request bodies, query parameters, and responses.",
        "access": "Authenticated users if global API authentication requires it; otherwise public depending on project settings.",
    },
    {
        "method": "GET",
        "path": "/api/devices/info/{deviceid}/",
        "name": "Device info detail",
        "description": "Returns one device by deviceid, including active status, legacy/main organization, and organizations allowed to view it.",
        "access": "Device must be visible to the authenticated user.",
    },
    {
        "method": "POST",
        "path": "/api/devices/{deviceid}/status/",
        "name": "Change device status",
        "description": "Activates or deactivates a device. Send {\"active\": true/false} or {\"action\": \"activate\"/\"deactivate\"}.",
        "access": "Device must be visible to the authenticated user.",
    },
    {
        "method": "POST",
        "path": "/api/devices/{deviceid}/activate/",
        "name": "Activate device",
        "description": "Shortcut endpoint that activates one device. No request body is required.",
        "access": "Device must be visible to the authenticated user.",
    },
    {
        "method": "POST",
        "path": "/api/devices/{deviceid}/deactivate/",
        "name": "Deactivate device",
        "description": "Shortcut endpoint that deactivates one device. No request body is required.",
        "access": "Device must be visible to the authenticated user.",
    },
    {
        "method": "GET",
        "path": "/api/devices/data/",
        "name": "List aggregated device energy data",
        "description": "Returns total kWh and latest reading time grouped by deviceid. Query params: deviceid, time_start, time_end.",
        "access": "Readings are limited to devices visible to the authenticated user.",
    },
    {
        "method": "GET",
        "path": "/api/devices/data/{deviceid}/",
        "name": "Device energy data detail",
        "description": "Returns aggregated kWh and latest reading time for one deviceid. Query params: time_start, time_end.",
        "access": "Device must be visible to the authenticated user.",
    },
    {
        "method": "GET, POST",
        "path": "/api/device-schedules/",
        "name": "Device schedules",
        "description": "GET lists device command schedules. POST creates an ON/OFF schedule for one or more device IDs using action, devices, and scheduled_time.",
        "access": "Authenticated users. Devices must be visible to the user; superadmins can specify organization.",
    },
    {
        "method": "GET",
        "path": "/api/device-schedules/{id}/",
        "name": "Device schedule detail",
        "description": "Returns one scheduled device command including action, scheduled time, devices, organization, and execution status.",
        "access": "Schedule must belong to an organization visible to the authenticated user.",
    },
    {
        "method": "GET",
        "path": "/api/track-kwh/ and /api/track-kwh/{id}/",
        "name": "TrackKwh",
        "description": "Returns last tracked kWh records for visible devices.",
        "access": "Limited to devices visible to the authenticated user.",
    },
    {
        "method": "GET",
        "path": "/api/customers/",
        "name": "Customers",
        "description": "Lists customers. Query params: id_number and phone_number.",
        "access": "Limited to customers in organizations visible to the user.",
    },
    {
        "method": "GET",
        "path": "/api/sales/",
        "name": "Sales",
        "description": "Lists sales. Query params: product_serial_number, time_start, time_end.",
        "access": "Limited to sales in organizations visible to the user.",
    },
    {
        "method": "GET",
        "path": "/api/transactions/",
        "name": "Transactions",
        "description": "Lists payment transactions. Query params: ref and txn_id.",
        "access": "Limited to transactions in organizations visible to the user.",
    },
    {
        "method": "GET",
        "path": "/api/organizations/ and /api/organizations/{id}/",
        "name": "Organizations",
        "description": "Lists and retrieves organizations. Restricted to Django superusers only.",
        "access": "Django superusers only.",
    },
    {
        "method": "GET",
        "path": "/api/organization-access/ and /api/organization-access/{id}/",
        "name": "Organization access rules",
        "description": "Lists organization-to-organization visibility rules. Restricted to Django superusers only.",
        "access": "Django superusers only.",
    },
    {
        "method": "GET",
        "path": "/api/organization-app-access/ and /api/organization-app-access/{id}/",
        "name": "Organization app access",
        "description": "Lists app/module permissions enabled for organizations. Restricted to Django superusers only.",
        "access": "Django superusers only.",
    },
    {
        "method": "GET",
        "path": "/api/warehouses/ and /api/warehouses/{id}/",
        "name": "Warehouses",
        "description": "Lists and retrieves warehouses for organizations visible to the user.",
        "access": "Authenticated users, scoped by organization.",
    },
    {
        "method": "GET",
        "path": "/api/inventory-items/ and /api/inventory-items/{id}/",
        "name": "Inventory items",
        "description": "Lists and retrieves inventory items. Query params: serial_number and product_type.",
        "access": "Limited to items in visible warehouses.",
    },
    {
        "method": "GET",
        "path": "/api/inventory-movements/ and /api/inventory-movements/{id}/",
        "name": "Inventory movements",
        "description": "Lists and retrieves inventory movement history for visible inventory/warehouses.",
        "access": "Authenticated users, scoped by warehouse organization.",
    },
    {
        "method": "GET",
        "path": "/api/invoices/ and /api/invoices/{id}/",
        "name": "Invoices",
        "description": "Lists and retrieves hardware and SaaS invoices.",
        "access": "Limited to invoices in visible organizations.",
    },
    {
        "method": "GET",
        "path": "/api/invoice-items/ and /api/invoice-items/{id}/",
        "name": "Invoice items",
        "description": "Lists and retrieves invoice line items for visible invoices.",
        "access": "Limited to invoice items in visible organizations.",
    },
    {
        "method": "GET",
        "path": "/api/receipts/ and /api/receipts/{id}/",
        "name": "Receipts",
        "description": "Lists and retrieves receipts linked to visible invoices or transactions.",
        "access": "Authenticated users, scoped by invoice or transaction organization.",
    },
    {
        "method": "GET",
        "path": "/api/saas-billing-rules/ and /api/saas-billing-rules/{id}/",
        "name": "SaaS billing rules",
        "description": "Lists and retrieves SaaS billing automation rules. API is read-only for this model.",
        "access": "Limited to rules for visible organizations.",
    },
    {
        "method": "GET",
        "path": "/api/paygo-settings/ and /api/paygo-settings/{id}/",
        "name": "PayGo settings",
        "description": "Lists and retrieves PayGo settings for visible sales.",
        "access": "Authenticated users, scoped by sale organization.",
    },
    {
        "method": "GET",
        "path": "/api/tickets/ and /api/tickets/{id}/",
        "name": "Support tickets",
        "description": "Lists and retrieves support tickets for users in visible organizations.",
        "access": "Authenticated users, scoped by user organization.",
    },
    {
        "method": "GET",
        "path": "/api/ticket-messages/ and /api/ticket-messages/{id}/",
        "name": "Support ticket messages",
        "description": "Lists and retrieves messages for support tickets visible to the user.",
        "access": "Authenticated users, scoped by ticket organization.",
    },
    {
        "method": "GET",
        "path": "/api/devices/wallet/{deviceid}/",
        "name": "Check device wallet linkage",
        "description": "Checks whether a device has a blockchain wallet address linked.",
        "access": "Only superusers, role=superadmin, and user id=17.",
    },
    {
        "method": "POST",
        "path": "/api/devices/wallet/link/",
        "name": "Create/update device wallet linkage",
        "description": "Creates or updates the wallet address for a deviceid. Request body: deviceid and wallet_address.",
        "access": "Only superusers, role=superadmin, and user id=17.",
    },
]


class APIInstructionView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["API instructions"],
        summary="List API endpoint instructions",
        description=(
            "Returns a clear, human-readable catalogue of all API endpoints, including method, path, "
            "purpose, access rules, and key parameters. Use this when integrating with the API before "
            "opening the Swagger docs."
        ),
    )
    def get(self, request):
        return Response({
            "base_path": "/api/",
            "auth": "All business endpoints require an authenticated user. Visibility is organization-scoped unless noted otherwise.",
            "docs": "/api/docs/",
            "schema": "/api/schema/",
            "endpoints": API_ENDPOINT_INSTRUCTIONS,
        })


# ---------------------------------------------------------------------
# Shared API access helpers
# ---------------------------------------------------------------------

def _is_superadmin(user):
    return bool(
        user
        and user.is_authenticated
        and (user.is_superuser or getattr(user, "role", "") == "superadmin")
    )


def _accessible_orgs_for_user(user):
    if _is_superadmin(user):
        return Organization.objects.all()

    if getattr(user.organization, "can_view_other_orgs", False):
        target_ids = OrganizationAccess.objects.filter(
            source_org=user.organization
        ).values_list("target_org_id", flat=True)

        return Organization.objects.filter(
            Q(id=user.organization_id) | Q(id__in=target_ids)
        ).distinct()

    return Organization.objects.filter(id=user.organization_id)


def _accessible_org_ids_for_user(user):
    return list(_accessible_orgs_for_user(user).values_list("id", flat=True))


def _accessible_device_queryset_for_user(user):
    if _is_superadmin(user):
        return (
            DeviceInfo.objects
            .all()
            .select_related("organization")
            .prefetch_related("organizations")
            .distinct()
        )

    org_ids = _accessible_org_ids_for_user(user)

    return (
        DeviceInfo.objects
        .filter(
            Q(organization_id__in=org_ids) |
            Q(organizations__id__in=org_ids)
        )
        .select_related("organization")
        .prefetch_related("organizations")
        .distinct()
    )


class IsWalletLinkageUser(BasePermission):
    """
    Device wallet linkage APIs are visible only to superusers/superadmins
    and the special integration user with id=17.
    """

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and (
                user.is_superuser
                or getattr(user, "role", "") == "superadmin"
                or user.id == 17
            )
        )




class IsDjangoSuperUserOnly(BasePermission):
    """
    Allows access only to Django superusers.

    This intentionally does NOT allow role=superadmin unless
    request.user.is_superuser is also True.
    """

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.is_superuser)


class ReadOnlyOrgFilterMixin:
    """
    Generic read-only organization scoping.

    Supports:
    - organization FK
    - org FK
    - DeviceInfo M2M organizations + legacy organization_id
    - Inventory via warehouse organization
    - Billing line items via invoice organization
    - PayGo via sale organization
    - Tickets via user organization
    """

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user

        if _is_superadmin(user):
            return qs

        org_ids = _accessible_org_ids_for_user(user)
        model = qs.model

        if model is DeviceInfo:
            return qs.filter(
                Q(organization_id__in=org_ids) |
                Q(organizations__id__in=org_ids)
            ).distinct()

        if model is DeviceData:
            user_devices = _accessible_device_queryset_for_user(user).values_list("deviceid", flat=True)
            return qs.filter(deviceid__in=user_devices)

        if model is TrackKwh:
            user_devices = _accessible_device_queryset_for_user(user).values_list("deviceid", flat=True)
            return qs.filter(deviceid__in=user_devices)

        if model is Warehouse:
            return qs.filter(organization_id__in=org_ids)

        if model is InventoryItem:
            return qs.filter(current_warehouse__organization_id__in=org_ids)

        if model is InventoryMovement:
            return qs.filter(
                Q(from_warehouse__organization_id__in=org_ids) |
                Q(to_warehouse__organization_id__in=org_ids) |
                Q(item__current_warehouse__organization_id__in=org_ids)
            ).distinct()

        if model is Invoice:
            return qs.filter(organization_id__in=org_ids)

        if model is InvoiceItem:
            return qs.filter(invoice__organization_id__in=org_ids)

        if model is Receipt:
            return qs.filter(
                Q(invoice__organization_id__in=org_ids) |
                Q(transaction__org_id__in=org_ids)
            ).distinct()

        if model is SaaSBillingRule:
            return qs.filter(organization_id__in=org_ids)

        if model is PayGoSettings:
            return qs.filter(sale__organization_id__in=org_ids)

        if model is Ticket:
            return qs.filter(user__organization_id__in=org_ids)

        if model is TicketMessage:
            return qs.filter(ticket__user__organization_id__in=org_ids)

        if model is Organization:
            return qs.filter(id__in=org_ids)

        if model is OrganizationAccess:
            return qs.filter(Q(source_org_id__in=org_ids) | Q(target_org_id__in=org_ids)).distinct()

        if model is OrganizationAppAccess:
            return qs.filter(organization_id__in=org_ids)

        if hasattr(model, "organization"):
            return qs.filter(organization_id__in=org_ids)

        if hasattr(model, "org"):
            return qs.filter(org_id__in=org_ids)

        return qs.none()


# ---------------------------------------------------------------------
# Devices
# ---------------------------------------------------------------------

@extend_schema_view(
    retrieve=extend_schema(
        tags=["Devices"],
        summary="Get one device by device ID",
        description=(
            "Returns one device record using its deviceid. The response includes the device status, "
            "legacy/main organization, and organizations allowed to view the device. Access is limited "
            "to devices visible to the authenticated user. The list action is intentionally disabled; "
            "use this detail endpoint for device metadata."
        ),
    ),
    list=extend_schema(
        tags=["Devices"],
        summary="Device list disabled",
        description="This endpoint intentionally returns 405. Device metadata is exposed only by deviceid detail lookup.",
    ),
)
class DeviceInfoViewSet(ReadOnlyOrgFilterMixin, viewsets.ReadOnlyModelViewSet):
    queryset = DeviceInfo.objects.all().select_related("organization").prefetch_related("organizations")
    serializer_class = DeviceInfoSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "deviceid"
    lookup_value_regex = r"[^/]+"

    def list(self, request, *args, **kwargs):
        return Response({"detail": "Method not allowed"}, status=status.HTTP_405_METHOD_NOT_ALLOWED)


def _change_device_status_response(request, deviceid, target_status):
    device = get_object_or_404(_accessible_device_queryset_for_user(request.user), deviceid=deviceid)

    try:
        response = requests.post(
            "https://appliapay.com/changeStatus",
            json={
                "selectedDev": device.deviceid,
                "status": not target_status,
            },
            timeout=10,
        )
    except requests.exceptions.RequestException as exc:
        return Response(
            {"detail": f"API request failed: {exc}"},
            status=status.HTTP_502_BAD_GATEWAY,
        )

    if response.status_code != 200:
        return Response(
            {"detail": "External API error", "external_status_code": response.status_code},
            status=status.HTTP_502_BAD_GATEWAY,
        )

    data = response.json()
    new_status = data.get("status", target_status)

    if isinstance(new_status, str):
        new_status = new_status.lower() == "true"

    device.active = bool(new_status)
    device.save(update_fields=["active"])

    return Response(DeviceInfoSerializer(device, context={"request": request}).data)


class DeviceStatusChangeView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Devices"],
        summary="Activate or deactivate one device",
        request=DeviceStatusSerializer,
        responses=DeviceInfoSerializer,
        description=(
            "Changes one device status through the external AppliaPay status API and then saves the returned status locally. "
            "Send either {'active': true/false} or {'action': 'activate'/'deactivate'}. "
            "The user must have access to the device through legacy organization ownership or the multi-organization visibility table."
        ),
    )
    def post(self, request, deviceid):
        serializer = DeviceStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return _change_device_status_response(request, deviceid, serializer.target_status)


class DeviceActivateView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Devices"],
        summary="Activate one device",
        responses=DeviceInfoSerializer,
        description="Shortcut endpoint that activates the selected device. No request body is required.",
    )
    def post(self, request, deviceid):
        return _change_device_status_response(request, deviceid, True)


class DeviceDeactivateView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Devices"],
        summary="Deactivate one device",
        responses=DeviceInfoSerializer,
        description="Shortcut endpoint that deactivates the selected device. No request body is required.",
    )
    def post(self, request, deviceid):
        return _change_device_status_response(request, deviceid, False)


@extend_schema_view(
    list=extend_schema(
        tags=["Device energy data"],
        summary="List aggregated device energy data",
        description=(
            "Returns aggregated energy readings grouped by deviceid. Use query parameters to filter by "
            "deviceid and time range. Non-superadmin users only see readings for devices visible to their organization."
        ),
    ),
    retrieve=extend_schema(
        tags=["Device energy data"],
        summary="Get aggregated energy data for one device",
        description="Returns the aggregated kWh and latest reading time for a single deviceid within optional time filters.",
    ),
)
class DeviceDataViewSet(ReadOnlyOrgFilterMixin, viewsets.GenericViewSet, mixins.ListModelMixin, mixins.RetrieveModelMixin):
    serializer_class = DeviceDataSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "deviceid"
    lookup_value_regex = r"[^/]+"

    @extend_schema(
        parameters=[
            OpenApiParameter("deviceid", type=str, description="Filter by device ID"),
            OpenApiParameter("time_start", type=str, description="Filter from (YYYY-MM-DD HH:MM)"),
            OpenApiParameter("time_end", type=str, description="Filter to (YYYY-MM-DD HH:MM)"),
        ]
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    def get_queryset(self):
        qs = DeviceData.objects.all()
        user = self.request.user

        if not _is_superadmin(user):
            user_devices = _accessible_device_queryset_for_user(user).values_list("deviceid", flat=True)
            qs = qs.filter(deviceid__in=user_devices)

        deviceid = self.kwargs.get("deviceid") or self.request.query_params.get("deviceid")
        if deviceid:
            qs = qs.filter(deviceid=deviceid)

        time_start = self.request.query_params.get("time_start")
        time_end = self.request.query_params.get("time_end")
        if time_start:
            qs = qs.filter(time__gte=time_start)
        if time_end:
            qs = qs.filter(time__lte=time_end)

        return qs.values("deviceid").annotate(
            total_kwh=Sum("kwh"),
            latest_time=Max("time")
        ).order_by("deviceid")

    def retrieve(self, request, *args, **kwargs):
        qs = self.get_queryset()
        instance = qs.first()
        if not instance:
            return Response({"detail": "Not found"}, status=status.HTTP_404_NOT_FOUND)
        serializer = self.get_serializer(instance)
        return Response(serializer.data)


@extend_schema_view(
    list=extend_schema(
        tags=["Device schedules"],
        summary="List device command schedules",
        description=(
            "Lists scheduled ON/OFF commands for devices visible to the authenticated user. "
            "Superadmins see all schedules; other users are scoped to accessible organizations."
        ),
    ),
    retrieve=extend_schema(
        tags=["Device schedules"],
        summary="Get one device command schedule",
        description="Returns one scheduled device command, including action, scheduled time, execution status, devices, and organization.",
    ),
    create=extend_schema(
        tags=["Device schedules"],
        summary="Create a device command schedule",
        description=(
            "Creates a future ON/OFF command schedule for one or more device IDs. Request body requires action, "
            "devices, and scheduled_time. Superadmins may set organization; non-superadmins are assigned to their organization."
        ),
    ),
)
class DeviceCommandScheduleViewSet(ReadOnlyOrgFilterMixin,
                                   mixins.ListModelMixin,
                                   mixins.RetrieveModelMixin,
                                   mixins.CreateModelMixin,
                                   viewsets.GenericViewSet):
    queryset = DeviceCommandSchedule.objects.all().prefetch_related("devices").select_related("organization", "created_by")
    serializer_class = DeviceCommandScheduleSerializer
    permission_classes = [IsAuthenticated]

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["device_queryset"] = _accessible_device_queryset_for_user(self.request.user)
        context["organization_queryset"] = _accessible_orgs_for_user(self.request.user)
        return context

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


@extend_schema_view(
    list=extend_schema(tags=["Device energy data"], summary="List last tracked kWh records", description="Lists TrackKwh records for devices visible to the authenticated user."),
    retrieve=extend_schema(tags=["Device energy data"], summary="Get one last tracked kWh record", description="Returns one TrackKwh row by ID."),
)
class TrackKwhViewSet(ReadOnlyOrgFilterMixin, viewsets.ReadOnlyModelViewSet):
    queryset = TrackKwh.objects.all()
    serializer_class = TrackKwhSerializer
    permission_classes = [IsAuthenticated]


# ---------------------------------------------------------------------
# Core business models
# ---------------------------------------------------------------------

@extend_schema_view(
    list=extend_schema(
        tags=["Customers"],
        summary="List customers",
        description="Returns customers visible to the authenticated user. Optional filters: id_number and phone_number."
    ),
)
class CustomerViewSet(ReadOnlyOrgFilterMixin, mixins.ListModelMixin, viewsets.GenericViewSet):
    queryset = Customer.objects.all()
    serializer_class = CustomerSerializer
    permission_classes = [IsAuthenticated]

    @extend_schema(
        parameters=[
            OpenApiParameter("id_number", str, description="Filter by customer ID number"),
            OpenApiParameter("phone_number", str, description="Filter by customer phone number"),
        ]
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    def get_queryset(self):
        qs = super().get_queryset()
        id_number = self.request.query_params.get("id_number")
        phone_number = self.request.query_params.get("phone_number")

        if id_number:
            qs = qs.filter(id_number__icontains=id_number)
        if phone_number:
            qs = qs.filter(phone_number__icontains=phone_number)

        return qs


@extend_schema_view(
    list=extend_schema(
        tags=["Sales"],
        summary="List sales",
        description="Returns sales visible to the authenticated user. Optional filters: product_serial_number, time_start, and time_end."
    ),
)
class SaleViewSet(ReadOnlyOrgFilterMixin, mixins.ListModelMixin, viewsets.GenericViewSet):
    queryset = Sale.objects.all()
    serializer_class = SaleSerializer
    permission_classes = [IsAuthenticated]

    @extend_schema(
        parameters=[
            OpenApiParameter("product_serial_number", str, description="Filter by product serial number"),
            OpenApiParameter("time_start", str, description="Registration date from (YYYY-MM-DD)"),
            OpenApiParameter("time_end", str, description="Registration date to (YYYY-MM-DD)"),
        ]
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    def get_queryset(self):
        qs = super().get_queryset()
        serial = self.request.query_params.get("product_serial_number")
        time_start = self.request.query_params.get("time_start")
        time_end = self.request.query_params.get("time_end")

        if serial:
            qs = qs.filter(product_serial_number__icontains=serial)
        if time_start:
            qs = qs.filter(registration_date__gte=time_start)
        if time_end:
            qs = qs.filter(registration_date__lte=time_end)

        return qs


@extend_schema_view(
    list=extend_schema(
        tags=["Transactions"],
        summary="List transactions",
        description="Returns payment transactions visible to the authenticated user. Optional filters: ref and txn_id."
    ),
)
class TransactionViewSet(ReadOnlyOrgFilterMixin, mixins.ListModelMixin, viewsets.GenericViewSet):
    queryset = Transaction.objects.all()
    serializer_class = TransactionSerializer
    permission_classes = [IsAuthenticated]

    @extend_schema(
        parameters=[
            OpenApiParameter("ref", str, description="Filter by reference number"),
            OpenApiParameter("txn_id", str, description="Filter by transaction ID"),
        ]
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    def get_queryset(self):
        qs = super().get_queryset()
        ref = self.request.query_params.get("ref")
        txn_id = self.request.query_params.get("txn_id")

        if ref:
            qs = qs.filter(ref__icontains=ref)
        if txn_id:
            qs = qs.filter(txn_id__icontains=txn_id)

        return qs


@extend_schema_view(
    list=extend_schema(tags=["Organizations"], summary="List organizations", description="Lists organizations. Restricted to Django superusers only."),
    retrieve=extend_schema(tags=["Organizations"], summary="Get one organization", description="Returns one organization. Restricted to Django superusers only."),
)
class OrganizationViewSet(ReadOnlyOrgFilterMixin, viewsets.ReadOnlyModelViewSet):
    queryset = Organization.objects.all()
    serializer_class = OrganizationSerializer
    permission_classes = [IsAuthenticated, IsDjangoSuperUserOnly]


@extend_schema_view(
    list=extend_schema(tags=["Organizations"], summary="List organization access rules", description="Lists organization-to-organization visibility rules. Restricted to Django superusers only."),
    retrieve=extend_schema(tags=["Organizations"], summary="Get one organization access rule", description="Returns one organization access relationship. Restricted to Django superusers only."),
)
class OrganizationAccessViewSet(ReadOnlyOrgFilterMixin, viewsets.ReadOnlyModelViewSet):
    queryset = OrganizationAccess.objects.all().select_related("source_org", "target_org")
    serializer_class = OrganizationAccessSerializer
    permission_classes = [IsAuthenticated, IsDjangoSuperUserOnly]


@extend_schema_view(
    list=extend_schema(tags=["Organizations"], summary="List organization app access", description="Lists app/module access enabled for organizations. Restricted to Django superusers only."),
    retrieve=extend_schema(tags=["Organizations"], summary="Get one organization app access record", description="Returns one app access record for an organization. Restricted to Django superusers only."),
)
class OrganizationAppAccessViewSet(ReadOnlyOrgFilterMixin, viewsets.ReadOnlyModelViewSet):
    queryset = OrganizationAppAccess.objects.all().select_related("organization")
    serializer_class = OrganizationAppAccessSerializer
    permission_classes = [IsAuthenticated, IsDjangoSuperUserOnly]


@extend_schema_view(
    list=extend_schema(tags=["Inventory"], summary="List warehouses", description="Lists warehouses belonging to organizations visible to the authenticated user."),
    retrieve=extend_schema(tags=["Inventory"], summary="Get one warehouse", description="Returns one warehouse by ID."),
)
class WarehouseViewSet(ReadOnlyOrgFilterMixin, viewsets.ReadOnlyModelViewSet):
    queryset = Warehouse.objects.all().select_related("organization")
    serializer_class = WarehouseSerializer
    permission_classes = [IsAuthenticated]


@extend_schema_view(
    list=extend_schema(
        tags=["Inventory"],
        summary="List inventory items",
        description="Lists inventory items in warehouses visible to the authenticated user. Optional filters: serial_number and product_type."
    ),
    retrieve=extend_schema(tags=["Inventory"], summary="Get one inventory item", description="Returns one inventory item by ID."),
)
class InventoryItemViewSet(ReadOnlyOrgFilterMixin, viewsets.ReadOnlyModelViewSet):
    queryset = InventoryItem.objects.all().select_related("current_warehouse", "current_warehouse__organization")
    serializer_class = InventoryItemSerializer
    permission_classes = [IsAuthenticated]

    @extend_schema(
        parameters=[
            OpenApiParameter("serial_number", str, description="Filter by serial number"),
            OpenApiParameter("product_type", str, description="Filter by product type"),
        ]
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    def get_queryset(self):
        qs = super().get_queryset()
        serial_number = self.request.query_params.get("serial_number")
        product_type = self.request.query_params.get("product_type")

        if serial_number:
            qs = qs.filter(serial_number__icontains=serial_number)
        if product_type:
            qs = qs.filter(product_type__icontains=product_type)

        return qs


@extend_schema_view(
    list=extend_schema(tags=["Inventory"], summary="List inventory movements", description="Lists stock movement history for inventory visible to the authenticated user."),
    retrieve=extend_schema(tags=["Inventory"], summary="Get one inventory movement", description="Returns one inventory movement record by ID."),
)
class InventoryMovementViewSet(ReadOnlyOrgFilterMixin, viewsets.ReadOnlyModelViewSet):
    queryset = InventoryMovement.objects.all().select_related("item", "from_warehouse", "to_warehouse", "moved_by")
    serializer_class = InventoryMovementSerializer
    permission_classes = [IsAuthenticated]


@extend_schema_view(
    list=extend_schema(tags=["Billing"], summary="List invoices", description="Lists hardware and SaaS invoices visible to the authenticated user."),
    retrieve=extend_schema(tags=["Billing"], summary="Get one invoice", description="Returns one invoice by ID."),
)
class InvoiceViewSet(ReadOnlyOrgFilterMixin, viewsets.ReadOnlyModelViewSet):
    queryset = Invoice.objects.all().select_related("organization", "created_by")
    serializer_class = InvoiceSerializer
    permission_classes = [IsAuthenticated]


@extend_schema_view(
    list=extend_schema(tags=["Billing"], summary="List invoice items", description="Lists invoice line items belonging to visible invoices."),
    retrieve=extend_schema(tags=["Billing"], summary="Get one invoice item", description="Returns one invoice item by ID."),
)
class InvoiceItemViewSet(ReadOnlyOrgFilterMixin, viewsets.ReadOnlyModelViewSet):
    queryset = InvoiceItem.objects.all().select_related("invoice", "device")
    serializer_class = InvoiceItemSerializer
    permission_classes = [IsAuthenticated]


@extend_schema_view(
    list=extend_schema(tags=["Billing"], summary="List receipts", description="Lists receipts linked to visible invoices or visible transactions."),
    retrieve=extend_schema(tags=["Billing"], summary="Get one receipt", description="Returns one receipt by ID."),
)
class ReceiptViewSet(ReadOnlyOrgFilterMixin, viewsets.ReadOnlyModelViewSet):
    queryset = Receipt.objects.all().select_related("invoice", "transaction")
    serializer_class = ReceiptSerializer
    permission_classes = [IsAuthenticated]


@extend_schema_view(
    list=extend_schema(tags=["Billing"], summary="List SaaS billing rules", description="Lists SaaS billing automation rules for visible organizations. This is read-only through the API."),
    retrieve=extend_schema(tags=["Billing"], summary="Get one SaaS billing rule", description="Returns one SaaS billing rule by ID."),
)
class SaaSBillingRuleViewSet(ReadOnlyOrgFilterMixin, viewsets.ReadOnlyModelViewSet):
    queryset = SaaSBillingRule.objects.all().select_related("organization", "created_by")
    serializer_class = SaaSBillingRuleSerializer
    permission_classes = [IsAuthenticated]


@extend_schema_view(
    list=extend_schema(tags=["PayGo"], summary="List PayGo settings", description="Lists PayGo settings for sales visible to the authenticated user."),
    retrieve=extend_schema(tags=["PayGo"], summary="Get one PayGo setting", description="Returns one PayGo settings record by ID."),
)
class PayGoSettingsViewSet(ReadOnlyOrgFilterMixin, viewsets.ReadOnlyModelViewSet):
    queryset = PayGoSettings.objects.all().select_related("sale", "sale__organization")
    serializer_class = PayGoSettingsSerializer
    permission_classes = [IsAuthenticated]


@extend_schema_view(
    list=extend_schema(tags=["Support"], summary="List support tickets", description="Lists support tickets for users in organizations visible to the authenticated user."),
    retrieve=extend_schema(tags=["Support"], summary="Get one support ticket", description="Returns one support ticket by ID."),
)
class TicketViewSet(ReadOnlyOrgFilterMixin, viewsets.ReadOnlyModelViewSet):
    queryset = Ticket.objects.all().select_related("user")
    serializer_class = TicketSerializer
    permission_classes = [IsAuthenticated]


@extend_schema_view(
    list=extend_schema(tags=["Support"], summary="List support ticket messages", description="Lists messages belonging to support tickets visible to the authenticated user."),
    retrieve=extend_schema(tags=["Support"], summary="Get one support ticket message", description="Returns one ticket message by ID."),
)
class TicketMessageViewSet(ReadOnlyOrgFilterMixin, viewsets.ReadOnlyModelViewSet):
    queryset = TicketMessage.objects.all().select_related("ticket", "sender")
    serializer_class = TicketMessageSerializer
    permission_classes = [IsAuthenticated]


# ---------------------------------------------------------------------
# Blockchain/device wallet linkages
# ---------------------------------------------------------------------

class DeviceWalletCheckView(APIView):
    permission_classes = [IsAuthenticated, IsWalletLinkageUser]

    @extend_schema(
        tags=["Device wallet linkages"],
        summary="Check wallet linkage for one device",
        description=(
            "Returns whether a device is linked to a blockchain wallet and, if linked, the wallet address and timestamp. "
            "This endpoint is restricted to superusers, users with role superadmin, and user id=17 only."
        ),
    )
    def get(self, request, deviceid):
        device = DeviceInfo.objects.filter(deviceid=deviceid).first()

        if not device:
            return Response({"detail": "Device not found"}, status=status.HTTP_404_NOT_FOUND)

        mapping = DeviceWalletMap.objects.filter(device__deviceid=deviceid).first()

        if mapping:
            return Response({
                "deviceid": deviceid,
                "linked": True,
                "wallet_address": mapping.wallet_address,
                "linked_at": mapping.linked_at,
            })

        return Response({
            "deviceid": deviceid,
            "linked": False,
            "wallet_address": None,
            "linked_at": None,
        })


class DeviceWalletUpsertView(APIView):
    permission_classes = [IsAuthenticated, IsWalletLinkageUser]

    @extend_schema(
        tags=["Device wallet linkages"],
        summary="Create or update a device wallet linkage",
        request=DeviceWalletSerializer,
        responses=DeviceWalletSerializer,
        description=(
            "Creates or updates the wallet address linked to a deviceid. "
            "This endpoint is restricted to superusers, users with role superadmin, and user id=17 only."
        ),
    )
    def post(self, request):
        serializer = DeviceWalletSerializer(
            data=request.data,
            context={"request": request}
        )

        if serializer.is_valid():
            obj = serializer.save()
            return Response({
                "deviceid": obj.device.deviceid,
                "wallet_address": obj.wallet_address,
                "linked_at": obj.linked_at,
                "created": serializer.context.get("created", False),
            }, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
