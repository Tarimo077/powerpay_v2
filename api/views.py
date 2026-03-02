from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend, FilterSet, DateTimeFilter, CharFilter, NumberFilter
from django.db.models import Sum
from devices.models import DeviceInfo, DeviceData
from customers.models import Customer
from sales.models import Sale
from transactions.models import Transaction
from api.serializers import (
    DeviceInfoSerializer,
    DeviceDataSerializer,
    CustomerSerializer,
    SaleSerializer,
    TransactionSerializer,
)
from django.db import models

# -------------------------
# Role-based filtering mixin
# -------------------------
class ReadOnlyOrgFilterMixin:
    """
    Restrict normal users to their organization's data
    """
    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if getattr(user, "role", "") != "superadmin":
            if hasattr(qs.model, "organization"):
                qs = qs.filter(organization=user.organization)
            elif hasattr(qs.model, "org"):
                qs = qs.filter(org=user.organization)
            elif hasattr(qs.model, "deviceid"):
                # For DeviceData linked to DeviceInfo
                user_devices = DeviceInfo.objects.filter(
                    organization=user.organization
                ).values_list("deviceid", flat=True)
                qs = qs.filter(deviceid__in=user_devices)
        return qs

# -------------------------
# Filters per model
# -------------------------
class DeviceInfoFilter(FilterSet):
    deviceid = CharFilter(field_name="deviceid", lookup_expr="icontains")
    class Meta:
        model = DeviceInfo
        fields = ["deviceid", "active", "organization"]

class DeviceDataFilter(FilterSet):
    deviceid = CharFilter(field_name="deviceid", lookup_expr="icontains")
    status = CharFilter(field_name="status", lookup_expr="icontains")
    time_start = DateTimeFilter(field_name="time", lookup_expr="gte")
    time_end = DateTimeFilter(field_name="time", lookup_expr="lte")
    class Meta:
        model = DeviceData
        fields = ["deviceid", "status", "time"]

class CustomerFilter(FilterSet):
    name = CharFilter(field_name="name", lookup_expr="icontains")
    id_number = CharFilter(field_name="id_number", lookup_expr="icontains")
    phone_number = CharFilter(field_name="phone_number", lookup_expr="icontains")
    email = CharFilter(field_name="email", lookup_expr="icontains")
    county = CharFilter(field_name="county", lookup_expr="icontains")
    sub_county = CharFilter(field_name="sub_county", lookup_expr="icontains")
    class Meta:
        model = Customer
        fields = ["name", "id_number", "phone_number", "email", "county", "sub_county"]

class SaleFilter(FilterSet):
    product_serial_number = CharFilter(field_name="product_serial_number", lookup_expr="icontains")
    product_name = CharFilter(field_name="product_name", lookup_expr="icontains")
    sales_rep = CharFilter(field_name="sales_rep", lookup_expr="icontains")
    customer_id = NumberFilter(field_name="customer_id")
    start_date = DateTimeFilter(field_name="date", lookup_expr="gte")
    end_date = DateTimeFilter(field_name="date", lookup_expr="lte")
    class Meta:
        model = Sale
        fields = ["product_serial_number", "product_name", "sales_rep", "customer_id", "date"]

class TransactionFilter(FilterSet):
    txn_id = CharFilter(field_name="txn_id", lookup_expr="icontains")
    name = CharFilter(field_name="name", lookup_expr="icontains")
    ref = CharFilter(field_name="ref", lookup_expr="icontains")
    start_time = DateTimeFilter(field_name="time", lookup_expr="gte")
    end_time = DateTimeFilter(field_name="time", lookup_expr="lte")
    class Meta:
        model = Transaction
        fields = ["txn_id", "name", "ref", "time"]

# -------------------------
# ViewSets
# -------------------------
class DeviceInfoViewSet(ReadOnlyOrgFilterMixin, viewsets.ReadOnlyModelViewSet):
    queryset = DeviceInfo.objects.all()
    serializer_class = DeviceInfoSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_class = DeviceInfoFilter

from rest_framework.decorators import action
from rest_framework.response import Response

class DeviceDataViewSet(ReadOnlyOrgFilterMixin, viewsets.ReadOnlyModelViewSet):
    serializer_class = DeviceDataSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_class = DeviceDataFilter

    def get_queryset(self):
        qs = DeviceData.objects.all()
        user = self.request.user
        if getattr(user, "role", "") != "superadmin":
            user_devices = DeviceInfo.objects.filter(
                organization=user.organization
            ).values_list("deviceid", flat=True)
            qs = qs.filter(deviceid__in=user_devices)

        start = self.request.query_params.get("time_start")
        end = self.request.query_params.get("time_end")
        if start and end:
            qs = qs.filter(time__range=[start, end])

        qs = qs.values("deviceid").annotate(total_kwh=Sum("kwh")).order_by("deviceid")
        return qs

    # Custom detail route
    @action(detail=False, url_path=r'(?P<deviceid>[^/.]+)')
    def device_detail(self, request, deviceid=None):
        qs = self.get_queryset().filter(deviceid=deviceid)
        return Response(self.get_serializer(qs, many=True).data)

class CustomerViewSet(ReadOnlyOrgFilterMixin, viewsets.ReadOnlyModelViewSet):
    queryset = Customer.objects.all()
    serializer_class = CustomerSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_class = CustomerFilter

class SaleViewSet(ReadOnlyOrgFilterMixin, viewsets.ReadOnlyModelViewSet):
    queryset = Sale.objects.all()
    serializer_class = SaleSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_class = SaleFilter

class TransactionViewSet(ReadOnlyOrgFilterMixin, viewsets.ReadOnlyModelViewSet):
    queryset = Transaction.objects.all()
    serializer_class = TransactionSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_class = TransactionFilter