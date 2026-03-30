# tmf_base/models/tmf_mixin.py
import re
import uuid
from datetime import date, datetime, timezone
from odoo import models, fields, api

class TMFModelMixin(models.AbstractModel):
    """
    Abstract Class to provide TMF compliance to any Odoo model.
    Implements:
    - Universal ID (UUID)
    - HREF generation
    - Common TMF timestamps
    """
    _name = 'tmf.model.mixin'
    _description = 'TM Forum Common Attributes'

    # 1. TMF ID (String/UUID) - The bridge to external systems
    tmf_id = fields.Char(
        string="TMF ID",
        default=lambda self: str(uuid.uuid4()),
        required=True,
        index=True,
        readonly=True,
        copy=False,
        help="Unique identifier used in TMF API calls."
    )

    # 2. HREF - Self-referencing URL required by TMF
    href = fields.Char(
        string="Resource URL",
        compute="_compute_href",
        help="API reference URL"
    )

    # 3. Polymorphism (Optional but recommended)
    # TMF uses @type to distinguish objects (e.g., Individual vs Organization)
    tmf_type = fields.Char(string="TMF Type", compute="_compute_tmf_type")

    @api.depends('tmf_id')
    def _compute_href(self):
        """
        Generates the API URL.
        Logic: base_url + api_path + tmf_id
        """
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        for record in self:
            api_path = record._get_tmf_api_path()
            if api_path and record.tmf_id:
                normalized_path = api_path if str(api_path).startswith("/tmf-api") else f"/tmf-api{api_path}"
                record.href = f"{base_url}{normalized_path}/{record.tmf_id}"
            else:
                record.href = False

    def _compute_tmf_type(self):
        """
        Default implementation. Can be overridden by child models.
        """
        for record in self:
            record.tmf_type = record._name

    def _tmf_base_url(self):
        return (self.env["ir.config_parameter"].sudo().get_param("web.base.url") or "").rstrip("/")

    def _tmf_iso_datetime(self, value):
        if value is None:
            return None
        if isinstance(value, str):
            s = value.strip()
            if not s:
                return None
            if s.endswith("Z"):
                s = s[:-1] + "+00:00"
            try:
                value = datetime.fromisoformat(s)
            except Exception:
                parsed = fields.Datetime.to_datetime(s)
                if not parsed:
                    return value
                value = parsed
        if isinstance(value, date) and not isinstance(value, datetime):
            value = datetime.combine(value, datetime.min.time())
        if not isinstance(value, datetime):
            return value
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        else:
            value = value.astimezone(timezone.utc)
        return value.replace(microsecond=0).isoformat().replace("+00:00", "Z")

    def _tmf_iso_date(self, value):
        if value is None:
            return None
        if isinstance(value, str):
            s = value.strip()
            if not s:
                return None
            parsed = fields.Date.to_date(s)
            return parsed.isoformat() if parsed else value
        if isinstance(value, datetime):
            return value.date().isoformat()
        if isinstance(value, date):
            return value.isoformat()
        return value

    def _tmf_normalize_dates(self, value, key=None):
        if isinstance(value, dict):
            return {k: self._tmf_normalize_dates(v, k) for k, v in value.items()}
        if isinstance(value, list):
            return [self._tmf_normalize_dates(v, key) for v in value]
        if isinstance(value, tuple):
            return [self._tmf_normalize_dates(v, key) for v in value]
        if isinstance(value, (datetime, date)):
            if key and self._TMF_DATE_KEY_RE.search(str(key)):
                if "time" in str(key).lower() or "timestamp" in str(key).lower():
                    return self._tmf_iso_datetime(value)
                return self._tmf_iso_datetime(value)
            return self._tmf_iso_datetime(value)
        if isinstance(value, str) and key and self._TMF_DATE_KEY_RE.search(str(key)):
            key_l = str(key).lower()
            if "date" in key_l and "time" not in key_l and "timestamp" not in key_l:
                return self._tmf_iso_date(value)
            return self._tmf_iso_datetime(value)
        return value

    def _tmf_normalize_payload(self, payload):
        if not isinstance(payload, dict):
            return payload
        normalized = self._tmf_normalize_dates(payload)
        rec = self[:1]
        if rec:
            if rec.tmf_id:
                normalized["id"] = str(rec.tmf_id)
            href_value = normalized.get("href") or rec.href or rec.tmf_href
            if isinstance(href_value, str) and href_value:
                if href_value.startswith("/"):
                    base = rec._tmf_base_url()
                    normalized["href"] = f"{base}{href_value}" if base else href_value
                else:
                    normalized["href"] = href_value
        return normalized

    @api.model
    def _get_tmf_api_path(self):
        """
        Placeholder. Child models MUST override this.
        Example return: '/party/v4/individual'
        """
        return ""
    
    @property
    def tmf_href(self):
        """Default href builder using api path + tmf_id/id."""
        self.ensure_one()
        path = self._get_tmf_api_path() or ""
        if not path:
            return None
        base = path if str(path).startswith("/tmf-api") else "/tmf-api" + path
        return f"{base}/{self.tmf_id or self.id}"
    
    def _register_hook(self):
        # Register the unique constraint on the SQL table
        # We use a raw SQL constraint for mixins or define it on the child model
        pass
    
    # _sql_constraints = [
    #     ('tmf_id_uniq', 'unique (tmf_id)', 'The TMF ID must be unique!')
    # ]
    _TMF_DATE_KEY_RE = re.compile(r"(date|time|timestamp|validfor|start|end|from|to|update|creation)", re.IGNORECASE)
