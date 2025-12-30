from odoo import models, fields, api
import json

class TMFModel(models.Model):
    _name = 'tmf.service.problem'
    _description = 'ServiceProblem'
    _inherit = ['tmf.model.mixin']

    affected_number_of_services = fields.Integer(string="affectedNumberOfServices", help="Number of affected services")
    category = fields.Char(string="category", help="Classifier for the problem. Settable. For example, this is used for distinguish the category of prob")
    creation_date = fields.Datetime(string="creationDate", help="Time the problem was created")
    description = fields.Char(string="description", help="Free form text describing the Service Problem")
    impact_importance_factor = fields.Char(string="impactImportanceFactor", help="Impact Importance is characterized by an Impact Importance Factor: overall importance of the impact ")
    last_update = fields.Datetime(string="lastUpdate", help="Time the problem was last changed")
    name = fields.Char(string="name", help="Name of the Service Problem")
    originating_system = fields.Char(string="originatingSystem", help="Indicates where the problem was generated")
    priority = fields.Integer(string="priority", help="An indication varying from 1 (highest) to 10 (lowest) of how important it is for the service provide")
    problem_escalation = fields.Char(string="problemEscalation", help="Indicates if this service problem has been escalated or not. Possible values are 0 to 10. A value of")
    reason = fields.Char(string="reason", help="Free text or optionally structured text. It can be Unknown.")
    resolution_date = fields.Datetime(string="resolutionDate", help="Time the problem was resolved")
    status_change_date = fields.Datetime(string="statusChangeDate", help="Time the problem was last status changed")
    status_change_reason = fields.Char(string="statusChangeReason", help="The reason of state change")
    affected_location = fields.Char(string="affectedLocation", help="A list of the locations affected by the problem. At least one of affectedResource, affectedService o")
    affected_resource = fields.Char(string="affectedResource", help="A list of the resources affected by the problem. At least one of affectedResource, affectedService o")
    affected_service = fields.Char(string="affectedService", help="List of affected services. At least one of affectedResource, affectedService or affectedLocation sho")
    characteristic = fields.Char(string="characteristic", help="")
    external_identifier = fields.Char(string="externalIdentifier", help="")
    first_alert = fields.Char(string="firstAlert", help="Indicates what first alerted the system to the problem. It is not the root cause of the Service Prob")
    impact_pattern = fields.Char(string="impactPattern", help="Define the patterns of impact (optional)- e.g. other service characteristics- Used when defining imp")
    note = fields.Char(string="note", help="A list of comments or notes made on the problem")
    originator_party = fields.Char(string="originatorParty", help="Individual or organization that created the problem")
    parent_problem = fields.Char(string="parentProblem", help="The parent problem to which this problem is attached.")
    related_entity = fields.Char(string="relatedEntity", help="List of entities associated with this problem")
    related_event = fields.Char(string="relatedEvent", help="List of events associated to this problem")
    related_party = fields.Char(string="relatedParty", help="List of parties or party roles playing a role within the service problem")
    responsible_party = fields.Char(string="responsibleParty", help="Individual or organization responsible for handling this problem")
    root_cause_resource = fields.Char(string="rootCauseResource", help="Resource(s) that are associated to the underlying service problems that are the Root Cause of this o")
    root_cause_service = fields.Char(string="rootCauseService", help="Service(s) that are associated to the underlying service problems that are the Root Cause of this on")
    sla_violation = fields.Char(string="slaViolation", help="A List of SLA violations associated with this problem.")
    status = fields.Char(string="status", help="")
    tracking_record = fields.Char(string="trackingRecord", help="List of tracking records that allow the tracking of modifications on the problem.The tracking record")
    trouble_ticket = fields.Char(string="troubleTicket", help="A list of trouble tickets associated with this problem.")
    underlying_alarm = fields.Char(string="underlyingAlarm", help="A list of alarms underlying this problem.")
    underlying_problem = fields.Char(string="underlyingProblem", help="A list of underlying problems. Relevant only if this problem is derived from other problems.")

    def _get_tmf_api_path(self):
        return "/service_problemManagement/v4/ServiceProblem"

    def to_tmf_json(self):
        self.ensure_one()
        return {
            "id": self.tmf_id,
            "href": self.href,
            "@type": "ServiceProblem",
            "affectedNumberOfServices": self.affected_number_of_services,
            "category": self.category,
            "creationDate": self.creation_date.isoformat() if self.creation_date else None,
            "description": self.description,
            "impactImportanceFactor": self.impact_importance_factor,
            "lastUpdate": self.last_update.isoformat() if self.last_update else None,
            "name": self.name,
            "originatingSystem": self.originating_system,
            "priority": self.priority,
            "problemEscalation": self.problem_escalation,
            "reason": self.reason,
            "resolutionDate": self.resolution_date.isoformat() if self.resolution_date else None,
            "statusChangeDate": self.status_change_date.isoformat() if self.status_change_date else None,
            "statusChangeReason": self.status_change_reason,
            "affectedLocation": self.affected_location,
            "affectedResource": self.affected_resource,
            "affectedService": self.affected_service,
            "characteristic": self.characteristic,
            "externalIdentifier": self.external_identifier,
            "firstAlert": self.first_alert,
            "impactPattern": self.impact_pattern,
            "note": self.note,
            "originatorParty": self.originator_party,
            "parentProblem": self.parent_problem,
            "relatedEntity": self.related_entity,
            "relatedEvent": self.related_event,
            "relatedParty": self.related_party,
            "responsibleParty": self.responsible_party,
            "rootCauseResource": self.root_cause_resource,
            "rootCauseService": self.root_cause_service,
            "slaViolation": self.sla_violation,
            "status": self.status,
            "trackingRecord": self.tracking_record,
            "troubleTicket": self.trouble_ticket,
            "underlyingAlarm": self.underlying_alarm,
            "underlyingProblem": self.underlying_problem,

        }

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        for rec in recs:
            self._notify('serviceProblem', 'create', rec)
        return recs

    def write(self, vals):
        res = super().write(vals)
        for rec in self:
            self._notify('serviceProblem', 'update', rec)
        return res

    def unlink(self):
        payloads = [r.to_tmf_json() for r in self]
        res = super().unlink()
        for resource in payloads:
            try:
                self.env['tmf.hub.subscription']._notify_subscribers(
                    api_name='serviceProblem',
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
