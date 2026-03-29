# TMF Open API Registry — Full List with CTK Status
# Source: Joao's screenshot of TMForum API table
# ✅ = 100% CTK available  ⚠️ = NO CTK (cannot certify yet)

| TMF ID | CTK | API Name |
|--------|-----|----------|
| TMF620 | ✅  | Product Catalog Management API |
| TMF621 | ✅  | Trouble Ticket Management API |
| TMF622 | ✅  | Product Ordering Management API |
| TMF623 | ⚠️  | SLA Management API |
| TMF628 | ⚠️  | Performance Management API |
| TMF629 | ✅  | Customer Management API |
| TMF632 | ✅  | Party Management API |
| TMF633 | ✅  | Service Catalog Management API |
| TMF634 | ✅  | Resource Catalog Management API |
| TMF635 | ✅  | Usage Management API |
| TMF637 | ✅  | Product Inventory Management API |
| TMF638 | ✅  | Service Inventory Management API |
| TMF639 | ✅  | Resource Inventory Management API |
| TMF640 | ✅  | Service Activation Management API |
| TMF641 | ✅  | Service Ordering Management API |
| TMF642 | ✅  | Alarm Management API |
| TMF644 | ✅  | Privacy Management API |
| TMF645 | ✅  | Service Qualification Management API |
| TMF646 | ✅  | Appointment Management API |
| TMF648 | ✅  | Quote Management API |
| TMF649 | ⚠️  | Performance Thresholding Management API |
| TMF651 | ✅  | Agreement Management API |
| TMF652 | ✅  | Resource Ordering Management API |
| TMF653 | ✅  | Service Test Management API |
| TMF654 | ✅  | Prepay Balance Management API |
| TMF655 | ✅  | Change Management API |
| TMF656 | ✅  | Service Problem Management API |
| TMF657 | ✅  | Service Quality Management API |
| TMF658 | ⚠️  | Loyalty Management API |
| TMF662 | ✅  | Entity Catalog Management API |
| TMF663 | ✅  | Shopping Cart Management API |
| TMF664 | ✅  | Resource Function Activation Management API |
| TMF666 | ✅  | Account Management API |
| TMF667 | ✅  | Document Management API |
| TMF668 | ✅  | Partnership Management API |
| TMF669 | ✅  | Party Role Management API |
| TMF670 | ✅  | Payment Method Management API |
| TMF671 | ✅  | Promotion Management API |
| TMF672 | ✅  | User Role Permission Management API |
| TMF673 | ✅  | Geographic Address Management API |
| TMF674 | ✅  | Geographic Site Management API |
| TMF675 | ⚠️  | Geographic Location Management API |
| TMF676 | ✅  | Payment Management API |
| TMF677 | ✅  | Usage Consumption Management API |
| TMF678 | ✅  | Customer Bill Management API |
| TMF679 | ✅  | Product Offering Qualification Management API |
| TMF680 | ✅  | Recommendation Management API |
| TMF681 | ✅  | Communication Management API |
| TMF683 | ✅  | Party Interaction Management API |
| TMF684 | ⚠️  | Shipment Tracking Management API |
| TMF685 | ⚠️  | Resource Pool Management API |
| TMF686 | ⚠️  | Topology Management API |
| TMF687 | ✅  | Stock Management API |
| TMF688 | ⚠️  | Event Management API |
| TMF691 | ✅  | Federated ID Management API |
| TMF696 | ✅  | Risk Management API |
| TMF699 | ✅  | Sales Management API |
| TMF700 | ⚠️  | Shipping Order Management API |
| TMF701 | ⚠️  | Process Flow Management API |
| TMF702 | ✅  | Resource Activation Management API |
| TMF703 | ⚠️  | Entity Inventory Management API |
| TMF704 | ✅  | Test Case Management API |
| TMF705 | ✅  | Test Environment Management API |
| TMF706 | ✅  | Test Data Management API |
| TMF707 | ✅  | Test Execution Management API (note: likely TMF708) |
| TMF708 | ✅  | Test Execution Management API |
| TMF709 | ✅  | Test Scenario Management API |
| TMF710 | ✅  | General Test Artifact Management API |
| TMF711 | ⚠️  | Shipment Management API |
| TMF713 | ⚠️  | Work Management Management API |
| TMF714 | ⚠️  | Work Qualification Management |
| TMF715 | ⚠️  | Warranty Management |
| TMF716 | ✅  | Resource Reservation |
| TMF717 | ⚠️  | Customer360 Management API |
| TMF720 | ✅  | Digital Identity Management API |
| TMF724 | ⚠️  | Incident Management API |
| TMF725 | ⚠️  | Metadata Catalog Management API |
| TMF727 | ⚠️  | Service Usage Management API |
| TMF728 | ⚠️  | Dunning Case Management API |
| TMF730 | ✅  | Software And Compute Management API |
| TMF735 | ✅  | CDR Transaction Management API |
| TMF736 | ✅  | Revenue Sharing Algorithm Management API |
| TMF737 | ✅  | Revenue Sharing Model Management API |
| TMF738 | ✅  | Revenue Sharing Model Management API |
| TMF759 | ⚠️  | Private Optimized Binding |
| TMF760 | ✅  | Product Configuration Management API |
| TMF764 | ⚠️  | Cost Management API |
| TMF767 | ⚠️  | Product Usage Catalog Management API |
| TMF768 | ✅  | Resource Role API |
| TMF771 | ✅  | Resource Usage API |
| TMF777 | ✅  | Outage Management API |
| TMF908 | ⚠️  | IoT Agent and Device Management API |
| TMF909 | ⚠️  | Network as a Service Management API |
| TMF910 | ⚠️  | Self Care Management API |
| TMF914 | ✅  | IoT Service Management API |
| TMF915 | ✅  | AI Management API |
| TMF921 | ✅  | Intent Management API |
| TMF924 | ⚠️  | DCS 5GSlice Service Activation API |
| TMF931 | ✅  | Open Gateway Onboarding and Ordering Component Suite |
| TMF936 | ✅  | Open Gateway Operate Product Catalog API |

---

## Strategic Implications for OdooTMFOpenAPI

### CTK-certifiable APIs (focus for production compliance)
All APIs marked ✅ have a Conformance Test Kit — these MUST pass CTK to claim ODA component compliance.
Your implementation already covers most of these. The gaps are in wiring (cross-API dependency resolution), not in API scaffolding.

### NO CTK APIs — implement but don't block on certification
APIs marked ⚠️ can be implemented (your scaffolds already exist) but ODA certification won't require them yet.
Key ones in this bucket that affect your commercial flow: TMF675 (Geographic Location), TMF701 (Process Flow), TMF685 (Resource Pool).

### Priority focus for CTK compliance
1. TMF620/622/637 — full CRUD + events (commercial core)
2. TMF632/629/669 — party management  
3. TMF638/641 — service order/inventory
4. TMF621/656 — assurance (trouble ticket / service problem)
