from odoo import api, fields, models


TMFC027_LISTENER_EVENTS = {
    "CatalogCreateEvent",
    "CatalogAttributeValueChangeEvent",
    "CatalogStateChangeEvent",
    "ProductOfferingCreateEvent",
    "ProductOfferingAttributeValueChangeEvent",
    "ProductOfferingStateChangeEvent",
    "ProductOfferingDeleteEvent",
    "ProductOfferingPriceCreateEvent",
    "ProductOfferingPriceAttributeValueChangeEvent",
    "ProductOfferingPriceStateChangeEvent",
    "ProductOfferingPriceDeleteEvent",
    "ProductSpecificationCreateEvent",
    "ProductSpecificationAttributeValueChangeEvent",
    "ProductSpecificationStateChangeEvent",
    "ProductSpecificationDeleteEvent",
    "checkServiceQualificationStateChangeEvent",
    "queryServiceQualificationStateChangeEvent",
}


def _resolve_ids(env, model, items, id_field="tmf_id"):
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


class CheckPOQTMFC027Wiring(models.Model):
    """TMFC027 dependent API wiring for CheckProductOfferingQualification."""
    _inherit = "tmf.check.product.offering.qualification"

    related_party_json = fields.Json(default=list, string="Related Parties JSON (TMF632)")
    product_json = fields.Json(default=list, string="Product refs JSON (TMF637)")
    product_offering_json = fields.Json(default=list, string="Product Offering refs JSON (TMF620)")
    product_order_json = fields.Json(default=list, string="Product Order refs JSON (TMF622)")
    service_qualification_json = fields.Json(default=list, string="Service Qualification refs JSON (TMF645)")
    agreement_json = fields.Json(default=list, string="Agreement refs JSON (TMF651)")
    place_json = fields.Json(default=list, string="Place refs JSON (TMF673/674)")
    entity_catalog_json = fields.Json(default=dict, string="Entity Catalog JSON (TMF662)")
    intent_json = fields.Json(default=dict, string="Intent JSON (TMF921)")
    payload = fields.Json(default=dict, string="Full Request Payload")

    related_partner_ids = fields.Many2many(
        "res.partner", "tmfc027_check_poq_partner_rel",
        "poq_id", "partner_id", string="Related Parties (TMF632)"
    )
    product_ids = fields.Many2many(
        "tmf.product", "tmfc027_check_poq_product_rel",
        "poq_id", "product_id", string="Products (TMF637)"
    )
    product_offering_ids = fields.Many2many(
        "product.template", "tmfc027_check_poq_offering_rel",
        "poq_id", "offering_id", string="Product Offerings (TMF620)"
    )
    service_qualification_ids = fields.Many2many(
        "tmf.service.qualification", "tmfc027_check_poq_sq_rel",
        "poq_id", "sq_id", string="Service Qualifications (TMF645)"
    )
    agreement_ids = fields.Many2many(
        "tmf.agreement", "tmfc027_check_poq_agreement_rel",
        "poq_id", "agreement_id", string="Agreements (TMF651)"
    )
    billing_account_id = fields.Many2one(
        "tmf.billing.account", string="Billing Account (TMF666)",
        index=True, ondelete="set null"
    )
    party_role_id = fields.Many2one(
        "tmf.party.role", string="Party Role (TMF669)",
        index=True, ondelete="set null"
    )
    geographic_address_id = fields.Many2one(
        "tmf.geographic.address", string="Geographic Address (TMF673)",
        index=True, ondelete="set null"
    )
    geographic_site_id = fields.Many2one(
        "tmf.geographic.site", string="Geographic Site (TMF674)",
        index=True, ondelete="set null"
    )
    entity_specification_id = fields.Many2one(
        "tmf.entity.specification", string="Entity Specification (TMF662)",
        index=True, ondelete="set null"
    )
    intent_id = fields.Many2one(
        "tmf.intent.management.resource", string="Intent (TMF921)",
        index=True, ondelete="set null"
    )
    process_flow_ids = fields.Many2many(
        "tmf.process.flow", "tmfc027_check_poq_process_flow_rel",
        "poq_id", "process_flow_id", string="Process Flows (TMF701)"
    )
    task_flow_ids = fields.Many2many(
        "tmf.task.flow", "tmfc027_check_poq_task_flow_rel",
        "poq_id", "task_flow_id", string="Task Flows (TMF701)"
    )

    def _resolve_tmf_refs(self):
        ctx = {"skip_tmf_wiring": True}
        for rec in self:
            updates = {}
            payload = (rec.payload if hasattr(rec, "payload") else None) or {}

            effective_party_json = rec.related_party_json or payload.get("relatedParty") or []
            effective_offering_json = rec.product_offering_json or []
            if not effective_offering_json:
                for item in (payload.get("productOfferingQualificationItem") or payload.get("checkProductOfferingQualificationItem") or []):
                    if isinstance(item, dict):
                        po = item.get("productOffering") or {}
                        if po.get("id"):
                            effective_offering_json.append(po)
            effective_product_json = rec.product_json or []
            if not effective_product_json:
                for item in (payload.get("productOfferingQualificationItem") or payload.get("checkProductOfferingQualificationItem") or []):
                    if isinstance(item, dict):
                        prod = item.get("product") or {}
                        if prod.get("id"):
                            effective_product_json.append(prod)
            effective_order_json = rec.product_order_json or payload.get("productOrder") or []
            if isinstance(effective_order_json, dict):
                effective_order_json = [effective_order_json]
            effective_service_qualification_json = rec.service_qualification_json or payload.get("serviceQualification") or []
            if isinstance(effective_service_qualification_json, dict):
                effective_service_qualification_json = [effective_service_qualification_json]
            effective_agreement_json = rec.agreement_json or payload.get("agreement") or []
            if isinstance(effective_agreement_json, dict):
                effective_agreement_json = [effective_agreement_json]
            effective_place_json = rec.place_json or payload.get("place") or []
            if isinstance(effective_place_json, dict):
                effective_place_json = [effective_place_json]

            if not rec.related_partner_ids and effective_party_json:
                ids = _resolve_ids(self.env, "res.partner", effective_party_json)
                if ids:
                    updates["related_partner_ids"] = [(6, 0, ids)]

            if not rec.product_ids and effective_product_json:
                ids = _resolve_ids(self.env, "tmf.product", effective_product_json)
                if ids:
                    updates["product_ids"] = [(6, 0, ids)]

            if not rec.product_offering_ids and effective_offering_json:
                ids = _resolve_ids(self.env, "product.template", effective_offering_json)
                if ids:
                    updates["product_offering_ids"] = [(6, 0, ids)]

            if not rec.service_qualification_ids and effective_service_qualification_json:
                ids = _resolve_ids(self.env, "tmf.service.qualification", effective_service_qualification_json)
                if ids:
                    updates["service_qualification_ids"] = [(6, 0, ids)]

            if not rec.agreement_ids and effective_agreement_json:
                ids = _resolve_ids(self.env, "tmf.agreement", effective_agreement_json)
                if ids:
                    updates["agreement_ids"] = [(6, 0, ids)]

            if not rec.billing_account_id:
                ba = payload.get("billingAccount") or {}
                ba_id = str(ba.get("id") or "").strip()
                if ba_id:
                    match = self.env["tmf.billing.account"].sudo().search(
                        [("tmf_id", "=", ba_id)], limit=1
                    )
                    if match:
                        updates["billing_account_id"] = match.id

            if not rec.party_role_id and effective_party_json:
                items = [i for i in (effective_party_json or []) if isinstance(i, dict) and i.get("@type") in ("PartyRole", "PartyRoleRef")]
                ids = _resolve_ids(self.env, "tmf.party.role", items)
                if ids:
                    updates["party_role_id"] = ids[0]

            if not rec.geographic_address_id or not rec.geographic_site_id:
                addr_ids, site_ids = [], []
                for item in effective_place_json:
                    if not isinstance(item, dict):
                        continue
                    ref_id = str(item.get("id") or "").strip()
                    at_type = item.get("@type", "")
                    if ref_id and at_type in ("GeographicAddress", "GeographicAddressRef"):
                        addr_ids.append(ref_id)
                    elif ref_id and at_type in ("GeographicSite", "GeographicSiteRef"):
                        site_ids.append(ref_id)
                if addr_ids and not rec.geographic_address_id:
                    match = self.env["tmf.geographic.address"].sudo().search([("tmf_id", "in", addr_ids)], limit=1)
                    if match:
                        updates["geographic_address_id"] = match.id
                if site_ids and not rec.geographic_site_id:
                    match = self.env["tmf.geographic.site"].sudo().search([("tmf_id", "in", site_ids)], limit=1)
                    if match:
                        updates["geographic_site_id"] = match.id

            if not rec.entity_specification_id:
                ec = rec.entity_catalog_json or payload.get("entityCatalog") or {}
                ec_id = str(ec.get("id") or "").strip()
                if ec_id:
                    match = self.env["tmf.entity.specification"].sudo().search([("tmf_id", "=", ec_id)], limit=1)
                    if match:
                        updates["entity_specification_id"] = match.id

            if not rec.intent_id:
                intent = rec.intent_json or payload.get("intent") or {}
                intent_ref_id = str(intent.get("id") or "").strip()
                if intent_ref_id:
                    match = self.env["tmf.intent.management.resource"].sudo().search([("tmf_id", "=", intent_ref_id)], limit=1)
                    if match:
                        updates["intent_id"] = match.id

            if updates:
                rec.with_context(**ctx).write(updates)

    def _ensure_process_flows(self):
        ctx = {"skip_tmf_wiring": True}
        ProcessFlow = self.env["tmf.process.flow"].sudo()
        TaskFlow = self.env["tmf.task.flow"].sudo()
        for rec in self:
            process_flow = rec.process_flow_ids[:1] or ProcessFlow.search([("tmf_id", "=", f"tmfc027-check-{rec.tmf_id or rec.id}")], limit=1)
            if not process_flow:
                process_flow = ProcessFlow.create({
                    "tmf_id": f"tmfc027-check-{rec.tmf_id or rec.id}",
                    "name": f"POQ flow {rec.name or rec.tmf_id or rec.id}",
                    "description": f"Auto-generated TMFC027 process flow for check qualification {rec.tmf_id or rec.id}",
                    "status": getattr(rec, "state", False) or getattr(rec, "status", False) or "acknowledged",
                    "related_party": rec.related_party_json or [],
                })
            task_flow = rec.task_flow_ids[:1] or TaskFlow.search([("tmf_id", "=", f"tmfc027-check-task-{rec.tmf_id or rec.id}")], limit=1)
            if not task_flow:
                task_flow = TaskFlow.create({
                    "tmf_id": f"tmfc027-check-task-{rec.tmf_id or rec.id}",
                    "name": f"POQ task {rec.name or rec.tmf_id or rec.id}",
                    "description": f"Auto-generated TMFC027 task flow for check qualification {rec.tmf_id or rec.id}",
                    "status": getattr(rec, "state", False) or getattr(rec, "status", False) or "acknowledged",
                    "process_flow_id": process_flow.id,
                })
            rec.with_context(**ctx).write({
                "process_flow_ids": [(6, 0, [process_flow.id])],
                "task_flow_ids": [(6, 0, [task_flow.id])],
            })

    @api.model
    def create_from_json(self, data):
        data = data or {}
        offering_refs = []
        product_refs = []
        for item in (data.get("checkProductOfferingQualificationItem") or data.get("productOfferingQualificationItem") or []):
            if not isinstance(item, dict):
                continue
            po = item.get("productOffering") or {}
            if isinstance(po, dict) and po.get("id"):
                offering_refs.append(po)
            prod = item.get("product") or {}
            if isinstance(prod, dict) and prod.get("id"):
                product_refs.append(prod)
        rec = super().create_from_json(data)
        rec.with_context(skip_tmf_wiring=True).write({
            "payload": data,
            "product_json": product_refs or [],
            "product_offering_json": offering_refs or [],
            "product_order_json": data.get("productOrder") or [],
            "service_qualification_json": data.get("serviceQualification") or [],
            "agreement_json": data.get("agreement") or [],
            "place_json": data.get("place") or [],
            "entity_catalog_json": data.get("entityCatalog") or {},
            "intent_json": data.get("intent") or {},
        })
        rec._resolve_tmf_refs()
        rec._ensure_process_flows()
        return rec

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        if not self.env.context.get("skip_tmf_wiring"):
            recs._resolve_tmf_refs()
            recs._ensure_process_flows()
        return recs

    def write(self, vals):
        res = super().write(vals)
        if not self.env.context.get("skip_tmf_wiring"):
            wiring_keys = {
                "related_party_json", "product_json", "product_offering_json", "product_order_json",
                "service_qualification_json", "agreement_json", "place_json", "entity_catalog_json",
                "intent_json", "payload",
            }
            if wiring_keys & set(vals.keys()):
                self._resolve_tmf_refs()
                self._ensure_process_flows()
        return res


class QueryPOQTMFC027Wiring(models.Model):
    """TMFC027 dependent API wiring for QueryProductOfferingQualification."""
    _inherit = "tmf.query.product.offering.qualification"

    related_party_json = fields.Json(default=list, string="Related Parties JSON (TMF632)")
    product_json = fields.Json(default=list, string="Product refs JSON (TMF637)")
    product_offering_json = fields.Json(default=list, string="Product Offering refs JSON (TMF620)")
    service_qualification_json = fields.Json(default=list, string="Service Qualification refs JSON (TMF645)")
    agreement_json = fields.Json(default=list, string="Agreement refs JSON (TMF651)")

    related_partner_ids = fields.Many2many(
        "res.partner", "tmfc027_query_poq_partner_rel",
        "poq_id", "partner_id", string="Related Parties (TMF632)"
    )
    product_ids = fields.Many2many(
        "tmf.product", "tmfc027_query_poq_product_rel",
        "poq_id", "product_id", string="Products (TMF637)"
    )
    product_offering_ids = fields.Many2many(
        "product.template", "tmfc027_query_poq_offering_rel",
        "poq_id", "offering_id", string="Product Offerings (TMF620)"
    )
    service_qualification_ids = fields.Many2many(
        "tmf.service.qualification", "tmfc027_query_poq_sq_rel",
        "poq_id", "sq_id", string="Service Qualifications (TMF645)"
    )
    agreement_ids = fields.Many2many(
        "tmf.agreement", "tmfc027_query_poq_agreement_rel",
        "poq_id", "agreement_id", string="Agreements (TMF651)"
    )
    party_role_id = fields.Many2one(
        "tmf.party.role", string="Party Role (TMF669)",
        index=True, ondelete="set null"
    )
    process_flow_ids = fields.Many2many(
        "tmf.process.flow", "tmfc027_query_poq_process_flow_rel",
        "poq_id", "process_flow_id", string="Process Flows (TMF701)"
    )
    task_flow_ids = fields.Many2many(
        "tmf.task.flow", "tmfc027_query_poq_task_flow_rel",
        "poq_id", "task_flow_id", string="Task Flows (TMF701)"
    )

    def _resolve_tmf_refs(self):
        ctx = {"skip_tmf_wiring": True}
        for rec in self:
            updates = {}

            if not rec.related_partner_ids and rec.related_party_json:
                ids = _resolve_ids(self.env, "res.partner", rec.related_party_json)
                if ids:
                    updates["related_partner_ids"] = [(6, 0, ids)]

            if not rec.product_ids and rec.product_json:
                ids = _resolve_ids(self.env, "tmf.product", rec.product_json)
                if ids:
                    updates["product_ids"] = [(6, 0, ids)]

            if not rec.product_offering_ids and rec.product_offering_json:
                ids = _resolve_ids(self.env, "product.template", rec.product_offering_json)
                if ids:
                    updates["product_offering_ids"] = [(6, 0, ids)]

            if not rec.service_qualification_ids and rec.service_qualification_json:
                ids = _resolve_ids(self.env, "tmf.service.qualification", rec.service_qualification_json)
                if ids:
                    updates["service_qualification_ids"] = [(6, 0, ids)]

            if not rec.agreement_ids and rec.agreement_json:
                ids = _resolve_ids(self.env, "tmf.agreement", rec.agreement_json)
                if ids:
                    updates["agreement_ids"] = [(6, 0, ids)]

            if not rec.party_role_id and rec.related_party_json:
                items = [i for i in (rec.related_party_json or []) if isinstance(i, dict) and i.get("@type") in ("PartyRole", "PartyRoleRef")]
                ids = _resolve_ids(self.env, "tmf.party.role", items)
                if ids:
                    updates["party_role_id"] = ids[0]

            if updates:
                rec.with_context(**ctx).write(updates)

    def _ensure_process_flows(self):
        ctx = {"skip_tmf_wiring": True}
        ProcessFlow = self.env["tmf.process.flow"].sudo()
        TaskFlow = self.env["tmf.task.flow"].sudo()
        for rec in self:
            process_flow = rec.process_flow_ids[:1] or ProcessFlow.search([("tmf_id", "=", f"tmfc027-query-{rec.tmf_id or rec.id}")], limit=1)
            if not process_flow:
                process_flow = ProcessFlow.create({
                    "tmf_id": f"tmfc027-query-{rec.tmf_id or rec.id}",
                    "name": f"POQ query flow {rec.name or rec.tmf_id or rec.id}",
                    "description": f"Auto-generated TMFC027 process flow for query qualification {rec.tmf_id or rec.id}",
                    "status": getattr(rec, "state", False) or getattr(rec, "status", False) or "acknowledged",
                    "related_party": rec.related_party_json or [],
                })
            task_flow = rec.task_flow_ids[:1] or TaskFlow.search([("tmf_id", "=", f"tmfc027-query-task-{rec.tmf_id or rec.id}")], limit=1)
            if not task_flow:
                task_flow = TaskFlow.create({
                    "tmf_id": f"tmfc027-query-task-{rec.tmf_id or rec.id}",
                    "name": f"POQ query task {rec.name or rec.tmf_id or rec.id}",
                    "description": f"Auto-generated TMFC027 task flow for query qualification {rec.tmf_id or rec.id}",
                    "status": getattr(rec, "state", False) or getattr(rec, "status", False) or "acknowledged",
                    "process_flow_id": process_flow.id,
                })
            rec.with_context(**ctx).write({
                "process_flow_ids": [(6, 0, [process_flow.id])],
                "task_flow_ids": [(6, 0, [task_flow.id])],
            })

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        if not self.env.context.get("skip_tmf_wiring"):
            recs._resolve_tmf_refs()
            recs._ensure_process_flows()
        return recs

    def write(self, vals):
        res = super().write(vals)
        if not self.env.context.get("skip_tmf_wiring"):
            wiring_keys = {"related_party_json", "product_json", "product_offering_json", "service_qualification_json", "agreement_json"}
            if wiring_keys & set(vals.keys()):
                self._resolve_tmf_refs()
                self._ensure_process_flows()
        return res


class TMFC027WiringTools(models.AbstractModel):
    _name = "tmfc027.wiring.tools"
    _description = "TMFC027 Wiring Reconciliation Tools"

    def _extract_event_resource(self, payload):
        if not isinstance(payload, dict):
            return {}
        if isinstance(payload.get("event"), dict):
            event = payload["event"]
            for key in ("resource", "catalog", "productOffering", "productOfferingPrice", "productSpecification", "checkServiceQualification", "queryServiceQualification"):
                if isinstance(event.get(key), dict):
                    return event[key]
        if isinstance(payload.get("resource"), dict):
            return payload["resource"]
        return payload

    def _extract_resource_id(self, payload):
        resource = self._extract_event_resource(payload)
        return str(resource.get("id") or payload.get("id") or "").strip()

    def _cleanup_check_records(self, ref_id, json_field=None, relation_field=None, singular_field=None):
        for model_name in ("tmf.check.product.offering.qualification", "tmf.query.product.offering.qualification"):
            for rec in self.env[model_name].sudo().search([]):
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

    def _reconcile_product_offering(self, payload=None):
        ref_id = self._extract_resource_id(payload or {})
        self._cleanup_check_records(ref_id, json_field="product_offering_json", relation_field="product_offering_ids")

    def _reconcile_product_offering_price(self, payload=None):
        ref_id = self._extract_resource_id(payload or {})
        self._cleanup_check_records(ref_id, json_field="payload")

    def _reconcile_product_specification(self, payload=None):
        ref_id = self._extract_resource_id(payload or {})
        self._cleanup_check_records(ref_id, json_field="payload")

    def _reconcile_service_qualification_state(self, payload=None):
        ref_id = self._extract_resource_id(payload or {})
        resource = self._extract_event_resource(payload or {})
        new_state = resource.get("state") or resource.get("status")
        if not ref_id or not new_state:
            return
        for model_name in ("tmf.check.product.offering.qualification", "tmf.query.product.offering.qualification"):
            for rec in self.env[model_name].sudo().search([]):
                if "service_qualification_ids" not in rec._fields:
                    continue
                matched = any((sq.tmf_id or str(sq.id)) == ref_id for sq in rec.service_qualification_ids)
                if matched and "state" in rec._fields:
                    rec.with_context(skip_tmf_wiring=True).write({"state": new_state})
                elif matched and "status" in rec._fields:
                    rec.with_context(skip_tmf_wiring=True).write({"status": new_state})

    def handle_event(self, event_name, payload=None):
        if event_name in {
            "ProductOfferingCreateEvent", "ProductOfferingAttributeValueChangeEvent",
            "ProductOfferingStateChangeEvent", "ProductOfferingDeleteEvent",
        }:
            self._reconcile_product_offering(payload)
        elif event_name in {
            "ProductOfferingPriceCreateEvent", "ProductOfferingPriceAttributeValueChangeEvent",
            "ProductOfferingPriceStateChangeEvent", "ProductOfferingPriceDeleteEvent",
        }:
            self._reconcile_product_offering_price(payload)
        elif event_name in {
            "ProductSpecificationCreateEvent", "ProductSpecificationAttributeValueChangeEvent",
            "ProductSpecificationStateChangeEvent", "ProductSpecificationDeleteEvent",
        }:
            self._reconcile_product_specification(payload)
        elif event_name in {"checkServiceQualificationStateChangeEvent", "queryServiceQualificationStateChangeEvent"}:
            self._reconcile_service_qualification_state(payload)
