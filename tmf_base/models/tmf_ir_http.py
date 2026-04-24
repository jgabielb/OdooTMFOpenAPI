# tmf_base/models/tmf_ir_http.py
"""
Centralized TMF API authentication via ir.http dispatch override.

When ``tmf.api.auth.enabled`` is ``True``, every request whose path starts
with ``/tmf-api/`` must carry a valid active API key (X-API-Key header or
``api_key`` query parameter).  All other paths are unaffected.

This single override provides authentication for ALL TMF Open API endpoints
from one place, so individual controllers stay clean.
"""
import json
import logging

from odoo import models
from odoo.http import request

_logger = logging.getLogger(__name__)

_UNAUTHORIZED_BODY = json.dumps(
    {"code": "401", "reason": "Unauthorized", "message": "Invalid or missing API key"},
    ensure_ascii=False,
)
_UNAUTHORIZED_HEADERS = [("Content-Type", "application/json")]

TMF_API_PREFIX = "/tmf-api/"


class IrHttp(models.AbstractModel):
    _inherit = "ir.http"

    @classmethod
    def _dispatch(cls, endpoint):
        """Check TMF API key auth before dispatching to any controller endpoint."""
        http_req = request.httprequest

        # Only guard requests whose path begins with /tmf-api/
        if http_req.path.startswith(TMF_API_PREFIX):
            denied = cls._tmf_check_api_key(http_req)
            if denied is not None:
                return denied

        return super()._dispatch(endpoint)

    @classmethod
    def _tmf_check_api_key(cls, http_req):
        """Return a 401 Response if auth is enabled and the key is invalid.

        Returns ``None`` when auth passes (disabled or valid key found).
        """
        try:
            # We need a cursor to hit the database; use sudo to avoid ACL issues.
            enabled = (
                request.env["ir.config_parameter"]
                .sudo()
                .get_param("tmf.api.auth.enabled", "False")
            )
        except Exception:
            # If we can't read the param (e.g. no DB yet) skip auth.
            return None

        if enabled.strip().lower() != "true":
            return None

        # Extract the key from the X-API-Key header or ?api_key= query param.
        api_key = (
            http_req.headers.get("X-API-Key", "").strip()
            or http_req.args.get("api_key", "").strip()
        )

        if not api_key:
            _logger.warning(
                "TMF auth: missing API key for %s %s",
                http_req.method,
                http_req.path,
            )
            return request.make_response(
                _UNAUTHORIZED_BODY, status=401, headers=_UNAUTHORIZED_HEADERS
            )

        try:
            key_rec = (
                request.env["tmf.api.key"]
                .sudo()
                .search([("key", "=", api_key), ("is_active", "=", True)], limit=1)
            )
            key_valid = bool(key_rec)
        except Exception:
            key_valid = False

        if not key_valid:
            _logger.warning(
                "TMF auth: invalid API key for %s %s (prefix: %s...)",
                http_req.method,
                http_req.path,
                api_key[:8] if len(api_key) >= 8 else api_key,
            )
            return request.make_response(
                _UNAUTHORIZED_BODY, status=401, headers=_UNAUTHORIZED_HEADERS
            )

        return None
