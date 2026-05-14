# Generated for SaaS billing rule automation.

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('billing', '0002_remove_receipt_sale_receipt_transaction'),
        ('organizations', '0002_organizationaccess_organizationappaccess'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='SaaSBillingRule',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=150)),
                ('frequency', models.CharField(choices=[('DAILY', 'Every day'), ('WEEKLY', 'Every week'), ('MONTHLY', 'Every month'), ('CUSTOM', 'Custom interval')], max_length=20)),
                ('custom_interval_days', models.PositiveIntegerField(blank=True, null=True)),
                ('rate_per_device', models.DecimalField(decimal_places=2, max_digits=10)),
                ('due_days', models.PositiveIntegerField(default=7)),
                ('next_run_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('active', models.BooleanField(default=True)),
                ('auto_send_email', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
                ('organization', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='saas_billing_rules', to='organizations.organization')),
            ],
            options={
                'ordering': ['organization__name', 'name'],
            },
        ),
    ]
