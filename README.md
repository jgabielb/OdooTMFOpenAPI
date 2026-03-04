# OdooBSS

OdooBSS is an Odoo-based implementation of TM Forum Open APIs, with one addon per TMF domain, plus shared base tooling for payload mapping, controllers, and conformance validation workflows.

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

- `python OdooBSS/tools/tmf_api_smoke.py --config OdooBSS/tools/tmf_api_smoke.sample.json --workers 8`
- `python OdooBSS/tools/run_ctk_batch.py`

## CTK Compliance Matrix (Snapshot)

Snapshot source: provided project matrix (latest shared in session).  
Status values:
- `100%`: CTK currently passing
- `NO CTK`: no CTK package/run available in this project snapshot

| TMF ID | Result | Name |
|---|---|---|
| TMF620 | 100% | Product Catalog Management API |
| TMF621 | 100% | Trouble Ticket Management API |
| TMF622 | 100% | Product Ordering Management API |
| TMF623 | NO CTK | SLA Management API |
| TMF628 | NO CTK | Performance Management API |
| TMF629 | 100% | Customer Management API |
| TMF632 | 100% | Party Management API |
| TMF633 | 100% | Service Catalog Management API |
| TMF634 | 100% | Resource Catalog Management API |
| TMF635 | 100% | Usage Management API |
| TMF637 | 100% | Product Inventory Management API |
| TMF638 | 100% | Service Inventory Management API |
| TMF639 | 100% | Resource Inventory Management API |
| TMF640 | 100% | Service Activation Management API |
| TMF641 | 100% | Service Ordering Management API |
| TMF642 | 100% | Alarm Management API |
| TMF644 | 100% | Privacy Management API |
| TMF645 | 100% | Service Qualification Management API |
| TMF646 | 100% | Appointment Management API |
| TMF648 | 100% | Quote Management API |
| TMF649 | NO CTK | Performance Thresholding Management API |
| TMF651 | 100% | Agreement Management API |
| TMF652 | 100% | Resource Order Management API |
| TMF653 | 100% | Service Test Management API |
| TMF654 | 100% | Prepay Balance Management API |
| TMF655 | 100% | Change Management API |
| TMF656 | 100% | Service Problem Management API |
| TMF657 | 100% | Service Quality Management Management API |
| TMF658 | NO CTK | Loyalty Management API |
| TMF662 | 100% | Entity Catalog Management API |
| TMF663 | 100% | Shopping Cart Management API |
| TMF664 | 100% | Resource Function Activation Management API |
| TMF666 | 100% | Account Management API |
| TMF667 | 100% | Document Management API |
| TMF668 | 100% | Partnership Management API |
| TMF669 | 100% | Party Role Management API |
| TMF670 | 100% | Payment Method Management API |
| TMF671 | 100% | Promotion Management API |
| TMF672 | 100% | User Role Permission Management API |
| TMF673 | 100% | Geographic Address Management API |
| TMF674 | 100% | Geographic Site Management API |
| TMF675 | NO CTK | Geographic Location Management API |
| TMF676 | 100% | Payment Management API |
| TMF677 | 100% | Usage Consumption Management API |
| TMF678 | 100% | Customer Bill Management API |
| TMF679 | 100% | Product Offering Qualification Management API |
| TMF680 | 100% | Recommendation Management API |
| TMF681 | 100% | Communication Management API |
| TMF683 | 100% | Party Interaction Management API |
| TMF684 | NO CTK | Shipment Tracking Management API |
| TMF685 | NO CTK | Resource Pool Management API |
| TMF686 | NO CTK | Topology Management API |
| TMF687 | 100% | Stock Management API |
| TMF688 | NO CTK | Event Management API |
| TMF691 | NO CTK | Federated ID Management API |
| TMF696 | 100% | Risk Management API |
| TMF699 | 100% | Sales Management API |
| TMF700 | NO CTK | Shipping Order Management API |
| TMF701 | NO CTK | Process Flow Management API |
| TMF702 | 100% | Resource Activation Management API |
| TMF703 | NO CTK | Entity Inventory Management API |
| TMF704 | 100% | Test Case Management API |
| TMF705 | 100% | Test Environment Management API |
| TMF706 | 100% | Test Data Management API |
| TMF707 | 100% | Test Result Management API |
| TMF708 | 100% | Test Execution Management API |
| TMF709 | 100% | Test Scenario Management API |
| TMF710 | 100% | General Test Artifact Management API |
| TMF711 | NO CTK | Shipment Management Management API |
| TMF713 | NO CTK | Work Management |
| TMF714 | NO CTK | Work Qualification Management |
| TMF715 | NO CTK | Warranty Management |
| TMF716 | 100% | Resource Reservation |
| TMF717 | NO CTK | Customer360 Management |
| TMF720 | 100% | Digital Identity Management API |
| TMF724 | 100% | Incident Management API |
| TMF725 | NO CTK | Metadata Catalog Management API |
| TMF727 | NO CTK | Service Usage Management API |
| TMF728 | NO CTK | Dunning Case Management |
| TMF730 | 100% | Software And Compute Management API |
| TMF735 | 100% | CDR Transaction Management API |
| TMF736 | 100% | Revenue Sharing Algorithm Management API |
| TMF737 | 100% | Revenue Sharing Report Management API |
| TMF738 | 100% | Revenue Sharing Model Management |
| TMF759 | NO CTK | Private Optimized Binding |
| TMF760 | 100% | Product Configuration Management API |
| TMF764 | NO CTK | Cost Management API |
| TMF767 | NO CTK | Product Usage Catalog Management API |
| TMF768 | NO CTK | Resource Role API |
| TMF771 | 100% | Resource Usage API |
| TMF777 | NO CTK | Outage Management API |
| TMF908 | NO CTK | IoT Agent and Device Management API |
| TMF909 | NO CTK | Network as a Service Management API |
| TMF910 | NO CTK | Self Care Management API |
| TMF914 | NO CTK | IoT Service Management API |
| TMF915 | 100% | AI Management API |
| TMF921 | 100% | Intent Management API |
| TMF924 | NO CTK | DCS 5GSlice Service Activation API |
| TMF931 | 100% | Open Gateway Onboarding and Ordering Component Suite |
| TMF936 | 100% | Open Gateway Product Catalog API |

## Notes

- Some CTKs run inside Docker and need `host.docker.internal`.
- Some CTKs run locally (non-Docker) and must use `127.0.0.1`.
- Final pass/fail should always be taken from generated per-run summaries under `DOCUMENTATION/ctk_batch_reports/`.
