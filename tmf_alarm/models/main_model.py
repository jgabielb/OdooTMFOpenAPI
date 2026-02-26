# -*- coding: utf-8 -*-
from odoo import models, fields, api
import datetime


ALARM_TYPE = [
    ("communicationsAlarm", "communicationsAlarm"),
    ("processingErrorAlarm", "processingErrorAlarm"),
    ("environmentalAlarm", "environmentalAlarm"),
    ("qualityOfServiceAlarm", "qualityOfServiceAlarm"),
    ("equipmentAlarm", "equipmentAlarm"),
    ("integrityViolation", "integrityViolation"),
    ("operationalViolation", "operationalViolation"),
    ("physicalViolation", "physicalViolation"),
    ("securityService", "securityService"),
    ("mechanismViolation", "mechanismViolation"),
    ("timeDomainViolation", "timeDomainViolation"),
]

PERCEIVED_SEVERITY = [
    ("critical", "critical"),
    ("major", "major"),
    ("minor", "minor"),
    ("warning", "warning"),
    ("indeterminate", "indeterminate"),
    ("cleared", "cleared"),
]

ACK_STATE = [
    ("unacknowledged", "unacknowledged"),
    ("acknowledged", "acknowledged"),
]

PLANNED_OUTAGE = [
    ("InService", "InService"),
    ("OutOfService", "OutOfService"),
]

ALARM_STATE = [
    ("raised", "raised"),
    ("updated", "updated"),
    ("cleared", "cleared"),
]


class TMFAlarm(models.Model):
    _name = "tmf.alarm"
    _description = "TMF642 Alarm"
    _inherit = ["tmf.model.mixin"]

    # ---- Enumerations / mandatory fields ----
    ack_state = fields.Selection(ACK_STATE, string="ackState", default="unacknowledged")
    alarm_type = fields.Selection(ALARM_TYPE, string="alarmType", required=True)
    perceived_severity = fields.Selection(PERCEIVED_SEVERITY, string="perceivedSeverity", required=True)
    planned_outage_indicator = fields.Selection(PLANNED_OUTAGE, string="plannedOutageIndicator")
    state = fields.Selection(ALARM_STATE, string="state", required=True, default="raised")

    probable_cause = fields.Char(string="probableCause", required=True)
    source_system_id = fields.Char(string="sourceSystemId", required=True)
    alarm_raised_time = fields.Datetime(string="alarmRaisedTime", required=True)

    # ---- Other scalar fields ----
    ack_system_id = fields.Char(string="ackSystemId")
    ack_user_id = fields.Char(string="ackUserId")

    alarm_changed_time = fields.Datetime(string="alarmChangedTime")
    alarm_cleared_time = fields.Datetime(string="alarmClearedTime")
    alarm_details = fields.Char(string="alarmDetails")
    alarm_escalation = fields.Boolean(string="alarmEscalation")
    alarm_reporting_time = fields.Datetime(string="alarmReportingTime")

    alarmed_object_type = fields.Char(string="alarmedObjectType")
    clear_system_id = fields.Char(string="clearSystemId")
    clear_user_id = fields.Char(string="clearUserId")
    external_alarm_id = fields.Char(string="externalAlarmId")
    is_root_cause = fields.Boolean(string="isRootCause")
    proposed_repaired_actions = fields.Char(string="proposedRepairedActions")
    reporting_system_id = fields.Char(string="reportingSystemId")
    service_affecting = fields.Boolean(string="serviceAffecting")
    specific_problem = fields.Char(string="specificProblem")

    # ---- Complex fields (store JSON) ----
    affected_service = fields.Json(string="affectedService", default=list)  # [ServiceRef]
    alarmed_object = fields.Json(string="alarmedObject")                    # AlarmedObjectRef
    comment = fields.Json(string="comment", default=list)                   # [Comment]
    correlated_alarm = fields.Json(string="correlatedAlarm", default=list)  # [AlarmRef]
    crossed_threshold_information = fields.Json(string="crossedThresholdInformation")  # CrossedThresholdInformation
    parent_alarm = fields.Json(string="parentAlarm", default=list)          # [AlarmRef]
    place = fields.Json(string="place", default=list)                       # [RelatedPlace]
    helpdesk_ticket_id = fields.Integer(string="Helpdesk Ticket ID")

    # -------------------------
    # TMF helpers
    # -------------------------
    def _get_tmf_api_path(self):
        return "/alarmManagement/v5/alarm"

    def _iso(self, dt):
        """
        Serialize an Odoo datetime (naive UTC or string) to ISO-8601 with Z.
        """
        if not dt:
            return None
        if isinstance(dt, str):
            dt = fields.Datetime.to_datetime(dt)
        if not dt:
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.timezone.utc)
        else:
            dt = dt.astimezone(datetime.timezone.utc)
        return dt.isoformat().replace("+00:00", "Z")

    # -------------------------
    # Serialization
    # -------------------------
    def to_tmf_json(self):
        self.ensure_one()
        rid = self.tmf_id or str(self.id)
        href = self.href or f"{self._get_tmf_api_path()}/{rid}"

        payload = {
            "id": rid,
            "href": href,
            "@type": "Alarm",

            # Mandatory (per TMF642)
            "alarmRaisedTime": self._iso(self.alarm_raised_time),
            "alarmType": self.alarm_type,
            "perceivedSeverity": self.perceived_severity,
            "probableCause": self.probable_cause,
            "sourceSystemId": self.source_system_id,
            "state": self.state,

            # Enums / common
            "ackState": self.ack_state,
        }

        # Optional strings (ONLY include if non-empty string)
        def _add_str(k, v):
            if isinstance(v, str) and v.strip():
                payload[k] = v.strip()

        # Optional booleans (only include when True)
        def _add_bool(k, v):
            if v is True:
                payload[k] = True

        # Optional datetimes (ISO or omit)
        def _add_dt(k, v):
            iso = self._iso(v)
            if iso:
                payload[k] = iso

        _add_str("ackSystemId", self.ack_system_id)
        _add_str("ackUserId", self.ack_user_id)
        _add_dt("alarmChangedTime", self.alarm_changed_time)
        _add_dt("alarmClearedTime", self.alarm_cleared_time)
        _add_str("alarmDetails", self.alarm_details)
        _add_bool("alarmEscalation", self.alarm_escalation)
        _add_dt("alarmReportingTime", self.alarm_reporting_time)
        _add_str("alarmedObjectType", self.alarmed_object_type)
        _add_str("clearSystemId", self.clear_system_id)
        _add_str("clearUserId", self.clear_user_id)
        _add_str("externalAlarmId", self.external_alarm_id)
        _add_bool("isRootCause", self.is_root_cause)
        _add_str("plannedOutageIndicator", self.planned_outage_indicator)
        _add_str("proposedRepairedActions", self.proposed_repaired_actions)
        _add_str("reportingSystemId", self.reporting_system_id)  # <-- fixes "must be string"
        _add_bool("serviceAffecting", self.service_affecting)
        _add_str("specificProblem", self.specific_problem)

        # Complex (arrays/objects) - include only when present and well-typed
        if isinstance(self.affected_service, list) and self.affected_service:
            payload["affectedService"] = self.affected_service
        if isinstance(self.alarmed_object, dict) and self.alarmed_object:
            payload["alarmedObject"] = self.alarmed_object
        if isinstance(self.comment, list) and self.comment:
            payload["comment"] = self.comment
        if isinstance(self.correlated_alarm, list) and self.correlated_alarm:
            payload["correlatedAlarm"] = self.correlated_alarm
        if isinstance(self.crossed_threshold_information, dict) and self.crossed_threshold_information:
            payload["crossedThresholdInformation"] = self.crossed_threshold_information
        if isinstance(self.parent_alarm, list) and self.parent_alarm:
            payload["parentAlarm"] = self.parent_alarm
        if isinstance(self.place, list) and self.place:
            payload["place"] = self.place

        return payload

    def _sync_helpdesk_ticket(self):
        if not self.env.registry.get("helpdesk.ticket") or not self.env.registry.get("helpdesk.team"):
            return
        Ticket = self.env["helpdesk.ticket"].sudo()
        Team = self.env["helpdesk.team"].sudo()
        team = Team.search([], limit=1)
        if not team:
            return
        for rec in self:
            vals = {
                "name": f"TMF Alarm {rec.tmf_id or rec.id}",
                "description": rec.alarm_details or rec.probable_cause or "",
                "team_id": team.id,
            }
            if rec.helpdesk_ticket_id:
                existing = Ticket.browse(rec.helpdesk_ticket_id)
                if existing.exists():
                    existing.write(vals)
                    continue
            rec.helpdesk_ticket_id = Ticket.create(vals).id

    # -------------------------
    # CRUD hooks + notifications
    # -------------------------
    @api.model_create_multi
    def create(self, vals_list):
        now = fields.Datetime.now()
        for vals in vals_list:
            if not vals.get("alarm_reporting_time"):
                vals["alarm_reporting_time"] = vals.get("alarm_raised_time")
            if not vals.get("alarm_changed_time"):
                vals["alarm_changed_time"] = now

        recs = super().create(vals_list)
        recs._sync_helpdesk_ticket()
        for rec in recs:
            rec._notify("alarm", "raise", rec)
        return recs

    def write(self, vals):
        vals = dict(vals or {})
        vals.setdefault("alarm_changed_time", fields.Datetime.now())
        res = super().write(vals)
        self._sync_helpdesk_ticket()

        for rec in self:
            if rec.state == "cleared":
                updates = {}
                if not rec.alarm_cleared_time:
                    updates["alarm_cleared_time"] = fields.Datetime.now()
                if rec.perceived_severity != "cleared":
                    updates["perceived_severity"] = "cleared"
                if updates:
                    super(TMFAlarm, rec).write(updates)

            rec._notify("alarm", "change", rec)
        return res

    def unlink(self):
        payloads = [rec.to_tmf_json() for rec in self]
        res = super().unlink()
        for payload in payloads:
            try:
                self.env["tmf.hub.subscription"]._notify_subscribers(
                    api_name="alarm", event_type="delete", resource_json=payload
                )
            except Exception:
                pass
        return res

    def _notify(self, api_name, action, record):
        try:
            self.env["tmf.hub.subscription"]._notify_subscribers(
                api_name=api_name,
                event_type=action,
                resource_json=record.to_tmf_json(),
            )
        except Exception:
            pass
