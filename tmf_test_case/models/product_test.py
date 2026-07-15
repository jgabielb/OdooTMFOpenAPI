# -*- coding: utf-8 -*-
"""TMF769 Product Test Management resources.

ProductTest / ProductTestSpecification reuse the TMF704 artifact mixin so the
TMFC054 component gets its YAML-exposed TMF769 surface from the same addon.
"""
from odoo import api, fields, models

from .main_model import _dumps, _loads


class TMFProductTestSpecification(models.Model):
    _name = "tmf.product.test.specification"
    _description = "TMF769 ProductTestSpecification"
    _inherit = ["tmf.test.artifact.mixin"]

    name = fields.Char(string="name")
    is_bundle = fields.Boolean(string="isBundle", default=False)
    life_cycle_status = fields.Char(string="lifecycleStatus")
    valid_for_json = fields.Text(string="validFor")
    product_specification_json = fields.Text(string="productSpecification")
    test_measure_definition_json = fields.Text(string="testMeasureDefinition")
    related_test_spec_json = fields.Text(string="relatedProductTestSpecification")

    def _get_tmf_api_path(self):
        return "/productTestManagement/v4/productTestSpecification"

    def to_tmf_json(self):
        payload = self._artifact_to_tmf_json()
        payload["@type"] = self.tmf_type_value or "ProductTestSpecification"
        payload["name"] = self.name
        payload["isBundle"] = self.is_bundle
        payload["lifecycleStatus"] = self.life_cycle_status
        payload["validFor"] = _loads(self.valid_for_json)
        payload["productSpecification"] = _loads(self.product_specification_json)
        payload["testMeasureDefinition"] = _loads(self.test_measure_definition_json)
        payload["relatedProductTestSpecification"] = _loads(self.related_test_spec_json)
        return {k: v for k, v in payload.items() if v is not None}

    def from_tmf_json(self, data, partial=False):
        vals = self._artifact_from_tmf_json(data)
        if "name" in data:
            vals["name"] = data.get("name")
        if "isBundle" in data:
            vals["is_bundle"] = bool(data.get("isBundle"))
        if "lifecycleStatus" in data:
            vals["life_cycle_status"] = data.get("lifecycleStatus")
        for key, field_name in [
            ("validFor", "valid_for_json"),
            ("productSpecification", "product_specification_json"),
            ("testMeasureDefinition", "test_measure_definition_json"),
            ("relatedProductTestSpecification", "related_test_spec_json"),
        ]:
            if key in data:
                vals[field_name] = _dumps(data.get(key))
        return vals

    def _notify(self, action, rec=None, payload=None):
        try:
            self.env["tmf.hub.subscription"]._notify_subscribers(
                api_name="productTestSpecification",
                event_type=action,
                resource_json=payload if payload is not None else rec.to_tmf_json(),
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
        state_changed = "state" in vals or "life_cycle_status" in vals
        res = super().write(vals)
        for rec in self:
            self._notify("update", rec)
            if state_changed:
                self._notify("state_change", rec)
        return res

    def unlink(self):
        payloads = [rec.to_tmf_json() for rec in self]
        res = super().unlink()
        for payload in payloads:
            self._notify("delete", payload=payload)
        return res


class TMFProductTest(models.Model):
    _name = "tmf.product.test"
    _description = "TMF769 ProductTest"
    _inherit = ["tmf.test.artifact.mixin"]

    name = fields.Char(string="name")
    mode = fields.Char(string="mode")
    start_date_time = fields.Char(string="startDateTime")
    end_date_time = fields.Char(string="endDateTime")
    valid_for_json = fields.Text(string="validFor")
    product_json = fields.Text(string="product")
    test_measure_json = fields.Text(string="testMeasure")
    characteristic_json = fields.Text(string="characteristic")
    test_specification_json = fields.Text(string="productTestSpecification")

    def _get_tmf_api_path(self):
        return "/productTestManagement/v4/productTest"

    def to_tmf_json(self):
        payload = self._artifact_to_tmf_json()
        payload["@type"] = self.tmf_type_value or "ProductTest"
        payload["name"] = self.name
        payload["mode"] = self.mode
        payload["startDateTime"] = self.start_date_time
        payload["endDateTime"] = self.end_date_time
        payload["validFor"] = _loads(self.valid_for_json)
        payload["product"] = _loads(self.product_json)
        payload["testMeasure"] = _loads(self.test_measure_json)
        payload["characteristic"] = _loads(self.characteristic_json)
        payload["productTestSpecification"] = _loads(self.test_specification_json)
        return {k: v for k, v in payload.items() if v is not None}

    def from_tmf_json(self, data, partial=False):
        vals = self._artifact_from_tmf_json(data)
        for key, field_name in [
            ("name", "name"),
            ("mode", "mode"),
            ("startDateTime", "start_date_time"),
            ("endDateTime", "end_date_time"),
        ]:
            if key in data:
                vals[field_name] = data.get(key)
        for key, field_name in [
            ("validFor", "valid_for_json"),
            ("product", "product_json"),
            ("testMeasure", "test_measure_json"),
            ("characteristic", "characteristic_json"),
            ("productTestSpecification", "test_specification_json"),
        ]:
            if key in data:
                vals[field_name] = _dumps(data.get(key))
        return vals

    def _notify(self, action, rec=None, payload=None):
        try:
            self.env["tmf.hub.subscription"]._notify_subscribers(
                api_name="productTest",
                event_type=action,
                resource_json=payload if payload is not None else rec.to_tmf_json(),
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
        state_changed = "state" in vals
        res = super().write(vals)
        for rec in self:
            self._notify("update", rec)
            if state_changed:
                self._notify("state_change", rec)
        return res

    def unlink(self):
        payloads = [rec.to_tmf_json() for rec in self]
        res = super().unlink()
        for payload in payloads:
            self._notify("delete", payload=payload)
        return res
