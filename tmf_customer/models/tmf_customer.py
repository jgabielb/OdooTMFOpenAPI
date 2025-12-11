import logging
import uuid
import requests

from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)


class TmfCustomer(models.Model):
    _name = "tmf.customer"
    _description = "TMF Customer"

    email = fields.Char()
    phone = fields.Char()
    active = fields.Boolean(default=True)

    name = fields.Char(
        string="Customer Name",
        related="partner_id.name",
        store=True,
        readonly=False,
    )

    partner_id = fields.Many2one(
        "res.partner",
        string="Partner",
        required=True,
        ondelete="cascade",
        help="Underlying Odoo partner representing this customer.",
    )

    external_id = fields.Char(
        string="External Customer ID",
        help="Identifier of the customer in an external system (Siebel/BRM/etc.).",
    )

    status = fields.Selection(
        [
            ("prospect", "Prospect"),
            ("active", "Active"),
            ("inactive", "Inactive"),
        ],
        string="Status",
        default="active",
        required=True,
    )

    lifecycle_status = fields.Selection(
        [
            ("created", "Created"),
            ("validated", "Validated"),
            ("active", "Active"),
            ("inactive", "Inactive"),
        ],
        string="Lifecycle Status",
        default="created",
        required=True,
    )

    description = fields.Text(
        string="Description",
        help="Free-text description or notes about the customer.",
    )

    _sql_constraints = [
        (
            "external_id_uniq",
            "unique(external_id)",
            "External customer ID must be unique.",
        )
    ]

    # -------------------------------------------------------------------------
    # Core TMF mapping
    # -------------------------------------------------------------------------

    def _tmf_to_dict(self):
        """Map this record to a TMF629-style Customer representation."""
        self.ensure_one()

        result = {
            "id": str(self.id),
            "href": f"/tmf-api/customerManagement/v4/customer/{self.id}",
            "name": self.name,
            "status": self.status,
            "lifecycleStatus": self.lifecycle_status,
        }

        if self.description:
            result["description"] = self.description

        if self.external_id:
            result["externalId"] = self.external_id

        if self.partner_id:
            result["party"] = {
                "id": str(self.partner_id.id),
                "href": f"/tmf-api/partyManagement/v4/party/{self.partner_id.id}",
                "name": self.partner_id.name,
                "@referredType": (
                    "Individual" if not self.partner_id.is_company else "Organization"
                ),
            }

        return result

    @api.model
    def _tmf_map_data_to_vals(self, data, partial=True, existing=None):
        """
        Map TMF629 Customer JSON payload into Odoo create/write vals.
        - data: dict from API
        - partial: True when PATCH, False when POST
        - existing: record when updating
        """
        vals = {}

        # simple attributes
        if (not partial) or ("name" in data):
            name = data.get("name")
            if name and not existing:
                partner = self.env["res.partner"].sudo().create({"name": name})
                vals["partner_id"] = partner.id
            elif name and existing and existing.partner_id:
                existing.partner_id.sudo().write({"name": name})

        if (not partial) or ("status" in data):
            if "status" in data:
                vals["status"] = data["status"]

        if (not partial) or ("lifecycleStatus" in data):
            if "lifecycleStatus" in data:
                vals["lifecycle_status"] = data["lifecycleStatus"]

        if (not partial) or ("description" in data):
            if "description" in data:
                vals["description"] = data["description"]

        if (not partial) or ("externalId" in data):
            if "externalId" in data:
                vals["external_id"] = data["externalId"]

        # Party / engagedParty mapping
        party_data = data.get("party") or data.get("engagedParty")
        if party_data:
            partner_id = None
            party_id_raw = party_data.get("id")
            if party_id_raw:
                try:
                    partner_id = int(party_id_raw)
                except (TypeError, ValueError):
                    partner_id = None

            if partner_id:
                partner = self.env["res.partner"].sudo().browse(partner_id)
                if partner.exists():
                    vals["partner_id"] = partner.id
            elif data.get("name"):
                partner = self.env["res.partner"].sudo().create(
                    {"name": data.get("name")}
                )
                vals["partner_id"] = partner.id

        # If still no partner_id on create, create a generic one (for POST)
        if not partial and not vals.get("partner_id"):
            display_name = (
                data.get("name")
                or data.get("externalId")
                or _("Unnamed TMF Customer")
            )
            partner = self.env["res.partner"].sudo().create({"name": display_name})
            vals["partner_id"] = partner.id

        return vals

    @api.model
    def tmf_create_from_payload(self, data):
        """Create a customer from TMF payload."""
        vals = self._tmf_map_data_to_vals(data, partial=False, existing=None)

        # IMPORTANT: skip event in create(), send manually after
        record = self.with_context(tmf_skip_event=True).sudo().create(vals)
        record._tmf_send_event("CustomerCreateEvent")
        return record

    def tmf_update_from_payload(self, data):
        """Update a customer from TMF payload (PATCH)."""
        self.ensure_one()
        vals = self._tmf_map_data_to_vals(
            data, partial=True, existing=self.sudo()
        )
        if vals:
            # IMPORTANT: skip event in write(), send manually after
            self.with_context(tmf_skip_event=True).sudo().write(vals)
            self._tmf_send_event("CustomerAttributeValueChangeEvent")
        return self


    # -------------------------------------------------------------------------
    # Hub event publishing (TMF Hub pattern)
    # -------------------------------------------------------------------------

    def _tmf_event_payload(self, event_type, deleted=False):
        self.ensure_one()
        now_str = fields.Datetime.now()
        resource_path = f"/tmf-api/customerManagement/v4/customer/{self.id}"

        if deleted:
            customer_body = {"id": str(self.id)}
        else:
            customer_body = self._tmf_to_dict()

        return {
            "eventId": str(uuid.uuid4()),
            "eventType": event_type,
            "eventTime": now_str,
            "resourcePath": resource_path,
            "event": {
                "customer": customer_body,
            },
        }

    def _tmf_send_event(self, event_type, deleted=False):
        self.ensure_one()
        subscriptions = self.env["tmf.customer.subscription"].sudo().search([])
        if not subscriptions:
            return

        payload = self._tmf_event_payload(event_type, deleted=deleted)

        for sub in subscriptions:
            if not sub.callback:
                continue
            body = {
                "id": str(sub.id),
                "callback": sub.callback,
                "query": sub.query or "",
                "event": payload,
            }
            try:
                requests.post(sub.callback, json=body, timeout=5)
            except Exception as e:
                _logger.warning(
                    "Error sending TMF Customer event %s to %s: %s",
                    event_type,
                    sub.callback,
                    e,
                )

    # -------------------------------------------------------------------------
    # CRUD hooks – fire only if NOT tmf_skip_event
    # -------------------------------------------------------------------------
    @api.model
    def create(self, vals):
        record = super().create(vals)
        if not self.env.context.get("tmf_skip_event"):
            record._tmf_send_event("CustomerCreateEvent")
        return record

    def write(self, vals):
        res = super().write(vals)
        if not self.env.context.get("tmf_skip_event"):
            for rec in self:
                rec._tmf_send_event("CustomerAttributeValueChangeEvent")
        return res

    def unlink(self):
        if not self.env.context.get("tmf_skip_event"):
            for rec in self:
                rec._tmf_send_event("CustomerDeleteEvent", deleted=True)
        return super().unlink()


class TmfCustomerSubscription(models.Model):
    """
    TMF-style hub subscription for Customer events.

    Endpoint:
      POST /tmf-api/customerManagement/v4/hub
    """

    _name = "tmf.customer.subscription"
    _description = "TMF Customer Hub Subscription"

    callback = fields.Char(
        string="Callback URL",
        required=True,
        help="Listener URL where Customer events will be POSTed.",
    )
    query = fields.Char(
        string="Query",
        help="Optional filter/query as per TMF Hub pattern.",
    )
    # Simple enable/disable flag
    active = fields.Boolean(default=True)

    def to_tmf_dict(self):
        self.ensure_one()
        return {
            "id": str(self.id),
            "callback": self.callback,
            "query": self.query or "",
        }
