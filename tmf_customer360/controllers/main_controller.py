# -*- coding: utf-8 -*-
"""TMF717 Customer360 — live aggregation controller.

Customer360 is a **read-only** view that assembles data from across
Odoo / TMF models for a given customer (res.partner).  No records are
stored in ``tmf.customer360``; every GET builds the payload on the fly.
"""
import json
import logging

from odoo import http
from odoo.http import request

from odoo.addons.tmf_base.controllers.base_controller import TMFBaseController

_logger = logging.getLogger(__name__)

API_BASE = "/tmf-api/customer360/v4"


def _safe_tmf(rec):
    """Call to_tmf_json() and return dict, or None on failure."""
    try:
        return rec.to_tmf_json()
    except Exception:
        return None


def _ref(rec, role=None):
    """Build a lightweight TMF reference from an Odoo record."""
    d = {"id": str(getattr(rec, "tmf_id", rec.id)), "href": getattr(rec, "href", "")}
    name = getattr(rec, "name", None) or getattr(rec, "display_name", "")
    if name:
        d["name"] = name
    if role:
        d["role"] = role
    return d


def _model_exists(model_name):
    """Check if a model is installed in this Odoo instance."""
    return model_name in request.env


class TMFCustomer360Controller(TMFBaseController):

    # ------------------------------------------------------------------
    # Aggregation logic
    # ------------------------------------------------------------------

    def _build_customer360(self, partner):
        """Build a full TMF717 Customer360 payload for a res.partner."""
        pid = partner.id
        env = request.env

        # -- Engaged party --
        engaged_party = {
            "id": str(partner.tmf_id or partner.id),
            "href": partner.href if hasattr(partner, "href") else "",
            "name": partner.name,
            "@referredType": "Organization" if partner.is_company else "Individual",
        }

        # -- Accounts --
        accounts = []
        if _model_exists("tmf.account"):
            for rec in env["tmf.account"].sudo().search([("partner_id", "=", pid)], limit=50):
                accounts.append(_ref(rec))

        # -- Agreements --
        agreements = []
        if _model_exists("tmf.agreement"):
            for rec in env["tmf.agreement"].sudo().search([("partner_id", "=", pid)], limit=50):
                agreements.append(_ref(rec))

        # -- Appointments --
        appointments = []
        if _model_exists("tmf.appointment"):
            for rec in env["tmf.appointment"].sudo().search([("partner_id", "=", pid)], limit=50):
                appointments.append(_ref(rec))

        # -- Contact medium (from partner) --
        contact_medium = []
        if partner.email:
            contact_medium.append({
                "mediumType": "email",
                "preferred": True,
                "characteristic": {"emailAddress": partner.email},
            })
        if partner.phone:
            contact_medium.append({
                "mediumType": "phone",
                "characteristic": {"phoneNumber": partner.phone},
            })
        if hasattr(partner, "mobile") and partner.mobile:
            contact_medium.append({
                "mediumType": "mobile",
                "characteristic": {"phoneNumber": partner.mobile},
            })

        # -- Customer bills --
        customer_bills = []
        if _model_exists("account.move"):
            invoices = env["account.move"].sudo().search([
                ("partner_id", "=", pid),
                ("move_type", "in", ("out_invoice", "out_refund")),
            ], limit=50, order="invoice_date desc")
            for inv in invoices:
                customer_bills.append({
                    "id": str(inv.id),
                    "href": "",
                    "billNo": inv.name or "",
                    "state": inv.state,
                    "amountDue": {"value": inv.amount_residual, "unit": inv.currency_id.name},
                })

        # -- Payments --
        payments = []
        if _model_exists("tmf.payment"):
            for rec in env["tmf.payment"].sudo().search([("partner_id", "=", pid)], limit=50):
                payments.append(_ref(rec))

        # -- Product orders (sale.order) --
        product_orders = []
        if _model_exists("sale.order"):
            orders = env["sale.order"].sudo().search([("partner_id", "=", pid)], limit=50, order="date_order desc")
            for so in orders:
                product_orders.append({
                    "id": str(getattr(so, "tmf_id", so.id)),
                    "href": "",
                    "name": so.name,
                    "state": so.state,
                })

        # -- Trouble tickets --
        trouble_tickets = []
        if _model_exists("tmf.trouble.ticket"):
            for rec in env["tmf.trouble.ticket"].sudo().search([("partner_id", "=", pid)], limit=50):
                trouble_tickets.append(_ref(rec))

        # -- Quotes --
        quotes = []
        if _model_exists("tmf.quote"):
            for rec in env["tmf.quote"].sudo().search([("partner_id", "=", pid)], limit=50):
                quotes.append(_ref(rec))

        # -- Promotions (not partner-linked, skip or include all active) --

        # -- Interactions --
        interactions = []
        if _model_exists("tmf.party.interaction"):
            for rec in env["tmf.party.interaction"].sudo().search([("partner_id", "=", pid)], limit=50):
                interactions.append(_ref(rec))

        # -- Build payload --
        payload = {
            "id": str(partner.tmf_id or partner.id),
            "href": f"{API_BASE}/customer360/{partner.tmf_id or partner.id}",
            "@type": "Customer360",
            "name": partner.name,
            "status": "approved",
            "engagedParty": engaged_party,
            "relatedParty": [{"id": str(partner.tmf_id or partner.id), "name": partner.name, "role": "Customer"}],
        }

        # Only include non-empty arrays
        if accounts:
            payload["account"] = accounts
        if agreements:
            payload["agreement"] = agreements
        if appointments:
            payload["appointment"] = appointments
        if contact_medium:
            payload["contactMedium"] = contact_medium
        if customer_bills:
            payload["customerBill"] = customer_bills
        if payments:
            payload["paymentMethod"] = payments
        if product_orders:
            payload["productOrder"] = product_orders
        if trouble_tickets:
            payload["troubleTicket"] = trouble_tickets
        if quotes:
            payload["quote"] = quotes
        if interactions:
            payload["interactionItem"] = interactions

        return payload

    def _find_partner(self, rid):
        """Find partner by tmf_id or numeric id."""
        Partner = request.env["res.partner"].sudo()
        partner = Partner.search([("tmf_id", "=", rid)], limit=1)
        if not partner and str(rid).isdigit():
            partner = Partner.browse(int(rid))
            if not partner.exists():
                partner = Partner
        return partner

    # ------------------------------------------------------------------
    # Routes
    # ------------------------------------------------------------------

    @http.route(f"{API_BASE}/customer360", type="http", auth="public", methods=["GET"], csrf=False)
    def customer360_list(self, **kw):
        """GET /customer360 — list all partners as Customer360 views."""
        Partner = request.env["res.partner"].sudo()
        limit = min(int(kw.get("limit", 20)), 100)
        offset = int(kw.get("offset", 0))

        domain = [("tmf_id", "!=", False)]

        # Optional filter by name
        name = kw.get("name")
        if name:
            domain.append(("name", "ilike", name))

        total = Partner.search_count(domain)
        partners = Partner.search(domain, limit=limit, offset=offset, order="id asc")

        results = []
        for p in partners:
            results.append(self._build_customer360(p))

        headers = [
            ("X-Total-Count", str(total)),
            ("X-Result-Count", str(len(results))),
        ]
        return self._json(results, headers=headers)

    @http.route(f"{API_BASE}/customer360/<string:rid>", type="http", auth="public", methods=["GET"], csrf=False)
    def customer360_detail(self, rid, **kw):
        """GET /customer360/{id} — single customer 360 view."""
        partner = self._find_partner(rid)
        if not partner:
            return self._error(404, "Not Found", f"Customer {rid} not found")
        payload = self._build_customer360(partner)
        return self._json(self._select_fields(payload, kw.get("fields")))

    # ------------------------------------------------------------------
    # Hub (keep for TMF event subscription)
    # ------------------------------------------------------------------

    @http.route(f"{API_BASE}/hub", type="http", auth="public", methods=["GET", "POST"], csrf=False)
    def hub(self, **_kw):
        if request.httprequest.method == "GET":
            subs = request.env["tmf.hub.subscription"].sudo().search([("callback", "!=", False)])
            return self._json([{"id": str(s.id), "callback": s.callback, "query": s.query or ""} for s in subs])
        data = self._parse_json_body()
        callback = (data or {}).get("callback")
        if not callback:
            return self._error(400, "Bad Request", "Missing mandatory attribute: callback")
        rec = request.env["tmf.hub.subscription"].sudo().create({
            "name": f"tmf_customer360-{callback}",
            "api_name": "customer360",
            "callback": callback,
            "query": data.get("query", ""),
            "event_type": data.get("eventType") or "any",
            "content_type": "application/json",
        })
        return self._json({"id": str(rec.id), "callback": rec.callback, "query": rec.query or ""}, status=201)

    @http.route(f"{API_BASE}/hub/<string:sid>", type="http", auth="public", methods=["GET", "DELETE"], csrf=False)
    def hub_detail(self, sid, **_kw):
        if not str(sid).isdigit():
            return self._error(404, "Not Found", f"Hub subscription {sid} not found")
        rec = request.env["tmf.hub.subscription"].sudo().browse(int(sid))
        if not rec.exists():
            return self._error(404, "Not Found", f"Hub subscription {sid} not found")
        if request.httprequest.method == "DELETE":
            rec.unlink()
            return request.make_response("", status=204)
        return self._json({"id": str(rec.id), "callback": rec.callback, "query": rec.query or ""})
