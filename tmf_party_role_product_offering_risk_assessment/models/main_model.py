from odoo import api, fields, models


class TMFRiskAssessmentMixin(models.AbstractModel):
    _name = "tmf.risk.assessment.mixin"
    _description = "TMF696 Risk Assessment Mixin"
    _inherit = ["tmf.model.mixin"]

    status = fields.Char(string="status", default="inProgress")
    characteristic = fields.Json(default=list)
    place = fields.Json(default=list)
    risk_assessment_result = fields.Json(default=dict)
    extra_json = fields.Json(default=dict)

    def _build_common_payload(self):
        self.ensure_one()
        payload = {
            "id": self.tmf_id,
            "href": self.href,
            "@type": self._tmf_type_name(),
            "status": self.status or "inProgress",
            "riskAssessmentResult": self.risk_assessment_result or {},
        }
        if self.characteristic:
            payload["characteristic"] = self.characteristic
        if self.place:
            payload["place"] = self.place
        if isinstance(self.extra_json, dict):
            for key, value in self.extra_json.items():
                if key not in payload:
                    payload[key] = value
        return payload

    def _tmf_type_name(self):
        return "RiskAssessment"

    def _notify(self, action, rec):
        try:
            self.env["tmf.hub.subscription"]._notify_subscribers(
                api_name=self._tmf_api_name(),
                event_type=action,
                resource_json=rec.to_tmf_json(),
            )
        except Exception:
            pass

    def _tmf_api_name(self):
        return "riskAssessment"

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        for rec in recs:
            self._notify("create", rec)
        return recs

    def write(self, vals):
        previous = {rec.id: rec.status for rec in self}
        res = super().write(vals)
        for rec in self:
            self._notify("update", rec)
            if "status" in vals and previous.get(rec.id) != rec.status:
                self._notify("state_change", rec)
        return res

    def unlink(self):
        payloads = [rec.to_tmf_json() for rec in self]
        api_name = self._tmf_api_name()
        res = super().unlink()
        for resource in payloads:
            try:
                self.env["tmf.hub.subscription"]._notify_subscribers(
                    api_name=api_name,
                    event_type="delete",
                    resource_json=resource,
                )
            except Exception:
                pass
        return res


class TMFProductOfferingRiskAssessment(models.Model):
    _name = "tmf.product.offering.risk.assessment"
    _description = "ProductOfferingRiskAssessment"
    _inherit = ["tmf.risk.assessment.mixin"]

    product_offering = fields.Json(default=dict)

    def _tmf_api_name(self):
        return "productOfferingRiskAssessment"

    def _tmf_type_name(self):
        return "ProductOfferingRiskAssessment"

    def _get_tmf_api_path(self):
        return "/riskManagement/v4/productOfferingRiskAssessment"

    def to_tmf_json(self):
        payload = self._build_common_payload()
        if self.product_offering:
            payload["productOffering"] = self.product_offering
        return payload


class TMFPartyRoleRiskAssessment(models.Model):
    _name = "tmf.party.role.risk.assessment"
    _description = "PartyRoleRiskAssessment"
    _inherit = ["tmf.risk.assessment.mixin"]

    party_role = fields.Json(default=dict)

    def _tmf_api_name(self):
        return "partyRoleRiskAssessment"

    def _tmf_type_name(self):
        return "PartyRoleRiskAssessment"

    def _get_tmf_api_path(self):
        return "/riskManagement/v4/partyRoleRiskAssessment"

    def to_tmf_json(self):
        payload = self._build_common_payload()
        if self.party_role:
            payload["partyRole"] = self.party_role
        return payload


class TMFPartyRoleProductOfferingRiskAssessment(models.Model):
    _name = "tmf.party.role.product.offering.risk.assessment"
    _description = "PartyRoleProductOfferingRiskAssessment"
    _inherit = ["tmf.risk.assessment.mixin"]

    party_role = fields.Json(default=dict)
    product_offering = fields.Json(default=dict)

    def _tmf_api_name(self):
        return "partyRoleProductOfferingRiskAssessment"

    def _tmf_type_name(self):
        return "PartyRoleProductOfferingRiskAssessment"

    def _get_tmf_api_path(self):
        return "/riskManagement/v4/partyRoleProductOfferingRiskAssessment"

    def to_tmf_json(self):
        payload = self._build_common_payload()
        if self.party_role:
            payload["partyRole"] = self.party_role
        if self.product_offering:
            payload["productOffering"] = self.product_offering
        return payload


class TMFShoppingCartRiskAssessment(models.Model):
    _name = "tmf.shopping.cart.risk.assessment"
    _description = "ShoppingCartRiskAssessment"
    _inherit = ["tmf.risk.assessment.mixin"]

    shopping_cart = fields.Json(default=dict)

    def _tmf_api_name(self):
        return "shoppingCartRiskAssessment"

    def _tmf_type_name(self):
        return "ShoppingCartRiskAssessment"

    def _get_tmf_api_path(self):
        return "/riskManagement/v4/shoppingCartRiskAssessment"

    def to_tmf_json(self):
        payload = self._build_common_payload()
        if self.shopping_cart:
            payload["shoppingCart"] = self.shopping_cart
        return payload


class TMFProductOrderRiskAssessment(models.Model):
    _name = "tmf.product.order.risk.assessment"
    _description = "ProductOrderRiskAssessment"
    _inherit = ["tmf.risk.assessment.mixin"]

    product_order = fields.Json(default=dict)

    def _tmf_api_name(self):
        return "productOrderRiskAssessment"

    def _tmf_type_name(self):
        return "ProductOrderRiskAssessment"

    def _get_tmf_api_path(self):
        return "/riskManagement/v4/productOrderRiskAssessment"

    def to_tmf_json(self):
        payload = self._build_common_payload()
        if self.product_order:
            payload["productOrder"] = self.product_order
        return payload
