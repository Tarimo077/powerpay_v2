from django.db import models
from sales.models import Sale

class PayGoSettings(models.Model):
    sale = models.OneToOneField(Sale, on_delete=models.CASCADE, related_name="paygo_settings")
    auto_disable = models.BooleanField(default=False)

    class Meta:
        db_table = "paygo_settings"

    def __str__(self):
        return f"{self.sale.product_serial_number} - Auto: {self.auto_disable}"