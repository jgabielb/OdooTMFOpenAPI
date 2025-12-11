import json
import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


def tmf_response(payload, status=200):
    body = json.dumps(payload)
    return request.make_response(
        body,
        headers=[("Content-Type", "application/json")],
        status=status,
    )


class TmfCustomerController(http.Controller):
    """
    TMF629-like Customer Management API

    Base paths:
      /tmf-api/customerManagement/v4/customer
      /tmf-api/customerManagement/v4/hub
    """

    # -------------------------------------------------------------------------
    # LIST / SEARCH
    # -------------------------------------------------------------------------
    @http.route(
        "/tmf-api/customerManagement/v4/customer",
        auth="public",
        type="http",
        methods=["GET"],
        csrf=False,
    )
    def list_customers(self, **kwargs):
        env = request.env["tmf.customer"].sudo()

        domain = []
        status = request.httprequest.args.get("status")
        external_id = request.httprequest.args.get("externalId")

        if status:
            domain.append(("status", "=", status))
        if external_id:
            domain.append(("external_id", "=", external_id))

        customers = env.search(domain)
        data = [c._tmf_to_dict() for c in customers]
        return tmf_response(data, status=200)

    # -------------------------------------------------------------------------
    # RETRIEVE (by TMF ID / external_id)
    # -------------------------------------------------------------------------
    @http.route(
        "/tmf-api/customerManagement/v4/customer/<string:customer_id>",
        auth="public",
        type="http",
        methods=["GET"],
        csrf=False,
    )
    def get_customer(self, customer_id, **kwargs):
        env = request.env["tmf.customer"].sudo()
        customer = env.search([("external_id", "=", customer_id)], limit=1)

        if not customer:
            return tmf_response(
                {"code": 404, "reason": "Customer not found"},
                status=404,
            )

        return tmf_response(customer._tmf_to_dict(), status=200)

    # -------------------------------------------------------------------------
    # CREATE
    # -------------------------------------------------------------------------
    @http.route(
        "/tmf-api/customerManagement/v4/customer",
        auth="public",
        type="http",  # usamos http y leemos JSON desde httprequest
        methods=["POST"],
        csrf=False,
    )
    def create_customer(self, **kwargs):
        payload = None

        try:
            # Werkzeug Request.get_json (Odoo >= 16)
            payload = request.httprequest.get_json(silent=True)
        except Exception:
            payload = None

        if payload is None:
            raw = request.httprequest.data
            try:
                payload = json.loads(raw) if raw else {}
            except Exception:
                payload = {}

        env = request.env["tmf.customer"].sudo()

        try:
            customer = env.tmf_create_from_payload(payload)
        except Exception as e:
            _logger.exception("Error creating TMF Customer")
            return tmf_response(
                {"code": 500, "reason": "Error creating Customer", "message": str(e)},
                status=500,
            )

        return tmf_response(customer._tmf_to_dict(), status=201)

    # -------------------------------------------------------------------------
    # PATCH / UPDATE (by TMF ID / external_id)
    # -------------------------------------------------------------------------
    @http.route(
        "/tmf-api/customerManagement/v4/customer/<string:customer_id>",
        auth="public",
        type="http",
        methods=["PATCH"],
        csrf=False,
    )
    def patch_customer(self, customer_id, **kwargs):
        payload = None

        try:
            payload = request.httprequest.get_json(silent=True)
        except Exception:
            payload = None

        if payload is None:
            raw = request.httprequest.data
            try:
                payload = json.loads(raw) if raw else {}
            except Exception:
                payload = {}

        env = request.env["tmf.customer"].sudo()
        customer = env.search([("external_id", "=", customer_id)], limit=1)

        if not customer:
            return tmf_response(
                {"code": 404, "reason": "Customer not found"},
                status=404,
            )

        try:
            customer.tmf_update_from_payload(payload)
        except Exception as e:
            _logger.exception("Error updating TMF Customer")
            return tmf_response(
                {"code": 500, "reason": "Error updating Customer", "message": str(e)},
                status=500,
            )

        return tmf_response(customer._tmf_to_dict(), status=200)

    # -------------------------------------------------------------------------
    # DELETE (by TMF ID / external_id)
    # -------------------------------------------------------------------------
    @http.route(
        "/tmf-api/customerManagement/v4/customer/<string:customer_id>",
        auth="public",
        type="http",
        methods=["DELETE"],
        csrf=False,
    )
    def delete_customer(self, customer_id, **kwargs):
        env = request.env["tmf.customer"].sudo()
        customer = env.search([("external_id", "=", customer_id)], limit=1)

        if not customer:
            return tmf_response(
                {"code": 404, "reason": "Customer not found"},
                status=404,
            )

        try:
            customer.unlink()
        except Exception as e:
            _logger.exception("Error deleting TMF Customer")
            return tmf_response(
                {
                    "code": 500,
                    "reason": "Error deleting Customer",
                    "message": str(e),
                },
                status=500,
            )

        # 204 No Content
        return tmf_response({}, status=204)

    # -------------------------------------------------------------------------
    # HUB: create subscription
    # -------------------------------------------------------------------------
    @http.route(
        "/tmf-api/customerManagement/v4/hub",
        auth="public",
        type="http",
        methods=["POST"],
        csrf=False,
    )
    def create_hub_subscription(self, **kwargs):
        """
        POST /tmf-api/customerManagement/v4/hub

        Body:
        {
          "callback": "https://listener.example.com/tmf/customerListener",
          "query": "eventType=CustomerCreateEvent"
        }
        """
        payload = None

        try:
            payload = request.httprequest.get_json(silent=True)
        except Exception:
            payload = None

        if payload is None:
            raw = request.httprequest.data
            try:
                payload = json.loads(raw) if raw else {}
            except Exception:
                payload = {}

        callback = payload.get("callback")
        query = payload.get("query")

        if not callback:
            return tmf_response(
                {
                    "code": 400,
                    "reason": "Missing 'callback' in subscription payload",
                },
                status=400,
            )

        subscription = request.env["tmf.customer.subscription"].sudo().create(
            {
                "callback": callback,
                "query": query or "",
            }
        )

        return tmf_response(subscription.to_tmf_dict(), status=201)

    # -------------------------------------------------------------------------
    # HUB: list subscriptions
    # -------------------------------------------------------------------------
    @http.route(
        "/tmf-api/customerManagement/v4/hub",
        auth="public",
        type="http",
        methods=["GET"],
        csrf=False,
    )
    def list_hub_subscriptions(self, **kwargs):
        subs = request.env["tmf.customer.subscription"].sudo().search([])
        data = [s.to_tmf_dict() for s in subs]
        return tmf_response(data, status=200)

    # -------------------------------------------------------------------------
    # HUB: get subscription
    # -------------------------------------------------------------------------
    @http.route(
        "/tmf-api/customerManagement/v4/hub/<int:sub_id>",
        auth="public",
        type="http",
        methods=["GET"],
        csrf=False,
    )
    def get_hub_subscription(self, sub_id, **kwargs):
        sub = request.env["tmf.customer.subscription"].sudo().browse(sub_id)
        if not sub.exists():
            return tmf_response(
                {"code": 404, "reason": "Subscription not found"},
                status=404,
            )
        return tmf_response(sub.to_tmf_dict(), status=200)

    # -------------------------------------------------------------------------
    # HUB: delete subscription
    # -------------------------------------------------------------------------
    @http.route(
        "/tmf-api/customerManagement/v4/hub/<int:sub_id>",
        auth="public",
        type="http",
        methods=["DELETE"],
        csrf=False,
    )
    def delete_hub_subscription(self, sub_id, **kwargs):
        sub = request.env["tmf.customer.subscription"].sudo().browse(sub_id)
        if not sub.exists():
            return tmf_response(
                {"code": 404, "reason": "Subscription not found"},
                status=404,
            )

        try:
            sub.unlink()
        except Exception as e:
            _logger.exception("Error deleting Customer hub subscription")
            return tmf_response(
                {
                    "code": 500,
                    "reason": "Error deleting subscription",
                    "message": str(e),
                },
                status=500,
            )

        return tmf_response({}, status=204)
