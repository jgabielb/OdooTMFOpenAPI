import json
from odoo import api, fields, models


def _dumps(value):
    return json.dumps(value, ensure_ascii=False) if value is not None else False


def _loads(value):
    if not value:
        return {}
    try:
        data = json.loads(value)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _compact(payload):
    return {k: v for k, v in payload.items() if v is not None and v is not False}


def _extract_first_dict(value):
    if isinstance(value, dict):
        return value
    if isinstance(value, list):
        for item in value:
            if isinstance(item, dict):
                return item
    return {}


def _safe_str(value):
    return str(value).strip() if value is not None else ""


class TMFOpenGatewayOperateMixin(models.AbstractModel):
    _name = "tmf.open.gateway.operate.mixin"
    _description = "TMF931 Open Gateway Operate Mixin"
    _inherit = ["tmf.model.mixin"]

    name = fields.Char(string="name")
    description = fields.Char(string="description")
    status = fields.Char(string="status")
    state = fields.Char(string="state")
    commercial_name = fields.Char(string="commercialName")
    payload_json = fields.Text(string="payload")
    tmf_type_value = fields.Char(string="@type")
    base_type = fields.Char(string="@baseType")
    schema_location = fields.Char(string="@schemaLocation")

    _api_name = None
    _default_type = None
    _api_path = None

    def _get_tmf_api_path(self):
        return self._api_path or "/openGatewayOperateAPIOnboardingandOrdering/v5"

    def to_tmf_json(self):
        self.ensure_one()
        payload = _loads(self.payload_json)
        payload["id"] = self.tmf_id
        payload["href"] = self.href
        if self.name is not None:
            payload["name"] = self.name
        if self.description is not None:
            payload["description"] = self.description
        if self.status is not None:
            payload["status"] = self.status
        if self.state is not None:
            payload["state"] = self.state
        if self.commercial_name is not None:
            payload["commercialName"] = self.commercial_name
        payload["@type"] = self.tmf_type_value or payload.get("@type") or self._default_type
        if self.base_type:
            payload["@baseType"] = self.base_type
        if self.schema_location:
            payload["@schemaLocation"] = self.schema_location
        return _compact(payload)

    def from_tmf_json(self, data, partial=False):
        vals = {"payload_json": _dumps(data)}
        for key, field_name in [
            ("name", "name"),
            ("description", "description"),
            ("status", "status"),
            ("state", "state"),
            ("commercialName", "commercial_name"),
            ("@type", "tmf_type_value"),
            ("@baseType", "base_type"),
            ("@schemaLocation", "schema_location"),
        ]:
            if key in data:
                vals[field_name] = data.get(key)
        return vals

    def _notify(self, action, rec):
        try:
            self.env["tmf.hub.subscription"]._notify_subscribers(
                api_name=self._api_name,
                event_type=action,
                resource_json=rec.to_tmf_json(),
            )
        except Exception:
            pass

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        for rec in recs:
            self._notify("create", rec)
        return recs

    def write(self, vals):
        state_changed = "state" in vals or "status" in vals
        res = super().write(vals)
        for rec in self:
            self._notify("update", rec)
            if state_changed:
                self._notify("state_change", rec)
        return res

    def unlink(self):
        payloads = [rec.to_tmf_json() for rec in self]
        api_name = self._api_name
        res = super().unlink()
        for payload in payloads:
            try:
                self.env["tmf.hub.subscription"]._notify_subscribers(
                    api_name=api_name,
                    event_type="delete",
                    resource_json=payload,
                )
            except Exception:
                pass
        return res


class TMFApiProduct(models.Model):
    _name = "tmf.ogw.api.product"
    _description = "TMF931 ApiProduct"
    _inherit = ["tmf.open.gateway.operate.mixin"]

    _api_name = "apiProduct"
    _default_type = "ApiProduct"
    _api_path = "/openGatewayOperateAPIOnboardingandOrdering/v5/apiProduct"


_PRODUCT_ORDER_ITEM_TYPE_MAP = {
    "add": "ApiProductOrderItemAdd",
    "modify": "ApiProductOrderItemModify",
    "delete": "ProductOrderItemDelete",
}


class TMFApiProductOrder(models.Model):
    _name = "tmf.ogw.api.product.order"
    _description = "TMF931 ApiProductOrder"
    _inherit = ["tmf.open.gateway.operate.mixin"]

    _api_name = "apiProductOrder"
    _default_type = "ApiProductOrder"
    _api_path = "/openGatewayOperateAPIOnboardingandOrdering/v5/apiProductOrder"

    sale_order_id = fields.Many2one("sale.order", string="Sales Order", copy=False, index=True)

    def to_tmf_json(self):
        payload = super().to_tmf_json()
        # Fix productOrderItem: correct @type per action, and ensure product is a dict
        items = payload.get("productOrderItem")
        if isinstance(items, list):
            fixed_items = []
            for item in items:
                if isinstance(item, dict):
                    action = _safe_str(item.get("action", "")).lower()
                    item["@type"] = _PRODUCT_ORDER_ITEM_TYPE_MAP.get(action, "ApiProductOrderItemAdd")
                    product = item.get("product")
                    if product is not None:
                        if isinstance(product, str):
                            item["product"] = {"@type": "ProductRef", "id": product or "0", "name": product} if product else {"@type": "ProductRef", "id": "0"}
                        elif isinstance(product, dict):
                            product["@type"] = "ProductRef"
                            if "id" not in product:
                                product["id"] = product.get("name", "0") or "0"
                        else:
                            item["product"] = {"@type": "ProductRef", "id": "0"}
                fixed_items.append(item)
            payload["productOrderItem"] = fixed_items
        return payload

    def _resolve_partner_from_payload(self, payload):
        partner = self.env["res.partner"]
        related = payload.get("relatedParty")
        entries = related if isinstance(related, list) else [related]
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            pid = _safe_str(entry.get("id"))
            pname = _safe_str(entry.get("name"))
            if pid and "tmf_id" in partner._fields:
                found = partner.sudo().search([("tmf_id", "=", pid)], limit=1)
                if found:
                    return found
            if pname:
                found = partner.sudo().search([("name", "=", pname)], limit=1)
                if found:
                    return found
                return partner.sudo().create({"name": pname})
        return partner

    def _sync_sale_order_link(self):
        SaleOrder = self.env["sale.order"].sudo()
        for rec in self:
            payload = _loads(rec.payload_json)
            external_ref = _safe_str(payload.get("externalId")) or _safe_str(payload.get("id")) or rec.tmf_id
            order = rec.sale_order_id
            if not order and external_ref:
                order = SaleOrder.search([("client_order_ref", "=", external_ref)], limit=1)
            partner = rec._resolve_partner_from_payload(payload)
            if not order and partner:
                order_vals = {
                    "partner_id": partner.id,
                    "client_order_ref": external_ref or rec.tmf_id,
                    "origin": rec.tmf_id,
                }
                order = SaleOrder.create(order_vals)
            if order and not rec.sale_order_id:
                rec.with_context(skip_tmf931_sale_sync=True).write({"sale_order_id": order.id})

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        recs._sync_sale_order_link()
        return recs

    def write(self, vals):
        res = super().write(vals)
        if not self.env.context.get("skip_tmf931_sale_sync"):
            self._sync_sale_order_link()
        return res


class TMFApplication(models.Model):
    _name = "tmf.ogw.application"
    _description = "TMF931 Application"
    _inherit = ["tmf.open.gateway.operate.mixin"]

    _api_name = "application"
    _default_type = "Application"
    _api_path = "/openGatewayOperateAPIOnboardingandOrdering/v5/application"

    partner_id = fields.Many2one("res.partner", string="Owner Partner", copy=False, index=True)

    def to_tmf_json(self):
        payload = super().to_tmf_json()
        # Ensure description and applicationOwner are always present
        if "description" not in payload:
            payload["description"] = ""
        app_owner = payload.get("applicationOwner")
        fallback_owner_id = ""
        if self.partner_id:
            fallback_owner_id = getattr(self.partner_id, "tmf_id", "") or str(self.partner_id.id)

        if app_owner is None:
            payload["applicationOwner"] = {"@type": "PartyRoleRef", "id": fallback_owner_id}
        elif isinstance(app_owner, dict):
            if not app_owner.get("@type"):
                app_owner["@type"] = "PartyRoleRef"
            if "id" not in app_owner:
                app_owner["id"] = fallback_owner_id
        elif isinstance(app_owner, list):
            for ao in app_owner:
                if isinstance(ao, dict):
                    if not ao.get("@type"):
                        ao["@type"] = "PartyRoleRef"
                    if "id" not in ao:
                        ao["id"] = fallback_owner_id
        return payload

    def _sync_owner_partner(self):
        Partner = self.env["res.partner"].sudo()
        Owner = self.env["tmf.ogw.application.owner"].sudo()
        for rec in self:
            payload = _loads(rec.payload_json)
            owner = _extract_first_dict(payload.get("applicationOwner"))
            partner = rec.partner_id
            owner_id = _safe_str(owner.get("id"))
            owner_name = _safe_str(owner.get("name"))
            if not partner and owner_id:
                owner_rec = Owner.search([("tmf_id", "=", owner_id)], limit=1)
                partner = owner_rec.partner_id
                if not partner and "tmf_id" in Partner._fields:
                    partner = Partner.search([("tmf_id", "=", owner_id)], limit=1)
            if not partner and owner_name:
                partner = Partner.search([("name", "=", owner_name)], limit=1)
            if partner and rec.partner_id != partner:
                rec.with_context(skip_tmf931_partner_sync=True).write({"partner_id": partner.id})

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        recs._sync_owner_partner()
        return recs

    def write(self, vals):
        res = super().write(vals)
        if not self.env.context.get("skip_tmf931_partner_sync"):
            self._sync_owner_partner()
        return res


class TMFApplicationOwner(models.Model):
    _name = "tmf.ogw.application.owner"
    _description = "TMF931 ApplicationOwner"
    _inherit = ["tmf.open.gateway.operate.mixin"]

    _api_name = "applicationOwner"
    _default_type = "ApplicationOwner"
    _api_path = "/openGatewayOperateAPIOnboardingandOrdering/v5/applicationOwner"

    partner_id = fields.Many2one("res.partner", string="Partner", copy=False, index=True)

    def to_tmf_json(self):
        payload = super().to_tmf_json()
        # Ensure engagedParty is always present with correct @type
        engaged_party = payload.get("engagedParty")
        if not isinstance(engaged_party, dict):
            engaged_party = {}
        engaged_party["@type"] = "ApplicationOwnerOrganization"
        payload["engagedParty"] = engaged_party
        return payload

    def _sync_partner_link(self):
        Partner = self.env["res.partner"].sudo()
        for rec in self:
            payload = _loads(rec.payload_json)
            engaged_party = _extract_first_dict(payload.get("engagedParty"))
            party_id = _safe_str(engaged_party.get("id"))
            party_name = _safe_str(engaged_party.get("name")) or rec.name or "TMF Application Owner"
            partner = rec.partner_id
            if not partner and party_id and "tmf_id" in Partner._fields:
                partner = Partner.search([("tmf_id", "=", party_id)], limit=1)
            if not partner and party_name:
                partner = Partner.search([("name", "=", party_name)], limit=1)
            if not partner:
                create_vals = {"name": party_name}
                if party_id and "tmf_id" in Partner._fields:
                    create_vals["tmf_id"] = party_id
                partner = Partner.create(create_vals)
            elif party_id and "tmf_id" in Partner._fields and not partner.tmf_id:
                partner.write({"tmf_id": party_id})
            if partner and rec.partner_id != partner:
                rec.with_context(skip_tmf931_partner_sync=True).write({"partner_id": partner.id})

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        recs._sync_partner_link()
        return recs

    def write(self, vals):
        res = super().write(vals)
        if not self.env.context.get("skip_tmf931_partner_sync"):
            self._sync_partner_link()
        return res


class TMFOperateMonitor(models.Model):
    _name = "tmf.ogw.monitor"
    _description = "TMF931 Monitor"
    _inherit = ["tmf.open.gateway.operate.mixin"]

    _api_name = "monitor"
    _default_type = "Monitor"
    _api_path = "/openGatewayOperateAPIOnboardingandOrdering/v5/monitor"
