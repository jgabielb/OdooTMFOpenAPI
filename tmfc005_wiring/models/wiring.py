import json

from odoo import api, fields, models


TMFC005_LISTENER_EVENTS = {
    "resourceDeleteEvent",
    "serviceDeleteEvent",
    "productSpecificationDeleteEvent",
    "productOfferingDeleteEvent",
    "productOfferingPriceDeleteEvent",
    "partyRoleDeleteEvent",
    "agreementDeleteEvent",
}


def _loads(value):
    if not value:
        return None
    try:
        return json.loads(value) if isinstance(value, str) else value
    except Exception:
        return None


def _resolve_ids(env, model, items, id_field="tmf_id"):
    """Batch-search model by tmf_id for all item dicts. Returns list of record IDs."""
    ref_ids = []
    for item in (items or []):
        if not isinstance(item, dict):
            continue
        ref_id = str(item.get("id") or "").strip()
        if ref_id:
            ref_ids.append(ref_id)
    if not ref_ids:
        return []
    return env[model].sudo().search([(id_field, "in", ref_ids)]).ids


class ProductInventoryTMFC005Wiring(models.Model):
    """TMFC005 dependent API wiring for Product Inventory (TMF637-style Product).

    This wiring does NOT change TMF API behaviour. It enriches tmf.product
    records (extended by tmf_product_inventory) with Odoo stock relations and
    ODA dependency links so the ProductInventory component can navigate:

    - TMF Product -> Odoo product.template/product.product
    - TMF Product -> stock.location/stock.lot/stock.quant
    - TMF Product -> ProductCatalog/Party/Agreement/Billing/Service refs
    """

    _inherit = "tmf.product"

    stock_location_ref_json = fields.Json(default=list, string="Location refs JSON (TMF673/675)")
    lot_ref_json = fields.Json(default=list, string="Batch/Lot refs JSON")
    agreement_ref_json = fields.Json(default=list, string="Agreement refs JSON (TMF651)")
    billing_account_ref_json = fields.Json(default=dict, string="BillingAccount JSON (TMF666)")
    product_specification_ref_json = fields.Json(default=dict, string="ProductSpecification JSON (TMF620)")
    product_offering_ref_json = fields.Json(default=list, string="ProductOffering refs JSON (TMF620)")
    product_offering_price_ref_json = fields.Json(default=list, string="ProductOfferingPrice refs JSON (TMF620)")
    product_order_ref_json = fields.Json(default=list, string="ProductOrder refs JSON (TMF622)")
    related_party_ref_json = fields.Json(default=list, string="Related parties JSON (TMF632/TMF669)")
    realizing_service_ref_json = fields.Json(default=list, string="Realizing service refs JSON (TMF638)")
    realizing_resource_ref_json = fields.Json(default=list, string="Realizing resource refs JSON (TMF639)")
    place_ref_json = fields.Json(default=list, string="Place refs JSON (TMF673/674/675)")

    product_tmpl_id = fields.Many2one(
        "product.template", string="Odoo Product Template",
        index=True, ondelete="set null",
    )
    product_id = fields.Many2one(
        "product.product", string="Odoo Product",
        index=True, ondelete="set null",
    )
    stock_location_id = fields.Many2one(
        "stock.location", string="Stock Location",
        index=True, ondelete="set null",
    )
    stock_lot_id = fields.Many2one(
        "stock.lot", string="Lot/Serial",
        index=True, ondelete="set null",
    )
    stock_quant_id = fields.Many2one(
        "stock.quant", string="Stock Quant",
        index=True, ondelete="set null",
    )
    product_specification_id = fields.Many2one(
        "tmf.product.specification", string="Product Specification (TMF620)",
        index=True, ondelete="set null",
    )
    party_role_id = fields.Many2one(
        "tmf.party.role", string="Party Role (TMF669)",
        index=True, ondelete="set null",
    )
    billing_account_id = fields.Many2one(
        "tmf.billing.account", string="Billing Account (TMF666)",
        index=True, ondelete="set null",
    )
    geographic_address_id = fields.Many2one(
        "tmf.geographic.address", string="Geographic Address (TMF673)",
        index=True, ondelete="set null",
    )
    geographic_site_id = fields.Many2one(
        "tmf.geographic.site", string="Geographic Site (TMF674)",
        index=True, ondelete="set null",
    )
    geographic_location_id = fields.Many2one(
        "tmf.geographic.location", string="Geographic Location (TMF675)",
        index=True, ondelete="set null",
    )
    agreement_ids = fields.Many2many(
        "tmf.agreement", "tmfc005_product_agreement_rel",
        "product_id", "agreement_id", string="Agreements (TMF651)",
    )
    related_partner_ids = fields.Many2many(
        "res.partner", "tmfc005_product_partner_rel",
        "product_id", "partner_id", string="Related Parties (TMF632)",
    )
    product_offering_ids = fields.Many2many(
        "product.template", "tmfc005_product_offering_rel",
        "product_id", "offering_id", string="Product Offerings (TMF620)",
    )
    product_offering_price_ids = fields.Many2many(
        "tmf.product.offering.price", "tmfc005_product_offering_price_rel",
        "product_id", "price_id", string="Product Offering Prices (TMF620)",
    )
    service_ids = fields.Many2many(
        "tmf.service", "tmfc005_product_service_rel",
        "product_id", "service_id", string="Realizing Services (TMF638)",
    )
    resource_ids = fields.Many2many(
        "tmf.resource", "tmfc005_product_resource_rel",
        "product_id", "resource_id", string="Realizing Resources (TMF639)",
    )
    process_flow_ids = fields.Many2many(
        "tmf.process.flow", "tmfc005_product_process_flow_rel",
        "product_id", "process_flow_id", string="Process Flows (TMF701)",
    )
    task_flow_ids = fields.Many2many(
        "tmf.task.flow", "tmfc005_product_task_flow_rel",
        "product_id", "task_flow_id", string="Task Flows (TMF701)",
    )

    def _notify(self, api_name_or_action, action=None, record=None, payloads=None):
        hub = self.env["tmf.hub.subscription"].sudo()
        action_name = api_name_or_action if action is None else action

        event_map = {
            "create": "ProductCreateEvent",
            "update": "ProductAttributeValueChangeEvent",
            "state_change": "ProductStateChangeEvent",
            "delete": "ProductDeleteEvent",
            "batch": "ProductBatchEvent",
        }
        event_name = event_map.get(action_name)
        if not event_name:
            return
        if payloads is None:
            if record is not None:
                payloads = [record.to_tmf_json()]
            else:
                payloads = [rec.to_tmf_json() for rec in self]
        if action_name == "batch":
            payload = {
                "eventId": "tmfc005-product-batch",
                "eventType": event_name,
                "event": {
                    "product": payloads,
                },
            }
            try:
                hub._notify_subscribers("product", event_name, payload)
            except Exception:
                return
            return
        for payload in payloads:
            try:
                hub._notify_subscribers("product", event_name, payload)
            except Exception:
                continue

    def _resolve_tmf_refs(self):
        ctx = {"skip_tmf_wiring": True}
        for rec in self:
            updates = {}

            payload = _loads(getattr(rec, "payload", None)) or {}

            if not rec.product_tmpl_id:
                name = (rec.name or "").strip()
                tmpl = None
                if getattr(rec, "product_template_tmf_id", None):
                    tmpl = self.env["product.template"].sudo().search(
                        [("tmf_id", "=", rec.product_template_tmf_id)], limit=1
                    )
                if not tmpl and name:
                    tmpl = self.env["product.template"].sudo().search(
                        [("name", "=", name)], limit=1
                    )
                if not tmpl and rec.odoo_product_tmpl_id:
                    tmpl = rec.odoo_product_tmpl_id
                if not tmpl and rec.odoo_product_id:
                    tmpl = rec.odoo_product_id.product_tmpl_id
                if tmpl:
                    updates["product_tmpl_id"] = tmpl.id

            effective_product = rec.product_id or rec.odoo_product_id
            effective_tmpl = rec.product_tmpl_id or rec.odoo_product_tmpl_id
            if not rec.product_id and effective_tmpl:
                prod = self.env["product.product"].sudo().search(
                    [("product_tmpl_id", "=", effective_tmpl.id)], limit=1
                )
                if prod:
                    updates["product_id"] = prod.id
                    effective_product = prod

            loc_items = rec.stock_location_ref_json or rec.place_ref_json or payload.get("place") or []
            if isinstance(loc_items, dict):
                loc_items = [loc_items]
            if not rec.stock_location_id and loc_items:
                ids = _resolve_ids(self.env, "stock.location", loc_items, id_field="tmf_id")
                if not ids:
                    names = {str(i.get("name") or "").strip() for i in loc_items if isinstance(i, dict)}
                    if names:
                        match = self.env["stock.location"].sudo().search(
                            [("name", "in", list(names))], limit=1
                        )
                        if match:
                            ids = [match.id]
                if ids:
                    updates["stock_location_id"] = ids[0]

            lot_items = rec.lot_ref_json or payload.get("productInstance") or []
            if isinstance(lot_items, dict):
                lot_items = [lot_items]
            if not rec.stock_lot_id and lot_items:
                ids = _resolve_ids(self.env, "stock.lot", lot_items, id_field="tmf_id")
                if not ids:
                    serials = {str(i.get("serialNumber") or "").strip() for i in lot_items if isinstance(i, dict)}
                    if serials:
                        match = self.env["stock.lot"].sudo().search(
                            [("name", "in", list(serials))], limit=1
                        )
                        if match:
                            ids = [match.id]
                if ids:
                    updates["stock_lot_id"] = ids[0]

            effective_location = rec.stock_location_id or self.env["stock.location"].browse(updates.get("stock_location_id", False))
            effective_lot = rec.stock_lot_id or self.env["stock.lot"].browse(updates.get("stock_lot_id", False))
            if not rec.stock_quant_id and effective_product and effective_location:
                domain = [
                    ("product_id", "=", effective_product.id),
                    ("location_id", "=", effective_location.id),
                ]
                if effective_lot:
                    domain.append(("lot_id", "=", effective_lot.id))
                quant = self.env["stock.quant"].sudo().search(domain, limit=1)
                if quant:
                    updates["stock_quant_id"] = quant.id

            effective_product_spec = rec.product_specification_ref_json or rec.product_specification_json or payload.get("productSpecification") or {}
            if not rec.product_specification_id and isinstance(effective_product_spec, dict):
                spec_id = str(effective_product_spec.get("id") or "").strip()
                if spec_id:
                    match = self.env["tmf.product.specification"].sudo().search(
                        [("tmf_id", "=", spec_id)], limit=1
                    )
                    if match:
                        updates["product_specification_id"] = match.id

            offering_refs = rec.product_offering_ref_json or payload.get("productOffering") or rec.product_offering or []
            if isinstance(offering_refs, dict):
                offering_refs = [offering_refs]
            if not rec.product_offering_ids and offering_refs:
                ids = _resolve_ids(self.env, "product.template", offering_refs)
                if ids:
                    updates["product_offering_ids"] = [(6, 0, ids)]

            price_refs = rec.product_offering_price_ref_json or payload.get("productPrice") or rec.product_price or []
            if isinstance(price_refs, dict):
                price_refs = [price_refs]
            if not rec.product_offering_price_ids and price_refs:
                ids = _resolve_ids(self.env, "tmf.product.offering.price", price_refs)
                if ids:
                    updates["product_offering_price_ids"] = [(6, 0, ids)]

            agreement_refs = rec.agreement_ref_json or payload.get("agreement") or rec.agreement or []
            if isinstance(agreement_refs, dict):
                agreement_refs = [agreement_refs]
            if not rec.agreement_ids and agreement_refs:
                ids = _resolve_ids(self.env, "tmf.agreement", agreement_refs)
                if ids:
                    updates["agreement_ids"] = [(6, 0, ids)]

            related_party_refs = rec.related_party_ref_json or payload.get("relatedParty") or rec.related_party_json or rec.related_party or []
            if isinstance(related_party_refs, dict):
                related_party_refs = [related_party_refs]
            if not rec.related_partner_ids and related_party_refs:
                partner_items = [
                    item for item in related_party_refs
                    if isinstance(item, dict) and item.get("@type") not in ("PartyRole", "PartyRoleRef")
                ]
                ids = _resolve_ids(self.env, "res.partner", partner_items)
                if ids:
                    updates["related_partner_ids"] = [(6, 0, ids)]
            if not rec.party_role_id and related_party_refs:
                role_items = [
                    item for item in related_party_refs
                    if isinstance(item, dict) and item.get("@type") in ("PartyRole", "PartyRoleRef")
                ]
                ids = _resolve_ids(self.env, "tmf.party.role", role_items)
                if ids:
                    updates["party_role_id"] = ids[0]

            if not rec.billing_account_id:
                ba = rec.billing_account_ref_json or payload.get("billingAccount") or rec.billing_account or {}
                if isinstance(ba, dict):
                    ba_id = str(ba.get("id") or "").strip()
                    if ba_id:
                        match = self.env["tmf.billing.account"].sudo().search(
                            [("tmf_id", "=", ba_id)], limit=1
                        )
                        if match:
                            updates["billing_account_id"] = match.id

            service_refs = rec.realizing_service_ref_json or payload.get("realizingService") or rec.realizing_service_json or rec.realizing_service or []
            if isinstance(service_refs, dict):
                service_refs = [service_refs]
            if not rec.service_ids and service_refs:
                ids = _resolve_ids(self.env, "tmf.service", service_refs)
                if ids:
                    updates["service_ids"] = [(6, 0, ids)]

            resource_refs = rec.realizing_resource_ref_json or payload.get("realizingResource") or rec.realizing_resource or []
            if isinstance(resource_refs, dict):
                resource_refs = [resource_refs]
            if not rec.resource_ids and resource_refs:
                ids = _resolve_ids(self.env, "tmf.resource", resource_refs)
                if ids:
                    updates["resource_ids"] = [(6, 0, ids)]

            place_refs = rec.place_ref_json or payload.get("place") or rec.place_json or rec.place or []
            if isinstance(place_refs, dict):
                place_refs = [place_refs]
            if place_refs and not all([rec.geographic_address_id, rec.geographic_site_id, rec.geographic_location_id]):
                addr_ids, site_ids, loc_ids = [], [], []
                for item in place_refs:
                    if not isinstance(item, dict):
                        continue
                    ref_id = str(item.get("id") or "").strip()
                    if not ref_id:
                        continue
                    at_type = item.get("@type", "")
                    if at_type in ("GeographicAddress", "GeographicAddressRef"):
                        addr_ids.append(ref_id)
                    elif at_type in ("GeographicSite", "GeographicSiteRef"):
                        site_ids.append(ref_id)
                    elif at_type in ("GeographicLocation", "GeographicLocationRef"):
                        loc_ids.append(ref_id)
                if addr_ids and not rec.geographic_address_id:
                    match = self.env["tmf.geographic.address"].sudo().search([("tmf_id", "in", addr_ids)], limit=1)
                    if match:
                        updates["geographic_address_id"] = match.id
                if site_ids and not rec.geographic_site_id:
                    match = self.env["tmf.geographic.site"].sudo().search([("tmf_id", "in", site_ids)], limit=1)
                    if match:
                        updates["geographic_site_id"] = match.id
                if loc_ids and not rec.geographic_location_id:
                    match = self.env["tmf.geographic.location"].sudo().search([("tmf_id", "in", loc_ids)], limit=1)
                    if match:
                        updates["geographic_location_id"] = match.id

            if updates:
                rec.with_context(**ctx).write(updates)

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        if not self.env.context.get("skip_tmf_wiring"):
            recs._resolve_tmf_refs()
            recs._ensure_tmfc005_process_flows()
            recs._notify("batch")
        return recs

    def write(self, vals):
        previous = {rec.id: (rec.status or "") for rec in self}
        res = super().write(vals)
        if not self.env.context.get("skip_tmf_wiring"):
            wiring_keys = {
                "stock_location_ref_json", "lot_ref_json", "agreement_ref_json", "billing_account_ref_json",
                "product_specification_ref_json", "product_offering_ref_json", "product_offering_price_ref_json",
                "product_order_ref_json", "related_party_ref_json", "realizing_service_ref_json",
                "realizing_resource_ref_json", "place_ref_json", "payload", "status",
            }
            if wiring_keys & set(vals.keys()):
                self._resolve_tmf_refs()
                self._ensure_tmfc005_process_flows()
            if "status" in vals:
                changed = self.filtered(lambda rec: previous.get(rec.id) != (rec.status or ""))
                if changed:
                    changed._notify("state_change")
        return res

    def _build_process_flow_resource(self):
        self.ensure_one()
        return {
            "id": f"tmfc005-product-{self.tmf_id or self.id}",
            "name": f"Product flow {self.name or self.tmf_id or self.id}",
            "description": f"Auto-generated TMFC005 process flow for product {self.tmf_id or self.id}",
            "state": self.status or "inProgress",

        }

    def _build_task_flow_resource(self):
        self.ensure_one()
        return {
            "id": f"tmfc005-task-{self.tmf_id or self.id}",
            "name": f"Inventory task {self.name or self.tmf_id or self.id}",
            "description": f"Auto-generated TMFC005 task flow for product {self.tmf_id or self.id}",
            "state": self.status or "inProgress",
        }

    def _ensure_tmfc005_process_flows(self):
        ctx = {"skip_tmf_wiring": True}
        ProcessFlow = self.env["tmf.process.flow"].sudo()
        TaskFlow = self.env["tmf.task.flow"].sudo()
        for rec in self:
            updates = {}
            process_flow = rec.process_flow_ids[:1]
            if not process_flow:
                process_flow = ProcessFlow.search([("tmf_id", "=", f"tmfc005-product-{rec.tmf_id or rec.id}")], limit=1)
            if not process_flow:
                process_flow = ProcessFlow.create({
                    "tmf_id": f"tmfc005-product-{rec.tmf_id or rec.id}",
                    "name": f"Product flow {rec.name or rec.tmf_id or rec.id}",
                    "description": f"Auto-generated TMFC005 process flow for product {rec.tmf_id or rec.id}",
                    "state": rec.status or "inProgress",
                })
            else:
                process_flow.write({
                    "name": f"Product flow {rec.name or rec.tmf_id or rec.id}",
                    "description": f"Auto-generated TMFC005 process flow for product {rec.tmf_id or rec.id}",
                    "state": rec.status or process_flow.state,
                })
            task_flow = rec.task_flow_ids[:1]
            if not task_flow:
                task_flow = TaskFlow.search([("tmf_id", "=", f"tmfc005-task-{rec.tmf_id or rec.id}")], limit=1)
            if not task_flow:
                task_flow = TaskFlow.create({
                    "tmf_id": f"tmfc005-task-{rec.tmf_id or rec.id}",
                    "name": f"Inventory task {rec.name or rec.tmf_id or rec.id}",
                    "description": f"Auto-generated TMFC005 task flow for product {rec.tmf_id or rec.id}",
                    "state": rec.status or "inProgress",
                    "process_flow_id": process_flow.id,
                })
            else:
                task_flow.write({
                    "name": f"Inventory task {rec.name or rec.tmf_id or rec.id}",
                    "description": f"Auto-generated TMFC005 task flow for product {rec.tmf_id or rec.id}",
                    "state": rec.status or task_flow.state,
                    "process_flow_id": process_flow.id,
                })
            updates["process_flow_ids"] = [(6, 0, [process_flow.id])]
            updates["task_flow_ids"] = [(6, 0, [task_flow.id])]
            rec.with_context(**ctx).write(updates)


class TMFC005WiringTools(models.AbstractModel):
    _name = "tmfc005.wiring.tools"
    _description = "TMFC005 Wiring Reconciliation Tools"

    def _extract_event_resource(self, payload):
        if not isinstance(payload, dict):
            return {}
        if isinstance(payload.get("event"), dict):
            event = payload["event"]
            for key in (
                "resource", "product", "resourceInventory", "service", "productSpecification",
                "productOffering", "productOfferingPrice", "partyRole", "agreement",
            ):
                if isinstance(event.get(key), dict):
                    return event[key]
        if isinstance(payload.get("resource"), dict):
            return payload["resource"]
        return payload

    def _extract_resource_id(self, payload):
        resource = self._extract_event_resource(payload)
        return str(resource.get("id") or payload.get("id") or "").strip()

    def _records_with_ref(self, json_field, ref_id):
        records = self.env["tmf.product"].sudo().search([])
        return records.filtered(
            lambda rec: any(
                isinstance(item, dict) and str(item.get("id") or "").strip() == ref_id
                for item in ((getattr(rec, json_field, None) or []) if isinstance(getattr(rec, json_field, None), list) else [getattr(rec, json_field, None)])
                if item
            )
        )

    def _cleanup_product_refs(self, ref_id, relation_field=None, json_field=None, singular_field=None):
        if not ref_id:
            return
        for rec in self.env["tmf.product"].sudo().search([]):
            vals = {}
            if relation_field and relation_field in rec._fields:
                current = rec[relation_field]
                kept = current.filtered(lambda r: (r.tmf_id or str(r.id)) != ref_id)
                if len(kept) != len(current):
                    vals[relation_field] = [(6, 0, kept.ids)]
            if singular_field and singular_field in rec._fields:
                current = rec[singular_field]
                if current and (current.tmf_id or str(current.id)) == ref_id:
                    vals[singular_field] = False
            if json_field and json_field in rec._fields:
                current_json = getattr(rec, json_field)
                if isinstance(current_json, list):
                    kept_json = [item for item in current_json if str((item or {}).get("id") or "").strip() != ref_id]
                    if kept_json != current_json:
                        vals[json_field] = kept_json
                elif isinstance(current_json, dict) and str(current_json.get("id") or "").strip() == ref_id:
                    vals[json_field] = False
            if vals:
                rec.with_context(skip_tmf_wiring=True).write(vals)

    def _deactivate_products_for_refs(self, ref_ids=None, json_field=None, relation_field=None):
        ref_ids = {rid for rid in (ref_ids or []) if rid}
        if not ref_ids:
            return
        for rec in self.env["tmf.product"].sudo().search([]):
            matched = False
            if json_field and json_field in rec._fields:
                current_json = getattr(rec, json_field)
                items = current_json if isinstance(current_json, list) else [current_json]
                matched = any(isinstance(item, dict) and str(item.get("id") or "").strip() in ref_ids for item in items if item)
            if not matched and relation_field and relation_field in rec._fields:
                matched = any((r.tmf_id or str(r.id)) in ref_ids for r in rec[relation_field])
            if matched and "status" in rec._fields and rec.status != "inactive":
                rec.with_context(skip_tmf_wiring=True).write({"status": "inactive"})

    def _reconcile_resource_delete(self, payload=None):
        ref_id = self._extract_resource_id(payload or {})
        self._cleanup_product_refs(ref_id, relation_field="resource_ids", json_field="realizing_resource_ref_json")
        self._cleanup_product_refs(ref_id, json_field="realizing_resource_json")

    def _reconcile_service_delete(self, payload=None):
        ref_id = self._extract_resource_id(payload or {})
        self._cleanup_product_refs(ref_id, relation_field="service_ids", json_field="realizing_service_ref_json")
        self._cleanup_product_refs(ref_id, json_field="realizing_service_json")

    def _reconcile_product_specification_delete(self, payload=None):
        ref_id = self._extract_resource_id(payload or {})
        self._cleanup_product_refs(ref_id, singular_field="product_specification_id", json_field="product_specification_ref_json")
        self._cleanup_product_refs(ref_id, json_field="product_specification_json")

    def _reconcile_product_offering_delete(self, payload=None):
        ref_id = self._extract_resource_id(payload or {})
        self._cleanup_product_refs(ref_id, relation_field="product_offering_ids", json_field="product_offering_ref_json")
        self._cleanup_product_refs(ref_id, json_field="product_offering")

    def _reconcile_product_offering_price_delete(self, payload=None):
        ref_id = self._extract_resource_id(payload or {})
        self._cleanup_product_refs(ref_id, relation_field="product_offering_price_ids", json_field="product_offering_price_ref_json")
        self._cleanup_product_refs(ref_id, json_field="product_price")

    def _reconcile_party_role_delete(self, payload=None):
        ref_id = self._extract_resource_id(payload or {})
        self._cleanup_product_refs(ref_id, singular_field="party_role_id", json_field="related_party_ref_json")
        self._cleanup_product_refs(ref_id, json_field="related_party_json")

    def _reconcile_agreement_delete(self, payload=None):
        ref_id = self._extract_resource_id(payload or {})
        self._cleanup_product_refs(ref_id, relation_field="agreement_ids", json_field="agreement_ref_json")
        self._cleanup_product_refs(ref_id, json_field="agreement")

    def handle_event(self, event_name, payload=None):
        handlers = {
            "resourceDeleteEvent": self._reconcile_resource_delete,
            "serviceDeleteEvent": self._reconcile_service_delete,
            "productSpecificationDeleteEvent": self._reconcile_product_specification_delete,
            "productOfferingDeleteEvent": self._reconcile_product_offering_delete,
            "productOfferingPriceDeleteEvent": self._reconcile_product_offering_price_delete,
            "partyRoleDeleteEvent": self._reconcile_party_role_delete,
            "agreementDeleteEvent": self._reconcile_agreement_delete,
        }
        handler = handlers.get(event_name)
        if handler:
            handler(payload or {})
