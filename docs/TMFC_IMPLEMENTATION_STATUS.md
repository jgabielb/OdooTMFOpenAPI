# TMFC Implementation Status — OdooBSS

This table tracks which TM Forum ODA Components (TMFCs) are realized in the OdooBSS repo, based on verified code in this workspace session.

Classification used here is intentionally stricter than "the TMF API exists":
- **Fully wired**: exposed APIs, dependent reference wiring, and event wiring are materially evidenced in code for the TMFC.
- **Partially wired**: some ODA wiring exists, but coverage is incomplete, placeholder-only, or not evidenced for the full TMFC contract.
- **Missing**: no TMFC-specific wiring was found in the repo; only underlying TMF APIs may exist.

Legend:
- ✅ Fully wired
- ⚠️ Partially wired
- ❌ Missing / not evidenced

| TMFC ID  | Name                                           | Status | Evidence-backed notes |
|----------|------------------------------------------------|--------|-----------------------|
| TMFC001  | ProductCatalogManagement                       | ⚠️ | `tmfc001_wiring` resolves TMF633/634/632/669/651/673/674/675 refs into `tmf_product_catalog` models. `tmf_product_catalog` now exposes productSpecification, productOffering, productOfferingPrice, catalog, category, importJob, and exportJob. TMFC001 listener routes now reconcile TMF633 service/resource specification events and TMF632/TMF669 delete events. It remains partially wired because TMF671/TMF701 fit and residual event completeness still need verification. |
| TMFC002  | ProductOrderCaptureAndValidation               | ⚠️ | `tmfc002_wiring` exists and enriches `tmf.product.order` with resolved links to Party, ProductOffering, BillingAccount, POQ, ServiceQualification, ShoppingCart, and native `sale.order`. This is real ODA side-car wiring, but full TMFC002 event/subscription coverage was not evidenced in the wiring addon itself. |
| TMFC003  | ProductOrderDeliveryOrchestrationAndManagement | ❌ | No `tmfc003_*` wiring addon or TMFC003-specific orchestration layer was found. Base modules such as `tmf_product_ordering`, `tmf_service_order`, `tmf_service_inventory`, `tmf_resource_order`, and `tmf_resource_inventory` exist, but that is not sufficient evidence of TMFC003 ODA wiring. |
| TMFC005  | ProductInventory                               | ⚠️ | `tmfc005_wiring` exists and links `tmf.product` to Odoo `product.template`, `product.product`, `stock.location`, `stock.lot`, and `stock.quant`. This is concrete side-car inventory wiring, but full TMFC005 event/subscription coverage was not evidenced. |
| TMFC006  | ServiceCatalogManagement                       | ❌ | `tmf_service_catalog` and `tmf_service_quality_management` exist, but no `tmfc006_*` wiring addon or TMFC006-specific dependent/subscribed-event wiring was found. |
| TMFC007  | ServiceOrderManagement                         | ❌ | `tmf_service_order` and related TMF modules exist, but no `tmfc007_*` wiring addon or TMFC007-specific ODA side-car wiring was found. |
| TMFC008  | ServiceInventory                               | ❌ | `tmf_service_inventory` exists, but no `tmfc008_*` wiring addon or TMFC008-specific cross-component wiring was found. |
| TMFC009  | ServiceQualificationManagement                 | ❌ | `tmf_service_qualification` exists, but no `tmfc009_*` wiring addon or TMFC009-specific ODA wiring was found. |
| TMFC010  | ResourceCatalogManagement                      | ❌ | `tmf_resource_catalog` exists, but no `tmfc010_*` wiring addon or TMFC010-specific dependent/subscribed-event wiring was found. |
| TMFC011  | ResourceOrderManagement                        | ❌ | `tmf_resource_order` exists, but no `tmfc011_*` wiring addon or TMFC011-specific orchestration wiring was found. |
| TMFC012  | ResourceInventory                              | ❌ | `tmf_resource_inventory`, `tmf_resource_pool_management`, and `tmf_resource_reservation` exist, but no `tmfc012_*` wiring addon or TMFC012-specific ODA side-car wiring was found. |
| TMFC014  | LocationManagement                             | ❌ | TMF673/674/675 modules exist, but no `tmfc014_*` wiring addon or LocationManagement component wiring layer was found. |
| TMFC020  | DigitalIdentityManagement                      | ⚠️ | `tmfc020_wiring` exists and resolves TMF632, TMF669, and TMF639 refs into `tmf.digital.identity`. Concrete side-car wiring is present, but full TMFC020 event/subscription completeness was not evidenced. |
| TMFC022  | PartyPrivacyManagement                         | ⚠️ | `tmfc022_wiring` exists and links `tmf.party.privacy.agreement` to Party and DigitalIdentity via JSON-ref resolution. This is real ODA wiring, but event/subscription completeness was not evidenced. |
| TMFC023  | PartyInteractionManagement                     | ⚠️ | `tmfc023_wiring` addon exists, but `_resolve_tmf_refs()` is currently a documented no-op placeholder. The side-car structure is present, but the component is only partially wired. |
| TMFC024  | BillingAccountManagement                       | ❌ | `tmf_account` / billing-account APIs exist, but no `tmfc024_*` wiring addon or TMFC024-specific ODA cross-component wiring was found. |
| TMFC027  | ProductConfigurator                            | ⚠️ | `tmfc027_wiring` exists and resolves ProductOfferingQualification refs to Product, ProductOffering, ProductOrder, BillingAccount, PartyRole, GeographicAddress/Site, EntitySpecification, and Intent. This is substantial ODA wiring, but full TMFC027 contract coverage, especially events/subscriptions, was not fully evidenced. |
| TMFC028  | PartyManagement                                | ⚠️ | `tmfc028_wiring` exists, but it mainly adds relational convenience links from `res.partner` to DigitalIdentity, PrivacyAgreement, and PartyInteraction. Useful, but not enough evidence to mark the whole TMFC fully wired. |
| TMFC029  | PaymentManagement                              | ❌ | `tmf_payment`, `tmf_payment_method`, and `tmf_transfer_balance` exist, but no `tmfc029_*` wiring addon or TMFC029-specific ODA wiring was found. |
| TMFC030  | BillGeneration                                 | ❌ | `tmf_customer_bill_management` exists, but no `tmfc030_*` wiring addon or TMFC030-specific ODA orchestration/wiring was found. |
| TMFC031  | BillCalculation                                | ⚠️ | `tmfc031_wiring` exists and resolves CustomerBill / AppliedBillingRate refs to BillingAccount, Product, Usage, PartyRole, and ProcessFlow. Concrete side-car wiring is present, but full TMFC031 completeness was not evidenced. |
| TMFC035  | PermissionsManagement                          | ❌ | `tmf_user_role_permission` and `tmf_party_role` exist, but no `tmfc035_*` wiring addon or TMFC035-specific ODA wiring was found. |
| TMFC036  | LeadAndOpportunityManagement                   | ❌ | `tmf_sales` references TMFC036 in code, but no dedicated `tmfc036_*` wiring addon or full TMFC036 ODA component wiring layer was found. |
| TMFC037  | ServicePerformanceManagement                   | ❌ | `tmf_performance_management` exists, but no `tmfc037_*` wiring addon or TMFC037-specific ODA side-car wiring was found. |
| TMFC038  | ResourcePerformanceManagement                  | ❌ | Underlying performance/resource modules exist, but no `tmfc038_*` wiring addon or TMFC038-specific ODA component wiring was found. |
| TMFC039  | AgreementManagement                            | ❌ | `tmf_agreement` exists, but no `tmfc039_*` wiring addon or TMFC039-specific ODA wiring was found. |
| TMFC040  | ProductUsageManagement                         | ❌ | `tmf_usage` / `tmf_usage_consumption` exist, but no `tmfc040_*` wiring addon or TMFC040-specific ODA wiring was found. |
| TMFC041  | AnomalyManagement                              | ❌ | No `tmfc041_*` wiring addon or anomaly-specific ODA component wiring was found. Underlying TMF modules alone are not enough evidence. |
| TMFC043  | FaultManagement                                | ❌ | Alarm / service problem / trouble ticket modules exist, but no `tmfc043_*` wiring addon or TMFC043-specific ODA side-car wiring was found. |
| TMFC046  | WorkforceManagement                            | ❌ | `tmf_work_management` / related workforce modules exist, but no `tmfc046_*` wiring addon or TMFC046-specific ODA wiring was found. |
| TMFC050  | ProductRecommendation                          | ❌ | `tmf_recommendation_management` exists, but no `tmfc050_*` wiring addon or TMFC050-specific ODA component wiring was found. |
| TMFC054  | ProductTestManagement                          | ❌ | Test-related TMF modules exist, but no `tmfc054_*` wiring addon or TMFC054-specific ODA wiring was found. |
| TMFC055  | ServiceTestManagement                          | ❌ | `tmf_service_test` exists, but no `tmfc055_*` wiring addon or TMFC055-specific ODA component wiring was found. |
| TMFC061  | WorkOrderManagement                            | ❌ | Work-management APIs exist, but no `tmfc061_*` wiring addon or TMFC061-specific ODA side-car wiring was found. |
| TMFC062  | ResourceConfigurationandActivation             | ❌ | `tmf_resource_activation` / `tmf_resource_function` exist, but no `tmfc062_*` wiring addon or TMFC062-specific ODA component wiring was found. |

## Summary

What is clearly implemented today is a **repeatable side-car wiring pattern** for a subset of TMFCs:
`tmfc001`, `tmfc002`, `tmfc005`, `tmfc020`, `tmfc022`, `tmfc023`, `tmfc027`, `tmfc028`, `tmfc031`.

That pattern typically does one or more of the following:
- persist raw TMF JSON refs,
- resolve `tmf_id` references into relational Odoo fields,
- avoid recursion with `skip_tmf_wiring`,
- enrich existing TMF base models without changing CTK-visible behavior.

Architecturally, that is the right direction. But most TMFCs in the repo are still at the stage of **"TMF API implementation present"**, not **"ODA component wiring implemented"**. 🏛️
