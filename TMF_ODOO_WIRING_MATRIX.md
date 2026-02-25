# TMF <-> Odoo Wiring Matrix

This matrix defines where TMF resources should anchor in native Odoo apps so we can leverage CRM, Sales, Inventory, Accounting, Contacts, and Calendar consistently.

## Core Mapping

- `TMF629 Customer` -> `res.partner` (Contacts)
- `TMF632 Party` / `TMF669 PartyRole` -> `res.partner` + tags/categories (Contacts/CRM)
- `TMF620 Product Catalog` / `TMF633 Service Catalog` / `TMF634 Resource Catalog` -> `product.template` and catalog-side specification models
- `TMF622 Product Ordering` / `TMF641 Service Ordering` / `TMF652 Resource Order` -> `sale.order` (+ lines), optionally `purchase.order` when needed
- `TMF640 Service Activation` / `TMF702 Resource Activation` -> `project.task` + `stock.picking` / provisioning workflows
- `TMF687 Stock Management` / `TMF639 Resource Inventory` / `TMF638 Service Inventory` -> `stock.quant`, `stock.move`, `stock.picking`, inventory-related custom models
- `TMF678 Customer Bill` / `TMF676 Payment` / `TMF670 Payment Method` -> `account.move`, `account.payment`, journals/payment methods
- `TMF646 Appointment` -> `calendar.event`
- `TMF642 Alarm` / `TMF656 Service Problem` / `TMF724 Incident` / `TMF621 Trouble Ticket` -> `helpdesk.ticket` / issue models
- `TMF648 Quote` -> `sale.order` (quotation stage) + CRM opportunity linkage
- `TMF699 Sales Management` / `TMF760 Product Configuration` -> `crm.lead`, `sale.order`, product configurator fields
- `TMF671 Promotion` / `TMF658 Loyalty` -> pricing rules / loyalty program models (if enabled)

## Wiring Rules

- Every TMF transactional model should keep a direct reference to the native Odoo business object whenever equivalent exists.
- Prefer `Many2one` link fields with clear names:
  - `partner_id`, `lead_id`, `sale_order_id`, `invoice_id`, `picking_id`, `calendar_event_id`.
- Keep TMF `id` (`tmf_id`) as external/public identifier and Odoo relational IDs for internal process orchestration.
- Notifications (`tmf.hub.subscription`) should emit TMF payloads only; internal Odoo links stay server-side.
- Dates exposed to TMF must remain RFC3339 UTC (`Z`) via shared normalization in `tmf_base`.

## Implementation Priority

1. Commercial flow: Customer -> Quote -> Product Order -> Invoice/Payment.
2. Fulfillment flow: Product/Service/Resource Order -> Activation -> Inventory.
3. Assurance flow: Alarm/Incident/Trouble Ticket -> Work/Appointment.
4. Catalog and governance APIs.

## Done (platform-wide enablers)

- Unified backend menu root: `TMF OpenApis`.
- Shared TMF payload normalization for `id`, `href`, and date/datetime formatting.
- Odoo app bootstrap in `Set.ps1`: contacts, calendar, crm, sales, stock, account, purchase, project, helpdesk.
- TMF622 ProductOrder wiring improved:
  - ProductOrder `quote`/`quoteId` now links to TMF648 quote (`tmf.quote`) and reuses quote customer/context.
  - ProductOrder item `productOffering.id` now maps to `product.template.tmf_id` and uses the real Odoo variant when found.
- TMF641 ServiceOrder wiring improved:
  - TMF service orders now link to `res.partner` (when resolvable from `relatedParty`).
  - TMF service orders now auto-create/update a linked `project.task` (`project_task_id`) for fulfillment tracking.
- TMF652 ResourceOrder wiring improved:
  - TMF resource orders now persist `relatedParty`, `note`, and `externalReference` collections from API payload.
  - TMF resource orders now link to `res.partner` (resolved from `relatedParty`).
  - TMF resource orders now auto-create/update linked fulfillment records:
    - `project.task` (`project_task_id`)
    - `stock.picking` (`picking_id`)
- TMF640 Service Activation wiring improved:
  - TMF services now link to `res.partner` (resolved from `relatedParty`).
  - TMF services now auto-create/update a linked `project.task` (`project_task_id`) for activation tracking.
- TMF702 Resource Activation wiring improved:
  - TMF resources now link to `res.partner` (resolved from `relatedParty`).
  - TMF resources now auto-create/update linked fulfillment records:
    - `project.task` (`project_task_id`)
    - `stock.picking` (`picking_id`)
- Assurance flow wiring improved:
  - TMF642 Alarm now auto-creates/updates a linked `helpdesk.ticket` (`helpdesk_ticket_id`).
  - TMF656 ServiceProblem now auto-creates/updates a linked `helpdesk.ticket` (`helpdesk_ticket_id`) and resolves partner from related/originator party.
  - TMF724 Incident now auto-creates/updates a linked `helpdesk.ticket` (`helpdesk_ticket_id`) and resolves partner from `relatedParty`.
  - TMF621 TroubleTicket now auto-creates/updates a linked `helpdesk.ticket` (`helpdesk_ticket_id`).
- Billing/payments wiring improved:
  - TMF678 CustomerBill now auto-creates/updates a linked `account.move` (`move_id`) when customer exists.
  - TMF676 Payment now auto-creates/updates a linked `account.payment` (`account_payment_id`), resolves customer from TMF `account`, and resolves related invoices from `paymentItem`.
  - TMF670 PaymentMethod now links to native accounting payment method/journal (`payment_method_line_id`, `journal_id`) for reuse by TMF676 payment creation.
- Inventory flow wiring improved:
  - TMF638 Service Inventory now keeps stock linkage to fulfillment (`stock_picking_id`) inferred from the originating sales order/picking or supporting resource moves.
  - TMF639 Resource Inventory (stock lot mapping) now exposes stock-native context (current location and last picking metadata).
  - `tmf_resource_inventory` no longer overrides TMF638 serialization/routes, avoiding duplicate event/JSON behavior and keeping TMF638 canonical in `tmf_service_inventory`.
- TMF687 is implemented as v4 in `tmf_product_stock_relationship` (`/tmf-api/stock/v4/productStock` and `/tmf-api/stock/v4/reserveProductStock`), now wired to native stock:
  - `tmf.product.stock` links to `product.product` and optional `stock.location`
  - quantities are synchronized from Odoo stock (`stock.quant` / product availability)
- Open Gateway wiring improved:
  - TMF931 (`tmf_open_gateway_operate_onboarding_ordering`):
    - `ApiProductOrder` links to `sale.order` via `sale_order_id` (reuses by `client_order_ref` when possible, creates when needed).
    - `ApplicationOwner` links to `res.partner` via `partner_id` (resolved from `engagedParty`).
    - `Application` links to owner `res.partner` via `partner_id` (resolved from `applicationOwner`).
  - TMF936 (`tmf_open_gateway_operate_product_catalog`):
    - `ProductOffering` / `ProductSpecification` link to `product.template` via `product_tmpl_id`.
    - Product template is reused by TMF id/name or auto-created when absent.
