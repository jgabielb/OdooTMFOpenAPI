from odoo import api, fields, models


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


class CheckPOQTMFC027Wiring(models.Model):
    """TMFC027 dependent API wiring for CheckProductOfferingQualification."""
    _inherit = "tmf.check.product.offering.qualification"

    # Raw JSON storage
    related_party_json = fields.Json(default=list, string="Related Parties JSON (TMF632)")
    product_json = fields.Json(default=list, string="Product refs JSON (TMF637)")
    product_offering_json = fields.Json(default=list, string="Product Offering refs JSON (TMF620)")
    product_order_json = fields.Json(default=list, string="Product Order refs JSON (TMF622)")
    payload = fields.Json(default=dict, string="Full Request Payload")

    # Resolved relational fields
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
    product_order_ids = fields.Many2many(
        "sale.order", "tmfc027_check_poq_order_rel",
        "poq_id", "order_id", string="Product Orders (TMF622)"
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

    def _resolve_tmf_refs(self):
        ctx = {"skip_tmf_wiring": True}
        for rec in self:
            updates = {}
            payload = (rec.payload if hasattr(rec, "payload") else None) or {}

            # Supplement dedicated JSON fields from payload when controller didn't populate them.
            # Controller only stores relatedParty explicitly; other refs live in the stored payload.
            effective_party_json = rec.related_party_json or payload.get("relatedParty") or []

            # Extract productOffering refs from qualificationItems in payload
            effective_offering_json = rec.product_offering_json or []
            if not effective_offering_json:
                for item in (payload.get("productOfferingQualificationItem") or []):
                    if isinstance(item, dict):
                        po = item.get("productOffering") or {}
                        if po.get("id"):
                            effective_offering_json.append(po)

            effective_order_json = rec.product_order_json or payload.get("productOrder") or []

            # TMF632 relatedParty -> res.partner
            if not rec.related_partner_ids and effective_party_json:
                ids = _resolve_ids(self.env, "res.partner", effective_party_json)
                if ids:
                    updates["related_partner_ids"] = [(6, 0, ids)]

            # TMF637 product -> tmf.product (from item-level product_json)
            if not rec.product_ids and rec.product_json:
                ids = _resolve_ids(self.env, "tmf.product", rec.product_json)
                if ids:
                    updates["product_ids"] = [(6, 0, ids)]

            # TMF620 productOffering -> product.template
            if not rec.product_offering_ids and effective_offering_json:
                ids = _resolve_ids(self.env, "product.template", effective_offering_json)
                if ids:
                    updates["product_offering_ids"] = [(6, 0, ids)]

            # TMF622 productOrder -> sale.order
            if not rec.product_order_ids and effective_order_json:
                ids = _resolve_ids(self.env, "sale.order", effective_order_json)
                if ids:
                    updates["product_order_ids"] = [(6, 0, ids)]

            # TMF666 billingAccount — from payload
            if not rec.billing_account_id:
                ba = payload.get("billingAccount") or {}
                ba_id = str(ba.get("id") or "").strip()
                if ba_id:
                    match = self.env["tmf.billing.account"].sudo().search(
                        [("tmf_id", "=", ba_id)], limit=1
                    )
                    if match:
                        updates["billing_account_id"] = match.id

            # TMF669 partyRole — PartyRole @type entries in relatedParty
            if not rec.party_role_id and effective_party_json:
                items = [i for i in (effective_party_json or [])
                         if isinstance(i, dict) and i.get("@type") in ("PartyRole", "PartyRoleRef")]
                ids = _resolve_ids(self.env, "tmf.party.role", items)
                if ids:
                    updates["party_role_id"] = ids[0]

            # TMF673/674 place — batch by @type
            if not rec.geographic_address_id or not rec.geographic_site_id:
                addr_ids, site_ids = [], []
                for item in (payload.get("place") or []):
                    if not isinstance(item, dict):
                        continue
                    ref_id = str(item.get("id") or "").strip()
                    at_type = item.get("@type", "")
                    if ref_id and at_type in ("GeographicAddress", "GeographicAddressRef"):
                        addr_ids.append(ref_id)
                    elif ref_id and at_type in ("GeographicSite", "GeographicSiteRef"):
                        site_ids.append(ref_id)
                if addr_ids and not rec.geographic_address_id:
                    match = self.env["tmf.geographic.address"].sudo().search(
                        [("tmf_id", "in", addr_ids)], limit=1
                    )
                    if match:
                        updates["geographic_address_id"] = match.id
                if site_ids and not rec.geographic_site_id:
                    match = self.env["tmf.geographic.site"].sudo().search(
                        [("tmf_id", "in", site_ids)], limit=1
                    )
                    if match:
                        updates["geographic_site_id"] = match.id

            # TMF662 entityCatalog — from payload
            if not rec.entity_specification_id:
                ec = payload.get("entityCatalog") or {}
                ec_id = str(ec.get("id") or "").strip()
                if ec_id:
                    match = self.env["tmf.entity.specification"].sudo().search(
                        [("tmf_id", "=", ec_id)], limit=1
                    )
                    if match:
                        updates["entity_specification_id"] = match.id

            # TMF921 intent — from payload
            if not rec.intent_id:
                intent = payload.get("intent") or {}
                intent_ref_id = str(intent.get("id") or "").strip()
                if intent_ref_id:
                    match = self.env["tmf.intent.management.resource"].sudo().search(
                        [("tmf_id", "=", intent_ref_id)], limit=1
                    )
                    if match:
                        updates["intent_id"] = match.id

            if updates:
                rec.with_context(**ctx).write(updates)

    @api.model
    def create_from_json(self, data):
        data = data or {}

        # Collect product refs from item-level productOffering entries
        offering_refs = []
        product_refs = []
        for item in (data.get("checkProductOfferingQualificationItem") or []):
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
        })
        rec._resolve_tmf_refs()
        return rec

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        if not self.env.context.get("skip_tmf_wiring"):
            recs._resolve_tmf_refs()
        return recs

    def write(self, vals):
        res = super().write(vals)
        if not self.env.context.get("skip_tmf_wiring"):
            wiring_keys = {
                "related_party_json", "product_json", "product_offering_json",
                "product_order_json", "payload",
            }
            if wiring_keys & set(vals.keys()):
                self._resolve_tmf_refs()
        return res


class QueryPOQTMFC027Wiring(models.Model):
    """TMFC027 dependent API wiring for QueryProductOfferingQualification."""
    _inherit = "tmf.query.product.offering.qualification"

    related_party_json = fields.Json(default=list, string="Related Parties JSON (TMF632)")
    product_json = fields.Json(default=list, string="Product refs JSON (TMF637)")
    product_offering_json = fields.Json(default=list, string="Product Offering refs JSON (TMF620)")

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
    party_role_id = fields.Many2one(
        "tmf.party.role", string="Party Role (TMF669)",
        index=True, ondelete="set null"
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

            if not rec.party_role_id and rec.related_party_json:
                items = [i for i in (rec.related_party_json or [])
                         if isinstance(i, dict) and i.get("@type") in ("PartyRole", "PartyRoleRef")]
                ids = _resolve_ids(self.env, "tmf.party.role", items)
                if ids:
                    updates["party_role_id"] = ids[0]

            if updates:
                rec.with_context(**ctx).write(updates)

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        if not self.env.context.get("skip_tmf_wiring"):
            recs._resolve_tmf_refs()
        return recs

    def write(self, vals):
        res = super().write(vals)
        if not self.env.context.get("skip_tmf_wiring"):
            wiring_keys = {"related_party_json", "product_json", "product_offering_json"}
            if wiring_keys & set(vals.keys()):
                self._resolve_tmf_refs()
        return res
