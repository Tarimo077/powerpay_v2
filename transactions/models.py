from django.db import models
from organizations.models import Organization

class Transaction(models.Model):
    id = models.BigAutoField(primary_key=True)  # corresponds to BIGSERIAL in PostgreSQL
    time = models.DateTimeField()
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    txn_id = models.CharField(max_length=50)
    name = models.CharField(max_length=255)
    ref = models.CharField(max_length=100, blank=True, null=True)
    transtime = models.BigIntegerField()
    
    # Relation to Organization
    org = models.ForeignKey(
        Organization,
        on_delete=models.PROTECT,  # or models.SET_NULL if you prefer
        db_column="org_id"
    )

    class Meta:
        managed = False  # Django will not manage migrations for this table
        db_table = "transactions"  # exact name in PostgreSQL

    def __str__(self):
        return f"{self.txn_id} - {self.name} - {self.amount}"
