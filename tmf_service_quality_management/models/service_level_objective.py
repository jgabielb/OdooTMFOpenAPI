# -*- coding: utf-8 -*-
import json
from odoo import models, fields, api


class TMFServiceLevelObjective(models.Model):
    _name = "tmf.service.level.objective"
    _description = "TMF657 ServiceLevelObjective"
    _rec_name = "name"

    # TMF identifiers
    tmf_id = fields.Char(string="id", required=True, index=True)   # <-- was id
    href = fields.Char()
    name = fields.Char()

    conformance_comparator = fields.Char(string="conformanceComparator", required=True)
    conformance_target = fields.Char(string="conformanceTarget", required=True)

    conformance_period_json = fields.Text(string="conformancePeriod")  # TimePeriod as JSON
    grace_times = fields.Char(string="graceTimes")
    threshold_target = fields.Char(string="thresholdTarget")
    tolerance_target = fields.Char(string="toleranceTarget")
    tolerance_period_json = fields.Text(string="tolerancePeriod")      # TimePeriod as JSON
    valid_for_json = fields.Text(string="validFor")                    # TimePeriod as JSON

    service_level_objective_parameter_json = fields.Text(string="serviceLevelObjectiveParameter", required=True)
    service_level_objective_consequence_json = fields.Text(string="serviceLevelObjectiveConsequence")

    raw_json = fields.Text(string="raw payload (json)")

    _sql_constraints = [
        ("tmf_slo_id_unique", "unique(tmf_id)", "ServiceLevelObjective id must be unique."),
    ]

    def _notify(self, action, payloads=None):
        hub = self.env["tmf.hub.subscription"].sudo()
        event_map = {
            "create": "ServiceLevelObjectiveCreateEvent",
            "update": "ServiceLevelObjectiveAttributeValueChangeEvent",
            "delete": "ServiceLevelObjectiveDeleteEvent",
        }
        if payloads is None:
            payloads = [rec.to_tmf_dict() for rec in self]
        event_name = event_map.get(action)
        if not event_name:
            return
        for payload in payloads:
            try:
                hub._notify_subscribers("serviceLevelObjective", event_name, payload)
            except Exception:
                continue


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

            "conformanceComparator": self.conformance_comparator,
            "conformanceTarget": self.conformance_target,
            "graceTimes": self.grace_times,
            "thresholdTarget": self.threshold_target,
            "toleranceTarget": self.tolerance_target,

            "conformancePeriod": self._loads(self.conformance_period_json),
            "tolerancePeriod": self._loads(self.tolerance_period_json),
            "validFor": self._loads(self.valid_for_json),

            "serviceLevelObjectiveParameter": self._loads(self.service_level_objective_parameter_json),
            "serviceLevelObjectiveConsequence": self._loads(self.service_level_objective_consequence_json),
        }
        return {k: v for k, v in out.items() if v is not None}

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        recs._notify("create")
        return recs

    def write(self, vals):
        res = super().write(vals)
        self._notify("update")
        return res

    def unlink(self):
        payloads = [rec.to_tmf_dict() for rec in self]
        res = super().unlink()
        self._notify("delete", payloads=payloads)
        return res

