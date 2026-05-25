# PowerPay Africa Management Platform

<div align="center">

**A Django-powered operations platform for PayGo energy businesses, device fleets, customer management, inventory control, billing, support, reporting, and analytics.**

</div>

---

## Table of Contents

- [Overview](#overview)
- [Key Features](#key-features)
- [Technology Stack](#technology-stack)
- [Project Structure](#project-structure)
- [Core Apps](#core-apps)
- [Architecture](#architecture)
- [Database Design](#database-design)
- [User Roles and Access Control](#user-roles-and-access-control)
- [Main Workflows](#main-workflows)
- [REST API](#rest-api)
- [Local Development Setup](#local-development-setup)
- [Environment Variables](#environment-variables)
- [Database Setup Notes](#database-setup-notes)
- [Running the Project](#running-the-project)
- [Background Workers](#background-workers)
- [Static Assets and Frontend](#static-assets-and-frontend)
- [Import and Export Center](#import-and-export-center)
- [Testing](#testing)
- [Deployment Notes](#deployment-notes)
- [Security Checklist](#security-checklist)
- [Troubleshooting](#troubleshooting)
- [Repository Hygiene](#repository-hygiene)
- [Useful Commands](#useful-commands)

---

## Overview

**PowerPay Africa** is a modular Django platform designed to manage the operational workflow of a PayGo and asset-based energy business.

The system brings together:

- Customer management
- Sales management
- Device management
- Device command scheduling
- Device testing batches
- Device packing and dispatch tracking
- Inventory and warehouse tracking
- PayGo automation
- Transactions
- Invoicing and receipts
- SaaS billing automation
- Support tickets
- Organization-based access control
- Data imports and exports
- REST API access
- Dashboard analytics

The application is built around **multi-organization visibility**, meaning users only see data belonging to their organization or organizations they are allowed to access.

---

## Key Features

### Platform

- Multi-organization support
- Role-based access control
- Organization-level app/module access
- Dashboard analytics
- Notifications
- Import center
- Export center
- REST API with JWT authentication
- Responsive sidebar navigation
- HTMX-powered tables and partial updates
- Chart.js dashboards
- Tailwind CSS and DaisyUI styling

### Devices

- Device listing
- Device creation
- Bulk device creation
- Device detail pages
- Device status updates
- Device live view
- MQTT-backed live updates
- Device wallet mapping
- Device command scheduling
- Manual schedule trigger
- Device testing batches
- Batch test result tracking
- Packing workflow
- Batch dispatch workflow
- Testing batch deletion

### Inventory

- Inventory item list
- Unique serialized item tracking
- Shared quantity-based stock tracking
- Warehouse management
- Inventory movement history
- Partial quantity movement for shared items
- Bulk add inventory
- Bulk move inventory
- Inventory growth charts
- Units-per-warehouse charts

### Billing

- Hardware invoices
- SaaS invoices
- Invoice PDF generation
- Invoice email sending
- Receipt generation
- Receipt PDF generation
- SaaS billing rules
- Scheduled billing automation with Celery

### API

- JWT login and refresh
- Device info endpoints
- Device energy data endpoints
- Device status change endpoints
- Customer endpoints
- Sales endpoints
- Transactions endpoints
- Inventory endpoints
- Billing endpoints
- Support endpoints
- Swagger UI
- OpenAPI schema

---

## Technology Stack

### Backend

- Python
- Django 5.2
- Django REST Framework
- Simple JWT
- PostgreSQL
- SQLite
- Celery
- Redis
- Django Channels
- Daphne
- Django Celery Beat

### Frontend

- Django templates
- Tailwind CSS
- DaisyUI
- HTMX
- Font Awesome
- Chart.js
- chartjs-plugin-datalabels

### Data and Reports

- Pandas
- OpenPyXL
- xhtml2pdf
- ReportLab

### Real-Time and Device Communication

- Django Channels
- Redis channel layer
- MQTT client
- External device status API

---

## Project Structure

```text
powerpay_v2/
├── accounts/              # Custom user model, login, OTP, invites, profile
├── api/                   # DRF API endpoints, serializers, Swagger/OpenAPI
├── billing/               # Invoices, receipts, SaaS billing rules
├── core/                  # Dashboard, import center, export center
├── customers/             # Customer records and customer detail pages
├── device_orders/         # Device order request/approval/fulfillment workflow
├── devices/               # Devices, schedules, testing batches, live views
├── inventory/             # Inventory items, warehouses, movements
├── notifications/         # User notifications and unread counts
├── organizations/         # Organizations, access rules, app permissions
├── paygo/                 # PayGo sales and auto-disable settings
├── sales/                 # Sales records, receipts, customer sales
├── support/               # Support tickets and ticket messages
├── transactions/          # Transaction history
├── powerpay_v2/           # Django settings, ASGI, WSGI, Celery, DB router
├── templates/             # Shared base templates and partials
├── static/                # Static assets
├── media/                 # Uploaded files
├── manage.py
├── requirements.txt
├── package.json
└── README.md
```

---

## Core Apps

### `accounts`

Handles authentication and users.

Main features:

- Custom `User` model
- Email login
- OTP verification
- Password reset
- Terms acceptance
- User invites
- User profile management
- JWT token endpoints

Important models:

- `User`
- `EmailOTP`
- `UserInvite`

---

### `organizations`

Handles organizations and access rules.

Main features:

- Organization records
- Organization-to-organization visibility
- Organization app access control
- Plan tracking

Important models:

- `Organization`
- `OrganizationAccess`
- `OrganizationAppAccess`

Many organization tables are marked as unmanaged, meaning they already exist in the database and are not created by Django migrations.

---

### `core`

Handles system-wide pages and data tools.

Main features:

- Dashboard
- Dashboard caching
- Export center
- Import center
- Customer/sales import
- Transaction import
- Export record counts
- Organization-aware dashboard filtering

Important views:

- `index`
- `export_data_view`
- `export_count_view`
- `import_center`
- `import_customers_sales`
- `import_transactions`

---

### `devices`

Handles device operations.

Main features:

- Device list
- Device detail
- Device create/edit/delete
- Bulk device creation
- Bulk device actions
- Device status changes
- Device schedules
- Testing batches
- Batch dispatch
- Live device view
- MQTT support
- Device wallet mapping

Important models:

- `DeviceInfo`
- `DeviceData`
- `DeviceCommandSchedule`
- `TrackKwh`
- `DeviceWalletMap`
- `DeviceTestingBatch`
- `DeviceTestingBatchItem`
- `DeviceBatchDispatch`

---

### `inventory`

Handles stock and warehouse operations.

Main features:

- Inventory listing
- Unique item tracking
- Shared stock tracking
- Warehouse management
- Inventory movement history
- Bulk inventory add
- Bulk inventory move
- Partial quantity movement for shared stock
- Inventory charts

Important models:

- `Warehouse`
- `InventoryItem`
- `InventoryMovement`

Inventory tables are currently unmanaged, so schema changes must be applied manually unless the model management strategy is changed.

---

### `customers`

Handles customer records.

Main features:

- Customer listing
- Customer create/edit/delete
- Customer detail
- Linked sales
- Organization-scoped access

Important model:

- `Customer`

---

### `sales`

Handles sales records.

Main features:

- Sales listing
- Sales create/edit/delete
- Sale detail
- Sales receipts
- Receipt PDF generation
- Receipt email sending
- Customer search

Important model:

- `Sale`

---

### `transactions`

Handles payment transaction history.

Main features:

- Transactions listing
- Search
- Filters
- Organization-scoped access
- Export support

Important model:

- `Transaction`

---

### `paygo`

Handles PayGo settings and actions.

Main features:

- PayGo sales list
- Toggle auto-disable
- STK push action

Important model:

- `PayGoSettings`

---

### `billing`

Handles invoicing and billing automation.

Main features:

- Invoice list
- Hardware invoice creation
- SaaS invoice creation
- Invoice detail
- Invoice edit/delete
- Invoice PDF generation
- Invoice email sending
- Receipt list
- Receipt PDF generation
- Receipt syncing
- SaaS billing rules
- Run due SaaS rules

Important models:

- `Invoice`
- `InvoiceItem`
- `Receipt`
- `SaaSBillingRule`

---

### `device_orders`

Handles internal device order requests.

Main features:

- Order list
- New order request
- Order detail
- Approval
- Rejection
- Cancellation
- Fulfillment

Important model:

- `DeviceOrder`

---

### `support`

Handles user support tickets.

Main features:

- Create ticket
- User ticket list
- Ticket detail
- Admin ticket list
- Admin ticket detail
- Ticket messages

Important models:

- `Ticket`
- `TicketMessage`

---

### `notifications`

Handles in-app notifications.

Main features:

- Notification list
- Dropdown notifications
- Mark single notification as read
- Mark all notifications as read
- Unread count endpoint

Important model:

- `Notification`

---

### `api`

Handles REST API access.

Main features:

- JWT authenticated API
- Swagger docs
- OpenAPI schema
- Device endpoints
- Customer endpoints
- Sales endpoints
- Transactions endpoints
- Inventory endpoints
- Billing endpoints
- Support endpoints

API docs are available at:

```text
/api/docs/
```

OpenAPI schema is available at:

```text
/api/schema/
```

Human-readable endpoint instructions are available at:

```text
/api/instructions/
```

---

## Architecture

High-level request flow:

```text
Browser
  ↓
Django URL router
  ↓
Django views / class-based views
  ↓
Access control + organization filtering
  ↓
Django ORM
  ↓
PostgreSQL / SQLite
```

HTMX is used mainly for interactive tables and partial page updates.

Django Channels is used for websocket functionality.

Celery is used for scheduled background jobs.

Redis is used for:

- Celery broker
- Django cache
- Channels layer

---

## Database Design

The project uses more than one database configuration.

Current settings include:

```python
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / config("DB_NAME_INTERNAL"),
    },
    "coords": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": config("DB_NAME_COORDS"),
        "USER": config("DB_USER_COORDS"),
        "PASSWORD": config("DB_PASSWORD_COORDS"),
        "HOST": config("DB_HOST_COORDS"),
        "PORT": config("DB_PORT_COORDS"),
    },
}
```

The current database router is:

```python
powerpay_v2.routers.CoordsRouter
```

The router sends reads and writes to the `coords` database and selectively allows migrations.

### Managed Tables

These models are intended to be managed by Django migrations:

- `accounts`
- `notifications`
- `support`
- `auth`
- `contenttypes`
- `sessions`
- `admin`
- `django_celery_beat`
- `paygo`
- `billing`
- `devices.DeviceCommandSchedule`

### Existing / Unmanaged Tables

These apps contain models mapped to existing tables:

- `organizations`
- `transactions`
- `customers`
- `sales`
- `inventory`
- several device data tables

Many of these models use:

```python
managed = False
```

That means Django will not create, alter, or delete those database tables through migrations.

---

## User Roles and Access Control

The custom user model supports these roles:

```text
superadmin
admin
staff
support
```

### Superuser / Superadmin

Can access broader platform functions, including:

- All organizations
- All devices
- Organization management
- Warehouse management
- Superuser-only exports
- Device testing exports
- Billing administration
- SaaS billing rules

### Admin

Typically has elevated organization-level permissions.

### Staff

Typically works within assigned organization access.

### Support

Used for support-oriented workflows.

### Organization Access

Device and business data visibility is based on:

1. The user's primary organization
2. Organization access relationships
3. Device many-to-many organization visibility
4. Organization app access permissions

The project supports both:

- legacy device ownership through `DeviceInfo.organization`
- newer multi-organization visibility through `DeviceInfo.organizations`

---

## Main Workflows

### 1. Authentication Workflow

```text
User visits login page
  ↓
User enters email/password
  ↓
OTP may be required
  ↓
User verifies OTP
  ↓
User accepts terms if required
  ↓
User enters dashboard
```

Important routes:

```text
/accounts/login/
/accounts/verify-otp/
/accounts/resend-otp/
/accounts/profile/
/accounts/invite/
/accounts/accept-invite/<token>/
/accounts/password-reset/
```

---

### 2. Device Management Workflow

```text
Create or import devices
  ↓
Assign devices to one or more organizations
  ↓
View devices
  ↓
Change active/inactive status
  ↓
Schedule ON/OFF commands
  ↓
Track live data and energy usage
```

Important routes:

```text
/devices/
/devices/create/
/devices/bulk-create/
/devices/<deviceid>/
/devices/edit/<deviceid>/
/devices/delete/<deviceid>/
/devices/live/<deviceid>/
```

---

### 3. Device Schedule Workflow

```text
Create command schedule
  ↓
Select ON or OFF
  ↓
Select devices
  ↓
Set scheduled time
  ↓
Celery task or manual trigger sends command
  ↓
Schedule marked executed
```

Important routes:

```text
/devices/schedules/
/devices/schedules/add/
/devices/schedules/<id>/edit/
/devices/schedules/<id>/delete/
/devices/schedules/<id>/trigger/
```

The schedule list supports pagination and items-per-page selection.

Supported page sizes:

```text
10
25
50
100
```

---

### 4. Device Testing Batch Workflow

Testing batches digitize the manual process of selecting devices, testing them, packing them, and dispatching them.

```text
Devices are added to the system
  ↓
Create testing batch
  ↓
Choose devices for the current batch
  ↓
Tick Test 1 and Test 2 per device
  ↓
Pack devices that passed both tests
  ↓
Batch becomes ready for dispatch
  ↓
Dispatch batch
  ↓
Dispatch is recorded under the logged-in user
```

Important routes:

```text
/devices/testing-batches/
/devices/testing-batches/create/
/devices/testing-batches/<id>/
/devices/testing-batches/<id>/update-results/
/devices/testing-batches/<id>/dispatch/
/devices/testing-batches/<id>/dispatch-detail/
/devices/testing-batches/<id>/delete/
```

Testing batch statuses:

```text
open
in_progress
ready
dispatched
```

A device in a batch is ready for dispatch only when:

```text
Test 1 passed
Test 2 passed
Packed
```

The batch is ready for dispatch only when every device in the batch is ready.

Testing batches do not require a direct organization field. Access is based on:

- batch creator
- devices in organizations the user can access
- superuser/superadmin permissions

---

### 5. Inventory Workflow

Inventory supports two item types.

#### Unique Items

Unique items represent individually tracked physical assets.

Example:

```text
SM-001 | Smart Meter | Unique | Qty 1 | Warehouse A
```

Rules:

- One serial number represents one physical item.
- Quantity is always `1`.
- The item moves as a whole unit.

#### Shared Items

Shared items represent quantity-based stock that may share the same serial number across warehouses.

Example:

```text
RES-100 | Resistor | Shared | Qty 2 | Warehouse A
RES-100 | Resistor | Shared | Qty 3 | Warehouse B
```

Rules:

- Same serial number can exist in more than one warehouse.
- Quantity can be partially moved.
- Moving shared stock subtracts from the source warehouse and adds to the destination warehouse.

Important routes:

```text
/inventory/
/inventory/items/add/
/inventory/items/bulk-add/
/inventory/items/<id>/
/inventory/items/<id>/edit/
/inventory/items/<id>/delete/
/inventory/items/<id>/move/
/inventory/items/bulk-move/
/inventory/warehouses/
/inventory/warehouses/add/
```

---

### 6. Customer and Sales Workflow

```text
Create customer
  ↓
Create sale linked to customer
  ↓
Track product details and purchase mode
  ↓
Generate receipt PDF
  ↓
Email receipt if needed
```

Important customer routes:

```text
/customers/
/customers/new/
/customers/<id>/
/customers/<id>/edit/
/customers/<id>/delete/
```

Important sales routes:

```text
/sales/
/sales/new/
/sales/<id>/
/sales/<id>/edit/
/sales/<id>/delete
/sales/<id>/receipt/pdf/
/sales/<id>/receipt/email/
/sales/search/
```

---

### 7. Billing Workflow

```text
Create invoice
  ↓
Add invoice items
  ↓
Send invoice
  ↓
Generate PDF
  ↓
Sync or create receipt
  ↓
Generate receipt PDF
```

Billing supports:

- Hardware invoices
- SaaS invoices
- Receipts
- SaaS billing automation rules

Important routes:

```text
/billing/invoices
/billing/invoices/create/hardware/
/billing/invoices/create/saas/
/billing/invoice/<id>/
/billing/invoice/<id>/edit/
/billing/invoice/<id>/delete/
/billing/invoice/<id>/send/
/billing/invoice/<id>/pdf/
/billing/receipts/
/billing/receipts/sync/
/billing/receipt/<id>/
/billing/receipt/<id>/pdf/
/billing/saas-rules/
/billing/saas-rules/create/
/billing/saas-rules/<id>/edit/
/billing/saas-rules/<id>/delete/
/billing/saas-rules/<id>/run-now/
/billing/saas-rules/run-due/
```

---

### 8. Import Workflow

The import center supports:

- Customer and sales import
- Transaction import

Important routes:

```text
/import/
/import-cs/upload/
/import-tx/upload/
```

Customer/sales imports support CSV and Excel files.

Transaction imports support CSV and Excel files.

---

### 9. Export Workflow

The export center supports CSV and Excel exports.

Important routes:

```text
/export/
/export/count/
```

Exportable datasets include:

- Device Info
- Device Data
- Customers
- Sales
- Transactions
- Inventory
- Organizations
- Support Tickets
- Users
- Device Testing Batches
- Device Testing Batch Items
- Device Batch Dispatches

Device testing batch exports are restricted to Django superusers only.

---

## REST API

Base API path:

```text
/api/
```

Authentication is JWT-based.

Token routes:

```text
/accounts/api/token/
/accounts/api/token/refresh/
```

API documentation:

```text
/api/docs/
/api/schema/
/api/instructions/
```

Main API groups:

```text
/api/devices/info/<deviceid>/
/api/devices/<deviceid>/status/
/api/devices/<deviceid>/activate/
/api/devices/<deviceid>/deactivate/
/api/devices/data/
/api/devices/data/<deviceid>/
/api/device-schedules/
/api/track-kwh/
/api/customers/
/api/sales/
/api/transactions/
/api/organizations/
/api/organization-access/
/api/organization-app-access/
/api/warehouses/
/api/inventory-items/
/api/inventory-movements/
/api/invoices/
/api/invoice-items/
/api/receipts/
/api/saas-billing-rules/
/api/paygo-settings/
/api/tickets/
/api/ticket-messages/
/api/devices/wallet/link/
/api/devices/wallet/<deviceid>/
```

Example JWT request:

```bash
curl -X POST http://127.0.0.1:8000/accounts/api/token/ \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@example.com", "password": "your-password"}'
```

Example authenticated API request:

```bash
curl http://127.0.0.1:8000/api/customers/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

---

## Local Development Setup

### 1. Clone the repository

```bash
git clone <repository-url>
cd powerpay_v2
```

### 2. Create a virtual environment

```bash
python -m venv venv
```

Activate it.

Linux/macOS:

```bash
source venv/bin/activate
```

Windows PowerShell:

```powershell
venv\Scripts\Activate.ps1
```

Windows CMD:

```cmd
venv\Scripts\activate.bat
```

### 3. Install Python dependencies

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Install frontend dependencies

```bash
npm install
```

### 5. Create `.env`

Create a `.env` file in the project root.

Use the template below and replace the values.

```env
# Internal DB
DB_NAME_INTERNAL=db.sqlite3

# PowerPay DB
DB_NAME_POWERPAY=your_powerpay_db
DB_USER_POWERPAY=your_powerpay_user
DB_PASSWORD_POWERPAY=your_powerpay_password
DB_HOST_POWERPAY=localhost
DB_PORT_POWERPAY=5432

# Coords DB
DB_NAME_COORDS=your_coords_db
DB_USER_COORDS=your_coords_user
DB_PASSWORD_COORDS=your_coords_password
DB_HOST_COORDS=localhost
DB_PORT_COORDS=5432

# Mpesa DB
DB_NAME_MPESA=your_mpesa_db
DB_USER_MPESA=your_mpesa_user
DB_PASSWORD_MPESA=your_mpesa_password
DB_HOST_MPESA=localhost
DB_PORT_MPESA=5432
MPESA_ENDPOINT=https://example.com/mpesa-endpoint

# Email
EMAIL_HOST=smtp.example.com
EMAIL_PORT=587
EMAIL_HOST_USER=your_email@example.com
EMAIL_HOST_PASSWORD=your_email_password
DEFAULT_FROM_EMAIL=your_email@example.com
SERVER_EMAIL=your_email@example.com

# MQTT
MQTT_BROKER=your_mqtt_host
MQTT_PORT=1883
MQTT_USER=your_mqtt_user
MQTT_PASSWORD=your_mqtt_password
MQTT_TOPIC=your/topic
```

### 6. Start Redis

Redis is required for:

- Celery
- Django cache
- Channels

Linux:

```bash
redis-server
```

Docker:

```bash
docker run --name powerpay-redis -p 6379:6379 -d redis:7
```

### 7. Apply migrations

```bash
python manage.py migrate
```

Important: because the project uses database routing and several unmanaged models, migrations will not create every table. Existing operational tables such as customers, sales, organizations, transactions, and inventory are expected to exist already.

### 8. Create a superuser

```bash
python manage.py createsuperuser
```

### 9. Run the development server

```bash
python manage.py runserver
```

Visit:

```text
http://127.0.0.1:8000/
```

---

## Environment Variables

| Variable | Purpose |
|---|---|
| `DB_NAME_INTERNAL` | SQLite/default database file name |
| `DB_NAME_POWERPAY` | PowerPay database name |
| `DB_USER_POWERPAY` | PowerPay database user |
| `DB_PASSWORD_POWERPAY` | PowerPay database password |
| `DB_HOST_POWERPAY` | PowerPay database host |
| `DB_PORT_POWERPAY` | PowerPay database port |
| `DB_NAME_COORDS` | Main PostgreSQL database name used by router |
| `DB_USER_COORDS` | Main PostgreSQL database user |
| `DB_PASSWORD_COORDS` | Main PostgreSQL database password |
| `DB_HOST_COORDS` | Main PostgreSQL database host |
| `DB_PORT_COORDS` | Main PostgreSQL database port |
| `DB_NAME_MPESA` | M-Pesa database name |
| `DB_USER_MPESA` | M-Pesa database user |
| `DB_PASSWORD_MPESA` | M-Pesa database password |
| `DB_HOST_MPESA` | M-Pesa database host |
| `DB_PORT_MPESA` | M-Pesa database port |
| `MPESA_ENDPOINT` | M-Pesa endpoint URL |
| `EMAIL_HOST` | SMTP host |
| `EMAIL_PORT` | SMTP port |
| `EMAIL_HOST_USER` | SMTP username |
| `EMAIL_HOST_PASSWORD` | SMTP password |
| `DEFAULT_FROM_EMAIL` | Default sender email |
| `SERVER_EMAIL` | Server sender email |
| `MQTT_BROKER` | MQTT broker host |
| `MQTT_PORT` | MQTT broker port |
| `MQTT_USER` | MQTT username |
| `MQTT_PASSWORD` | MQTT password |
| `MQTT_TOPIC` | MQTT topic |

Recommended production additions:

```env
SECRET_KEY=your-production-secret-key
DEBUG=False
ALLOWED_HOSTS=your-domain.com,www.your-domain.com
CSRF_TRUSTED_ORIGINS=https://your-domain.com
SITE_URL=https://your-domain.com
```

The current settings file still has some values hardcoded. For production, move secrets and deployment-specific values into environment variables.

---

## Database Setup Notes

The project uses a mixture of managed Django tables and existing operational tables.

### Managed tables

Managed tables can be created and updated using:

```bash
python manage.py migrate
```

Examples include:

- users and authentication tables
- notifications
- support tickets
- billing tables
- PayGo settings
- device command schedules
- selected device testing batch tables, depending on your router/migration configuration

### Unmanaged tables

Several models map to existing database tables and are marked with:

```python
managed = False
```

These tables must already exist in your database. Django migrations will not create or change them automatically.

Examples include:

- organizations
- organization access tables
- customers
- sales
- transactions
- warehouses
- inventory items
- inventory movements
- device energy data
- device activity data
- device wallet map

### Device testing batches

Device testing batches are part of the `devices` app. They support:

- selecting devices into a testing batch
- ticking Test 1 and Test 2 results
- marking passed devices as packed
- dispatching a ready batch
- recording dispatch under the logged-in user

If migrations are not allowed for the devices app in your database router, create or update the testing batch tables manually using your database administration workflow.

### Inventory shared quantity support

Inventory supports both unique and shared stock:

- **Unique items** have a globally unique serial number and quantity `1`.
- **Shared items** can use the same serial number in different warehouses with separate quantities.

Shared item movement requires the movement table to track the quantity moved. If your existing inventory schema does not include this, update it through your database administration workflow.

---

## Running the Project

### Development server

```bash
python manage.py runserver
```

### Django shell

```bash
python manage.py shell
```

### Create superuser

```bash
python manage.py createsuperuser
```

### Check project configuration

```bash
python manage.py check
```

### Collect static files

```bash
python manage.py collectstatic --noinput
```

---

## Background Workers

### Start Redis

```bash
redis-server
```

or:

```bash
docker run --name powerpay-redis -p 6379:6379 -d redis:7
```

### Start Celery worker

```bash
celery -A powerpay_v2 worker -l info
```

### Start Celery beat

```bash
celery -A powerpay_v2 beat -l info
```

The project uses:

```python
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"
```

### Important Celery tasks

Device schedules:

```python
devices.tasks.run_pending_device_schedules
```

Billing automation:

```python
billing.tasks.run_due_saas_billing_rules
```

Dashboard caching:

```python
core.tasks.cache_dashboard_superadmin
core.tasks.cache_dashboard_for_user
core.tasks.refresh_all_org_dashboards
```

---

## Static Assets and Frontend

The project uses Tailwind CSS and DaisyUI.

Install frontend dependencies:

```bash
npm install
```

Important frontend packages:

```text
tailwindcss
daisyui
flowbite
```

Static files are located in:

```text
static/
```

Shared templates are located in:

```text
templates/
templates/partials/
```

App-specific templates are located inside each app:

```text
devices/templates/devices/
inventory/templates/inventory/
billing/templates/billing/
core/templates/core/
```

---

## Import and Export Center

### Import Center

Route:

```text
/import/
```

Supports:

- customer/sales import
- transaction import

Accepted file types:

```text
.csv
.xlsx
.xls
```

### Export Center

Route:

```text
/export/
```

Supports:

```text
CSV
Excel
```

Export counts are loaded through:

```text
/export/count/
```

Non-superadmins are restricted to organization-scoped data.

Device testing exports are visible only to Django superusers.

---

## Testing

Run all tests:

```bash
python manage.py test
```

Run tests for one app:

```bash
python manage.py test devices
```

Run Django system checks:

```bash
python manage.py check
```

Check migrations:

```bash
python manage.py makemigrations --check --dry-run
```

Because many models map to existing unmanaged tables, tests may require a test database that includes those tables or mocked data.

---

## Deployment Notes

Recommended deployment stack:

```text
Nginx
Gunicorn or Daphne
PostgreSQL
Redis
Celery Worker
Celery Beat
```

For normal HTTP-only deployment, Gunicorn is enough.

For websocket support, use Daphne or another ASGI server.

Example Gunicorn command:

```bash
gunicorn powerpay_v2.wsgi:application --bind 0.0.0.0:8000
```

Example Daphne command:

```bash
daphne -b 0.0.0.0 -p 8001 powerpay_v2.asgi:application
```

Recommended production checklist:

```bash
python manage.py check --deploy
python manage.py collectstatic --noinput
python manage.py migrate --noinput
```

Remember that unmanaged tables still need manual database setup outside Django migrations.

---

## Security Checklist

Before production deployment:

- Move `SECRET_KEY` to environment variables.
- Set `DEBUG=False`.
- Configure `ALLOWED_HOSTS`.
- Configure `CSRF_TRUSTED_ORIGINS`.
- Do not commit `.env`.
- Do not commit database files.
- Do not commit `node_modules`.
- Use strong database passwords.
- Use HTTPS.
- Use secure cookies.
- Restrict admin access.
- Review superuser-only export permissions.
- Review API permissions.
- Review wallet-link permissions.
- Run Django's deployment checks before going live.

Recommended production settings:

```python
DEBUG = False

SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_SSL_REDIRECT = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
```

---

## Troubleshooting

### `relation does not exist`

This usually means an unmanaged table has not been created.

Check whether the related model has:

```python
managed = False
```

If yes, create the required table through your normal database administration process.

---

### Device testing batch tables are missing

Create them manually through your database administration workflow, or update the database router to allow migrations for the testing batch models.

---

### Device schedules do not execute

Check that Redis, Celery worker, and Celery beat are running:

```bash
redis-server
celery -A powerpay_v2 worker -l info
celery -A powerpay_v2 beat -l info
```

Also confirm that the Celery beat schedule includes the device schedule task if you expect it to run automatically.

---

### Websockets do not connect

Check:

- Redis is running.
- ASGI server is being used.
- Channels layer is configured.
- Websocket URL routing exists in `devices.routing`.
- Reverse proxy supports websocket upgrade headers.

---

### API returns unauthorized

Check:

- JWT token is present.
- Token has not expired.
- User belongs to the correct organization.
- Device/customer/sale belongs to an accessible organization.
- Endpoint is not superuser-only.

---

### Exports are missing some options

Some export types are superuser-only.

Device testing exports are visible only to Django superusers:

```text
Device Testing Batches
Device Testing Batch Items
Device Batch Dispatches
```

---

### Inventory movement fails

Check that the inventory movement schema supports quantity movement for shared stock.

If the project is using shared inventory quantities, the movement table must be able to record how many units were moved.

---

## Repository Hygiene

Recommended files to keep out of version control:

```text
.env
db.sqlite3
*.sqlite3
media/
node_modules/
__pycache__/
*.pyc
celerybeat-schedule*
```

Recommended files to keep in version control:

```text
manage.py
requirements.txt
package.json
package-lock.json
README.md
```

If `manage.py`, `package.json`, or `package-lock.json` are ignored in `.gitignore`, consider removing those entries so the project can be cloned and installed reliably.

---

## Useful Commands

```bash
# Activate environment
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run server
python manage.py runserver

# Run checks
python manage.py check

# Run tests
python manage.py test

# Make migrations
python manage.py makemigrations

# Apply migrations
python manage.py migrate

# Collect static
python manage.py collectstatic --noinput

# Create superuser
python manage.py createsuperuser

# Celery worker
celery -A powerpay_v2 worker -l info

# Celery beat
celery -A powerpay_v2 beat -l info

# Daphne ASGI server
daphne powerpay_v2.asgi:application
```

---

## Summary

PowerPay Africa is a modular Django platform for managing energy-business operations across devices, customers, sales, inventory, transactions, billing, support, and analytics.

The project is designed around:

- multi-organization access
- device operations
- PayGo workflows
- warehouse and inventory control
- device testing and dispatch workflows
- billing automation
- exports and reporting
- API integrations
- scalable operational dashboards
