from rest_framework import viewsets, mixins, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Sum, Max, Q
from drf_spectacular.utils import extend_schema, OpenApiParameter
from devices.models import DeviceInfo, DeviceData
from customers.models import Customer
from sales.models import Sale
from transactions.models import Transaction
from api.serializers import (
    DeviceInfoSerializer, DeviceDataSerializer, CustomerSerializer,
    SaleSerializer, TransactionSerializer,
)

class ReadOnlyOrgFilterMixin:
    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if getattr(user, "role", "") != "superadmin":
            if hasattr(qs.model, "organization"):
                qs = qs.filter(organization=user.organization)
            elif hasattr(qs.model, "org"):
                qs = qs.filter(org=user.organization)
            elif hasattr(qs.model, "deviceid"):
                user_devices = DeviceInfo.objects.filter(organization=user.organization).values_list("deviceid", flat=True)
                qs = qs.filter(deviceid__in=user_devices)
        return qs

class DeviceInfoViewSet(ReadOnlyOrgFilterMixin, viewsets.ReadOnlyModelViewSet):
    queryset = DeviceInfo.objects.all()
    serializer_class = DeviceInfoSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'deviceid'
    lookup_value_regex = r'[^/]+' # Allows special characters in deviceid

    def list(self, request, *args, **kwargs):
        return Response({"detail": "Method not allowed"}, status=status.HTTP_405_METHOD_NOT_ALLOWED)

class DeviceDataViewSet(ReadOnlyOrgFilterMixin, viewsets.GenericViewSet, mixins.ListModelMixin, mixins.RetrieveModelMixin):
    serializer_class = DeviceDataSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'deviceid'
    lookup_value_regex = r'[^/]+'

    @extend_schema(
        parameters=[
            OpenApiParameter("time_start", type=str, description="Filter from (YYYY-MM-DD HH:MM)"),
            OpenApiParameter("time_end", type=str, description="Filter to (YYYY-MM-DD HH:MM)"),
        ]
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    def get_queryset(self):
        qs = DeviceData.objects.all()
        user = self.request.user
        
        # Security: Filter by organization
        if getattr(user, "role", "") != "superadmin":
            user_devices = DeviceInfo.objects.filter(organization=user.organization).values_list("deviceid", flat=True)
            qs = qs.filter(deviceid__in=user_devices)

        # Apply specific device filter if in detail view or query param
        deviceid = self.kwargs.get("deviceid") or self.request.query_params.get("deviceid")
        if deviceid:
            qs = qs.filter(deviceid=deviceid)

        # Date filtering
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

class CustomerViewSet(ReadOnlyOrgFilterMixin,
                      mixins.ListModelMixin,
                      viewsets.GenericViewSet):
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

class SaleViewSet(ReadOnlyOrgFilterMixin,
                  mixins.ListModelMixin,
                  viewsets.GenericViewSet):
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

class TransactionViewSet(ReadOnlyOrgFilterMixin,
                         mixins.ListModelMixin,
                         viewsets.GenericViewSet):
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