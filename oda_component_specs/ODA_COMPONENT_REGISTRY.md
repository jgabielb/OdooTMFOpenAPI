# ODA Component Registry — Authoritative Spec Data
# Source: https://oda-production.s3.eu-west-2.amazonaws.com/v1beta3/
# Retrieved: 2026-03-26
# Last reconciled: 2026-07-16 against docs/TMFC_IMPLEMENTATION_STATUS.md (all 35 wiring side-cars present).
# Machine-readable requirements now live in mappings/tmfc_requirements.json; conformance verdicts in docs/ODA_CONFORMANCE.md.

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
- **Odoo wiring module:** `tmfc002_wiring` ✅ — see docs/TMFC_IMPLEMENTATION_STATUS.md

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
- **Odoo wiring module:** `tmfc005_wiring` ✅ — see docs/TMFC_IMPLEMENTATION_STATUS.md

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
- **Odoo wiring module:** `tmfc008_wiring` ✅ — see docs/TMFC_IMPLEMENTATION_STATUS.md

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
- **Odoo wiring module:** `tmfc024_wiring` ✅ — see docs/TMFC_IMPLEMENTATION_STATUS.md

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

Retired 2026-07-16 — all 35 wiring side-cars are implemented (docs/TMFC_IMPLEMENTATION_STATUS.md).
Current per-component conformance status and remaining gaps live in docs/ODA_CONFORMANCE.md.
