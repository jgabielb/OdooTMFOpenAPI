# OdooTMFOpenAPI

OdooTMFOpenAPI is an Odoo-based implementation of TM Forum Open APIs, with one addon per TMF domain, plus shared base tooling for payload mapping, controllers, and conformance validation workflows.

## Project Scope

- TMF API implementation as Odoo modules (`tmf_*`)
- Odoo wiring for CRM, Sales, Product, Project, Inventory, and related core apps where applicable
- Automated API smoke testing
- Batch CTK execution/reporting utilities

## Repository Structure

- `tmf_*`: TMF API modules (models, controllers, views, security)
- `tmf_base`: shared TMF helpers/mixins
- `tools/tmf_api_smoke.py`: end-to-end API smoke runner
- `tools/run_ctk_batch.py`: CTK batch runner/report generator
- `TMF_ODOO_WIRING_MATRIX.md`: wiring status matrix

## Local Run

Use your existing PowerShell bootstrap script:

- `Set.ps1`

Typical validation commands:

- `python OdooTMFOpenAPI/tools/tmf_api_smoke.py --config OdooTMFOpenAPI/tools/tmf_api_smoke.sample.json --workers 8`
- `python OdooTMFOpenAPI/tools/run_ctk_batch.py`

## API Compliance Status

Snapshot source: provided project matrix (latest shared in session).

### APIs with CTK Coverage (Current: 100%)

| TMF ID | CTK | API Name | Module |
|---|---|---|---|
| TMF620 | 100% | Product Catalog Management API | `tmf_product_catalog` |
| TMF621 | 100% | Trouble Ticket Management API | `tmf_trouble_ticket` |
| TMF622 | 100% | Product Ordering Management API | `tmf_product_ordering` |
| TMF629 | 100% | Customer Management API | `tmf_customer` |
| TMF632 | 100% | Party Management API | `tmf_party` |
| TMF633 | 100% | Service Catalog Management API | `tmf_service_catalog` |
| TMF634 | 100% | Resource Catalog Management API | `tmf_resource_catalog` |
| TMF635 | 100% | Usage Management API | `tmf_usage` |
| TMF637 | 100% | Product Inventory Management API | `tmf_product_inventory` |
| TMF638 | 100% | Service Inventory Management API | `tmf_service_inventory` |
| TMF639 | 100% | Resource Inventory Management API | `tmf_resource_inventory` |
| TMF640 | 100% | Service Activation Management API | `tmf_service_activation_configuration` |
| TMF641 | 100% | Service Ordering Management API | `tmf_service_order` |
| TMF642 | 100% | Alarm Management API | `tmf_alarm` |
| TMF644 | 100% | Privacy Management API | `tmf_privacy_management` |
| TMF645 | 100% | Service Qualification Management API | `tmf_service_qualification` |
| TMF646 | 100% | Appointment Management API | `tmf_appointment` |
| TMF648 | 100% | Quote Management API | `tmf_quote_management` |
| TMF651 | 100% | Agreement Management API | `tmf_agreement` |
| TMF652 | 100% | Resource Order Management API | `tmf_resource_order` |
| TMF653 | 100% | Service Test Management API | `tmf_service_test` |
| TMF654 | 100% | Prepay Balance Management API | `tmf_prepay_balance_management` |
| TMF655 | 100% | Change Management API | `tmf_change_management` |
| TMF656 | 100% | Service Problem Management API | `tmf_service_problem` |
| TMF657 | 100% | Service Quality Management API | `tmf_service_quality_management` |
| TMF662 | 100% | Entity Catalog Management API | `tmf_entity_catalog` |
| TMF663 | 100% | Shopping Cart Management API | `tmf_shopping_cart` |
| TMF664 | 100% | Resource Function Activation Management API | `tmf_resource_function` |
| TMF666 | 100% | Account Management API | `tmf_account` |
| TMF667 | 100% | Document Management API | `tmf_document` |
| TMF668 | 100% | Partnership Management API | `tmf_partnership_management` |
| TMF669 | 100% | Party Role Management API | `tmf_party_role` |
| TMF670 | 100% | Payment Method Management API | `tmf_payment_method` |
| TMF671 | 100% | Promotion Management API | `tmf_promotion_management` |
| TMF672 | 100% | User Role Permission Management API | `tmf_user_role_permission` |
| TMF673 | 100% | Geographic Address Management API | `tmf_geographic_address` |
| TMF674 | 100% | Geographic Site Management API | `tmf_geographic_site` |
| TMF676 | 100% | Payment Management API | `tmf_payment` |
| TMF677 | 100% | Usage Consumption Management API | `tmf_usage_consumption` |
| TMF678 | 100% | Customer Bill Management API | `tmf_customer_bill_management` |
| TMF679 | 100% | Product Offering Qualification Management API | `tmf_product_offering_qualification` |
| TMF680 | 100% | Recommendation Management API | `tmf_recommendation_management` |
| TMF681 | 100% | Communication Management API | `tmf_communication_message` |
| TMF683 | 100% | Party Interaction Management API | `tmf_party_interaction` |
| TMF687 | 100% | Stock Management API | `tmf_product_stock_relationship` |
| TMF696 | 100% | Risk Management API | `tmf_party_role_product_offering_risk_assessment` |
| TMF699 | 100% | Sales Management API | `tmf_sales` |
| TMF702 | 100% | Resource Activation Management API | `tmf_resource_activation` |
| TMF704 | 100% | Test Case Management API | `tmf_test_case` |
| TMF705 | 100% | Test Environment Management API | `tmf_test_environment` |
| TMF706 | 100% | Test Data Management API | `tmf_test_data` |
| TMF707 | 100% | Test Result Management API | `tmf_test_result` |
| TMF708 | 100% | Test Execution Management API | `tmf_test_execution` |
| TMF709 | 100% | Test Scenario Management API | `tmf_test_scenario` |
| TMF710 | 100% | General Test Artifact Management API | `tmf_general_test_artifact` |
| TMF716 | 100% | Resource Reservation API | `tmf_resource_reservation` |
| TMF720 | 100% | Digital Identity Management API | `tmf_digital_identity_management` |
| TMF724 | 100% | Incident Management API | `tmf_incident_management` |
| TMF730 | 100% | Software and Compute Management API | `tmf_software_compute_management` |
| TMF735 | 100% | CDR Transaction Management API | `tmf_cdr_transaction_management` |
| TMF736 | 100% | Revenue Sharing Algorithm Management API | `tmf_revenue_sharing_algorithm_management` |
| TMF737 | 100% | Revenue Sharing Report Management API | `tmf_revenue_sharing_report_management` |
| TMF738 | 100% | Revenue Sharing Model Management API | `tmf_revenue_sharing_model_management` |
| TMF760 | 100% | Product Configuration Management API | `tmf_product` |
| TMF771 | 100% | Resource Usage Management API | `tmf_resource_usage_management` |
| TMF915 | 100% | AI Management API | `tmf_ai_management` |
| TMF921 | 100% | Intent Management API | `tmf_intent_management` |
| TMF931 | 100% | Open Gateway Onboarding and Ordering Component Suite API | `tmf_open_gateway_operate_onboarding_ordering` |
| TMF936 | 100% | Open Gateway Product Catalog API | `tmf_open_gateway_operate_product_catalog` |

### APIs without CTK Availability (`NO CTK` in current matrix)

These APIs may still be implemented and wired in Odoo, but currently have no CTK package/run in this project snapshot.

| TMF ID | CTK | API Name | Module |
|---|---|---|---|
| TMF623 | NO CTK | SLA Management API | `tmf_service_level_objective` |
| TMF628 | NO CTK | Performance Management API | `tmf_performance_management` |
| TMF649 | NO CTK | Performance Thresholding Management API | `tmf_performance_management` |
| TMF658 | NO CTK | Loyalty Management API | `tmf_billing_management` |
| TMF675 | NO CTK | Geographic Location Management API | `tmf_geographic_location` |
| TMF684 | NO CTK | Shipment Tracking Management API | `tmf_shipment_tracking_management` |
| TMF685 | NO CTK | Resource Pool Management API | `tmf_resource_pool_management` |
| TMF686 | NO CTK | Topology Management API | `tmf_resource_pool_management` |
| TMF688 | NO CTK | Event Management API | `tmf_event` |
| TMF691 | NO CTK | Federated ID Management API | `tmf_userinfo` |
| TMF700 | NO CTK | Shipping Order Management API | `tmf_shipping_order` |
| TMF701 | NO CTK | Process Flow Management API | `tmf_process_flow` |
| TMF703 | NO CTK | Entity Inventory Management API | `tmf_entity` |
| TMF711 | NO CTK | Shipment Management API | `tmf_shipment_management` |
| TMF713 | NO CTK | Work Management API | `tmf_work_management` |
| TMF714 | NO CTK | Work Qualification Management API | `tmf_work_qualification` |
| TMF715 | NO CTK | Warranty Management API | `tmf_warranty_management` |
| TMF717 | NO CTK | Customer360 Management API | `tmf_customer360` |
| TMF725 | NO CTK | Metadata Catalog Management API | `tmf_metadata_catalog_management` |
| TMF727 | NO CTK | Service Usage Management API | `tmf_service_usage_management` |
| TMF728 | NO CTK | Dunning Case Management API | `tmf_dunning_case_management` |
| TMF759 | NO CTK | Private Optimized Binding API | `tmf_private_optimized_binding` |
| TMF764 | NO CTK | Cost Management API | `tmf_cost_management` |
| TMF767 | NO CTK | Product Usage Catalog Management API | `tmf_product_usage_catalog_management` |
| TMF768 | NO CTK | Resource Role API | `tmf_resource_role_management` |
| TMF777 | NO CTK | Outage Management API | `tmf_outage_management` |
| TMF908 | NO CTK | IoT Agent and Device Management API | `tmf_iot_agent_device_management` |
| TMF909 | NO CTK | Network as a Service Management API | `tmf_network_as_a_service_management` |
| TMF910 | NO CTK | Self Care Management API | `tmf_self_care_management` |
| TMF914 | NO CTK | IoT Service Management API | `tmf_iot_service_management` |
| TMF924 | NO CTK | DCS 5G Slice Service Activation API | `tmf_5gslice_service_activation` |

### Modules not currently listed in the two TMF ID tables

These modules exist in the repository but are not represented as standalone rows in the CTK/NO-CTK API tables above. Most are sub-resources or supporting components within already listed TMF domains.

| Module | Purpose |
|---|---|
| `tmf_ai_contract_specification` | AI contract specification sub-resource used under AI Management domain. |
| `tmf_device` | IoT device resource support for IoT Agent/Device and related domains. |
| `tmf_managed_entity` | Managed entity sub-resource used by Entity/Inventory-related APIs. |
| `tmf_non_functional_test_result_definition` | Non-functional test result definition sub-resource for TMF test result domain. |
| `tmf_party_privacy_agreement` | Party privacy agreement sub-resource used with privacy/party APIs. |
| `tmf_permission` | Permission sub-resource used with user role/permission APIs. |
| `tmf_physical_resource` | Physical resource sub-resource used by resource activation/inventory domains. |
| `tmf_test_data_instance_definition` | Test data instance definition sub-resource in TMF test data domain. |
| `tmf_transfer_balance` | Transfer balance sub-resource for prepay balance management flows. |

## Notes

- Some CTKs run inside Docker and need `host.docker.internal`.
- Some CTKs run locally (non-Docker) and must use `127.0.0.1`.

