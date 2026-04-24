# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import uuid
from datetime import datetime, timezone


def _rfc3339_now():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _safe_date(value):
    if not value:
        return False
    # Odoo may carry booleans for unset/invalid datetime values; guard before .date()
    if isinstance(value, bool):
        return False
    if hasattr(value, "date"):
        return value.date()
    return False


# ------------------------------------------------------------
# Sub-resources
# ------------------------------------------------------------
class TMFExternalReference(models.Model):
    _name = "tmf.external.reference"
    _description = "TMF ExternalReference"

    name = fields.Char(required=True)  # TMF652 additional rules: externalReference.name mandatory
    externalReferenceType = fields.Char()
    href = fields.Char()

    resource_order_id = fields.Many2one("tmf.resource.order", ondelete="cascade", required=True)


class TMFNote(models.Model):
    _name = "tmf.note"
    _description = "TMF Note"

    tmf_note_id = fields.Char(default=lambda self: uuid.uuid4().hex, required=True)
    author = fields.Char()
    date = fields.Datetime()
    text = fields.Text(required=True)  # TMF652 additional rules: note.text mandatory
    href = fields.Char()

    resource_order_id = fields.Many2one("tmf.resource.order", ondelete="cascade", required=True)


class TMFRelatedParty(models.Model):
    _name = "tmf.related.party"
    _description = "TMF RelatedParty"

    tmf_party_id = fields.Char(required=True)  # TMF652 additional rules: relatedParty.id mandatory
    name = fields.Char()
    href = fields.Char()
    role = fields.Char()  # TMF652: role mandatory if id identifies a party (we enforce)
    referredType = fields.Char(required=True)  # TMF652 additional rules: relatedParty.@referredType mandatory

    resource_order_id = fields.Many2one("tmf.resource.order", ondelete="cascade", required=True)


class TMFCharacteristic(models.Model):
    _name = "tmf.characteristic"
    _description = "TMF Characteristic"

    tmf_char_id = fields.Char(default=lambda self: uuid.uuid4().hex, required=True)
    name = fields.Char(required=True)  # TMF652 additional rules: resourceCharacteristic.name mandatory
    value = fields.Char()
    valueType = fields.Char()

    resource_id = fields.Many2one("tmf.resource", ondelete="cascade", required=True)


class TMFResource(models.Model):
    _name = "tmf.resource"
    _description = "TMF Resource (RefOrValue minimal)"

    tmf_resource_id = fields.Char(default=lambda self: uuid.uuid4().hex, required=True)
    href = fields.Char()
    name = fields.Char()
    category = fields.Char()
    description = fields.Text()
    resourceVersion = fields.Char()

    # Polymorphism helpers
    baseType = fields.Char()
    schemaLocation = fields.Char()
    type = fields.Char()  # e.g. PhysicalResource / LogicalResource

    characteristic_ids = fields.One2many("tmf.characteristic", "resource_id", string="resourceCharacteristic")

    order_item_id = fields.Many2one("tmf.resource.order.item", ondelete="cascade", required=True)


# ------------------------------------------------------------
# Main resources
# ------------------------------------------------------------
class TMFResourceOrderItem(models.Model):
    _name = "tmf.resource.order.item"
    _description = "TMF ResourceOrderItem"

    item_id = fields.Char(required=True)  # TMF "id" for item line
    action = fields.Selection(
        selection=[
            ("add", "add"),
            ("modify", "modify"),
            ("delete", "delete"),
            ("noChange", "noChange"),
        ],
        required=True,
    )
    quantity = fields.Integer()
    state = fields.Char()  # TMF652 POST rule: must NOT be set on create

    # AppointmentRef minimal (if present, id required)
    appointment_id = fields.Char()
    appointment_href = fields.Char()
    appointment_description = fields.Char()

    resource_id = fields.Many2one("tmf.resource", ondelete="set null")

    resource_order_id = fields.Many2one("tmf.resource.order", ondelete="cascade", required=True)


class TMFResourceOrder(models.Model):
    _name = "tmf.resource.order"
    _description = "TMF ResourceOrder (TMF652 v4)"

    def to_tmf_json(self):
        self.ensure_one()

        def dt(v):
            if not v:
                return None
            return fields.Datetime.to_string(v).replace(" ", "T") + "Z"

        def clean(d):
            return {k: v for k, v in d.items() if v is not None}

        return clean({
            "id": self.tmf_id,
            "href": self.href or f"/tmf-api/resourceOrdering/v4/resourceOrder/{self.tmf_id}",
            "category": self.category,
            "description": self.description,
            "name": self.name,
            "orderDate": dt(self.orderDate),
            "priority": self.priority,
            "requestedStartDate": dt(self.requestedStartDate),
            "requestedCompletionDate": dt(self.requestedCompletionDate),
            "expectedCompletionDate": dt(self.expectedCompletionDate),
            "startDate": dt(self.startDate),
            "completionDate": dt(self.completionDate),
            "cancellationDate": dt(self.cancellationDate),
            "cancellationReason": self.cancellationReason,
            "orderType": self.orderType,
            "state": self.state,
            "orderItem": [
                clean({
                    "id": i.item_id,
                    "action": i.action,
                    "quantity": i.quantity,
                    # Ensure a string is always present:
                    "state": i.state or "acknowledged",
                    "appointment": clean({
                        "id": i.appointment_id,
                        "href": i.appointment_href,
                        "description": i.appointment_description,
                    }) if (i.appointment_id or i.appointment_href or i.appointment_description) else None,
                })
                for i in self.order_item_ids
            ],
        })

    def _notify(self, action, payloads=None):
        hub = self.env["tmf.hub.subscription"].sudo()
        event_map = {
            "create": "ResourceOrderCreateEvent",
            "update": "ResourceOrderAttributeValueChangeEvent",
            "delete": "ResourceOrderDeleteEvent",
        }
        event_name = event_map.get(action)
        if not event_name:
            return
        if payloads is None:
            payloads = [rec.to_tmf_json() for rec in self]
        for payload in payloads:
            try:
                hub._notify_subscribers("resourceOrder", event_name, payload)
            except Exception:
                continue


    # Identifiers
    tmf_id = fields.Char(default=lambda self: uuid.uuid4().hex, required=True, index=True)
    href = fields.Char()

    # Business fields
    category = fields.Char()
    description = fields.Text()
    name = fields.Char()
    orderType = fields.Char()
    priority = fields.Integer()
    partner_id = fields.Many2one("res.partner", string="Customer", ondelete="set null")
    project_task_id = fields.Many2one("project.task", string="Fulfillment Task", ondelete="set null")
    picking_id = fields.Many2one("stock.picking", string="Stock Picking", ondelete="set null")

    # Dates
    orderDate = fields.Datetime()
    startDate = fields.Datetime()
    requestedStartDate = fields.Datetime()
    requestedCompletionDate = fields.Datetime()
    expectedCompletionDate = fields.Datetime()
    completionDate = fields.Datetime()

    # Cancellation
    cancellationDate = fields.Datetime()
    cancellationReason = fields.Char()

    # State
    state = fields.Selection(
        selection=[
            ("acknowledged", "acknowledged"),
            ("inProgress", "inProgress"),
            ("pending", "pending"),
            ("held", "held"),
            ("assessingCancellation", "assessingCancellation"),
            ("pendingCancellation", "pendingCancellation"),
            ("cancelled", "cancelled"),
            ("rejected", "rejected"),
            ("partial", "partial"),
            ("failed", "failed"),
            ("completed", "completed"),
        ]
    )

    # Collections
    external_reference_ids = fields.One2many("tmf.external.reference", "resource_order_id", string="externalReference")
    note_ids = fields.One2many("tmf.note", "resource_order_id", string="note")
    related_party_ids = fields.One2many("tmf.related.party", "resource_order_id", string="relatedParty")
    order_item_ids = fields.One2many("tmf.resource.order.item", "resource_order_id", string="orderItem", required=True)


    # -------------------------
    # TMF helper methods
    # -------------------------
    def _get_tmf_api_base(self):
        return "/tmf-api/resourceOrdering/v4"

    def _compute_href(self):
        for rec in self:
            rec.href = f"{rec._get_tmf_api_base()}/resourceOrder/{rec.tmf_id}"

    def _resolve_partner_from_related_party(self):
        self.ensure_one()
        Partner = self.env["res.partner"].sudo()
        for rp in self.related_party_ids:
            pid = rp.tmf_party_id
            if not pid:
                continue
            partner = Partner.search([("tmf_id", "=", str(pid))], limit=1)
            if not partner and str(pid).isdigit():
                partner = Partner.browse(int(pid))
            if partner and partner.exists():
                return partner
        return self.env["res.partner"]

    def _sync_fulfillment_records(self):
        Task = self.env["project.task"].sudo()
        Project = self.env["project.project"].sudo()
        Picking = self.env["stock.picking"].sudo()
        PickingType = self.env["stock.picking.type"].sudo()

        for rec in self:
            partner = rec.partner_id
            if not partner:
                partner = rec._resolve_partner_from_related_party()
                if partner and partner.exists():
                    rec.partner_id = partner.id

            # Project Task
            project = Project.search([], limit=1)
            task_vals = {
                "name": rec.name or rec.description or f"TMF ResourceOrder {rec.tmf_id}",
                "description": rec.description or "",
                "partner_id": partner.id if partner and partner.exists() else False,
                "date_deadline": _safe_date(rec.requestedCompletionDate),
            }
            if project:
                task_vals["project_id"] = project.id
            if rec.project_task_id and rec.project_task_id.exists():
                rec.project_task_id.write(task_vals)
            else:
                rec.project_task_id = Task.create(task_vals).id

            # Stock Picking
            picking_type = PickingType.search([("code", "=", "outgoing")], limit=1) or PickingType.search([], limit=1)
            if not picking_type:
                continue
            pick_vals = {
                "partner_id": partner.id if partner and partner.exists() else False,
                "origin": rec.tmf_id,
                "scheduled_date": rec.requestedStartDate or False,
                "note": rec.description or "",
                "picking_type_id": picking_type.id,
                "location_id": picking_type.default_location_src_id.id,
                "location_dest_id": picking_type.default_location_dest_id.id,
            }
            if rec.picking_id and rec.picking_id.exists():
                rec.picking_id.write(pick_vals)
            else:
                rec.picking_id = Picking.create(pick_vals).id

    @api.model_create_multi
    def create(self, vals_list):
        """
        TMF652 POST preconditions (defense-in-depth):
        - order must NOT have: state, cancellationDate, cancellationReason, completionDate, orderDate
        - orderItem must NOT have: state
        - orderItem is mandatory
        """
        forbidden_on_post = {"cancellationDate", "cancellationReason", "completionDate"}

        for vals in vals_list:
            bad = forbidden_on_post.intersection(vals.keys())
            if bad:
                raise ValidationError(
                    _("TMF652 POST: these fields must not be provided on create: %s") % ", ".join(sorted(bad))
                )

            if not vals.get("order_item_ids"):
                raise ValidationError(_("TMF652 POST: 'orderItem' is mandatory."))

            for cmd in (vals.get("order_item_ids") or []):
                # (0, 0, values) = create child
                if isinstance(cmd, (list, tuple)) and len(cmd) >= 3 and cmd[0] == 0:
                    item_vals = cmd[2] or {}
                    if item_vals.get("state"):
                        raise ValidationError(_("TMF652 POST: orderItem.state must not be provided on create."))
                    if not item_vals.get("item_id"):
                        raise ValidationError(_("TMF652 POST: orderItem.id (item_id) is mandatory."))
                    if not item_vals.get("action"):
                        raise ValidationError(_("TMF652 POST: orderItem.action is mandatory."))
                    if any(item_vals.get(k) for k in ("appointment_href", "appointment_description")) and not item_vals.get("appointment_id"):
                        raise ValidationError(_("TMF652 POST: appointment.id is mandatory when appointment is provided."))

        recs = super().create(vals_list)
        recs._compute_href()
        try:
            recs._sync_fulfillment_records()
        except Exception:
            # Fulfillment sync should never break TMF API create flow.
            pass
        recs._notify("create")
        return recs

    def write(self, vals):
        res = super().write(vals)
        try:
            self._sync_fulfillment_records()
        except Exception:
            pass
        self._notify("update")
        return res

    def unlink(self):
        payloads = [rec.to_tmf_json() for rec in self]
        res = super().unlink()
        self._notify("delete", payloads=payloads)
        return res

    @api.constrains("external_reference_ids", "note_ids", "related_party_ids", "order_item_ids")
    def _check_tmf_additional_rules(self):
        for rec in self:
            for ext in rec.external_reference_ids:
                if not ext.name:
                    raise ValidationError(_("TMF652: externalReference.name is mandatory."))

            for note in rec.note_ids:
                if not note.text:
                    raise ValidationError(_("TMF652: note.text is mandatory."))
                if not note.tmf_note_id:
                    raise ValidationError(_("TMF652: note.id is mandatory."))

            for rp in rec.related_party_ids:
                if not rp.tmf_party_id:
                    raise ValidationError(_("TMF652: relatedParty.id is mandatory."))
                if not rp.referredType:
                    raise ValidationError(_("TMF652: relatedParty.@referredType is mandatory."))
                if not rp.role:
                    raise ValidationError(_("TMF652: relatedParty.role is mandatory when relatedParty.id is provided."))

            if not rec.order_item_ids:
                raise ValidationError(_("TMF652: orderItem is mandatory."))
