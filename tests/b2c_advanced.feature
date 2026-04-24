# ============================================================
# Feature: Advanced B2C lifecycle — design, inventory, variants,
#          multi-account, plan/promo change, device swap, SVAs,
#          address change, owner transfer.
# ============================================================
# Covers what a real telco BSS exercises every day beyond the
# basic "order-to-activate" path.
# ============================================================

@b2c @advanced
Feature: Advanced B2C lifecycle scenarios

  Background:
    Given the BSS platform is running
    And the TMF API base is "/tmf-api"


  # ══════════════════════════════════════════════════════════
  # Product design (TMF620 ProductSpec / ProductOffering)
  # ══════════════════════════════════════════════════════════

  @catalog @product-design
  Scenario: A product offering references a product specification
    Given at least one active product offering exists
    When I GET the offering with query "fields=productSpecification"
    Then the response includes a non-null "productSpecification" reference

  @catalog @product-design
  Scenario: A product specification exposes its characteristic schema
    Given a product specification "Internet Fiber"
    When I GET "/productCatalogManagement/v5/productSpecification/{id}"
    Then the response contains "productSpecCharacteristic"
    And each characteristic has a name, valueType and at least one value option

  @catalog @product-design
  Scenario: Bundled offerings declare their child offerings
    Given a bundle offering "Doblepack Negocios"
    When I GET it
    Then "isBundle" is true
    And "bundledProductOffering" contains broadband and telephony children

  @catalog @product-design
  Scenario: Offering with resource specification prescribes required devices
    Given an offering linked to a product spec that has resource specifications
    When I GET the product specification
    Then "resourceSpecification" lists at least one device/CPE spec
    And ordering the offering auto-creates an RFS for each resource specification


  # ══════════════════════════════════════════════════════════
  # Product variants (same spec, different characteristic values)
  # ══════════════════════════════════════════════════════════

  @catalog @variants
  Scenario Outline: Fiber speed variants share the same spec
    Given offerings "FIBER_200M", "FIBER_600M", "FIBER_1G" share product
      specification "Internet Fiber"
    When I order offering "<offering>"
    Then the resulting service has characteristic "downlinkSpeed" = "<speed>"
    And all three offerings produce services of the same @type

    Examples:
      | offering    | speed   |
      | FIBER_200M  | 200Mbps |
      | FIBER_600M  | 600Mbps |
      | FIBER_1G    | 1Gbps   |

  @catalog @variants
  Scenario: Variants can be filtered in the catalog via characteristic query
    When I GET offerings with "productSpecCharacteristic.downlinkSpeed=600Mbps"
    Then the response contains only the 600M variant


  # ══════════════════════════════════════════════════════════
  # Inventory (TMF639 ResourceInventory / stock.lot)
  # ══════════════════════════════════════════════════════════

  @inventory @tmf639
  Scenario: Resource inventory exposes physical devices with serial numbers
    Given CPE devices with serial numbers exist in stock.lot
    When I GET "/resourceInventoryManagement/v5/resource?resourceSpecification.name=CPE"
    Then each item exposes "serialNumber", "state", and "resourceSpecification"

  @inventory @tmf639
  Scenario: Ordering a device decrements available inventory
    Given a CPE with 5 units available
    When an order assigns one device to a service
    Then the available quantity becomes 4
    And the assigned lot is linked to the service resource

  @inventory @tmf639 @validation
  Scenario: Order fails when device stock is zero
    Given a CPE with 0 units available
    When an order requires this device
    Then the service RFS transitions to "failed"
    And the parent order goes to "held"
    And the error message references "OUT_OF_STOCK"


  # ══════════════════════════════════════════════════════════
  # Multi-account per customer (one RUT, multiple accounts)
  # ══════════════════════════════════════════════════════════

  @multi-account
  Scenario: One partner can own multiple accounts with different services
    Given a partner RUT "65614160-3" exists
    And account "HOME" has service "FIBER_200M"
    And account "OFFICE" has service "FIBER_1G" + telephony bundle
    When I GET "/partyManagement/v5/individual/{id}?fields=account"
    Then both accounts appear in the response
    And each account's services can be retrieved independently

  @multi-account @billing
  Scenario: Billing is scoped per account, not per partner
    Given partner has account "HOME" with active service billed at 20000 CLP
    And account "OFFICE" with active service billed at 50000 CLP
    When the monthly bill run is triggered
    Then two distinct customer bills are produced
    And each bill references only its own account


  # ══════════════════════════════════════════════════════════
  # Plan change (upgrade / downgrade)
  # ══════════════════════════════════════════════════════════

  @plan-change
  Scenario: Upgrade from FIBER_200M to FIBER_1G preserves the service identity
    Given an active service with offering "FIBER_200M"
    When I submit a modify order with action "modify" and new offering "FIBER_1G"
    Then the service tmf_id does not change
    And the service characteristic "downlinkSpeed" becomes "1Gbps"
    And a "ProductOrderStateChangeEvent" is published with action "modify"

  @plan-change
  Scenario: Downgrade honors contract commitment period
    Given an active service under minimum term until 2027-01-01
    When a downgrade is requested before the commitment end
    Then the response is 422 with code "TERM_COMMITMENT_ACTIVE"
    And the service plan is unchanged

  @plan-change @billing
  Scenario: Plan change prorates the current billing cycle
    Given a plan change occurs mid-cycle on day 15 of a 30-day cycle
    When the invoice is generated
    Then it contains a prorated credit for the old plan
    And a prorated charge for the new plan starting on day 15


  # ══════════════════════════════════════════════════════════
  # Promotion change
  # ══════════════════════════════════════════════════════════

  @promotion
  Scenario: Apply a promotion to an existing active service
    Given an active service with no promotion
    And a promotion "BLACK_FRIDAY_20" offering 20% off for 6 months
    When a modify order applies the promotion
    Then the service exposes a priceAlteration referencing "BLACK_FRIDAY_20"
    And the next invoice reflects the 20% discount

  @promotion
  Scenario: Swap one promotion for another
    Given an active service with promotion "BLACK_FRIDAY_20"
    When a modify order replaces it with "SUMMER_30"
    Then only "SUMMER_30" appears on the service
    And the original promotion end date is set to yesterday

  @promotion
  Scenario: Remove a promotion before its natural end date
    Given an active service with an ongoing promotion
    When a modify order removes the promotion
    Then the service price reverts to the list price
    And an audit record captures who removed it and when


  # ══════════════════════════════════════════════════════════
  # Device exchange (CPE failure, warranty swap)
  # ══════════════════════════════════════════════════════════

  @device-exchange @inventory
  Scenario: Exchange a faulty CPE while keeping the service active
    Given an active service using device with serial "CPE-OLD-001"
    And a replacement device with serial "CPE-NEW-001" is in stock
    When a device-exchange order is submitted referencing the serial numbers
    Then the service's resource reference is updated to "CPE-NEW-001"
    And "CPE-OLD-001" is moved to state "RMA" / "returned"
    And the service never leaves state "active"

  @device-exchange @billing
  Scenario: In-warranty device exchange is free; out-of-warranty is charged
    Given the faulty device is within its 12-month warranty
    When the exchange completes
    Then no charge is posted

    Given the faulty device is 18 months old (out of warranty)
    When the exchange completes
    Then a one-time charge for the replacement device is added to the next bill


  # ══════════════════════════════════════════════════════════
  # SVAs (Value-Added Services / add-ons)
  # ══════════════════════════════════════════════════════════

  @sva
  Scenario: Add an SVA (static IP) to an active broadband service
    Given an active broadband service
    And an SVA offering "STATIC_IP"
    When a modify order adds "STATIC_IP" as a child service
    Then a new tmf.service is created with parent_service_id = broadband
    And the broadband service's supportingService array now includes the SVA

  @sva
  Scenario Outline: Add multiple SVAs in one order
    Given an active broadband service
    When a modify order adds SVAs "<sva1>" and "<sva2>"
    Then both SVAs are created as child services
    And each is billable independently on the next bill

    Examples:
      | sva1            | sva2              |
      | STATIC_IP       | PREMIUM_SUPPORT   |
      | INT_CALLS_100   | STREAMING_BUNDLE  |

  @sva
  Scenario: Remove an SVA does not cancel the parent service
    Given an active broadband service with SVA "STATIC_IP"
    When a modify order removes "STATIC_IP"
    Then the SVA child service transitions to state "terminated"
    And the parent broadband service remains "active"


  # ══════════════════════════════════════════════════════════
  # Address change (same service, new location)
  # ══════════════════════════════════════════════════════════

  @address-change
  Scenario: Relocate a service to a new service address
    Given an active service installed at address A
    And a feasibility check exists approving address B for the same offering
    When a modify order changes the service address to address B
    Then the service's place reference points to address B
    And a technical work order is created to the field technician
    And the service state moves "active" → "pendingActive" → "active"

  @address-change @validation
  Scenario: Relocation fails when feasibility check for new address is denied
    Given a service at address A
    And feasibility at address B returned "unqualified"
    When a relocation to address B is requested
    Then the response is 422 with code "NO_FEASIBILITY"
    And the service address is unchanged


  # ══════════════════════════════════════════════════════════
  # Account owner change (service continuity)
  # ══════════════════════════════════════════════════════════

  @owner-change
  Scenario: Transfer ownership from partner A to partner B — services continue
    Given partner A owns account "ACCT-001" with two active services
    When an owner-change order transfers "ACCT-001" to partner B
    Then "ACCT-001".partner_id becomes partner B
    And both services remain in state "active"
    And the service tmf_ids are unchanged
    And the next invoice is issued to partner B

  @owner-change @billing
  Scenario: Outstanding balance of previous owner is NOT inherited
    Given partner A has unpaid invoices on the account being transferred
    When the ownership transfers to partner B
    Then the unpaid invoices remain attributed to partner A
    And partner B's first invoice starts from the transfer date


  # ══════════════════════════════════════════════════════════
  # Data integrity across the advanced flows
  # ══════════════════════════════════════════════════════════

  @data-integrity
  Scenario: Every active service always has a parent account
    Given the full test dataset has been seeded
    When I query all tmf.service records in state "active"
    Then every record has a non-null account_id

  @data-integrity
  Scenario: CFS always has at least one RFS child when required by its spec
    Given an active CFS whose product spec declares resourceSpecifications
    Then child_service_ids for that CFS is non-empty
