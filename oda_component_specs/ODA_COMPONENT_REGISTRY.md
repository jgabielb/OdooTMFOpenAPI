# ODA Component Registry — Authoritative Spec Data
# Source: https://oda-production.s3.eu-west-2.amazonaws.com/v1beta3/
# Retrieved: 2026-03-26

---

## TMFC001 — Product Catalog Management
- functionalBlock: CoreCommerce
- version: 2.0.0 (v2.1.0 latest)
- **Exposed APIs (mandatory):** TMF620 (catalog, category, productOffering, productSpecification, productOfferingPrice, importJob, exportJob — full CRUD)
- **Dependent APIs:**
  - TMF633 serviceSpecification GET
  - TMF669 partyRole GET
  - TMF632 individual/organisation GET
  - TMF634 resourceSpecification GET
  - TMF651 agreement/agreementSpecification GET
  - TMF673 geographicAddress GET
  - TMF674 geographicSite GET
  - TMF675 geographicLocation GET
  - TMF672 permission GET
  - TMF662 entitySpecification/associationSpecification GET
  - TMF688 event GET
  - TMF620 (self-reference for catalog hierarchy) GET+CRUD
- **Odoo wiring module:** `tmfc001_wiring` ✅

---

## TMFC002 — Product Order Capture And Validation
- functionalBlock: CoreCommerce
- version: 2.0.1 (v2.1.0 latest)
- **Exposed APIs (mandatory):** TMF622 (productOrder — full CRUD), TMF648 Quote (optional), TMF663 ShoppingCart (optional), TMF701 ProcessFlow (optional)
- **Dependent APIs:**
  - TMF620 productCategory/productOffering/productOfferingPrice/productSpecification GET (**required**)
  - TMF637 product GET+POST+PATCH (**required**)
  - TMF679 productOfferingQualification GET+POST+PATCH
  - TMF645 checkServiceQualification/queryServiceQualification GET+POST+PATCH
  - TMF646 appointment/searchTimeSlot GET+POST+PATCH+DELETE
  - TMF673 geographicAddress/geographicSubAddress/geographicAddressValidation GET+POST+PATCH
  - TMF674 geographicSite GET
  - TMF687 checkProductStock/queryProductStock/reserveProductStock/productStock GET+POST+PATCH+DELETE
  - TMF632 individual/organization GET
  - TMF669 partyRole GET
  - TMF666 billingAccount GET
  - TMF676 payment GET
- **Odoo wiring module:** `tmfc002_wiring` ❌ MISSING

---

## TMFC005 — Product Inventory
- functionalBlock: CoreCommerceManagement
- version: 1.2.0
- **Exposed APIs (mandatory):** TMF637 product (full CRUD)
- **Dependent APIs:**
  - TMF620 productSpecification/productOffering/productOfferingPrice GET (**required**)
  - TMF669 partyRole GET
  - TMF639 resource GET
  - TMF651 agreement GET
  - TMF673 geographicAddress/geographicSubAddress GET
  - TMF674 geographicSite GET
  - TMF675 geographicLocation GET
  - TMF666 billingAccount GET
  - TMF632 individual/organization GET
  - TMF637 product GET+POST+PATCH+DELETE
  - TMF638 service GET (truncated — also likely present)
- **Odoo wiring module:** `tmfc005_wiring` ❌ MISSING

---

## TMFC007 — Service Order Management
- functionalBlock: Production
- version: 2.0.0
- **Exposed APIs (mandatory):** TMF641 serviceOrder (full CRUD + cancelServiceOrder)
- **Dependent APIs:**
  - TMF632 individual/organization GET
  - TMF633 serviceSpecification GET (**required**)
  - TMF634 resourceSpecification GET
  - TMF638 service GET+POST+PATCH+DELETE (**required**)
  - TMF639 resource GET
  - TMF640 monitor GET
  - TMF641 serviceOrder/cancelServiceOrder GET+POST+PATCH+DELETE
  - TMF645 checkServiceQualification/queryServiceQualification GET+POST+PATCH
  - TMF646 appointment/searchTimeSlot GET+POST+PATCH
- **Odoo wiring module:** `tmfc007_wiring` ⚠️ PARTIAL (TMF641/TMF701 exposed, TMF638/TMF652/TMF645/TMF681/TMF697 dependencies wired; TMF632/TMF669 left at base behaviour)

---

## TMFC008 — Service Inventory
- functionalBlock: Production
- version: 1.1.0
- **Exposed APIs (mandatory):** TMF638 service (full CRUD)
- **Dependent APIs:**
  - TMF633 serviceSpecification GET (**required**)
  - TMF669 partyRole GET
  - TMF639 resource GET
  - TMF638 service GET (self-reference)
  - TMF673 geographicAddress/geographicSubAddress GET
  - TMF674 geographicSite GET
  - TMF675 geographicLocation GET
  - TMF672 permission GET (truncated — likely more)
- **Odoo wiring module:** `tmfc008_wiring` ❌ MISSING

---

## TMFC020 — Digital Identity Management
- functionalBlock: PartyManagement
- **Exposed APIs:** TMF720 DigitalIdentity
- **Dependent APIs:** TMF632, TMF669
- **Odoo wiring module:** `tmfc020_wiring` ✅ (partial — covers digital identity linkage)

---

## TMFC024 — Billing Account Management
- functionalBlock: PartyManagement
- **Exposed APIs:** TMF666 Account Management API, TMF701 (optional)
- **Dependent APIs:** TMF632 (**required**), TMF669
- **Odoo wiring module:** `tmfc024_wiring` ❌ MISSING

---

## TMFC025 — (Party Role Management — maps to your tmfc020 scope)
- **Odoo wiring module:** see tmfc020_wiring

---

## TMFC027 — Product Offering Qualification
- **Exposed APIs:** TMF679 CheckProductOfferingQualification
- **Odoo wiring module:** `tmfc027_wiring` ✅

---

## TMFC031 — Customer Bill / Payment
- **Exposed APIs:** TMF678 CustomerBill, TMF676 Payment
- **Odoo wiring module:** `tmfc031_wiring` ✅

---

## Priority Queue for Implementation

### Priority 1 — Commercial flow (blocks everything else)
1. `tmfc002_wiring` — Product Order Capture (TMF622 + TMF637 + TMF679/645/646/673/632/666/676)
2. `tmfc005_wiring` — Product Inventory (TMF637 + TMF620/632/639/651/673/674/666)
3. `tmfc024_wiring` — Billing Account (TMF666 + TMF632/669)

### Priority 2 — Fulfillment / Production
4. `tmfc007_wiring` — Service Order (TMF641 + TMF633/638/639/640/645/646)
5. `tmfc008_wiring` — Service Inventory (TMF638 + TMF633/639/669/673)
6. `tmfc012_wiring` — Resource Inventory (TMF639 + TMF634/632/638)

### Priority 3 — Pre-order / Qualification
7. `tmfc009_wiring` — Service Qualification (TMF645 + deps)
8. `tmfc010_wiring` — Resource Catalog (TMF634 + deps)

### Priority 4 — Assurance
9. `tmfc013_wiring` — Trouble Ticket (TMF621 + helpdesk)
10. `tmfc014_wiring` — Service Problem (TMF656/642/724)
