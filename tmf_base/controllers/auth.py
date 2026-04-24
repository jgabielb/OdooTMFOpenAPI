# tmf_base/controllers/auth.py
"""
TMF API Key authentication helper.

Usage in any TMF controller route method::

    from odoo.addons.tmf_base.controllers.auth import check_api_key

    def my_route(self, **kw):
        denied = check_api_key()
        if denied:
            return denied
        ...

Auth is opt-in: it is only enforced when the ir.config_parameter
``tmf.api.auth.enabled`` is set to ``True`` (case-insensitive).
Existing deployments are therefore unaffected until the parameter is flipped.
"""

import json
import logging

from odoo.http import request

_logger = logging.getLogger(__name__)

_UNAUTHORIZED_BODY = json.dumps(
    {"code": "401", "reason": "Unauthorized", "message": "Invalid or missing API key"},
    ensure_ascii=False,
)
_UNAUTHORIZED_HEADERS = [("Content-Type", "application/json")]


def _make_401():
    return request.make_response(
        _UNAUTHORIZED_BODY,
        status=401,
        headers=_UNAUTHORIZED_HEADERS,
    )


def check_api_key():
    """Return a 401 response if auth is enabled and no valid API key is present.

    Returns ``None`` when auth passes (either disabled or key is valid).
    Returns an HTTP response object with status 401 when the check fails.

    Typical usage::

        denied = check_api_key()
        if denied:
            return denied
    """
    # Check whether auth is enabled for this installation.
    enabled = (
        request.env["ir.config_parameter"]
        .sudo()
        .get_param("tmf.api.auth.enabled", "False")
    )
    if enabled.strip().lower() != "true":
        return None

    # Extract the key from the X-API-Key header or ?api_key= query parameter.
    http_req = request.httprequest
    api_key = (
        http_req.headers.get("X-API-Key", "").strip()
        or http_req.args.get("api_key", "").strip()
    )

    if not api_key:
        _logger.warning("TMF auth: request with no API key from %s %s", http_req.method, http_req.path)
        return _make_401()

    # Look up the key in the database.
    key_rec = (
        request.env["tmf.api.key"]
        .sudo()
        .search([("key", "=", api_key), ("is_active", "=", True)], limit=1)
    )

    if not key_rec:
        _logger.warning(
            "TMF auth: invalid API key for %s %s (key prefix: %s...)",
            http_req.method,
            http_req.path,
            api_key[:8] if len(api_key) >= 8 else api_key,
        )
        return _make_401()

    return None
