# PowerPay API endpoint instructions

Base path: `/api/`

Authentication: all business endpoints require an authenticated user. Most endpoints are scoped to the authenticated user's visible organizations. Device visibility supports both the legacy `organization_id` relationship and the new device `organizations` many-to-many access table.

Interactive documentation:

- Swagger UI: `/api/docs/`
- OpenAPI schema: `/api/schema/`
- Human-readable endpoint catalogue: `/api/instructions/`

## Endpoint summary

| Method | Endpoint | What it does | Access notes |
|---|---|---|---|
| GET | `/api/instructions/` | Returns this endpoint catalogue as JSON. | Authenticated users. |
| GET | `/api/schema/` | Machine-readable OpenAPI schema. | Depends on project schema settings. |
| GET | `/api/docs/` | Swagger UI for exploring and testing endpoints. | Depends on project schema settings. |
| GET | `/api/devices/info/{deviceid}/` | Returns one device by device ID, including active status, main org, and orgs that can view it. | Device must be visible to the user. |
| POST | `/api/devices/{deviceid}/status/` | Activates or deactivates one device. Body: `{"active": true}` or `{"action": "activate"}`. | Device must be visible to the user. |
| POST | `/api/devices/{deviceid}/activate/` | Activates one device. | Device must be visible to the user. |
| POST | `/api/devices/{deviceid}/deactivate/` | Deactivates one device. | Device must be visible to the user. |
| GET | `/api/devices/data/` | Lists aggregated kWh data grouped by device. Query params: `deviceid`, `time_start`, `time_end`. | Limited to visible devices. |
| GET | `/api/devices/data/{deviceid}/` | Gets aggregated kWh data for one device. Query params: `time_start`, `time_end`. | Device must be visible to the user. |
| GET, POST | `/api/device-schedules/` | Lists or creates ON/OFF device schedules. POST requires `action`, `devices`, `scheduled_time`. | Devices must be visible to the user. |
| GET | `/api/device-schedules/{id}/` | Gets one device schedule. | Schedule org must be visible to the user. |
| GET | `/api/track-kwh/` | Lists latest tracked kWh records. | Limited to visible devices. |
| GET | `/api/track-kwh/{id}/` | Gets one tracked kWh record. | Limited to visible devices. |
| GET | `/api/customers/` | Lists customers. Query params: `id_number`, `phone_number`. | Organization-scoped. |
| GET | `/api/sales/` | Lists sales. Query params: `product_serial_number`, `time_start`, `time_end`. | Organization-scoped. |
| GET | `/api/transactions/` | Lists transactions. Query params: `ref`, `txn_id`. | Organization-scoped. |
| GET | `/api/organizations/` | Lists organizations. | Django superusers only. |
| GET | `/api/organizations/{id}/` | Gets one organization. | Django superusers only. |
| GET | `/api/organization-access/` | Lists organization visibility relationships. | Django superusers only. |
| GET | `/api/organization-app-access/` | Lists app/module access enabled for organizations. | Django superusers only. |
| GET | `/api/warehouses/` | Lists warehouses. | Organization-scoped. |
| GET | `/api/warehouses/{id}/` | Gets one warehouse. | Organization-scoped. |
| GET | `/api/inventory-items/` | Lists inventory items. Query params: `serial_number`, `product_type`. | Limited to visible warehouses. |
| GET | `/api/inventory-items/{id}/` | Gets one inventory item. | Limited to visible warehouses. |
| GET | `/api/inventory-movements/` | Lists inventory movement history. | Limited to visible warehouses/inventory. |
| GET | `/api/inventory-movements/{id}/` | Gets one inventory movement. | Limited to visible warehouses/inventory. |
| GET | `/api/invoices/` | Lists hardware and SaaS invoices. | Organization-scoped. |
| GET | `/api/invoices/{id}/` | Gets one invoice. | Organization-scoped. |
| GET | `/api/invoice-items/` | Lists invoice line items. | Scoped through invoice organization. |
| GET | `/api/invoice-items/{id}/` | Gets one invoice line item. | Scoped through invoice organization. |
| GET | `/api/receipts/` | Lists receipts linked to visible invoices or transactions. | Organization-scoped. |
| GET | `/api/receipts/{id}/` | Gets one receipt. | Organization-scoped. |
| GET | `/api/saas-billing-rules/` | Lists SaaS billing rules. | Organization-scoped; read-only API. |
| GET | `/api/saas-billing-rules/{id}/` | Gets one SaaS billing rule. | Organization-scoped; read-only API. |
| GET | `/api/paygo-settings/` | Lists PayGo settings for visible sales. | Organization-scoped through sale. |
| GET | `/api/paygo-settings/{id}/` | Gets one PayGo setting. | Organization-scoped through sale. |
| GET | `/api/tickets/` | Lists support tickets. | Scoped by ticket user's organization. |
| GET | `/api/tickets/{id}/` | Gets one support ticket. | Scoped by ticket user's organization. |
| GET | `/api/ticket-messages/` | Lists support ticket messages. | Scoped through ticket organization. |
| GET | `/api/ticket-messages/{id}/` | Gets one ticket message. | Scoped through ticket organization. |
| GET | `/api/devices/wallet/{deviceid}/` | Checks if a device has a linked blockchain wallet. | Only superusers, `role=superadmin`, and user `id=17`. |
| POST | `/api/devices/wallet/link/` | Creates or updates a device wallet linkage. Body: `deviceid`, `wallet_address`. | Only superusers, `role=superadmin`, and user `id=17`. |

## Device status examples

Activate with explicit status:

```json
{
  "active": true
}
```

Deactivate with action:

```json
{
  "action": "deactivate"
}
```

## Device schedule example

```json
{
  "action": "ON",
  "devices": ["NEOPRS000001", "NEOPRS000002"],
  "scheduled_time": "2026-05-14T09:00:00+03:00"
}
```

Superadmins may also send `organization` if they want to force the schedule to belong to a specific organization.

## Wallet linkage example

```json
{
  "deviceid": "NEOPRS000001",
  "wallet_address": "0x1234567890abcdef..."
}
```
