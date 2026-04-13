import json
import logging

from odoo import api, fields, models


_logger = logging.getLogger(__name__)


class TMFC008ServiceWiring(models.Model):
    """TMFC008 wiring extension for ``tmf.service`` (Service Inventory).

    Pass 1 responsibilities are intentionally narrow and additive:

    - keep existing TMF638 behaviour unchanged (URLs + payload shapes);
    - introduce JSON + relational fields for key YAML dependencies where
      base models already exist (ServiceCatalog, ResourceInventory,
      Party/PartyRole, ServiceOrder);
    - add optional TMF701 process/task-flow links without provisioning
      any flows yet.

    This model does **not** attempt to reconcile geo (TMF673/674/675)
    or permission (TMF672) dependencies in this pass.
    """

    _inherit = "tmf.service"

    # ------------------------------------------------------------------
    # TMF701 linkage (shared with other TMFCs)
    # ------------------------------------------------------------------

    tmfc008_process_flow_ids = fields.Many2many(
        "tmf.process.flow",
        "tmfc008_service_process_flow_rel",
        "service_id",
        "process_flow_id",
        string="Process Flows (TMF701)",
        help=(
            "Optional linkage to TMF701 processFlow records that track "
            "the lifecycle of this Service. Provisioning of flows "
            "remains the responsibility of orchestration components."
        ),
    )

    tmfc008_task_flow_ids = fields.Many2many(
        "tmf.task.flow",
        "tmfc008_service_task_flow_rel",
        "service_id",
        "task_flow_id",
        string="Task Flows (TMF701)",
        help=(
            "Optional linkage to TMF701 taskFlow records spawned as part "
            "of Service lifecycle operations."
        ),
    )

    # ------------------------------------------------------------------
    # Foundational dependency wiring surfaces
    # ------------------------------------------------------------------

    # TMF633 ServiceCatalog: ServiceSpecification refs
    tmfc008_service_spec_ref_json = fields.Json(
        default=list,
        string="ServiceSpecification refs JSON (TMF633)",
        help=(
            "Raw TMF633 ServiceSpecificationRef fragments associated with "
            "this Service (for example from incoming events). Kept for "
            "CTK-level fidelity; relational links below are the "
            "authoritative navigation surface inside Odoo."
        ),
    )

    tmfc008_service_specification_ids = fields.Many2many(
        "tmf.service.specification",
        "tmfc008_service_service_spec_rel",
        "service_id",
        "service_spec_id",
        string="Service Specifications (TMF633)",
        help=(
            "Resolved TMF633 ServiceSpecification records related to this "
            "Service. Resolution logic will be added in a later pass."
        ),
    )

    # TMF639 ResourceInventory: supportingResource refs
    tmfc008_supporting_resource_ref_json = fields.Json(
        default=list,
        string="Supporting Resource refs JSON (TMF639)",
        help=(
            "Raw TMF639 ResourceRef fragments associated with this "
            "Service outside of the primary stock.lot linkage. Used for "
            "future reconciliation without altering TMF638 payloads."
        ),
    )

    tmfc008_supporting_resource_ids = fields.Many2many(
        "stock.lot",
        "tmfc008_service_resource_rel",
        "service_id",
        "lot_id",
        string="Supporting Resources (TMF639)",
        help=(
            "Additional ResourceInventory records (stock.lot) related to "
            "this Service beyond the primary resource_id, when wiring is "
            "available."
        ),
    )

    # TMF632 / TMF669: Party / PartyRole refs
    tmfc008_related_party_json = fields.Json(
        default=list,
        string="RelatedParty JSON (TMF632/TMF669)",
        help=(
            "Raw relatedParty / partyRole fragments from TMF638 payloads. "
            "Existing partner_id and CTK-facing behaviour are preserved."
        ),
    )

    tmfc008_related_partner_ids = fields.Many2many(
        "res.partner",
        "tmfc008_service_partner_rel",
        "service_id",
        "partner_id",
        string="Related Partners (TMF632)",
        help="Resolved TMF632 parties related to this Service.",
    )

    tmfc008_party_role_ids = fields.Many2many(
        "tmf.party.role",
        "tmfc008_service_party_role_rel",
        "service_id",
        "party_role_id",
        string="Party Roles (TMF669)",
        help=(
            "Resolved TMF669 PartyRole records associated with this Service. "
            "Resolution rules will be introduced once we have concrete "
            "payload examples."
        ),
    )

    # TMF641: ServiceOrder refs
    tmfc008_service_order_ref_json = fields.Json(
        default=list,
        string="ServiceOrder refs JSON (TMF641)",
        help=(
            "Raw TMF641 ServiceOrderRef fragments pointing at ServiceOrders "
            "that own or affect this Service."
        ),
    )

    tmfc008_service_order_ids = fields.Many2many(
        "tmf.service.order",
        "tmfc008_service_service_order_rel",
        "service_id",
        "service_order_id",
        string="Service Orders (TMF641)",
        help=(
            "Resolved TMF641 ServiceOrder records that reference this "
            "Service. Wiring is additive and never alters TMF641 payloads."
        ),
    )


class TMFC008WiringTools(models.AbstractModel):
    """Thin wiring/tools layer for TMFC008 listener callbacks.

    In this first implementation pass we **only** provide envelope
    validation and logging. All handlers are deliberately non-mutating
    so that URLs can be considered stable while we gather concrete
    payload examples for reconciliation.
    """

    _name = "tmfc008.wiring.tools"
    _description = "TMFC008 wiring helpers"

    # ------------------------------------------------------------------
    # Generic helpers
    # ------------------------------------------------------------------

    def _log_received_event(self, source, payload):
        _logger.info("TMFC008: received event from %s", source)
        _logger.debug("TMFC008 payload from %s: %s", source, json.dumps(payload))

    # ------------------------------------------------------------------
    # TMF639 ResourceInventory events
    # ------------------------------------------------------------------

    @api.model
    def handle_resource_event(self, payload):
        """Entry point for TMF639 ResourceInventory callbacks.

        Pass 1: log-only, no reconciliation. The primary goal is to keep
        `/tmfc008/listener/resourceInventory` URL stable for future work.
        """

        if not isinstance(payload, dict):
            return
        self._log_received_event("resourceInventory", payload)

    # ------------------------------------------------------------------
    # TMF638 ServiceInventory self-events
    # ------------------------------------------------------------------

    @api.model
    def handle_service_event(self, payload):
        """Entry point for TMF638 ServiceInventory self-subscriptions.

        We currently do not reconcile Service events into additional
        state; the core ``tmf.service`` model already publishes hub
        notifications. This hook reserves the URL for future use.
        """

        if not isinstance(payload, dict):
            return
        self._log_received_event("serviceInventory", payload)

    # ------------------------------------------------------------------
    # TMF633 ServiceCatalog events
    # ------------------------------------------------------------------

    @api.model
    def handle_service_spec_event(self, payload):
        """Entry point for TMF633 ServiceSpecification delete/change events.

        Pass 1: non-mutating scaffolding; concrete reconciliation between
        ServiceInventory and ServiceCatalog will be added once we have
        shared test payloads and rules.
        """

        if not isinstance(payload, dict):
            return
        self._log_received_event("serviceCatalog", payload)

    # ------------------------------------------------------------------
    # TMF632 / TMF669 Party / PartyRole events
    # ------------------------------------------------------------------

    @api.model
    def handle_party_event(self, payload):
        if not isinstance(payload, dict):
            return
        self._log_received_event("party", payload)

    @api.model
    def handle_party_role_event(self, payload):
        if not isinstance(payload, dict):
            return
        self._log_received_event("partyRole", payload)

    # ------------------------------------------------------------------
    # TMF641 ServiceOrder events
    # ------------------------------------------------------------------

    @api.model
    def handle_service_order_event(self, payload):
        if not isinstance(payload, dict):
            return
        self._log_received_event("serviceOrder", payload)


