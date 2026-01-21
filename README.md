# PowerPay Africa – Management Platform

A full-stack **Django-based management platform** for managing **customers, sales, devices, inventory, warehouses, transactions, and analytics**, designed for PayGo / energy / asset-based businesses.

The system supports **multi-organization access**, **role-based permissions**, **HTMX-powered interactivity**, and **rich analytics dashboards**.

---

## Table of Contents

- [Overview](#overview)
- [Key Features](#key-features)
- [Technology Stack](#technology-stack)
- [System Architecture](#system-architecture)
- [User Roles & Permissions](#user-roles--permissions)
- [Core Modules](#core-modules)
- [UI & UX](#ui--ux)
- [Charts & Analytics](#charts--analytics)
- [HTMX Usage](#htmx-usage)
- [Database Models (High Level)](#database-models-high-level)
- [Installation & Setup](#installation--setup)
- [Environment Variables](#environment-variables)
- [Running the Project](#running-the-project)
- [Project Structure](#project-structure)
- [Deployment Tips](#deployment-tips)
- [Contact](#contact)

---

## Overview

**PowerPay Africa** is a modular management system built to track:

- Customers and their sales
- Inventory items and warehouse movement
- Devices linked to customers
- Transactions and payments
- Organization-level data isolation
- Growth and performance metrics over time

The platform emphasizes:
- **Speed** (HTMX partial updates)
- **Clarity** (clean UI and sortable tables)
- **Scalability** (organization-based filtering)
- **Operational insight** (charts & KPIs)

---

## Key Features

- 🔐 Role-based access control
- 🏢 Multi-organization support
- 📦 Inventory & warehouse tracking
- 💰 Sales and transaction management
- 👥 Customer lifecycle management
- 📊 Charts and cumulative growth analytics
- ⚡ HTMX-powered search, sort & pagination
- 📱 Responsive sidebar with mobile support
- 🎨 Tailwind CSS + DaisyUI styling

---

## Technology Stack

### Backend
- Python 3
- Django
- PostgreSQL
- Django ORM
- Django authentication & permissions

### Frontend
- HTMX
- Tailwind CSS
- DaisyUI
- Font Awesome

### Charts & Analytics
- Chart.js
- chartjs-plugin-datalabels

---

## System Architecture
Browser
├── HTMX Requests (partial updates)
├── Full Page Requests
↓
Django Views
├── Role & Organization filtering
├── Aggregations & annotations
↓
Django ORM
↓
PostgreSQL

HTMX is used for **tables only**, while pages load normally to preserve URLs, browser history, and SEO.

---

## User Roles & Permissions

### Superuser
- Access to all organizations
- Manage inventory & warehouses
- Full analytics visibility
- Data migration & admin tasks

### Standard User
- Restricted to their organization
- Manage customers, sales, devices, and transactions
- Scoped access to inventory data

Permissions are enforced at the **queryset level**.

---

## Core Modules

### Dashboard
- High-level KPIs
- Growth charts
- Quick navigation to key sections

### Customers
- Searchable & sortable customer list
- Customer detail page
- Gender distribution chart
- Customer growth chart (monthly cumulative, all-time)
- Linked sales & devices

### Sales
- Sales table with search, sort & pagination
- HTMX-powered interactions
- Customer & sales rep linkage
- Monthly cumulative sales growth
- Sales distribution charts

### Inventory
- Inventory item tracking
- Organization-aware filtering
- Search, sort & pagination
- Days-in-warehouse calculations
- Inventory growth charts
- Inventory per warehouse distribution

### Warehouses
- Warehouse management (superusers only)
- Inventory distribution per warehouse
- Inventory movement tracking

### Devices
- Device listing
- Customer association
- Status & activity tracking

### Transactions
- Transaction history
- Time-series charts
- Excel export support

---

## UI & UX

- Collapsible desktop sidebar
- Responsive mobile sidebar
- No horizontal scrolling
- Consistent table styling
- Visual sorting indicators
- HTMX loading states

---

## Charts & Analytics

All charts are built using **Chart.js**:
- Line charts for growth over time
- Doughnut charts for distributions
- Monthly aggregation via `TruncMonth`
- Server-side cumulative totals

---

## HTMX Usage

HTMX is used for:
- Table search
- Sorting
- Pagination
- Partial page updates

### Benefits
- Faster UX
- Minimal JavaScript
- Clean Django templates
- URL state preserved

---

## Database Models (High Level)

### Core Models
- Organization
- User
- Customer
- Sale
- Transaction
- Device
- InventoryItem
- Warehouse
- InventoryMovement

### Relationships
- Organization → Users
- Organization → Warehouses
- Customer → Sales
- Sale → Devices
- InventoryItem → Warehouse
- InventoryMovement → InventoryItem

---

## Installation & Setup

### 1. Clone the repository
```bash

git clone https://github.com/Tarimo077/powerpay_v2.git
cd powerpay_v2
```

### 2. Create a virtual environment
```bash

python -m venv venv
source venv/bin/activate
```

### 3. Install dependencies
``` bash

pip install -r requirements.txt
 
```

### 4. Environment Variables
- Create .env file

``` bash
DEBUG=True
SECRET_KEY=************
DATABASE_NAME=**********
DATABASE_USER=************
DATABASE_PASSWORD=********
DATABASE_HOST=***********
DATABASE_PORT=****
```

### 5. Running The Project
```bash
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

- Visit http://127.0.0.1:8000

### Project Structure

powerpay_v2/
├── customers/
├── sales/
├── inventory/
├── warehouses/
├── devices/
├── transactions/
├── support/
├── templates/
│   ├── partials/
│   ├── base.html
│   └── sidebar.html
├── static/
├── manage.py
└── requirements.txt

## 📤 Deployment Tips

- Use `gunicorn` or `daphne` with `pm2` or `supervisor`
- Configure `nginx` as reverse proxy
- Run `collectstatic`
- Set `DEBUG = False` and add allowed hosts

---

## 🙋 Contact

If you have any questions, please open an issue or contact:

- **Jeff Tarimo** — [GitHub](https://github.com/Tarimo077) | [Email](mailto:tarimojeff@gmail.com)