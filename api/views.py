from rest_framework import viewsets, mixins, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Sum, Max
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
        if time_start: qs = qs.filter(time__gte=time_start)
        if time_end: qs = qs.filter(time__lte=time_end)

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

# Standard ViewSets for other models
class CustomerViewSet(ReadOnlyOrgFilterMixin, viewsets.ReadOnlyModelViewSet):
    queryset = Customer.objects.all()
    serializer_class = CustomerSerializer
    permission_classes = [IsAuthenticated]

class SaleViewSet(ReadOnlyOrgFilterMixin, viewsets.ReadOnlyModelViewSet):
    queryset = Sale.objects.all()
    serializer_class = SaleSerializer
    permission_classes = [IsAuthenticated]

class TransactionViewSet(ReadOnlyOrgFilterMixin, viewsets.ReadOnlyModelViewSet):
    queryset = Transaction.objects.all()
    serializer_class = TransactionSerializer
    permission_classes = [IsAuthenticated]