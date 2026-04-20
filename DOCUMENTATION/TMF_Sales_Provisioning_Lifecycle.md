# TMF Sales & Provisioning Lifecycle

## Overview

This document describes the end-to-end lifecycle from product configuration through sale, provisioning, and service activation in the TMF-native Odoo platform.

## Architecture

```
ProductOffering (product.template)
  └─ ProductSpecification (tmf.product.specification)
       ├─ ServiceSpecification (tmf.service.specification)
       └─ ResourceSpecification (tmf.resource.specification)
```

### Key Models

| TMF Standard | Odoo Model | Purpose |
|--------------|-----------|---------|
| TMF620 ProductSpecification | `tmf.product.specification` | Blueprint linking services and resources |
| TMF633 ServiceSpecification | `tmf.service.specification` | Defines what gets provisioned |
| TMF634 ResourceSpecification | `tmf.resource.specification` | Defines required devices/assets |
| TMF620 ProductOffering | `product.template` | What the salesperson sells (with price) |
| TMF666 PartyAccount | `tmf.account` | Customer account holding services |
| TMF666 BillingAccount | `tmf.account` | Billing relationship |
| TMF638 Service | `tmf.service` | Instance of a provisioned service |
| TMF622 ProductOrder | `sale.order` | Commercial order |

## Customer-Account-Service Hierarchy

```
Party (res.partner) — e.g., "Empresa Demo SpA" (RUT 76086428-5)
  ├─ PartyAccount: "Casa Matriz - Santiago"
  │    ├─ BillingAccount
  │    ├─ Service: Internet 500Mbps (active)
  │    ├─ Service: TV Full HD 120ch (active)
  │    └─ Service: Telefonia Fija (active)
  ├─ PartyAccount: "Sucursal Viña del Mar"
  │    ├─ BillingAccount
  │    ├─ Service: Internet 200Mbps (active)
  │    └─ Service: Movil 50GB (active)
  └─ PartyAccount: "Oficina Digital (Remoto)"
       ├─ BillingAccount
       ├─ Service: Pack Streaming Premium (active)
       └─ Service: Movil 50GB (active)
```

One Party (RUT) can have multiple Accounts. Each Account can have owners and tenants. Services are linked to Accounts, not directly to the Party.

## Provisioning Lifecycle

### TMF638 Service State Machine

```
feasabilityChecked → designed → reserved → inactive → active
```

### End-to-End Flow

1. **Catalog Setup** (one-time)
   - Create ServiceSpecification (e.g., "Internet Access CFS")
   - Create ResourceSpecification (e.g., "GPON ONT HG8245H")
   - Create ProductSpecification linking both
   - Create ProductOffering (product.template) with price, linked to spec

2. **Sale** (per customer)
   - Salesperson creates a Sale Order
   - Selects Customer and TMF Account (or account is auto-created)
   - Adds products to order lines
   - Confirms the order

3. **Auto-Provisioning** (bridge module: `tmf_bridge_provisioning`)
   - On order confirmation (draft → sale):
     - Finds or creates a PartyAccount for the customer
     - For each order line with a ProductSpecification:
       - Reads linked ServiceSpecifications
       - Creates `tmf.service` records in `feasabilityChecked` state
       - Links services to the Account and Partner

4. **OSS Provisioning** (external or mock)
   - Polls TMF638 API for services in non-terminal states
   - Advances each service one step per cycle
   - `feasabilityChecked → designed → reserved → inactive → active`

5. **Active Service**
   - Service appears in Customer Portfolio tab on the partner form
   - Visible via TMF638 API for external systems
   - Linked to supporting resources (devices) and billing accounts

## Modules Involved

| Module | Role |
|--------|------|
| `tmf_product_catalog` | ProductSpecification, ProductOffering |
| `tmf_service_catalog` | ServiceSpecification |
| `tmf_resource_catalog` | ResourceSpecification |
| `tmfc001_wiring` | Cross-API links (Spec → ServiceSpec → ResourceSpec) |
| `tmf_bridge_provisioning` | Auto-create services on sale confirmation |
| `tmf_account` | TMF666 Account Management |
| `tmf_service_inventory` | TMF638 Service records |
| `tmf_sales_dashboard` | Customer Portfolio view (accounts + services) |
| `mock_oss/` | Standalone mock OSS provisioner |

## Mock OSS Provisioner

Standalone Python script (zero dependencies) that simulates an external OSS system.

```bash
# Default: localhost:8069, 10s poll
python mock_oss/oss_provisioner.py

# Single pass
python mock_oss/oss_provisioner.py --once

# Docker
docker build -t mock-oss mock_oss/
docker run --rm mock-oss
```

## Demo Data Seed Script

Creates a complete demo scenario via XML-RPC:

```bash
python mock_oss/seed_demo_data.py --host localhost --port 8069
```

Creates:
- 1 Customer (Empresa Demo SpA)
- 3 Accounts with different addresses
- 5 service types (Internet, TV, Voice, Mobile, OTT)
- Product Specifications with linked Service + Resource specs
- Product Offerings with prices
- Sale Orders per account (auto-confirmed)
- Device resources linked to services

## TMF Account on Sale Order

The `tmf_bridge_provisioning` module adds a **TMF Account** field to the sale order form. This allows salespersons to select which account to provision against:

- If an account is selected → services are linked to that account
- If left empty → a default PartyAccount is auto-created for the customer
- The field is filtered to show only PartyAccounts belonging to the selected customer
