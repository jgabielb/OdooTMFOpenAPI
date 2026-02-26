from odoo import models, fields, api
import json
import logging

_logger = logging.getLogger(__name__)

class TMFModel(models.Model):
    _name = 'tmf.service.level.objective'
    _description = 'ServiceLevelObjective'
    _inherit = ['tmf.model.mixin']

    conformance_comparator = fields.Char(string="conformanceComparator", help="An operator that specifies whether a Service Level Objective is violated above or below the conform")
    conformance_target = fields.Char(string="conformanceTarget", help="A value used to determine if Service Level Objective is met. The data type should be adjusted case ")
    grace_times = fields.Char(string="graceTimes", help="The number of times an objective can remain un-updated without a violation of a Service Level Agree")
    name = fields.Char(string="name", help="The name of the service level objectives.")
    threshold_target = fields.Char(string="thresholdTarget", help="A value that used to specify when a warning should be used that indicates an objective is danger of")
    tolerance_target = fields.Char(string="toleranceTarget", help="A value that specifies the allowable variation of a conformance Target. The data type should be adj")
    conformance_period = fields.Char(string="conformancePeriod", help="An interval of time during which the Conformance Target must be measured.")
    service_level_objective_consequence = fields.Char(string="serviceLevelObjectiveConsequence", help="A list of consequences for this objective.")
    service_level_objective_parameter = fields.Char(string="serviceLevelObjectiveParameter", help="A parameter for this objective")
    tolerance_period = fields.Char(string="tolerancePeriod", help="A value that specifies the allowable time variation of a conformance")
    valid_for = fields.Char(string="validFor", help="A valid duration of a thing.")
    helpdesk_sla_id = fields.Many2one("helpdesk.sla", string="Helpdesk SLA", copy=False, index=True)

    def _get_tmf_api_path(self):
        return "/service_level_objectiveManagement/v4/ServiceLevelObjective"

    def to_tmf_json(self):
        self.ensure_one()
        payload = {
            "id": self.tmf_id,
            "href": self.href,
            "@type": "ServiceLevelObjective",
            "conformanceComparator": self.conformance_comparator,
            "conformanceTarget": self.conformance_target,
            "graceTimes": self.grace_times,
            "name": self.name,
            "thresholdTarget": self.threshold_target,
            "toleranceTarget": self.tolerance_target,
            "conformancePeriod": self.conformance_period,
            "serviceLevelObjectiveConsequence": self.service_level_objective_consequence,
            "serviceLevelObjectiveParameter": self.service_level_objective_parameter,
            "tolerancePeriod": self.tolerance_period,
            "validFor": self.valid_for,

        }
        return self._tmf_normalize_payload(payload)

    def _parse_hours(self):
        self.ensure_one()
        raw = (self.conformance_target or "").strip()
        if not raw:
            return None
        try:
            return float(raw)
        except Exception:
            return None

    def _sync_helpdesk_sla(self):
        Sla = self.env["helpdesk.sla"].sudo().with_context(skip_tmf_slo_sync=True)
        Team = self.env["helpdesk.team"].sudo().with_context(skip_tmf_slo_sync=True)
        for rec in self:
            team = Team.search([], limit=1)
            if not team:
                continue

            vals = {"name": rec.name or f"TMF SLO {rec.tmf_id}"}
            if "team_id" in Sla._fields:
                vals["team_id"] = team.id
            if "description" in Sla._fields:
                vals["description"] = rec.service_level_objective_parameter or rec.service_level_objective_consequence or ""

            hours = rec._parse_hours()
            if hours is not None:
                for key in ("time", "target_time", "time_hours"):
                    if key in Sla._fields:
                        vals[key] = hours
                        break

            if rec.helpdesk_sla_id:
                rec.helpdesk_sla_id.write(vals)
                continue

            try:
                sla = Sla.create(vals)
                rec.with_context(skip_tmf_slo_sync=True).write({"helpdesk_sla_id": sla.id})
            except Exception:
                _logger.exception("TMF623 failed to create helpdesk.sla link for tmf_id=%s", rec.tmf_id)

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        if not self.env.context.get("skip_tmf_slo_sync"):
            recs._sync_helpdesk_sla()
        for rec in recs:
            self._notify('serviceLevelObjective', 'create', rec)
        return recs

    def write(self, vals):
        res = super().write(vals)
        if not self.env.context.get("skip_tmf_slo_sync"):
            self._sync_helpdesk_sla()
        for rec in self:
            self._notify('serviceLevelObjective', 'update', rec)
        return res

    def unlink(self):
        payloads = [r.to_tmf_json() for r in self]
        res = super().unlink()
        for resource in payloads:
            try:
                self.env['tmf.hub.subscription']._notify_subscribers(
                    api_name='serviceLevelObjective',
                    event_type='delete',
                    resource_json=resource,
                )
            except Exception:
                pass
        return res

    def _notify(self, api_name, action, record):
        try:
            self.env['tmf.hub.subscription']._notify_subscribers(
                api_name=api_name,
                event_type=action,
                resource_json=record.to_tmf_json(),
            )
        except Exception:
            pass
