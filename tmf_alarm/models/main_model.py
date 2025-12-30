from odoo import models, fields, api
import json

class TMFModel(models.Model):
    _name = 'tmf.alarm'
    _description = 'Alarm'
    _inherit = ['tmf.model.mixin']

    ack_state = fields.Char(string="ackState", help="Provides the Acknowledgement State of the alarm (unacknowledged | acknowledged).")
    ack_system_id = fields.Char(string="ackSystemId", help="Provides the name of the system that last changed the ackState of an alarm, i.e. acknowledged or una")
    ack_user_id = fields.Char(string="ackUserId", help="Provides the id of the user who has last changed the ack state of the alarm, i.e. acknowledged or un")
    alarm_changed_time = fields.Datetime(string="alarmChangedTime", help="Indicates the last date and time when the alarm is changed on the alarm-owning system. Any change to")
    alarm_cleared_time = fields.Datetime(string="alarmClearedTime", help="Indicates the time (as a date + time) at which the alarm is cleared at the source. ")
    alarm_details = fields.Char(string="alarmDetails", help="Contains further information on the alarm.")
    alarm_escalation = fields.Boolean(string="alarmEscalation", help="Indicates if this alarm has been escalated or not. ")
    alarm_raised_time = fields.Datetime(string="alarmRaisedTime", help="Indicates the time (as a date + time) at which the alarm occurred at its source.")
    alarm_reporting_time = fields.Datetime(string="alarmReportingTime", help="Indicates the time (as a date + time) at which the alarm was reported by the owning OSS. It might be")
    alarmed_object_type = fields.Char(string="alarmedObjectType", help="The type (class) of the managed object associated with the event.")
    clear_system_id = fields.Char(string="clearSystemId", help="Provides the id of the system where the user who invoked the alarmCleared operation is located. ")
    clear_user_id = fields.Char(string="clearUserId", help="Provides the id of the user who invoked the alarmCleared operation")
    external_alarm_id = fields.Char(string="externalAlarmId", help="An identifier of the alarm in the source system.")
    is_root_cause = fields.Boolean(string="isRootCause", help="Indicates whether the alarm is a root cause alarm.. ")
    planned_outage_indicator = fields.Char(string="plannedOutageIndicator", help="Indicates that the Managed Object (related to this alarm) is in planned outage (in planned maintenan")
    probable_cause = fields.Char(string="probableCause", help="Provides the probable cause of the alarm. The values are consistent with ITU-T Recommendation X.733 ")
    proposed_repaired_actions = fields.Char(string="proposedRepairedActions", help="Indicates proposed repair actions, if known to the system emitting the alarm.")
    reporting_system_id = fields.Char(string="reportingSystemId", help="Reporting system identity.")
    service_affecting = fields.Boolean(string="serviceAffecting", help="Indicates whether the alarm affects service or not.")
    source_system_id = fields.Char(string="sourceSystemId", help="Source system identity.")
    specific_problem = fields.Char(string="specificProblem", help="Provides more specific information about the alarm.")
    state = fields.Char(string="state", help="Defines the alarm state during its life cycle (raised | updated | cleared).")
    affected_service = fields.Char(string="affectedService", help="")
    alarm_type = fields.Char(string="alarmType", help="")
    alarmed_object = fields.Char(string="alarmedObject", help="")
    comment = fields.Char(string="comment", help="")
    correlated_alarm = fields.Char(string="correlatedAlarm", help="")
    crossed_threshold_information = fields.Char(string="crossedThresholdInformation", help="")
    parent_alarm = fields.Char(string="parentAlarm", help="")
    perceived_severity = fields.Char(string="perceivedSeverity", help="")
    place = fields.Char(string="place", help="")

    def _get_tmf_api_path(self):
        return "/alarmManagement/v4/Alarm"

    def to_tmf_json(self):
        self.ensure_one()
        return {
            "id": self.tmf_id,
            "href": self.href,
            "@type": "Alarm",
            "ackState": self.ack_state,
            "ackSystemId": self.ack_system_id,
            "ackUserId": self.ack_user_id,
            "alarmChangedTime": self.alarm_changed_time.isoformat() if self.alarm_changed_time else None,
            "alarmClearedTime": self.alarm_cleared_time.isoformat() if self.alarm_cleared_time else None,
            "alarmDetails": self.alarm_details,
            "alarmEscalation": self.alarm_escalation,
            "alarmRaisedTime": self.alarm_raised_time.isoformat() if self.alarm_raised_time else None,
            "alarmReportingTime": self.alarm_reporting_time.isoformat() if self.alarm_reporting_time else None,
            "alarmedObjectType": self.alarmed_object_type,
            "clearSystemId": self.clear_system_id,
            "clearUserId": self.clear_user_id,
            "externalAlarmId": self.external_alarm_id,
            "isRootCause": self.is_root_cause,
            "plannedOutageIndicator": self.planned_outage_indicator,
            "probableCause": self.probable_cause,
            "proposedRepairedActions": self.proposed_repaired_actions,
            "reportingSystemId": self.reporting_system_id,
            "serviceAffecting": self.service_affecting,
            "sourceSystemId": self.source_system_id,
            "specificProblem": self.specific_problem,
            "state": self.state,
            "affectedService": self.affected_service,
            "alarmType": self.alarm_type,
            "alarmedObject": self.alarmed_object,
            "comment": self.comment,
            "correlatedAlarm": self.correlated_alarm,
            "crossedThresholdInformation": self.crossed_threshold_information,
            "parentAlarm": self.parent_alarm,
            "perceivedSeverity": self.perceived_severity,
            "place": self.place,

        }

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        for rec in recs:
            self._notify('alarm', 'create', rec)
        return recs

    def write(self, vals):
        res = super().write(vals)
        for rec in self:
            self._notify('alarm', 'update', rec)
        return res

    def unlink(self):
        payloads = [r.to_tmf_json() for r in self]
        res = super().unlink()
        for resource in payloads:
            try:
                self.env['tmf.hub.subscription']._notify_subscribers(
                    api_name='alarm',
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
