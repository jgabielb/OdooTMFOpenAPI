# -*- coding: utf-8 -*-
from odoo import models, fields, api


# -------------------------
# Common helpers
# -------------------------
def _only_fields(payload: dict, fields_csv: str | None):
    if not fields_csv:
        return payload
    wanted = {f.strip() for f in fields_csv.split(",") if f.strip()}
    # TMF commonly requests fields like "id,href,status,usageType,usageDate"
    return {k: v for k, v in payload.items() if k in wanted}


# -------------------------
# UsageCharacteristic
# -------------------------
class TMFUsageCharacteristic(models.Model):
    _name = "tmf.usage.characteristic"
    _description = "TMF635 UsageCharacteristic"
    _inherit = ["tmf.model.mixin"]

    usage_id = fields.Many2one("tmf.usage", required=True, ondelete="cascade")
    name = fields.Char(required=True)
    value_type = fields.Char(string="valueType")
    value = fields.Char(string="value")
    # (Optional) characteristicRelationship omitted for now; can be added if you need.

    def _get_tmf_api_path(self):
        return "/tmf-api/usageManagement/v4/usage"

    def to_tmf_json(self):
        self.ensure_one()
        return {
            "name": self.name,
            "value": self.value,
            "valueType": self.value_type or None,
        }


# -------------------------
# RelatedParty
# -------------------------
class TMFUsageRelatedParty(models.Model):
    _name = "tmf.usage.related.party"
    _description = "TMF635 RelatedParty (Usage)"
    _inherit = ["tmf.model.mixin"]

    usage_id = fields.Many2one("tmf.usage", required=True, ondelete="cascade")
    party_id = fields.Char(string="id")  # TMF party id
    href = fields.Char()
    name = fields.Char()
    role = fields.Char()
    referred_type = fields.Char(string="@referredType")

    def _get_tmf_api_path(self):
        return "/tmf-api/usageManagement/v4/usage"

    def to_tmf_json(self):
        self.ensure_one()
        out = {
            "id": self.party_id or None,
            "href": self.href or None,
            "name": self.name or None,
            "role": self.role or None,
        }
        if self.referred_type:
            out["@referredType"] = self.referred_type
        return {k: v for k, v in out.items() if v is not None}


# -------------------------
# RatedProductUsage (light but relational)
# -------------------------
class TMFRatedProductUsage(models.Model):
    _name = "tmf.rated.product.usage"
    _description = "TMF635 RatedProductUsage"
    _inherit = ["tmf.model.mixin"]

    usage_id = fields.Many2one("tmf.usage", required=True, ondelete="cascade")

    # minimal set that is commonly used; extend as your CTK requires
    usage_rating_tag = fields.Char(string="usageRatingTag")
    rating_date = fields.Datetime(string="ratingDate")
    is_billed = fields.Boolean(string="isBilled")
    tax_included_rating_amount = fields.Float(string="taxIncludedRatingAmount")
    tax_excluded_rating_amount = fields.Float(string="taxExcludedRatingAmount")
    currency_code = fields.Char(string="currencyCode")

    def _get_tmf_api_path(self):
        return "/tmf-api/usageManagement/v4/usage"

    def to_tmf_json(self):
        self.ensure_one()
        out = {
            "usageRatingTag": self.usage_rating_tag or None,
            "ratingDate": fields.Datetime.to_string(self.rating_date) if self.rating_date else None,
            "isBilled": bool(self.is_billed),
            "taxIncludedRatingAmount": self.tax_included_rating_amount if self.tax_included_rating_amount is not None else None,
            "taxExcludedRatingAmount": self.tax_excluded_rating_amount if self.tax_excluded_rating_amount is not None else None,
            "currencyCode": self.currency_code or None,
        }
        return {k: v for k, v in out.items() if v is not None}


# -------------------------
# UsageSpecification
# -------------------------
class TMFUsageSpecification(models.Model):
    _name = "tmf.usage.specification"
    _description = "TMF635 UsageSpecification"
    _inherit = ["tmf.model.mixin"]

    name = fields.Char(required=True)
    description = fields.Char()
    is_bundle = fields.Boolean(string="isBundle", default=False)
    last_update = fields.Datetime(string="lastUpdate")
    lifecycle_status = fields.Char(string="lifecycleStatus")
    version = fields.Char()

    def _get_tmf_api_path(self):
        return "/tmf-api/usageManagement/v4/usageSpecification"

    def to_tmf_json(self):
        self.ensure_one()
        tmf_id = self.tmf_id or str(self.id)
        href = f"/tmf-api/usageManagement/v4/usageSpecification/{tmf_id}"
        out = {
            "id": tmf_id,
            "href": href,
            "name": self.name,
            "description": self.description or None,
            "isBundle": bool(self.is_bundle),
            "lastUpdate": fields.Datetime.to_string(self.last_update) if self.last_update else None,
            "lifecycleStatus": self.lifecycle_status or None,
            "version": self.version or None,
            "@type": "UsageSpecification",
        }
        return {k: v for k, v in out.items() if v is not None}


# -------------------------
# Usage (main)
# -------------------------
class TMFUsage(models.Model):
    _name = "tmf.usage"
    _description = "TMF635 Usage"
    _inherit = ["tmf.model.mixin"]

    description = fields.Char(string="description")
    usage_date = fields.Datetime(string="usageDate")
    usage_type = fields.Char(string="usageType")
    status = fields.Char(string="status")

    usage_specification_id = fields.Many2one(
        "tmf.usage.specification",
        string="usageSpecification",
        ondelete="set null"
    )

    rated_product_usage_ids = fields.One2many(
        "tmf.rated.product.usage", "usage_id", string="ratedProductUsage"
    )
    related_party_ids = fields.One2many(
        "tmf.usage.related.party", "usage_id", string="relatedParty"
    )
    usage_characteristic_ids = fields.One2many(
        "tmf.usage.characteristic", "usage_id", string="usageCharacteristic"
    )

    def _get_tmf_api_path(self):
        return "/tmf-api/usageManagement/v4/usage"

    def to_tmf_json(self, fields_csv: str | None = None):
        self.ensure_one()
        tmf_id = self.tmf_id or str(self.id)
        href = f"/tmf-api/usageManagement/v4/usage/{tmf_id}"

        usage_spec_ref = None
        if self.usage_specification_id:
            sid = self.usage_specification_id.tmf_id or str(self.usage_specification_id.id)
            usage_spec_ref = {
                "id": sid,
                "href": f"/tmf-api/usageManagement/v4/usageSpecification/{sid}",
                "name": self.usage_specification_id.name,
                "@referredType": "UsageSpecification",
            }

        payload = {
            "id": tmf_id,
            "href": href,
            "@type": "Usage",
            "description": self.description or None,
            "usageDate": fields.Datetime.to_string(self.usage_date) if self.usage_date else None,
            "usageType": self.usage_type or None,
            "status": self.status or None,

            # IMPORTANT: CTK expects this key to exist always
            "usageSpecification": usage_spec_ref,  # can be None

            "ratedProductUsage": [x.to_tmf_json() for x in self.rated_product_usage_ids],
            "relatedParty": [x.to_tmf_json() for x in self.related_party_ids],
            "usageCharacteristic": [x.to_tmf_json() for x in self.usage_characteristic_ids],
        }

        # Remove None values BUT keep usageSpecification even if None
        payload = {k: v for k, v in payload.items() if (v is not None) or (k == "usageSpecification")}

        return _only_fields(payload, fields_csv)

    # -------------------------
    # Notifications (keep your pattern)
    # -------------------------
    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        for r in recs:
            r._notify("usageManagement", "UsageCreateEvent", r)
        return recs

    def write(self, vals):
        res = super().write(vals)
        for r in self:
            r._notify("usageManagement", "UsageAttributeValueChangeEvent", r)
        return res

    def unlink(self):
        for r in self:
            r._notify("usageManagement", "UsageDeleteEvent", r)
        return super().unlink()

    def _notify(self, api_name, action, record):
        try:
            self.env["tmf.hub.subscription"].sudo()._notify_subscribers(
                api_name=api_name,
                event_type=action,
                resource_json=record.to_tmf_json(),
            )
        except Exception:
            pass
