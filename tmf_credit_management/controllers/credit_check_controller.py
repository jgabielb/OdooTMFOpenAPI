"""TMF645 Credit Management — REST controller.

Endpoints:
    POST /tmf-api/creditManagement/v4/creditRatingCheck
    GET  /tmf-api/creditManagement/v4/creditRatingCheck
    GET  /tmf-api/creditManagement/v4/creditRatingCheck/<id>
"""
import logging

from odoo.http import request, route

from odoo.addons.tmf_base.controllers.base_controller import TMFBaseController

_logger = logging.getLogger(__name__)


class CreditCheckController(TMFBaseController):

    BASE = "/tmf-api/creditManagement/v4/creditRatingCheck"

    # ------------------------------------------------------------------
    # POST — submit a new credit rating check
    # ------------------------------------------------------------------
    @route([BASE, BASE + "/"], type="http", auth="public", methods=["POST"], csrf=False)
    def post_credit_rating_check(self, **params):
        try:
            body = self._parse_json_body()
            if not isinstance(body, dict):
                return self._error(400, "InvalidRequest", "Invalid JSON body")

            related = body.get("relatedParty") or []
            if not related:
                return self._error(400, "MissingMandatoryAttribute",
                                   "relatedParty is required")

            party_ref = related[0]
            party_id = str(party_ref.get("id") or "").strip()
            if not party_id:
                return self._error(400, "MissingMandatoryAttribute",
                                   "relatedParty[0].id is required")

            Partner = request.env["res.partner"].sudo()
            partner = Partner.search([("tmf_id", "=", party_id)], limit=1) \
                if "tmf_id" in Partner._fields else Partner
            if not partner and party_id.isdigit():
                partner = Partner.browse(int(party_id))
                if not partner.exists():
                    partner = Partner
            if not partner:
                return self._error(404, "NotFound", f"Party {party_id} not found")

            req_amount = body.get("requestedCreditAmount") or {}
            amount = req_amount.get("value") or 0.0
            unit = req_amount.get("unit") or "USD"

            CRC = request.env["tmf.credit.rating.check"].sudo()
            check = CRC.create({
                "partner_id": partner.id,
                "requested_amount": amount,
                "requested_unit": unit,
                "state": "done",
            })
            outcome = check._evaluate(partner, amount)
            check.write({
                "credit_score": outcome["score"],
                "credit_rating_result": outcome["result"],
            })

            payload = check.to_tmf_json()
            return self._json(payload, status=201,
                              headers=[("Location", payload.get("href"))])
        except Exception as e:
            _logger.exception("TMF645 POST creditRatingCheck failed")
            return self._error(500, "InternalError", str(e))

    # ------------------------------------------------------------------
    # GET — list credit rating checks (filterable by relatedParty.id)
    # ------------------------------------------------------------------
    @route([BASE, BASE + "/"], type="http", auth="public", methods=["GET"], csrf=False)
    def list_credit_rating_check(self, **params):
        domain = []
        related_party_id = params.get("relatedParty.id")
        if related_party_id:
            Partner = request.env["res.partner"].sudo()
            partner = Partner.search([("tmf_id", "=", related_party_id)], limit=1) \
                if "tmf_id" in Partner._fields else Partner
            if not partner and related_party_id.isdigit():
                partner = Partner.browse(int(related_party_id))
            if partner:
                domain.append(("partner_id", "=", partner.id))
            else:
                return self._json([])

        limit, offset = self._paginate_params(params)
        CRC = request.env["tmf.credit.rating.check"].sudo()
        recs = CRC.search(domain, limit=limit, offset=offset, order="create_date desc")
        total = CRC.search_count(domain)
        data = [r.to_tmf_json() for r in recs]
        return self._json(data, headers=[
            ("X-Total-Count", str(total)),
            ("X-Result-Count", str(len(data))),
        ])

    # ------------------------------------------------------------------
    # GET single
    # ------------------------------------------------------------------
    @route([BASE + "/<string:rid>", BASE + "/<string:rid>/"],
           type="http", auth="public", methods=["GET"], csrf=False)
    def get_credit_rating_check(self, rid, **params):
        rid = self._normalize_tmf_id(rid)
        CRC = request.env["tmf.credit.rating.check"].sudo()
        rec = CRC.search([("tmf_id", "=", rid)], limit=1)
        if not rec and rid.isdigit():
            rec = CRC.browse(int(rid))
            if not rec.exists():
                rec = CRC
        if not rec:
            return self._error(404, "NotFound",
                               f"CreditRatingCheck {rid} not found")
        return self._json(rec.to_tmf_json())
