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


class TMFCostMixin(models.AbstractModel):
    _name = "tmf.cost.mixin"
    _description = "TMF764 Cost Mixin"
    _inherit = ["tmf.model.mixin"]

    name = fields.Char(string="name")
    description = fields.Char(string="description")
    state = fields.Char(string="state")
    payload_json = fields.Text(string="payload")
    tmf_type_value = fields.Char(string="@type")
    base_type = fields.Char(string="@baseType")
    schema_location = fields.Char(string="@schemaLocation")
    partner_id = fields.Many2one("res.partner", string="Partner", copy=False, index=True)
    account_move_id = fields.Many2one("account.move", string="Account Move", copy=False, index=True)
    analytic_account_id = fields.Many2one("account.analytic.account", string="Analytic Account", copy=False, index=True)
    cost_amount = fields.Float(string="Cost Amount")
    cost_currency = fields.Char(string="Cost Currency")

    _api_name = None
    _default_type = None
    _item_key = None

    def to_tmf_json(self):
        self.ensure_one()
        payload = _loads(self.payload_json)
        payload["id"] = self.tmf_id
        payload["href"] = self.href
        if self.name is not None:
            payload["name"] = self.name
        if self.description is not None:
            payload["description"] = self.description
        if self.state is not None:
            payload["state"] = self.state
        payload["@type"] = self.tmf_type_value or payload.get("@type") or self._default_type
        if self.base_type:
            payload["@baseType"] = self.base_type
        if self.schema_location:
            payload["@schemaLocation"] = self.schema_location
        return self._tmf_normalize_payload(_compact(payload))

    def from_tmf_json(self, data, partial=False):
        vals = {"payload_json": _dumps(data)}
        for key, field_name in [
            ("name", "name"),
            ("description", "description"),
            ("state", "state"),
            ("@type", "tmf_type_value"),
            ("@baseType", "base_type"),
            ("@schemaLocation", "schema_location"),
        ]:
            if key in data:
                vals[field_name] = data.get(key)
        return vals

    def _extract_item(self, payload):
        item_key = self._item_key or ""
        items = payload.get(item_key)
        if isinstance(items, list):
            for item in items:
                if isinstance(item, dict):
                    return item
        if isinstance(items, dict):
            return items
        return {}

    @staticmethod
    def _to_float(value):
        try:
            return float(value)
        except Exception:
            return 0.0

    def _resolve_partner_from_payload(self, payload):
        Partner = self.env["res.partner"].sudo()
        entries = payload.get("relatedParty")
        entries = entries if isinstance(entries, list) else [entries]
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            pid = str(entry.get("id") or "").strip()
            pname = str(entry.get("name") or "").strip()
            if pid and "tmf_id" in Partner._fields:
                partner = Partner.search([("tmf_id", "=", pid)], limit=1)
                if partner:
                    return partner
            if pid.isdigit():
                partner = Partner.browse(int(pid))
                if partner.exists():
                    return partner
            if pname:
                partner = Partner.search([("name", "=", pname)], limit=1)
                if partner:
                    return partner
                return Partner.create({"name": pname})
        return Partner

    def _resolve_account_move_from_payload(self, payload):
        Move = self.env["account.move"].sudo()
        account_ref = payload.get("account") or payload.get("billingAccount") or {}
        if not isinstance(account_ref, dict):
            return Move
        rid = str(account_ref.get("id") or "").strip()
        if not rid:
            return Move
        if rid.isdigit():
            move = Move.browse(int(rid))
            if move.exists():
                return move
        move = Move.search(["|", ("name", "=", rid), ("ref", "=", rid)], limit=1)
        if move:
            return move
        return Move

    def _resolve_analytic_from_payload(self, payload):
        Analytic = self.env["account.analytic.account"].sudo()
        item = self._extract_item(payload)
        acc_ref = item.get("costAccount") if isinstance(item, dict) else {}
        if not isinstance(acc_ref, dict):
            return Analytic
        rid = str(acc_ref.get("id") or "").strip()
        name = str(acc_ref.get("name") or "").strip()
        if rid:
            if rid.isdigit():
                rec = Analytic.browse(int(rid))
                if rec.exists():
                    return rec
            rec = Analytic.search([("code", "=", rid)], limit=1)
            if rec:
                return rec
        if name:
            rec = Analytic.search([("name", "=", name)], limit=1)
            if rec:
                return rec
            return Analytic.create({"name": name, "code": rid or False})
        return Analytic

    def _extract_amount_currency(self, payload):
        item = self._extract_item(payload)
        if not isinstance(item, dict):
            return 0.0, False
        amount = 0.0
        currency = False
        for key in ("amount", "totalAmount", "value"):
            if key in item:
                raw = item.get(key)
                if isinstance(raw, dict):
                    amount = self._to_float(raw.get("amount") or raw.get("value"))
                    currency = raw.get("unit") or raw.get("currencyCode") or raw.get("currency")
                else:
                    amount = self._to_float(raw)
                if amount:
                    break
        if not amount:
            price = item.get("price")
            if isinstance(price, dict):
                amount = self._to_float(price.get("taxIncludedAmount", {}).get("value") or price.get("value"))
                currency = currency or price.get("taxIncludedAmount", {}).get("unit") or price.get("unit")
        return amount, currency

    def _sync_odoo_links(self):
        for rec in self:
            payload = _loads(rec.payload_json) or {}
            vals = {}
            partner = rec._resolve_partner_from_payload(payload)
            if partner and rec.partner_id != partner:
                vals["partner_id"] = partner.id
            move = rec._resolve_account_move_from_payload(payload)
            if move and rec.account_move_id != move:
                vals["account_move_id"] = move.id
            analytic = rec._resolve_analytic_from_payload(payload)
            if analytic and rec.analytic_account_id != analytic:
                vals["analytic_account_id"] = analytic.id
            amount, currency = rec._extract_amount_currency(payload)
            if amount and rec.cost_amount != amount:
                vals["cost_amount"] = amount
            if currency and rec.cost_currency != currency:
                vals["cost_currency"] = str(currency)
            if vals:
                rec.with_context(skip_tmf_cost_sync=True).write(vals)

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
        if not self.env.context.get("skip_tmf_cost_sync"):
            recs._sync_odoo_links()
        for rec in recs:
            self._notify("create", rec)
        return recs

    def write(self, vals):
        state_changed = "state" in vals
        res = super().write(vals)
        if not self.env.context.get("skip_tmf_cost_sync"):
            self._sync_odoo_links()
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


class TMFActualCost(models.Model):
    _name = "tmf.actual.cost"
    _description = "TMF764 ActualCost"
    _inherit = ["tmf.cost.mixin"]

    _api_name = "actualCost"
    _default_type = "ActualCost"
    _item_key = "actualCostItem"

    def _get_tmf_api_path(self):
        return "/costManagement/v5/actualCost"


class TMFProjectedCost(models.Model):
    _name = "tmf.projected.cost"
    _description = "TMF764 ProjectedCost"
    _inherit = ["tmf.cost.mixin"]

    _api_name = "projectedCost"
    _default_type = "ProjectedCost"
    _item_key = "projectedCostItem"

    def _get_tmf_api_path(self):
        return "/costManagement/v5/projectedCost"
