# ============================================================
# Feature: New B2C Customer — Full Order-to-Activate
# BSS Platform: Odoo + TMF Open APIs + ODA Components
# ============================================================
# TMF APIs:  TMF620 (ProductCatalog), TMF622 (ProductOrdering),
#            TMF632 (PartyManagement), TMF641 (ServiceOrdering),
#            TMF645 (CreditManagement)
# ODA:       ProductCatalog, OrderMgmt, PartyMgmt, ServiceActivation
# ============================================================

@b2c @order-to-activate @e2e
Feature: New B2C Customer — Full Order-to-Activate

  Background:
    Given the BSS platform is running and all ODA components are healthy
    And the TMF API gateway is reachable at base URL "/tmf-api"
    And the product catalog contains an active offering "POSTPAID_BASIC_50GB"
      with monthly price 29.99 USD and eligibility segment "B2C"
    And no existing party record exists for email "john.doe@example.com"
    And the credit scoring service is available and in "online" mode


  # ══════════════════════════════════════════════════════════
  # STEP 1 — Customer self-registration (TMF632 PartyMgmt)
  # ══════════════════════════════════════════════════════════

  @registration @tmf632 @smoke
  Scenario: Successful new customer self-registration
    Given a prospective customer with the following details:
      | field          | value                  |
      | firstName      | John                   |
      | lastName       | Doe                    |
      | email          | john.doe@example.com   |
      | nationalId     | 123-45-6789            |
      | dateOfBirth    | 1990-05-15             |
      | contactPhone   | +1-555-010-0001        |
    When a POST request is sent to "/tmf-api/partyManagement/v4/individual"
      with the customer details as request body
    Then the response status code is 201
    And the response body contains a "partyId" field that is a non-empty UUID
    And the response body contains "status": "active"
    And an Odoo partner record is created with the same email and national ID
    And the Odoo partner's "x_tmf_party_id" field matches the returned "partyId"
    And a TMF event of type "PartyCreateEvent" is published to the event bus
      with the new "partyId" in its payload

  @registration @tmf632 @validation
  Scenario: Registration rejected when email already exists
    Given a party record already exists for email "john.doe@example.com"
    When a POST request is sent to "/tmf-api/partyManagement/v4/individual"
      with email "john.doe@example.com"
    Then the response status code is 422
    And the response body contains error code "DUPLICATE_PARTY"
    And no new Odoo partner record is created

  @registration @tmf632 @validation
  Scenario: Registration rejected when national ID already exists under different email
    Given a party record exists with nationalId "123-45-6789" and email "other@example.com"
    When a POST request is sent to "/tmf-api/partyManagement/v4/individual"
      with nationalId "123-45-6789" and email "new@example.com"
    Then the response status code is 422
    And the response body contains error code "DUPLICATE_NATIONAL_ID"

  @registration @tmf632 @validation
  Scenario Outline: Registration rejected for missing mandatory fields
    Given a registration request body missing the "<missing_field>" field
    When a POST request is sent to "/tmf-api/partyManagement/v4/individual"
    Then the response status code is 400
    And the response body contains a validation error referencing "<missing_field>"

    Examples:
      | missing_field |
      | email         |
      | nationalId    |
      | firstName     |
      | lastName      |
      | dateOfBirth   |


  # ══════════════════════════════════════════════════════════
  # STEP 2 — Credit check (TMF645 CreditManagement)
  # ══════════════════════════════════════════════════════════

  @credit-check @tmf645 @smoke
  Scenario: Credit check passes and allows order to proceed
    Given a registered party with partyId "party-uuid-001"
    And the credit scoring service will return score 720 for nationalId "123-45-6789"
    When a POST request is sent to "/tmf-api/creditManagement/v4/creditRatingCheck"
      with body:
        """
        {
          "relatedParty": [{ "id": "party-uuid-001", "@referredType": "Individual" }],
          "requestedCreditAmount": { "value": 29.99, "unit": "USD" }
        }
        """
    Then the response status code is 201
    And the response body contains "creditRatingResult": "approved"
    And the response body contains "creditScore" with value 720
    And the Odoo partner "party-uuid-001" has "credit_limit" set to 500.00
    And the credit check is synchronous — response arrives within 5000 ms

  @credit-check @tmf645 @negative
  Scenario: Credit check fails and blocks order creation
    Given a registered party with partyId "party-uuid-002"
    And the credit scoring service will return score 480 for that party (below threshold 550)
    When a POST request is sent to "/tmf-api/creditManagement/v4/creditRatingCheck"
      with the party reference in the body
    Then the response status code is 201
    And the response body contains "creditRatingResult": "rejected"
    And the Odoo partner "party-uuid-002" has flag "credit_blocked" set to true
    When a subsequent POST is attempted to "/tmf-api/productOrdering/v4/productOrder"
      for party "party-uuid-002"
    Then the response status code is 422
    And the response body contains error code "CREDIT_BLOCK_ACTIVE"

  @credit-check @tmf645 @resilience
  Scenario: Credit scoring service timeout is handled gracefully
    Given a registered party with partyId "party-uuid-003"
    And the credit scoring service is configured to timeout after 6000 ms
    When a POST request is sent to "/tmf-api/creditManagement/v4/creditRatingCheck"
    Then the response status code is 503
    And the response body contains error code "CREDIT_SERVICE_UNAVAILABLE"
    And no order is created for the party
    And the platform does NOT mark the party as credit-blocked


  # ══════════════════════════════════════════════════════════
  # STEP 3 — Product catalog browse (TMF620 ProductCatalog)
  # ══════════════════════════════════════════════════════════

  @catalog @tmf620 @smoke
  Scenario: Eligible B2C offerings are returned for a B2C party
    Given a credit-approved party with segment "B2C"
    When a GET request is sent to
      "/tmf-api/productCatalogManagement/v4/productOffering?segment=B2C&status=active"
    Then the response status code is 200
    And the response body is a JSON array with at least 1 item
    And each item contains "id", "name", "productOfferingPrice", and "validFor" fields
    And the offering "POSTPAID_BASIC_50GB" is present in the response
    And no offering with segment "B2B" appears in the response

  @catalog @tmf620
  Scenario: Pricing rules are applied based on Odoo pricelists
    Given the Odoo pricelist "PROMO_Q1" grants 15% discount for segment "B2C"
    And the pricelist is active and within its validity period
    When a GET request is sent to
      "/tmf-api/productCatalogManagement/v4/productOffering/POSTPAID_BASIC_50GB"
      with header "x-customer-segment: B2C"
    Then the response status code is 200
    And the response body contains a "productOfferingPrice" with value 25.49 USD
      (i.e., 29.99 minus 15%)
    And the price includes a "priceAlteration" entry referencing "PROMO_Q1"


  # ══════════════════════════════════════════════════════════
  # STEP 4 — Product order submission (TMF622 ProductOrdering)
  # ══════════════════════════════════════════════════════════

  @order @tmf622 @smoke
  Scenario: Successful product order submission creates Odoo sale order
    Given a credit-approved party with partyId "party-uuid-001"
    And a billing account exists for that party with billingAccountId "ba-001"
    When a POST request is sent to "/tmf-api/productOrdering/v4/productOrder"
      with body:
        """
        {
          "priority": "4",
          "description": "New B2C subscription",
          "requestedCompletionDate": "<today+5days>",
          "relatedParty": [{ "id": "party-uuid-001", "@referredType": "Individual", "role": "customer" }],
          "billingAccount": { "id": "ba-001" },
          "productOrderItem": [
            {
              "id": "1",
              "quantity": 1,
              "action": "add",
              "productOffering": { "id": "POSTPAID_BASIC_50GB" }
            }
          ]
        }
        """
    Then the response status code is 201
    And the response body contains a "productOrderId" that is a non-empty UUID
    And the response body contains "state": "acknowledged"
    And an Odoo sale order is created with:
      | field               | expected value           |
      | partner_id          | resolved from party-uuid-001 |
      | x_tmf_order_id      | returned productOrderId  |
      | state               | sale                     |
      | amount_total        | 29.99                    |
    And a TMF event "ProductOrderCreateEvent" is published to the event bus

  @order @tmf622
  Scenario: Order state transitions from acknowledged to inProgress
    Given a submitted product order with id "po-uuid-001" in state "acknowledged"
    When the order orchestration engine picks up the order
    Then within 30 seconds the order state transitions to "inProgress"
    And a PATCH is applied internally on "/tmf-api/productOrdering/v4/productOrder/po-uuid-001"
      setting "state": "inProgress"
    And a TMF event "ProductOrderStateChangeEvent" is published
      with "state": "inProgress"

  @order @tmf622 @validation
  Scenario: Order rejected when billingAccount is missing
    Given a credit-approved party with partyId "party-uuid-001"
    When a POST request is sent to "/tmf-api/productOrdering/v4/productOrder"
      with no "billingAccount" in the body
    Then the response status code is 400
    And the response body contains a validation error for "billingAccount"
    And no Odoo sale order is created

  @order @tmf622 @validation
  Scenario: Order rejected for a credit-blocked party
    Given a party with partyId "party-uuid-002" that has "credit_blocked" = true
    When a POST request is sent to "/tmf-api/productOrdering/v4/productOrder"
      for party "party-uuid-002"
    Then the response status code is 422
    And the response body contains error code "CREDIT_BLOCK_ACTIVE"


  # ══════════════════════════════════════════════════════════
  # STEP 5 — Order decomposition & service order (TMF641)
  # ══════════════════════════════════════════════════════════

  @orchestration @tmf641 @smoke
  Scenario: Product order decomposes into a service order
    Given a product order "po-uuid-001" in state "inProgress"
    When the order orchestration engine decomposes the product order
    Then a POST is made to "/tmf-api/serviceOrdering/v4/serviceOrder"
      with "productOrder.id": "po-uuid-001" in its relatedEntity
    And the service order response contains a "serviceOrderId" as non-empty UUID
    And the service order "state" is "acknowledged"
    And the service order is linked to product order "po-uuid-001"
      in the Odoo order management records

  @orchestration @tmf641
  Scenario: Service order progresses to active and SIM is provisioned
    Given a service order "so-uuid-001" linked to product order "po-uuid-001"
    When the ServiceActivation ODA component processes the service order
    Then the service order state transitions through: acknowledged → inProgress → completed
    And a SIM/MSISDN is allocated from the inventory and assigned to the order
    And the allocated MSISDN appears in the service order response under "service.serviceCharacteristic"
      with name "MSISDN"

  @orchestration @tmf641
  Scenario: All sub-orders are tracked independently with their own state
    Given a product order "po-uuid-002" with 3 product order items
    When the orchestration engine decomposes the order
    Then 3 independent service orders are created, one per product order item
    And each service order has its own unique "serviceOrderId"
    And each service order state can change independently without affecting the others


  # ══════════════════════════════════════════════════════════
  # STEP 6 — Provisioning failure & partial rollback
  # ══════════════════════════════════════════════════════════

  @error-path @tmf622 @tmf641 @resilience
  Scenario: SIM activation failure triggers order hold and no orphan service orders
    Given a product order "po-uuid-003" in state "inProgress"
    And a linked service order "so-uuid-003" in state "inProgress"
    When the SIM provisioning system returns a failure:
      """
      { "errorCode": "SIM_ACTIVATION_FAILED", "message": "ICCID not found in inventory" }
      """
    Then the service order "so-uuid-003" transitions to state "failed"
    And the product order "po-uuid-003" transitions to state "held"
    And a TMF event "ProductOrderStateChangeEvent" is published with "state": "held"
    And NO orphan service orders remain in state "inProgress" or "acknowledged"
    And the Odoo sale order remains in state "sale" (not confirmed/cancelled)
      pending manual agent intervention
    And a notification is sent to the operations team with the failure details

  @error-path @tmf622 @resilience
  Scenario: Partial rollback does not affect other concurrent active orders
    Given party "party-uuid-001" has a separate active product order "po-uuid-004"
      in state "completed"
    And a NEW product order "po-uuid-005" for the same party encounters provisioning failure
    When order "po-uuid-005" transitions to state "held"
    Then the pre-existing order "po-uuid-004" remains in state "completed"
    And the services associated with "po-uuid-004" remain active and unaffected

  @error-path @tmf641 @resilience
  Scenario: Service order retry succeeds after transient provisioning error
    Given a service order "so-uuid-006" that failed due to a transient network error
    And the product order is in state "held"
    When an agent triggers a retry by sending a PATCH to
      "/tmf-api/serviceOrdering/v4/serviceOrder/so-uuid-006"
      with body: { "state": "inProgress" }
    Then the service order re-enters state "inProgress"
    And on successful provisioning it transitions to "completed"
    And the parent product order "po-uuid-006" transitions to "completed"


  # ══════════════════════════════════════════════════════════
  # STEP 7 — Activation confirmation & invoice generation
  # ══════════════════════════════════════════════════════════

  @activation @tmf622 @smoke
  Scenario: Completed order triggers invoice generation in Odoo
    Given a product order "po-uuid-007" where all service orders are in state "completed"
    When the orchestration engine marks the product order as completed
    Then a PATCH is applied to "/tmf-api/productOrdering/v4/productOrder/po-uuid-007"
      with "state": "completed"
    And an Odoo invoice is generated with:
      | field         | expected value           |
      | partner_id    | resolved from party      |
      | amount_total  | 29.99                    |
      | currency_id   | USD                      |
      | state         | posted                   |
      | invoice_origin| matching Odoo SO number  |
    And the invoice tax lines reflect the applicable tax rules for the customer's region
    And the invoice is linked to the Odoo sale order via "invoice_ids"

  @activation @tmf622 @events
  Scenario: Completed order publishes event to subscriber webhook
    Given a TMF event subscription exists for event type "ProductOrderStateChangeEvent"
      targeting webhook URL "https://crm.example.com/tmf-events"
    And a product order "po-uuid-008" transitions to state "completed"
    When the event bus processes the state change
    Then a POST is made to "https://crm.example.com/tmf-events" within 10 seconds
      with body containing:
        | field                       | expected value         |
        | event.eventType             | ProductOrderStateChangeEvent |
        | event.event.productOrder.id | po-uuid-008            |
        | event.event.productOrder.state | completed           |
    And the webhook receives HTTP 200 response
    And if the webhook returns 4xx, the event bus retries up to 3 times with exponential backoff

  @activation @tmf622
  Scenario: Completed order state is retrievable via GET
    Given a product order "po-uuid-009" that has been completed
    When a GET request is sent to "/tmf-api/productOrdering/v4/productOrder/po-uuid-009"
    Then the response status code is 200
    And the response body contains "state": "completed"
    And the response body contains "completionDate" as a valid ISO-8601 timestamp
    And the response body contains the "orderItem" array with each item in state "completed"


  # ══════════════════════════════════════════════════════════
  # FULL E2E HAPPY PATH — combined scenario
  # ══════════════════════════════════════════════════════════

  @e2e @smoke @happy-path
  Scenario: Full B2C order-to-activate happy path end-to-end
    # Registration
    Given no existing party for email "e2e.test@example.com"
    When a POST to "/tmf-api/partyManagement/v4/individual" creates a new party
    Then a partyId is returned and stored as "E2E_PARTY_ID"

    # Credit check
    When a POST to "/tmf-api/creditManagement/v4/creditRatingCheck"
      references "E2E_PARTY_ID" and returns "approved"
    Then the Odoo partner is credit-approved

    # Catalog
    When a GET to "/tmf-api/productCatalogManagement/v4/productOffering"
      returns offering "POSTPAID_BASIC_50GB" with price 29.99 USD
    Then the offering is selected for ordering

    # Order
    When a POST to "/tmf-api/productOrdering/v4/productOrder"
      places an order for "POSTPAID_BASIC_50GB" for "E2E_PARTY_ID"
    Then a productOrderId is returned and stored as "E2E_ORDER_ID"
    And an Odoo sale order is created linked to "E2E_ORDER_ID"

    # Orchestration
    When the order orchestrates and creates a service order
    Then the service order transitions to "completed"
    And the product order "E2E_ORDER_ID" transitions to "completed"

    # Invoice
    Then an Odoo invoice of 29.99 USD is generated and posted
    And a "ProductOrderStateChangeEvent" with state "completed" is published

    # Data integrity
    And the TMF product order state is "completed"
    And the Odoo sale order state is "sale" with a linked posted invoice
    And no orphan service orders or resource orders exist for "E2E_ORDER_ID"


  # ══════════════════════════════════════════════════════════
  # DATA INTEGRITY & CROSS-SYSTEM CONSISTENCY
  # ══════════════════════════════════════════════════════════

  @data-integrity
  Scenario: TMF order ID and Odoo sale order are always bidirectionally linked
    Given any completed product order with id "po-uuid-010"
    When querying Odoo for sale orders where "x_tmf_order_id" = "po-uuid-010"
    Then exactly 1 Odoo sale order is returned
    And when querying GET "/tmf-api/productOrdering/v4/productOrder/po-uuid-010"
    Then the response contains "externalId" matching the Odoo sale order name

  @data-integrity
  Scenario: Invoice currency and tax lines match product offering price
    Given a completed order for customer in tax region "CA-US" (California)
    When the invoice is generated in Odoo
    Then the invoice subtotal equals 29.99 USD
    And a tax line for California sales tax (rate 7.25%) equals 2.17 USD
    And the invoice total equals 32.16 USD
    And the product offering price returned by TMF620 was 29.99 (exclusive of tax)

  @data-integrity
  Scenario: Duplicate order submission is idempotent
    Given a product order already submitted with externalId "ext-ref-001"
    When the same POST to "/tmf-api/productOrdering/v4/productOrder"
      is sent again with "externalId": "ext-ref-001"
    Then the response status code is 200 (not 201)
    And the response returns the existing productOrderId
    And no duplicate Odoo sale order is created
    And no duplicate service orders are created
