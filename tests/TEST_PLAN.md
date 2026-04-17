# TMF/Odoo TAM Integration Test Plan

## Test Architecture

```
┌─────────────────────────────────────────────────────┐
│                    Test Layers                       │
├──────────────┬──────────────┬───────────────────────┤
│  Layer 1     │  Layer 2     │  Layer 3              │
│  API Unit    │  E2E Flows   │  GUI Validation       │
│  (requests)  │  (scenarios) │  (Selenium/Odoo Tour) │
├──────────────┼──────────────┼───────────────────────┤
│ CRUD per API │ Cross-API    │ Odoo UI actions        │
│ Field valid. │ Bridge sync  │ verify TMF sync       │
│ Error cases  │ Lifecycle    │ Dashboard checks      │
└──────────────┴──────────────┴───────────────────────┘
```

---

## Scenario 1: Customer Onboarding (Engage)

**Goal:** Create a customer with multiple accounts, verify TMF↔Odoo sync

### API Steps
```
1. POST /tmf-api/party/v4/individual
   Body: { givenName: "John", familyName: "Doe", contactMedium: [...] }
   → Verify: res.partner created in Odoo with matching name

2. POST /tmf-api/customerManagement/v4/customer
   Body: { name: "John Doe", engagedParty: { id: "<party_id>" } }
   → Verify: tmf.customer linked to res.partner

3. POST /tmf-api/accountManagement/v4/billingAccount  (Account 1 - Personal)
   Body: { name: "Personal Account", relatedParty: [{ id: "<party_id>" }] }

4. POST /tmf-api/accountManagement/v4/billingAccount  (Account 2 - Business)
   Body: { name: "Business Account", relatedParty: [{ id: "<party_id>" }] }

5. GET /tmf-api/party/v4/individual/<party_id>
   → Verify: both accounts visible in relatedParty or via query
```

### GUI Steps
```
1. Open Odoo → Contacts → search "John Doe"
   → Verify: partner exists with TMF fields populated
2. Check TMF tab on partner form
   → Verify: tmf_id, tmf_status visible
3. Navigate to TMF > Billing Accounts
   → Verify: 2 accounts linked to same partner
```

### Validations
- [ ] Party created with tmf_id (UUID)
- [ ] res.partner auto-created with givenName → name mapping
- [ ] Customer record links to party via engagedParty
- [ ] Both billing accounts reference same party
- [ ] Editing partner name in Odoo UI updates party name via bridge

---

## Scenario 2: Product Catalog Setup (Design)

**Goal:** Create product specifications, offerings, and promotions

### API Steps
```
1. POST /tmf-api/serviceCatalogManagement/v4/serviceSpecification
   Body: { name: "Mobile Data Plan", lifecycleStatus: "Active",
           serviceSpecCharacteristic: [
             { name: "dataAllowance", valueType: "string" },
             { name: "speed", valueType: "string" }
           ] }
   → Verify: product.template created (type=service) via bridge

2. POST /tmf-api/resourceCatalogManagement/v4/resourceSpecification
   Body: { name: "5G SIM Card", lifecycleStatus: "Active" }
   → Verify: product.template created (type=consu) via bridge

3. POST /tmf-api/productCatalogManagement/v4/productOffering
   Body: { name: "5G Unlimited Plan", lifecycleStatus: "Active",
           productSpecification: { id: "<spec_id>" },
           productOfferingPrice: [{
             name: "Monthly Fee", priceType: "recurring",
             price: { amount: 49.99, units: "USD" },
             recurringChargePeriodType: "monthly"
           }] }

4. POST /tmf-api/promotionManagement/v4/promotion
   Body: { name: "First Month Free", lifecycleStatus: "Active",
           pattern: [{ action: { actionType: "discount" } }] }
   → Verify: product.pricelist created via bridge

5. GET /tmf-api/productCatalogManagement/v4/productOffering?lifecycleStatus=Active
   → Verify: offering appears in listing with price
```

### GUI Steps
```
1. Odoo → Sales → Products
   → Verify: "5G Unlimited Plan" product template exists
2. Check product form → TMF tab
   → Verify: product_specification_id linked
3. Odoo → Sales → Pricelists
   → Verify: "First Month Free" pricelist exists
```

### Validations
- [ ] Service spec creates product.template(type=service)
- [ ] Resource spec creates product.template(type=consu)
- [ ] Product offering links to product.template
- [ ] Offering price stored correctly
- [ ] Promotion creates pricelist via bridge
- [ ] All records have @type, id, href in API response

---

## Scenario 3: Order-to-Activate (Fulfill)

**Goal:** Full order lifecycle: quote → cart → order → service activation

### API Steps
```
1. POST /tmf-api/quoteManagement/v4/quote
   Body: { description: "Quote for John",
           quoteItem: [{ productOffering: { id: "<offering_id>" } }],
           relatedParty: [{ id: "<party_id>", role: "Customer" }] }
   → Verify: sale.order created in draft state via bridge

2. POST /tmf-api/shoppingCart/v4/shoppingCart
   Body: { cartItem: [{ productOffering: { id: "<offering_id>" },
                         quantity: 1 }],
           relatedParty: [{ id: "<party_id>" }] }
   → Verify: sale.order (quotation) created via bridge

3. POST /tmf-api/productOrderingManagement/v4/productOrder
   Body: { productOrderItem: [{
             action: "add",
             productOffering: { id: "<offering_id>" },
             product: { productCharacteristic: [
               { name: "dataAllowance", value: "Unlimited" },
               { name: "speed", value: "1Gbps" }
             ] }
           }],
           relatedParty: [{ id: "<party_id>", role: "Customer" }] }
   → Verify: sale.order created and linked

4. PATCH /tmf-api/productOrderingManagement/v4/productOrder/<order_id>
   Body: { state: "acknowledged" }
   → Verify: order state transitions

5. Wait for fulfillment chain:
   → tmfc003_wiring creates tmf.service.order
   → tmfc007_wiring fulfills service order
   → tmf.service record created in service inventory

6. GET /tmf-api/serviceInventory/v4/service?relatedParty.id=<party_id>
   → Verify: active service linked to customer

7. POST /tmf-api/ServiceActivationAndConfiguration/v4/service
   Body: { serviceSpecification: { id: "<service_spec_id>" },
           state: "active" }
   → Verify: serviceDate populated, state=active
```

### GUI Steps
```
1. Odoo → Sales → Orders → find order
   → Verify: order lines match product offering
2. Confirm order in Odoo UI (click "Confirm")
   → Verify: TMF status changes to "inProgress" via API
3. Check TMF > Services
   → Verify: service instance created with correct spec
```

### Validations
- [ ] Quote creates draft sale.order
- [ ] Cart creates quotation sale.order
- [ ] Product order creates confirmed sale.order
- [ ] Order confirmation triggers service order (tmfc003)
- [ ] Service order creates service instance (tmfc007/008)
- [ ] Service instance appears in service inventory API
- [ ] serviceDate auto-populated on activation
- [ ] All state transitions fire hub events

---

## Scenario 4: Billing Cycle (Bill)

**Goal:** Invoice generation, payment, and bill presentation

### API Steps
```
1. (After Scenario 3 - service is active)

2. POST /tmf-api/billingManagement/v4/appliedCustomerBillingRate
   Body: { name: "Monthly Data Plan",
           type: "recurring",
           appliedTax: [{ taxCategory: "VAT", taxRate: 20 }],
           bill: { id: "<bill_id>" },
           product: { id: "<product_id>" },
           taxIncludedAmount: { unit: "USD", value: 59.99 },
           taxExcludedAmount: { unit: "USD", value: 49.99 } }

3. GET /tmf-api/customerBillManagement/v4/customerBill
   → Verify: bill linked to billing account

4. POST /tmf-api/paymentManagement/v4/payment
   Body: { description: "Monthly payment",
           paymentDate: "2026-04-17T00:00:00Z",
           totalAmount: { unit: "USD", value: 59.99 },
           account: { id: "<billing_account_id>" },
           paymentMethod: { name: "Credit Card" },
           paymentItem: [{ totalAmount: { unit: "USD", value: 59.99 } }] }
   → Verify: account.payment created via bridge

5. GET /tmf-api/accountManagement/v4/billingAccount/<account_id>
   → Verify: balance updated
```

### GUI Steps
```
1. Odoo → Invoicing → Invoices
   → Verify: invoice exists for customer
2. Register payment on invoice via UI
   → Verify: tmf.payment record created via bridge
3. Check TMF > Billing Accounts
   → Verify: balance reflects payment
```

### Validations
- [ ] Billing rate creates/links to account.move
- [ ] Customer bill references correct billing account
- [ ] Payment creates account.payment in Odoo
- [ ] Payment status maps correctly (posted→approved)
- [ ] Bridge syncs bidirectionally (UI payment → TMF record)

---

## Scenario 5: Trouble-to-Resolve (Assure)

**Goal:** Incident → Trouble Ticket → Work Order → Resolution

### API Steps
```
1. POST /tmf-api/incidentManagement/v4/incident
   Body: { name: "Network Outage Sector 7",
           description: "Customer reports no connectivity",
           severity: "High", priority: "Critical",
           relatedParty: [{ id: "<party_id>", role: "Originator" }] }
   → Verify: helpdesk.ticket created via bridge

2. POST /tmf-api/troubleTicketManagement/v5/troubleTicket
   Body: { description: "Connectivity issue for John Doe",
           severity: "High", priority: "High",
           ticketType: "Complaint",
           relatedParty: [{ id: "<party_id>", role: "Customer" }] }
   → Verify: second helpdesk.ticket created

3. POST /tmf-api/alarmManagement/v4/alarm
   Body: { alarmType: "equipmentAlarm",
           perceivedSeverity: "critical",
           specificProblem: "Cell tower offline",
           alarmRaisedTime: "2026-04-17T10:00:00Z" }
   → Verify: mail.activity created via bridge

4. POST /tmf-api/workManagement/v4/work
   Body: { name: "Repair Cell Tower Sector 7",
           description: "Dispatch technician",
           workType: "fieldWork",
           relatedParty: [{ id: "<technician_party_id>", role: "Technician" }] }
   → Verify: project.task created via bridge

5. PATCH /tmf-api/workManagement/v4/work/<work_id>
   Body: { state: "completed" }

6. PATCH /tmf-api/troubleTicketManagement/v5/troubleTicket/<ticket_id>
   Body: { status: "Resolved" }
   → Verify: helpdesk.ticket stage updated

7. GET /tmf-api/troubleTicketManagement/v5/troubleTicket/<ticket_id>
   → Verify: status=Resolved, resolutionDate populated
```

### GUI Steps
```
1. Odoo → Helpdesk → All Tickets
   → Verify: 2 tickets visible, linked to customer
2. Drag ticket to "Resolved" stage in Kanban
   → Verify: TMF trouble ticket status updates via bridge
3. Odoo → Project → Tasks
   → Verify: repair task exists, linked to TMF work
4. Mark task as done in UI
   → Verify: tmf.work state = "completed"
```

### Validations
- [ ] Incident creates helpdesk.ticket
- [ ] Trouble ticket creates separate helpdesk.ticket
- [ ] Alarm creates mail.activity (todo)
- [ ] Work order creates project.task
- [ ] Resolving ticket in UI syncs to TMF
- [ ] Completing task in UI syncs to TMF work
- [ ] All events published to /hub subscribers

---

## Scenario 6: Resource & Shipment (Deliver)

**Goal:** Resource ordering, warehouse allocation, shipment tracking

### API Steps
```
1. POST /tmf-api/resourceOrderingManagement/v4/resourceOrder
   Body: { description: "Order 5G SIM cards",
           orderItem: [{ action: "add",
             resourceSpecification: { id: "<resource_spec_id>" },
             quantity: 100 }],
           relatedParty: [{ id: "<supplier_party_id>", role: "Supplier" }] }
   → Verify: purchase.order created via bridge

2. POST /tmf-api/resourceInventory/v4/resource
   Body: { name: "SIM-001", resourceStatus: "available",
           resourceSpecification: { id: "<resource_spec_id>" } }
   → Verify: stock.lot created/linked

3. POST /tmf-api/geographicSiteManagement/v4/geographicSite
   Body: { name: "Warehouse East", description: "Main distribution center" }
   → Verify: stock.warehouse created via bridge

4. POST /tmf-api/shippingOrder/v4.0/shippingOrder
   Body: { shippingOrderItem: [{ product: { id: "<resource_id>" } }],
           relatedParty: [{ id: "<party_id>", role: "Customer" }],
           expectedShippingStartDate: "2026-04-18" }
   → Verify: stock.picking created/linked

5. POST /tmf-api/shipmentManagement/v4/shipment
   Body: { name: "SHIP-001", state: "inTransit",
           relatedParty: [{ id: "<party_id>" }] }
   → Verify: stock.picking linked and state synced

6. PATCH /tmf-api/shipmentManagement/v4/shipment/<id>
   Body: { state: "delivered" }
   → Verify: picking state updates
```

### GUI Steps
```
1. Odoo → Purchase → Orders
   → Verify: PO exists for SIM cards
2. Odoo → Inventory → Operations → Transfers
   → Verify: picking exists with correct products
3. Validate transfer in Odoo UI
   → Verify: tmf.shipment state updates to "completed"
4. Odoo → Inventory → Warehouses
   → Verify: "Warehouse East" exists via bridge
```

---

## Scenario 7: Agreement & Document (Contract)

**Goal:** Create agreement with documents and geographic references

### API Steps
```
1. POST /tmf-api/agreementManagement/v4/agreement
   Body: { name: "Enterprise SLA Agreement",
           agreementType: "SLA",
           engagedParty: { id: "<party_id>", name: "John Doe" },
           agreementItem: [{ product: [{ id: "<offering_id>" }] }],
           agreementPeriod: { startDateTime: "2026-01-01", endDateTime: "2027-01-01" } }
   → Verify: sale.order created via bridge

2. POST /tmf-api/documentManagement/v4/document
   Body: { name: "SLA Terms v2.1",
           description: "Service Level Agreement document",
           documentType: "contract" }
   → Verify: ir.attachment created via bridge

3. POST /tmf-api/geographicAddressManagement/v4/geographicAddress
   Body: { streetName: "Main Street", streetNr: "123",
           city: "New York", postcode: "10001",
           country: "United States" }
   → Verify: res.partner address fields updated

4. POST /tmf-api/appointmentManagement/v4/appointment
   Body: { category: "Contract Signing",
           description: "Sign enterprise agreement",
           status: "confirmed",
           validFor: { startDateTime: "2026-04-20T14:00:00Z",
                       endDateTime: "2026-04-20T15:00:00Z" },
           relatedParty: [{ id: "<party_id>" }] }
   → Verify: calendar.event created via bridge
```

### GUI Steps
```
1. Odoo → Sales → Orders
   → Verify: agreement-linked SO exists
2. Odoo → Documents/Attachments
   → Verify: SLA document attachment exists
3. Odoo → Calendar
   → Verify: signing appointment event exists
```

---

## Scenario 8: Multi-Service Customer (Integration)

**Goal:** Single customer with multiple services, accounts, and interactions

### API Steps
```
1. Create party (reuse Scenario 1 customer)
2. Create 3 billing accounts (Personal, Business, Family)
3. Create 3 product orders (Mobile, Internet, TV)
4. Create 3 services (one per order)
5. Create usage records for each service
6. POST /tmf-api/communicationManagement/v4/communicationMessage
   Body: { content: "Your monthly bill is ready",
           messageType: "email",
           sender: { id: "<company_id>", name: "TelcoCo" },
           receiver: [{ id: "<party_id>", name: "John Doe" }] }
   → Verify: mail.message created

7. POST /tmf-api/partyInteraction/v2/partyInteraction
   Body: { description: "Customer called about bill dispute",
           interactionDate: { startDateTime: "2026-04-17T09:00:00Z" },
           relatedParty: [{ id: "<party_id>" }] }
   → Verify: mail.message created via bridge

8. Verify cross-references:
   GET /tmf-api/party/v4/individual/<id> → shows all services
   GET /tmf-api/accountManagement/v4/billingAccount?relatedParty.id=<id> → 3 accounts
   GET /tmf-api/serviceInventory/v4/service?relatedParty.id=<id> → 3 services
```

---

## Test Script Structure

```
tests/
├── conftest.py              # Shared fixtures (base_url, auth, cleanup)
├── helpers/
│   ├── __init__.py
│   ├── api_client.py        # TMF API wrapper (requests-based)
│   ├── odoo_xmlrpc.py       # Odoo XML-RPC client for GUI validation
│   └── assertions.py        # TMF-specific assertions
├── test_01_customer_onboarding.py
├── test_02_product_catalog.py
├── test_03_order_to_activate.py
├── test_04_billing_cycle.py
├── test_05_trouble_to_resolve.py
├── test_06_resource_shipment.py
├── test_07_agreement_document.py
├── test_08_multi_service_customer.py
├── gui/
│   ├── test_gui_partner_sync.py    # Selenium tests
│   ├── test_gui_order_flow.py
│   └── test_gui_helpdesk_sync.py
└── postman/
    ├── TAM_Full_Scenario.postman_collection.json
    └── TAM_Environment.postman_environment.json
```

---

## Environment Configuration

```python
# conftest.py
BASE_URL = "http://localhost:8069"
ODOO_DB = "TMF_Odoo_DB"
ODOO_USER = "admin"
ODOO_PASS = "admin"

TMF_APIS = {
    "party": f"{BASE_URL}/tmf-api/party/v4",
    "customer": f"{BASE_URL}/tmf-api/customerManagement/v4",
    "account": f"{BASE_URL}/tmf-api/accountManagement/v4",
    "catalog": f"{BASE_URL}/tmf-api/productCatalogManagement/v4",
    "ordering": f"{BASE_URL}/tmf-api/productOrderingManagement/v4",
    "service_inventory": f"{BASE_URL}/tmf-api/serviceInventory/v4",
    "resource_inventory": f"{BASE_URL}/tmf-api/resourceInventory/v4",
    "billing": f"{BASE_URL}/tmf-api/billingManagement/v4",
    "payment": f"{BASE_URL}/tmf-api/paymentManagement/v4",
    "trouble_ticket": f"{BASE_URL}/tmf-api/troubleTicketManagement/v5",
    "incident": f"{BASE_URL}/tmf-api/incidentManagement/v4",
    "work": f"{BASE_URL}/tmf-api/workManagement/v4",
    "appointment": f"{BASE_URL}/tmf-api/appointmentManagement/v4",
    "alarm": f"{BASE_URL}/tmf-api/alarmManagement/v4",
    "agreement": f"{BASE_URL}/tmf-api/agreementManagement/v4",
    "document": f"{BASE_URL}/tmf-api/documentManagement/v4",
    "communication": f"{BASE_URL}/tmf-api/communicationManagement/v4",
    "geographic_address": f"{BASE_URL}/tmf-api/geographicAddressManagement/v4",
    "geographic_site": f"{BASE_URL}/tmf-api/geographicSiteManagement/v4",
    "quote": f"{BASE_URL}/tmf-api/quoteManagement/v4",
    "shopping_cart": f"{BASE_URL}/tmf-api/shoppingCart/v4",
    "shipping_order": f"{BASE_URL}/tmf-api/shippingOrder/v4.0",
    "shipment": f"{BASE_URL}/tmf-api/shipmentManagement/v4",
    "promotion": f"{BASE_URL}/tmf-api/promotionManagement/v4",
    "usage": f"{BASE_URL}/tmf-api/usageManagement/v4",
    "service_catalog": f"{BASE_URL}/tmf-api/serviceCatalogManagement/v4",
    "resource_catalog": f"{BASE_URL}/tmf-api/resourceCatalogManagement/v4",
    "resource_order": f"{BASE_URL}/tmf-api/resourceOrderingManagement/v4",
    "service_activation": f"{BASE_URL}/tmf-api/ServiceActivationAndConfiguration/v4",
}
```
