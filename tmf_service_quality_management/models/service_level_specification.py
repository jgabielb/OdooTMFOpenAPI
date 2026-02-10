# -*- coding: utf-8 -*-
import json
from odoo import models, fields


class TMFServiceLevelSpecification(models.Model):
    _name = "tmf.service.level.specification"
    _description = "TMF657 ServiceLevelSpecification"
    _rec_name = "name"

    # TMF identifiers
    tmf_id = fields.Char(string="id", required=True, index=True)  # <-- DO NOT use 'id'
    href = fields.Char()
    name = fields.Char(required=True)
    description = fields.Char()

    valid_for_json = fields.Text(string="validFor")  # TimePeriod as JSON

    # list of ServiceLevelObjectiveRef[*] as JSON
    related_service_level_objective_json = fields.Text(string="relatedServiceLevelObjective", required=True)

    raw_json = fields.Text(string="raw payload (json)")

    _sql_constraints = [
        ("tmf_sls_tmf_id_unique", "unique(tmf_id)", "ServiceLevelSpecification id must be unique."),
    ]

    def _loads(self, txt):
        if not txt:
            return None
        try:
            return json.loads(txt)
        except Exception:
            return None

    def to_tmf_dict(self):
        self.ensure_one()
        out = {
            "id": self.tmf_id,
            "href": self.href,
            "name": self.name,
            "description": self.description,
            "validFor": self._loads(self.valid_for_json),
            "relatedServiceLevelObjective": self._loads(self.related_service_level_objective_json),
        }
        return {k: v for k, v in out.items() if v is not None}
