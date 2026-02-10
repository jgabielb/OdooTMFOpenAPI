from odoo import models, fields, api
from odoo.exceptions import ValidationError


def _drop_nones(d):
    return {k: v for k, v in (d or {}).items() if v is not None}


def _clean_meta(payload, base_type, schema_location):
    # Only include when they are real non-empty strings
    if isinstance(base_type, str) and base_type.strip():
        payload["@baseType"] = base_type
    if isinstance(schema_location, str) and schema_location.strip():
        payload["@schemaLocation"] = schema_location
    return payload


class TmfShoppingCart(models.Model):
    _name = "tmf.shopping.cart"
    _description = "TMF663 ShoppingCart"
    _inherit = ["tmf.model.mixin"]

    tmf_type = fields.Char(string="@type", default="ShoppingCart")
    tmf_base_type = fields.Char(string="@baseType")
    tmf_schema_location = fields.Char(string="@schemaLocation")

    creation_date = fields.Datetime(string="creationDate", readonly=True, default=fields.Datetime.now)
    last_update = fields.Datetime(string="lastUpdate", readonly=True)

    valid_for_start = fields.Datetime(string="validFor.startDateTime")
    valid_for_end = fields.Datetime(string="validFor.endDateTime")

    cart_item_ids = fields.One2many("tmf.shopping.cart.item", "cart_id", string="cartItem")
    cart_total_price_ids = fields.One2many("tmf.shopping.cart.price", "cart_id", string="cartTotalPrice")
    contact_medium_ids = fields.One2many("tmf.contact.medium", "shopping_cart_id", string="contactMedium")
    related_party_ids = fields.One2many("tmf.related.party", "shopping_cart_id", string="relatedParty")

    def _notify(self, api_name, action, record):
        try:
            self.env["tmf.hub.subscription"].sudo()._notify_subscribers(
                api_name=api_name,
                event_type=action,
                resource_json=record.to_tmf_json(),
            )
        except Exception:
            pass

    @api.model_create_multi
    def create(self, vals_list):
        now = fields.Datetime.now()
        for vals in vals_list:
            vals.setdefault("last_update", now)

        recs = super().create(vals_list)

        for rec in recs:
            try:
                rec._notify("shoppingCart", "create", rec)
            except Exception:
                pass
        return recs

    def write(self, vals):
        vals = dict(vals or {})
        vals.setdefault("last_update", fields.Datetime.now())

        res = super().write(vals)

        for rec in self:
            try:
                rec._notify("shoppingCart", "attributeValueChange", rec)
            except Exception:
                pass
        return res

    def _get_tmf_api_path(self):
        return "/tmf-api/shoppingCartManagement/v5/shoppingCart"

    def to_tmf_json(self):
        self.ensure_one()

        payload = {
            "id": self.tmf_id,
            "href": self.href,
            "@type": "ShoppingCart",
            "creationDate": self.creation_date.isoformat() if self.creation_date else None,
            "lastUpdate": self.last_update.isoformat() if self.last_update else None,
            "cartItem": [ci.to_tmf_json() for ci in self.cart_item_ids],
            "cartTotalPrice": [p.to_tmf_json() for p in self.cart_total_price_ids],
            "contactMedium": [cm.to_tmf_json() for cm in self.contact_medium_ids],
            "relatedParty": [rp.to_tmf_json() for rp in self.related_party_ids],
        }

        # validFor only when any value exists
        vf = {
            "startDateTime": self.valid_for_start.isoformat() if self.valid_for_start else None,
            "endDateTime": self.valid_for_end.isoformat() if self.valid_for_end else None,
        }
        vf = _drop_nones(vf)
        if vf:
            payload["validFor"] = vf

        payload = _drop_nones(payload)
        payload = _clean_meta(payload, self.tmf_base_type, self.tmf_schema_location)
        return payload

    def validate_tmf_create(self, payload: dict):
        if not payload.get("@type"):
            payload["@type"] = "ShoppingCart"

        if payload["@type"] != "ShoppingCart":
            raise ValidationError("TMF663: @type must be 'ShoppingCart'.")

        if "cartItem" in payload and not isinstance(payload["cartItem"], list):
            raise ValidationError("TMF663: cartItem must be an array when provided.")


class TmfCartItem(models.Model):
    _name = "tmf.shopping.cart.item"
    _description = "TMF663 CartItem"

    cart_id = fields.Many2one("tmf.shopping.cart", required=True, ondelete="cascade")
    item_id = fields.Char(string="id", required=True)
    tmf_type = fields.Char(string="@type", default="CartItem")

    action = fields.Selection(
        selection=[("add", "add"), ("modify", "modify"), ("delete", "delete"), ("noChange", "noChange")],
        string="action",
        required=True
    )
    quantity = fields.Integer(default=1)
    status = fields.Selection(
        selection=[("active", "active"), ("savedForLater", "savedForLater")],
        string="status",
        default="active"
    )

    note_ids = fields.One2many("tmf.note", "cart_item_id", string="note")
    item_price_ids = fields.One2many("tmf.shopping.cart.price", "cart_item_id", string="itemPrice")
    item_total_price_ids = fields.One2many("tmf.shopping.cart.price", "cart_item_total_id", string="itemTotalPrice")

    product_offering_id = fields.Many2one("tmf.product.offering.ref", string="productOffering")
    product_id = fields.Many2one("tmf.product.ref.or.value", string="product")

    def to_tmf_json(self):
        self.ensure_one()

        payload = {
            "id": self.item_id,
            "@type": self.tmf_type or "CartItem",
            "action": self.action,
            "quantity": self.quantity,
            "status": self.status,
            "note": [n.to_tmf_json() for n in self.note_ids],
            "itemPrice": [p.to_tmf_json() for p in self.item_price_ids],
            "itemTotalPrice": [p.to_tmf_json() for p in self.item_total_price_ids],
        }

        if self.product_offering_id:
            payload["productOffering"] = self.product_offering_id.to_tmf_json()

        if self.product_id:
            # MUST be an object if included
            payload["product"] = self.product_id.to_tmf_json()

        return _drop_nones(payload)


class TmfShoppingCartPrice(models.Model):
    _name = "tmf.shopping.cart.price"
    _description = "TMF663 CartPrice"

    cart_id = fields.Many2one("tmf.shopping.cart", string="Shopping Cart", ondelete="cascade")
    cart_item_id = fields.Many2one("tmf.shopping.cart.item", string="Cart Item", ondelete="cascade")
    cart_item_total_id = fields.Many2one("tmf.shopping.cart.item", string="Cart Item (Total Price)", ondelete="cascade")

    tmf_type = fields.Char(string="@type", default="CartPrice")
    tmf_base_type = fields.Char(string="@baseType")
    tmf_schema_location = fields.Char(string="@schemaLocation")

    name = fields.Char()
    description = fields.Char()
    price_type = fields.Char(string="priceType")
    recurring_charge_period = fields.Char(string="recurringChargePeriod")
    unit_of_measure = fields.Char(string="unitOfMeasure")

    price_amount = fields.Float(string="price.amount")
    price_currency = fields.Char(string="price.currency")

    def to_tmf_json(self):
        self.ensure_one()
        payload = {
            "name": self.name,
            "description": self.description,
            "priceType": self.price_type,
            "recurringChargePeriod": self.recurring_charge_period,
            "unitOfMeasure": self.unit_of_measure,
            "@type": self.tmf_type or "CartPrice",
            "price": {
                "amount": self.price_amount,
                "currency": self.price_currency,
            },
        }
        payload = _drop_nones(payload)
        payload = _clean_meta(payload, self.tmf_base_type, self.tmf_schema_location)
        return payload


class TmfContactMedium(models.Model):
    _name = "tmf.contact.medium"
    _description = "TMF ContactMedium"

    shopping_cart_id = fields.Many2one("tmf.shopping.cart", string="Shopping Cart", ondelete="cascade")

    tmf_type = fields.Char(string="@type", default="ContactMedium")
    tmf_base_type = fields.Char(string="@baseType")
    tmf_schema_location = fields.Char(string="@schemaLocation")

    tmf_id = fields.Char(string="id")
    contact_type = fields.Char(string="contactType")
    preferred = fields.Boolean(string="preferred")
    valid_for_start = fields.Datetime(string="validFor.startDateTime")
    valid_for_end = fields.Datetime(string="validFor.endDateTime")

    medium_type = fields.Char(string="medium.@type")
    email_address = fields.Char(string="emailAddress")
    phone_number = fields.Char(string="phoneNumber")

    def to_tmf_json(self):
        self.ensure_one()

        payload = {
            "@type": self.tmf_type or "ContactMedium",
            "id": self.tmf_id,
            "contactType": self.contact_type,
            "preferred": self.preferred,
        }

        vf = {
            "startDateTime": self.valid_for_start.isoformat() if self.valid_for_start else None,
            "endDateTime": self.valid_for_end.isoformat() if self.valid_for_end else None,
        }
        vf = _drop_nones(vf)
        if vf:
            payload["validFor"] = vf

        if self.email_address:
            payload["emailAddress"] = self.email_address
        if self.phone_number:
            payload["phoneNumber"] = self.phone_number

        payload = _drop_nones(payload)
        payload = _clean_meta(payload, self.tmf_base_type, self.tmf_schema_location)
        return payload


class TmfRelatedParty(models.Model):
    _inherit = "tmf.related.party"
    _description = "TMF RelatedParty"

    shopping_cart_id = fields.Many2one("tmf.shopping.cart", ondelete="cascade")


class TmfNote(models.Model):
    _inherit = "tmf.note"
    _description = "TMF Note"

    cart_item_id = fields.Many2one("tmf.shopping.cart.item", ondelete="cascade")
    shopping_cart_id = fields.Many2one("tmf.shopping.cart", ondelete="cascade")

    def to_tmf_json(self):
        self.ensure_one()
        payload = {
            "id": getattr(self, "tmf_id", None),
            "author": getattr(self, "author", None),
            "date": self.date.isoformat() if getattr(self, "date", None) else None,
            "text": getattr(self, "text", None),
            "@type": getattr(self, "tmf_type", None) or "Note",
        }
        payload = _drop_nones(payload)
        payload = _clean_meta(payload, getattr(self, "tmf_base_type", None), getattr(self, "tmf_schema_location", None))
        return payload


class TmfProductOfferingRef(models.Model):
    _name = "tmf.product.offering.ref"
    _description = "TMF ProductOfferingRef"

    tmf_id = fields.Char(string="id", required=True)
    href = fields.Char()
    name = fields.Char()

    referred_type = fields.Char(string="@referredType", default="ProductOffering")
    tmf_type = fields.Char(string="@type", default="ProductOfferingRef")
    tmf_base_type = fields.Char(string="@baseType")
    tmf_schema_location = fields.Char(string="@schemaLocation")

    def to_tmf_json(self):
        self.ensure_one()
        payload = {
            "id": self.tmf_id,
            "@referredType": self.referred_type,
            "@type": self.tmf_type or "ProductOfferingRef",
        }
        if isinstance(self.href, str) and self.href.strip():
            payload["href"] = self.href
        if isinstance(self.name, str) and self.name.strip():
            payload["name"] = self.name

        payload = _clean_meta(payload, self.tmf_base_type, self.tmf_schema_location)
        return payload



class TmfProductRefOrValue(models.Model):
    _name = "tmf.product.ref.or.value"
    _description = "TMF ProductRefOrValue"

    cart_item_id = fields.Many2one("tmf.shopping.cart.item", string="Cart Item", ondelete="cascade")

    tmf_id = fields.Char(string="id")
    href = fields.Char()
    name = fields.Char()
    referred_type = fields.Char(string="@referredType", default="Product")

    tmf_type = fields.Char(string="@type", default="ProductRefOrValue")
    tmf_base_type = fields.Char(string="@baseType")
    tmf_schema_location = fields.Char(string="@schemaLocation")

    product_json = fields.Text(string="productEmbeddedJson")

    def to_tmf_json(self):
        self.ensure_one()
        payload = {
            "id": self.tmf_id,
            "@referredType": self.referred_type,
            "@type": self.tmf_type or "ProductRefOrValue",
        }

        # only include if string
        if isinstance(self.href, str) and self.href.strip():
            payload["href"] = self.href
        if isinstance(self.name, str) and self.name.strip():
            payload["name"] = self.name

        payload = _clean_meta(payload, self.tmf_base_type, self.tmf_schema_location)
        return payload

