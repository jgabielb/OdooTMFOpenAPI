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
    """Wiring/tools layer for TMFC008 listener callbacks.

    Pass 2 behaviour stays **additive and conservative**:

    - Do not change TMF638 URLs or payload shapes.
    - Never create or delete master data records.
    - Use incoming events to keep TMFC008 side-car JSON + relational
      fields on ``tmf.service`` in sync with existing ServiceCatalog,
      ResourceInventory, Party/PartyRole, and ServiceOrder records.

    All writes use ``skip_tmf_wiring`` in context to avoid recursive
    notifications.
    """

    _name = "tmfc008.wiring.tools"
    _description = "TMFC008 wiring helpers"

    # ------------------------------------------------------------------
    # Generic helpers
    # ------------------------------------------------------------------

    def _log_received_event(self, source, event_name, payload):
        _logger.info("TMFC008: received %s event %s", source, event_name)
        _logger.debug(
            "TMFC008 payload for %s/%s: %s",
            source,
            event_name,
            json.dumps(payload),
        )

    def _extract_event_type(self, payload):
        if not isinstance(payload, dict):
            return ""
        return str(payload.get("eventType") or "").strip()

    def _extract_event_resource(self, payload, preferred_keys=None):
        """Extract nested resource dict from a TMF event envelope.

        Mirrors the helper patterns used in TMFC003/TMFC007 so that we
        can safely consume standard TMF event envelopes of the form:

            {"eventType": "...", "event": {"resource": {...}}}
        """

        if not isinstance(payload, dict):
            return {}

        event = payload.get("event")
        if isinstance(event, dict):
            keys = list(preferred_keys or []) or [
                "service",
                "resource",
                "serviceSpecification",
                "party",
                "partyRole",
                "individual",
                "organization",
                "serviceOrder",
            ]
            for key in keys:
                if isinstance(event.get(key), dict):
                    return event[key]

        # Fallback: treat payload as the resource itself
        return payload

    def _extract_resource_id(self, payload, preferred_keys=None):
        resource = self._extract_event_resource(payload, preferred_keys=preferred_keys)
        if not isinstance(resource, dict):
            resource = {}
        return str(resource.get("id") or payload.get("id") or "").strip()

    # ------------------------------------------------------------------
    # TMF639 ResourceInventory events
    # ------------------------------------------------------------------

    @api.model
    def handle_resource_event(self, payload):
        """Entry point for TMF639 ResourceInventory callbacks.

        Best-effort behaviour:
        - confirm the referenced Resource (stock.lot) exists;
        - attach it as a supporting resource on any Services that already
          point at it via ``resource_id``.

        This gives TMFC008 truthful dependency wiring without changing
        the primary ``resource_id`` linkage or creating new Resources.
        """

        if not isinstance(payload, dict):
            return

        event_type = self._extract_event_type(payload)
        self._log_received_event("resourceInventory", event_type, payload)

        rid = self._extract_resource_id(payload, preferred_keys=["resource"])
        if not rid:
            return

        Resource = self.env["stock.lot"].sudo()
        Service = self.env["tmf.service"].sudo()

        # Resolve the Resource by tmf_id first, then by numeric ID.
        resource = Resource.search([("tmf_id", "=", rid)], limit=1)
        if not resource and rid.isdigit():
            resource = Resource.browse(int(rid))
        if not resource or not resource.exists():
            return

        # Find services that already use this resource as their primary
        # supportingResource; we do not invent new links.
        services = Service.search([("resource_id", "=", resource.id)])
        if not services:
            return

        ctx = {"skip_tmf_wiring": True}
        for svc in services:
            # Build a minimal TMF639 ResourceRef payload for traceability.
            ref = {
                "id": resource.tmf_id or str(resource.id),
                "href": svc._abs_href(
                    f"/tmf-api/resourceInventoryManagement/v4/resource/{resource.tmf_id or resource.id}"
                ),
                "name": resource.name or getattr(resource, "display_name", "") or "",
                "@type": "ResourceRef",
                "@referredType": "Resource",
            }

            existing = svc.tmfc008_supporting_resource_ref_json or []
            if isinstance(existing, dict):
                existing = [existing]

            # Idempotent append.
            if not any(isinstance(e, dict) and str(e.get("id")) == ref["id"] for e in existing):
                existing.append(ref)

            svc.with_context(**ctx).write(
                {
                    "tmfc008_supporting_resource_ref_json": existing,
                    "tmfc008_supporting_resource_ids": [(4, resource.id)],
                }
            )

    # ------------------------------------------------------------------
    # TMF638 ServiceInventory self-events
    # ------------------------------------------------------------------

    @api.model
    def handle_service_event(self, payload):
        """Entry point for TMF638 ServiceInventory self-subscriptions.

        For now we keep this as a logging-only hook. The base
        ``tmf.service`` model already publishes TMF638 events; TMFC008
        does not need to mirror additional state from those events yet.
        """

        if not isinstance(payload, dict):
            return
        event_type = self._extract_event_type(payload)
        self._log_received_event("serviceInventory", event_type, payload)

    # ------------------------------------------------------------------
    # TMF633 ServiceCatalog events
    # ------------------------------------------------------------------

    @api.model
    def handle_service_spec_event(self, payload):
        """Handle TMF633 ServiceSpecification events.

        Best-effort behaviour:
        - locate the referenced ``tmf.service.specification`` record;
        - attach it to any Services that already expose it via
          ``product_specification_id``;
        - persist a minimal ServiceSpecificationRef in
          ``tmfc008_service_spec_ref_json`` for traceability.

        This keeps ServiceInventory�+?ServiceCatalog wiring truthful
        without changing the primary product_specification_id behaviour.
        """

        if not isinstance(payload, dict):
            return

        event_type = self._extract_event_type(payload)
        self._log_received_event("serviceCatalog", event_type, payload)

        spec_id = self._extract_resource_id(payload, preferred_keys=["serviceSpecification"])
        if not spec_id:
            return

        ServiceSpec = self.env["tmf.service.specification"].sudo()
        Service = self.env["tmf.service"].sudo()

        spec = ServiceSpec.search([("tmf_id", "=", spec_id)], limit=1)
        if not spec and spec_id.isdigit():
            spec = ServiceSpec.browse(int(spec_id))
        if not spec or not spec.exists():
            return

        # Only wire services that are already linked to this spec via the
        # existing product_specification_id field, to avoid guessing.
        services = Service.search([("product_specification_id", "=", spec.id)])
        if not services:
            return

        ctx = {"skip_tmf_wiring": True}
        for svc in services:
            ref = {
                "id": spec.tmf_id or str(spec.id),
                "href": svc._abs_href(
                    f"/tmf-api/serviceCatalogManagement/v5/serviceSpecification/{spec.tmf_id or spec.id}"
                ),
                "name": spec.name or "",
                "version": getattr(spec, "version", None) or None,
                "@type": "ServiceSpecificationRef",
                "@referredType": "ServiceSpecification",
            }

            existing = svc.tmfc008_service_spec_ref_json or []
            if isinstance(existing, dict):
                existing = [existing]

            if not any(isinstance(e, dict) and str(e.get("id")) == ref["id"] for e in existing):
                existing.append(ref)

            svc.with_context(**ctx).write(
                {
                    "tmfc008_service_spec_ref_json": existing,
                    "tmfc008_service_specification_ids": [(4, spec.id)],
                }
            )

    # ------------------------------------------------------------------
    # TMF632 / TMF669 Party / PartyRole events
    # ------------------------------------------------------------------

    @api.model
    def handle_party_event(self, payload):
        """Handle TMF632 PartyManagement events.

        Best-effort behaviour:
        - resolve the referenced Party to ``res.partner``;
        - ensure any Services already owned by that partner record the
          Party in ``tmfc008_related_partner_ids`` and capture a
          lightweight RelatedPartyRef in ``tmfc008_related_party_json``.
        """

        if not isinstance(payload, dict):
            return

        event_type = self._extract_event_type(payload)
        self._log_received_event("party", event_type, payload)

        party_id = self._extract_resource_id(payload, preferred_keys=["party", "individual", "organization"])
        if not party_id:
            return

        Partner = self.env["res.partner"].sudo()
        Service = self.env["tmf.service"].sudo()

        partner = Partner.search([("tmf_id", "=", party_id)], limit=1)
        if not partner and party_id.isdigit():
            partner = Partner.browse(int(party_id))
        if not partner or not partner.exists():
            return

        services = Service.search([("partner_id", "=", partner.id)])
        if not services:
            return

        ctx = {"skip_tmf_wiring": True}
        for svc in services:
            party_href = f"/tmf-api/partyManagement/v5/party/{partner.tmf_id or partner.id}"
            party_ref = {
                "id": partner.tmf_id or str(partner.id),
                "href": svc._abs_href(party_href),
                "name": partner.name or "",
                "@type": "PartyRef",
                "@referredType": "Organization" if partner.is_company else "Individual",
            }

            existing = svc.tmfc008_related_party_json or []
            if isinstance(existing, dict):
                existing = [existing]

            if not any(isinstance(e, dict) and str(e.get("id")) == party_ref["id"] for e in existing):
                existing.append(party_ref)

            svc.with_context(**ctx).write(
                {
                    "tmfc008_related_party_json": existing,
                    "tmfc008_related_partner_ids": [(4, partner.id)],
                }
            )

    @api.model
    def handle_party_role_event(self, payload):
        """Handle TMF669 PartyRoleManagement events.

        We keep this conservative: when the referenced PartyRole exists,
        attach it to Services whose customer (partner) matches the
        PartyRef inside the role payload, when that can be resolved.
        """

        if not isinstance(payload, dict):
            return

        event_type = self._extract_event_type(payload)
        self._log_received_event("partyRole", event_type, payload)

        resource = self._extract_event_resource(payload, preferred_keys=["partyRole"])
        if not isinstance(resource, dict):
            return

        role_id = str(resource.get("id") or "").strip()
        if not role_id:
            return

        PartyRole = self.env["tmf.party.role"].sudo()
        Partner = self.env["res.partner"].sudo()
        Service = self.env["tmf.service"].sudo()

        party_role = PartyRole.search([("tmf_id", "=", role_id)], limit=1)
        if not party_role and role_id.isdigit():
            party_role = PartyRole.browse(int(role_id))
        if not party_role or not party_role.exists():
            return

        # Try to infer the underlying party from the payload; if we
        # cannot, we still record the role on all services that already
        # reference this PartyRole.
        party_ref = resource.get("party") or {}
        partner_ids = []
        if isinstance(party_ref, dict):
            pid = str(party_ref.get("id") or "").strip()
            if pid:
                partner = Partner.search([("tmf_id", "=", pid)], limit=1)
                if not partner and pid.isdigit():
                    partner = Partner.browse(int(pid))
                if partner and partner.exists():
                    partner_ids.append(partner.id)

        domain = []
        if partner_ids:
            domain = ["&", ("partner_id", "in", partner_ids), ("id", "!=", False)]

        services = Service.search(domain) if domain else Service.browse()
        if not services:
            return

        ctx = {"skip_tmf_wiring": True}
        for svc in services:
            svc.with_context(**ctx).write(
                {
                    "tmfc008_party_role_ids": [(4, party_role.id)],
                }
            )

    # ------------------------------------------------------------------
    # TMF641 ServiceOrder events
    # ------------------------------------------------------------------

    @api.model
    def handle_service_order_event(self, payload):
        """Handle TMF641 ServiceOrder events.

        Best-effort behaviour:
        - resolve the ServiceOrder by tmf_id;
        - inspect ``serviceOrderItem[*].service`` for Service refs;
        - attach the ServiceOrder to matching ``tmf.service`` records via
          ``tmfc008_service_order_ids`` and persist raw ServiceOrderRef
          fragments in ``tmfc008_service_order_ref_json``.
        """

        if not isinstance(payload, dict):
            return

        event_type = self._extract_event_type(payload)
        self._log_received_event("serviceOrder", event_type, payload)

        ServiceOrder = self.env["tmf.service.order"].sudo()
        Service = self.env["tmf.service"].sudo()

        resource = self._extract_event_resource(payload, preferred_keys=["serviceOrder"])
        if not isinstance(resource, dict):
            return

        so_id = str(resource.get("id") or "").strip()
        if not so_id:
            return

        service_order = ServiceOrder.search([("tmf_id", "=", so_id)], limit=1)
        if not service_order and so_id.isdigit():
            service_order = ServiceOrder.browse(int(so_id))
        if not service_order or not service_order.exists():
            return

        items = resource.get("serviceOrderItem") or []
        if isinstance(items, dict):
            items = [items]
        if not isinstance(items, list):
            items = []

        # Collect service IDs referenced from the order items.
        service_ids = []
        for item in items:
            if not isinstance(item, dict):
                continue
            svc_ref = item.get("service") or {}
            if not isinstance(svc_ref, dict):
                continue
            sid = str(svc_ref.get("id") or "").strip()
            if not sid:
                continue

            svc = Service.search([("tmf_id", "=", sid)], limit=1)
            if not svc and sid.isdigit():
                svc = Service.browse(int(sid))
            if svc and svc.exists():
                service_ids.append(svc.id)

        if not service_ids:
            return

        ctx = {"skip_tmf_wiring": True}
        for svc in Service.browse(service_ids):
            existing = svc.tmfc008_service_order_ref_json or []
            if isinstance(existing, dict):
                existing = [existing]

            # Keep a minimal ServiceOrderRef for this link.
            order_ref = {
                "id": service_order.tmf_id or str(service_order.id),
                "href": svc._abs_href(
                    f"/tmf-api/serviceOrderingManagement/v5/serviceOrder/{service_order.tmf_id or service_order.id}"
                ),
                "@type": "ServiceOrderRef",
                "@referredType": "ServiceOrder",
            }

            if not any(isinstance(e, dict) and str(e.get("id")) == order_ref["id"] for e in existing):
                existing.append(order_ref)

            svc.with_context(**ctx).write(
                {
                    "tmfc008_service_order_ref_json": existing,
                    "tmfc008_service_order_ids": [(4, service_order.id)],
                }
            )

