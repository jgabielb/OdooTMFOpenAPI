import json
from datetime import datetime, timezone
from odoo import api, fields, models
import logging


_logger = logging.getLogger(__name__)


def _dumps(value):
    return json.dumps(value, ensure_ascii=False) if value is not None else False


def _loads(value):
    if not value:
        return None
    try:
        return json.loads(value)
    except Exception:
        return None


def _compact(payload):
    return {k: v for k, v in payload.items() if v is not None}


class _TMF728CommonMixin(models.AbstractModel):
    _name = "tmf.dunning.common.mixin"
    _description = "TMF728 Common Dunning Mixin"
    _inherit = ["tmf.model.mixin"]

    name = fields.Char(string="name")
    description = fields.Char(string="description")
    category = fields.Char(string="category")
    tmf_type_value = fields.Char(string="@type")
    base_type = fields.Char(string="@baseType")
    schema_location = fields.Char(string="@schemaLocation")

    @staticmethod
    def _now_iso():
        return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    def _common_to_tmf_json(self):
        self.ensure_one()
        return {
            "id": self.tmf_id,
            "href": self.href,
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "@type": self.tmf_type_value,
            "@baseType": self.base_type,
            "@schemaLocation": self.schema_location,
        }

    def _common_from_tmf_json(self, data):
        vals = {}
        for key, field_name in [
            ("name", "name"),
            ("description", "description"),
            ("category", "category"),
            ("@type", "tmf_type_value"),
            ("@baseType", "base_type"),
            ("@schemaLocation", "schema_location"),
        ]:
            if key in data:
                vals[field_name] = data.get(key)
        return vals

    def _notify(self, api_name, action, rec):
        try:
            self.env["tmf.hub.subscription"]._notify_subscribers(
                api_name=api_name,
                event_type=action,
                resource_json=rec.to_tmf_json(),
            )
        except Exception:
            pass


class TMFDunningScenario(models.Model):
    _name = "tmf.dunning.scenario"
    _description = "TMF728 DunningScenario"
    _inherit = ["tmf.dunning.common.mixin"]

    is_default = fields.Boolean(string="isDefault")
    dunning_rule_json = fields.Text(string="dunningRule")

    def _get_tmf_api_path(self):
        return "/dunningCase/v4/dunningScenario"

    def to_tmf_json(self):
        payload = self._common_to_tmf_json()
        payload.update(
            {
                "isDefault": self.is_default,
                "dunningRule": _loads(self.dunning_rule_json),
                "@type": self.tmf_type_value or "DunningScenario",
            }
        )
        return self._tmf_normalize_payload(_compact(payload))

    def from_tmf_json(self, data, partial=False):
        vals = self._common_from_tmf_json(data)
        if "isDefault" in data:
            vals["is_default"] = data.get("isDefault")
        if "dunningRule" in data:
            vals["dunning_rule_json"] = _dumps(data.get("dunningRule"))
        return vals

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        for rec in recs:
            self._notify("dunningScenario", "create", rec)
        return recs

    def write(self, vals):
        res = super().write(vals)
        for rec in self:
            self._notify("dunningScenario", "update", rec)
        return res

    def unlink(self):
        payloads = [rec.to_tmf_json() for rec in self]
        res = super().unlink()
        for payload in payloads:
            try:
                self.env["tmf.hub.subscription"]._notify_subscribers(
                    api_name="dunningScenario",
                    event_type="delete",
                    resource_json=payload,
                )
            except Exception:
                pass
        return res


class TMFDunningRule(models.Model):
    _name = "tmf.dunning.rule"
    _description = "TMF728 DunningRule"
    _inherit = ["tmf.dunning.common.mixin"]

    dunning_action = fields.Char(string="dunningAction")
    dunning_condition = fields.Char(string="dunningCondition")
    dunning_event = fields.Char(string="dunningEvent")
    dunning_rule_characteristic_json = fields.Text(string="dunningRuleCharacteristic")

    def _get_tmf_api_path(self):
        return "/dunningCase/v4/dunningRule"

    def to_tmf_json(self):
        payload = self._common_to_tmf_json()
        payload.update(
            {
                "dunningAction": self.dunning_action,
                "dunningCondition": self.dunning_condition,
                "dunningEvent": self.dunning_event,
                "dunningRuleCharacteristic": _loads(self.dunning_rule_characteristic_json),
                "@type": self.tmf_type_value or "DunningRule",
            }
        )
        return self._tmf_normalize_payload(_compact(payload))

    def from_tmf_json(self, data, partial=False):
        vals = self._common_from_tmf_json(data)
        for key, field_name in [
            ("dunningAction", "dunning_action"),
            ("dunningCondition", "dunning_condition"),
            ("dunningEvent", "dunning_event"),
        ]:
            if key in data:
                vals[field_name] = data.get(key)
        if "dunningRuleCharacteristic" in data:
            vals["dunning_rule_characteristic_json"] = _dumps(data.get("dunningRuleCharacteristic"))
        return vals

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        for rec in recs:
            self._notify("dunningRule", "create", rec)
        return recs

    def write(self, vals):
        res = super().write(vals)
        for rec in self:
            self._notify("dunningRule", "update", rec)
        return res

    def unlink(self):
        payloads = [rec.to_tmf_json() for rec in self]
        res = super().unlink()
        for payload in payloads:
            try:
                self.env["tmf.hub.subscription"]._notify_subscribers(
                    api_name="dunningRule",
                    event_type="delete",
                    resource_json=payload,
                )
            except Exception:
                pass
        return res


class TMFDunningCase(models.Model):
    _name = "tmf.dunning.case"
    _description = "TMF728 DunningCase"
    _inherit = ["tmf.dunning.common.mixin"]

    creation_date = fields.Char(string="creationDate")
    last_activity_date = fields.Char(string="lastActivityDate")
    last_update_date = fields.Char(string="lastUpdateDate")
    status = fields.Char(string="status")

    billing_account_json = fields.Text(string="billingAccount")
    dunning_case_rule_json = fields.Text(string="dunningCaseRule")
    dunning_scenario_json = fields.Text(string="dunningScenario")
    final_balance_json = fields.Text(string="finalBalance")
    initial_balance_json = fields.Text(string="initialBalance")
    note_json = fields.Text(string="note")
    related_party_json = fields.Text(string="relatedParty")
    valid_for_json = fields.Text(string="validFor")
    partner_id = fields.Many2one("res.partner", string="Partner", copy=False, index=True)
    account_move_id = fields.Many2one("account.move", string="Invoice/Move", copy=False, index=True)

    def _extract_partner_from_payload(self):
        self.ensure_one()
        Partner = self.env["res.partner"].sudo()
        related = _loads(self.related_party_json)
        entries = related if isinstance(related, list) else [related]
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
        return Partner

    def _extract_move_from_payload(self):
        self.ensure_one()
        Move = self.env["account.move"].sudo()
        billing = _loads(self.billing_account_json)
        if not isinstance(billing, dict):
            return Move

        bid = str(billing.get("id") or "").strip()
        bref = str(billing.get("accountBalance", "") or "").strip()
        bname = str(billing.get("name") or "").strip()

        if bid.isdigit():
            move = Move.browse(int(bid))
            if move.exists():
                return move

        for value in [bid, bname, bref]:
            if not value:
                continue
            for field_name in ("name", "ref", "payment_reference"):
                if field_name in Move._fields:
                    move = Move.search([(field_name, "=", value)], limit=1)
                    if move:
                        return move

        return Move

    def _sync_odoo_links(self):
        for rec in self:
            partner = rec.partner_id or rec._extract_partner_from_payload()
            move = rec.account_move_id or rec._extract_move_from_payload()
            vals = {}
            if partner and rec.partner_id != partner:
                vals["partner_id"] = partner.id
            if move and rec.account_move_id != move:
                vals["account_move_id"] = move.id
                if not vals.get("partner_id") and not rec.partner_id and move.partner_id:
                    vals["partner_id"] = move.partner_id.id
            if vals:
                rec.with_context(skip_tmf_dunning_sync=True).write(vals)

    def _get_tmf_api_path(self):
        return "/dunningCase/v4/dunningCase"

    def to_tmf_json(self):
        payload = self._common_to_tmf_json()
        payload.update(
            {
                "creationDate": self.creation_date,
                "lastActivityDate": self.last_activity_date,
                "lastUpdateDate": self.last_update_date,
                "status": self.status,
                "billingAccount": _loads(self.billing_account_json),
                "dunningCaseRule": _loads(self.dunning_case_rule_json),
                "dunningScenario": _loads(self.dunning_scenario_json),
                "finalBalance": _loads(self.final_balance_json),
                "initialBalance": _loads(self.initial_balance_json),
                "note": _loads(self.note_json),
                "relatedParty": _loads(self.related_party_json),
                "validFor": _loads(self.valid_for_json),
                "@type": self.tmf_type_value or "DunningCase",
            }
        )
        return self._tmf_normalize_payload(_compact(payload))

    def from_tmf_json(self, data, partial=False):
        vals = self._common_from_tmf_json(data)
        for key, field_name in [
            ("creationDate", "creation_date"),
            ("lastActivityDate", "last_activity_date"),
            ("lastUpdateDate", "last_update_date"),
            ("status", "status"),
        ]:
            if key in data:
                vals[field_name] = data.get(key)
        for key, field_name in [
            ("billingAccount", "billing_account_json"),
            ("dunningCaseRule", "dunning_case_rule_json"),
            ("dunningScenario", "dunning_scenario_json"),
            ("finalBalance", "final_balance_json"),
            ("initialBalance", "initial_balance_json"),
            ("note", "note_json"),
            ("relatedParty", "related_party_json"),
            ("validFor", "valid_for_json"),
        ]:
            if key in data:
                vals[field_name] = _dumps(data.get(key))
        return vals

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals.setdefault("creation_date", vals.get("creation_date") or self._now_iso())
            vals.setdefault("last_update_date", vals.get("last_update_date") or vals.get("creation_date"))
        recs = super().create(vals_list)
        if not self.env.context.get("skip_tmf_dunning_sync"):
            try:
                recs._sync_odoo_links()
            except Exception:
                _logger.exception("TMF728 failed to sync partner/account links during create")
        for rec in recs:
            self._notify("dunningCase", "create", rec)
        return recs

    def write(self, vals):
        status_changed = "status" in vals
        if "last_update_date" not in vals:
            vals = dict(vals)
            vals["last_update_date"] = self._now_iso()
        res = super().write(vals)
        if not self.env.context.get("skip_tmf_dunning_sync"):
            try:
                self._sync_odoo_links()
            except Exception:
                _logger.exception("TMF728 failed to sync partner/account links during write")
        for rec in self:
            self._notify("dunningCase", "update", rec)
            if status_changed:
                self._notify("dunningCase", "state_change", rec)
        return res

    def unlink(self):
        payloads = [rec.to_tmf_json() for rec in self]
        res = super().unlink()
        for payload in payloads:
            try:
                self.env["tmf.hub.subscription"]._notify_subscribers(
                    api_name="dunningCase",
                    event_type="delete",
                    resource_json=payload,
                )
            except Exception:
                pass
        return res

