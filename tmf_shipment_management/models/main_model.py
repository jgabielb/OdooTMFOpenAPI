import json
from odoo import api, fields, models


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


class _TMF711CommonMixin(models.AbstractModel):
    _name = "tmf.shipment.common.mixin"
    _description = "TMF711 Common Mixin"
    _inherit = ["tmf.model.mixin"]

    description = fields.Char(string="description")
    name = fields.Char(string="name")
    version = fields.Char(string="version")
    state = fields.Char(string="state")
    tmf_type_value = fields.Char(string="@type")
    base_type = fields.Char(string="@baseType")
    schema_location = fields.Char(string="@schemaLocation")

    def _common_to_tmf_json(self):
        self.ensure_one()
        return {
            "id": self.tmf_id,
            "href": self.href,
            "description": self.description,
            "name": self.name,
            "version": self.version,
            "@type": self.tmf_type_value,
            "@baseType": self.base_type,
            "@schemaLocation": self.schema_location,
        }

    def _common_from_tmf_json(self, data):
        vals = {}
        for key, field_name in [
            ("description", "description"),
            ("name", "name"),
            ("version", "version"),
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


class TMFShipment(models.Model):
    _name = "tmf.shipment"
    _description = "TMF711 Shipment"
    _inherit = ["tmf.shipment.common.mixin"]

    collection_date = fields.Char(string="collectionDate")
    completion_date = fields.Char(string="completionDate")
    delivery_date = fields.Char(string="deliveryDate")
    expected_delivery_date = fields.Char(string="expectedDeliveryDate")
    requested_delivery_date = fields.Char(string="requestedDeliveryDate")

    characteristic_json = fields.Text(string="characteristic")
    external_identifier_json = fields.Text(string="externalIdentifier")
    note_json = fields.Text(string="note")
    payment_method_json = fields.Text(string="paymentMethod")
    place_from_json = fields.Text(string="placeFrom")
    place_to_json = fields.Text(string="placeTo")
    related_party_json = fields.Text(string="relatedParty")
    related_shipment_json = fields.Text(string="relatedShipment")
    shipment_item_json = fields.Text(string="shipmentItem")
    shipment_price_json = fields.Text(string="shipmentPrice")
    shipment_specification_json = fields.Text(string="shipmentSpecification")
    shipment_tracking_json = fields.Text(string="shipmentTracking")
    shipping_instruction_json = fields.Text(string="shippingInstruction")
    weight_json = fields.Text(string="weight")

    def _get_tmf_api_path(self):
        return "/shipmentManagement/v4/shipment"

    def to_tmf_json(self):
        payload = self._common_to_tmf_json()
        payload["@type"] = self.tmf_type_value or "Shipment"
        payload["collectionDate"] = self.collection_date
        payload["completionDate"] = self.completion_date
        payload["deliveryDate"] = self.delivery_date
        payload["expectedDeliveryDate"] = self.expected_delivery_date
        payload["requestedDeliveryDate"] = self.requested_delivery_date
        payload["characteristic"] = _loads(self.characteristic_json)
        payload["externalIdentifier"] = _loads(self.external_identifier_json)
        payload["note"] = _loads(self.note_json)
        payload["paymentMethod"] = _loads(self.payment_method_json)
        payload["placeFrom"] = _loads(self.place_from_json)
        payload["placeTo"] = _loads(self.place_to_json)
        payload["relatedParty"] = _loads(self.related_party_json)
        payload["relatedShipment"] = _loads(self.related_shipment_json)
        payload["shipmentItem"] = _loads(self.shipment_item_json)
        payload["shipmentPrice"] = _loads(self.shipment_price_json)
        payload["shipmentSpecification"] = _loads(self.shipment_specification_json)
        payload["shipmentTracking"] = _loads(self.shipment_tracking_json)
        payload["shippingInstruction"] = _loads(self.shipping_instruction_json)
        payload["weight"] = _loads(self.weight_json)
        return self._tmf_normalize_payload(_compact(payload))

    def from_tmf_json(self, data, partial=False):
        vals = self._common_from_tmf_json(data)
        for key, field_name in [
            ("collectionDate", "collection_date"),
            ("completionDate", "completion_date"),
            ("deliveryDate", "delivery_date"),
            ("expectedDeliveryDate", "expected_delivery_date"),
            ("requestedDeliveryDate", "requested_delivery_date"),
        ]:
            if key in data:
                vals[field_name] = data.get(key)
        for key, field_name in [
            ("characteristic", "characteristic_json"),
            ("externalIdentifier", "external_identifier_json"),
            ("note", "note_json"),
            ("paymentMethod", "payment_method_json"),
            ("placeFrom", "place_from_json"),
            ("placeTo", "place_to_json"),
            ("relatedParty", "related_party_json"),
            ("relatedShipment", "related_shipment_json"),
            ("shipmentItem", "shipment_item_json"),
            ("shipmentPrice", "shipment_price_json"),
            ("shipmentSpecification", "shipment_specification_json"),
            ("shipmentTracking", "shipment_tracking_json"),
            ("shippingInstruction", "shipping_instruction_json"),
            ("weight", "weight_json"),
        ]:
            if key in data:
                vals[field_name] = _dumps(data.get(key))
        if "state" in data:
            vals["state"] = data.get("state")
        return vals

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        for rec in recs:
            self._notify("shipment", "create", rec)
        return recs

    def write(self, vals):
        state_changed = "state" in vals
        res = super().write(vals)
        for rec in self:
            self._notify("shipment", "update", rec)
            if state_changed:
                self._notify("shipment", "state_change", rec)
        return res

    def unlink(self):
        payloads = [rec.to_tmf_json() for rec in self]
        res = super().unlink()
        for payload in payloads:
            try:
                self.env["tmf.hub.subscription"]._notify_subscribers(
                    api_name="shipment",
                    event_type="delete",
                    resource_json=payload,
                )
            except Exception:
                pass
        return res


class TMFShipmentSpecification(models.Model):
    _name = "tmf.shipment.specification"
    _description = "TMF711 ShipmentSpecification"
    _inherit = ["tmf.shipment.common.mixin"]

    lifecycle_status = fields.Char(string="lifecycleStatus")
    is_bundle = fields.Boolean(string="isBundle")
    last_update = fields.Char(string="lastUpdate")

    attachment_json = fields.Text(string="attachment")
    constraint_json = fields.Text(string="constraint")
    related_party_json = fields.Text(string="relatedParty")
    shipment_spec_relationship_json = fields.Text(string="shipmentSpecRelationship")
    signature_required_by_json = fields.Text(string="signatureRequiredBy")
    spec_characteristic_json = fields.Text(string="specCharacteristic")
    target_shipment_schema_json = fields.Text(string="targetShipmentSchema")
    valid_for_json = fields.Text(string="validFor")

    def _get_tmf_api_path(self):
        return "/shipmentManagement/v4/shipmentSpecification"

    def to_tmf_json(self):
        payload = self._common_to_tmf_json()
        payload["@type"] = self.tmf_type_value or "ShipmentSpecification"
        payload["lifecycleStatus"] = self.lifecycle_status
        payload["isBundle"] = self.is_bundle
        payload["lastUpdate"] = self.last_update
        payload["attachment"] = _loads(self.attachment_json)
        payload["constraint"] = _loads(self.constraint_json)
        payload["relatedParty"] = _loads(self.related_party_json)
        payload["shipmentSpecRelationship"] = _loads(self.shipment_spec_relationship_json)
        payload["signatureRequiredBy"] = _loads(self.signature_required_by_json)
        payload["specCharacteristic"] = _loads(self.spec_characteristic_json)
        payload["targetShipmentSchema"] = _loads(self.target_shipment_schema_json)
        payload["validFor"] = _loads(self.valid_for_json)
        return self._tmf_normalize_payload(_compact(payload))

    def from_tmf_json(self, data, partial=False):
        vals = self._common_from_tmf_json(data)
        for key, field_name in [
            ("lifecycleStatus", "lifecycle_status"),
            ("lastUpdate", "last_update"),
            ("isBundle", "is_bundle"),
            ("state", "state"),
        ]:
            if key in data:
                vals[field_name] = data.get(key)
        for key, field_name in [
            ("attachment", "attachment_json"),
            ("constraint", "constraint_json"),
            ("relatedParty", "related_party_json"),
            ("shipmentSpecRelationship", "shipment_spec_relationship_json"),
            ("signatureRequiredBy", "signature_required_by_json"),
            ("specCharacteristic", "spec_characteristic_json"),
            ("targetShipmentSchema", "target_shipment_schema_json"),
            ("validFor", "valid_for_json"),
        ]:
            if key in data:
                vals[field_name] = _dumps(data.get(key))
        return vals

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        for rec in recs:
            self._notify("shipmentSpecification", "create", rec)
        return recs

    def write(self, vals):
        state_changed = "state" in vals or "lifecycle_status" in vals
        res = super().write(vals)
        for rec in self:
            self._notify("shipmentSpecification", "update", rec)
            if state_changed:
                self._notify("shipmentSpecification", "state_change", rec)
        return res

    def unlink(self):
        payloads = [rec.to_tmf_json() for rec in self]
        res = super().unlink()
        for payload in payloads:
            try:
                self.env["tmf.hub.subscription"]._notify_subscribers(
                    api_name="shipmentSpecification",
                    event_type="delete",
                    resource_json=payload,
                )
            except Exception:
                pass
        return res

