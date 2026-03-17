from django.db import models

class Organization(models.Model):
    name = models.CharField(max_length=255, unique=True)
    address = models.TextField(blank=True, null=True)
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    logo = models.ImageField(upload_to="org_logos/", blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    can_view_other_orgs = models.BooleanField(default=False)

    def __str__(self):
        return self.name
    
    class Meta:
        managed = False  # read-only
        db_table = "organization"


class OrganizationAccess(models.Model):
    source_org = models.ForeignKey(
        Organization,
        db_column="source_org_id",
        on_delete=models.CASCADE,
        related_name="source_access"
    )
    target_org = models.ForeignKey(
        Organization,
        db_column="target_org_id",
        on_delete=models.CASCADE,
        related_name="target_access"
    )

    class Meta:
        managed = False
        db_table = "organization_access"
        unique_together = ("source_org", "target_org")

    def __str__(self):
        return f"{self.source_org} -> {self.target_org}"