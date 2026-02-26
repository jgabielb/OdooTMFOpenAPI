# -*- coding: utf-8 -*-
from odoo import models, fields, api
import json

TMF656_STATUS = [
    ("acknowledged", "acknowledged"),
    ("rejected", "rejected"),
    ("inProgress", "inProgress"),
    ("held", "held"),
    ("pending", "pending"),
    ("resolved", "resolved"),
    ("closed", "closed"),
    ("cancelled", "cancelled"),
]

TMF_TASK_STATE = [
    ("acknowledged", "acknowledged"),
    ("inProgress", "inProgress"),
    ("terminatedWithError", "terminatedWithError"),
    ("done", "done"),
]


# -------------------------
# Shared helpers
# -------------------------
def _json_dumps(v):
    if v is None:
        return None
    if isinstance(v, (dict, list)):
        return json.dumps(v, ensure_ascii=False)
    # accept raw strings (already json) too
    return v


def _json_load(v):
    if not v:
        return None
    if isinstance(v, (dict, list)):
        return v
    try:
        return json.loads(v)
    except Exception:
        return v


def _as_array(v):
    """TMF 0..* fields must serialize as arrays."""
    if v is None:
        return []
    if isinstance(v, list):
        return v
    return [v]


def _as_object(v):
    """TMF 0..1 / 1 fields should serialize as objects (not arrays)."""
    if v is None:
        return None
    if isinstance(v, list):
        return v[0] if v else None
    return v


def _notify_records(records, api_name, event_name, payloads):
    hub = records.env["tmf.hub.subscription"].sudo()
    for payload in payloads:
        try:
            hub._notify_subscribers(api_name, event_name, payload)
        except Exception:
            continue


# ============================================================
# ServiceProblem (TMF656)
# ============================================================
class TMFServiceProblem(models.Model):
    _name = "tmf.service.problem"
    _description = "TMF656 ServiceProblem"
    _inherit = ["tmf.model.mixin"]

    # ---- Mandatory for POST /serviceProblem (TMF656 v5) ----
    category = fields.Char(required=True)
    description = fields.Char(required=True)
    priority = fields.Integer(required=True)
    reason = fields.Char(required=True)

    tmf_type = fields.Char(string="@type", required=True, default="ServiceProblem")
    originator_party_json = fields.Text(string="originatorParty", required=True)  # object

    # ---- Standard fields ----
    affected_number_of_services = fields.Integer(string="affectedNumberOfServices")
    creation_date = fields.Datetime(string="creationDate")
    last_update = fields.Datetime(string="lastUpdate")
    name = fields.Char(string="name")
    originating_system = fields.Char(string="originatingSystem")  # non-patchable
    problem_escalation = fields.Char(string="problemEscalation")
    resolution_date = fields.Datetime(string="resolutionDate")
    status_change_date = fields.Datetime(string="statusChangeDate")
    status_change_reason = fields.Char(string="statusChangeReason")
    impact_importance_factor = fields.Char(string="impactImportanceFactor")

    status = fields.Selection(TMF656_STATUS, string="status", default="acknowledged")

    # ---- Complex (JSON) ----
    affected_location_json = fields.Text(string="affectedLocation")      # 0..*
    affected_resource_json = fields.Text(string="affectedResource")      # 0..*
    affected_service_json = fields.Text(string="affectedService")        # 0..*
    characteristic_json = fields.Text(string="characteristic")           # 0..*
    external_identifier_json = fields.Text(string="externalIdentifier")  # 0..*
    impact_pattern_json = fields.Text(string="impactPattern")            # 0..1
    note_json = fields.Text(string="note")                               # 0..*
    parent_problem_json = fields.Text(string="parentProblem")            # 0..*
    related_entity_json = fields.Text(string="relatedEntity")            # 0..*
    related_event_json = fields.Text(string="relatedEvent")              # 0..*
    related_party_json = fields.Text(string="relatedParty")              # 0..*
    responsible_party_json = fields.Text(string="responsibleParty")      # 0..1
    root_cause_resource_json = fields.Text(string="rootCauseResource")   # 0..*
    root_cause_service_json = fields.Text(string="rootCauseService")     # 0..*
    sla_violation_json = fields.Text(string="slaViolation")              # 0..*
    trouble_ticket_json = fields.Text(string="troubleTicket")            # 0..*
    underlying_alarm_json = fields.Text(string="underlyingAlarm")        # 0..*
    underlying_problem_json = fields.Text(string="underlyingProblem")    # 0..*
    helpdesk_ticket_id = fields.Integer(string="Helpdesk Ticket ID")

    # Non-patchable per TMF rules
    first_alert_json = fields.Text(string="firstAlert")                  # 0..1
    error_message_json = fields.Text(string="errorMessage")              # 0..*
    tracking_record_json = fields.Text(string="trackingRecord")          # 0..*

    def _notify(self, action, payloads=None):
        event_map = {
            "create": "ServiceProblemCreateEvent",
            "update": "ServiceProblemAttributeValueChangeEvent",
            "delete": "ServiceProblemDeleteEvent",
        }
        if payloads is None:
            payloads = [rec.to_tmf_json() for rec in self]
        event_name = event_map.get(action)
        if event_name:
            _notify_records(self, "serviceProblem", event_name, payloads)

    def _resolve_partner_from_related_party(self):
        self.ensure_one()
        Partner = self.env["res.partner"].sudo()
        parties = _as_array(_json_load(self.related_party_json))
        for party in parties:
            if not isinstance(party, dict):
                continue
            pid = party.get("id")
            if not pid:
                continue
            partner = Partner.search([("tmf_id", "=", str(pid))], limit=1)
            if not partner and str(pid).isdigit():
                partner = Partner.browse(int(pid))
            if partner and partner.exists():
                return partner

        originator = _as_object(_json_load(self.originator_party_json))
        if isinstance(originator, dict):
            pid = originator.get("id")
            if pid:
                partner = Partner.search([("tmf_id", "=", str(pid))], limit=1)
                if not partner and str(pid).isdigit():
                    partner = Partner.browse(int(pid))
                if partner and partner.exists():
                    return partner
        return self.env["res.partner"]

    def _sync_helpdesk_ticket(self):
        if not self.env.registry.get("helpdesk.ticket") or not self.env.registry.get("helpdesk.team"):
            return
        Ticket = self.env["helpdesk.ticket"].sudo()
        Team = self.env["helpdesk.team"].sudo()
        team = Team.search([], limit=1)
        if not team:
            return
        for rec in self:
            partner = rec._resolve_partner_from_related_party()
            vals = {
                "name": rec.name or f"TMF ServiceProblem {rec.tmf_id or rec.id}",
                "description": rec.description or rec.reason or "",
                "team_id": team.id,
                "partner_id": partner.id if partner and partner.exists() else False,
            }
            if rec.helpdesk_ticket_id:
                existing = Ticket.browse(rec.helpdesk_ticket_id)
                if existing.exists():
                    existing.write(vals)
                    continue
            rec.helpdesk_ticket_id = Ticket.create(vals).id

    def _get_tmf_api_path(self):
        return "/tmf-api/serviceProblemManagement/v5/serviceProblem"

    def to_tmf_json(self):
        self.ensure_one()

        base = {
            "id": self.tmf_id,
            "href": self.href,
            "@type": self.tmf_type,

            "category": self.category,
            "priority": self.priority,
            "description": self.description,
            "reason": self.reason,
            "status": self.status,
        }

        # only include non-null scalar fields (avoid nulls)
        if self.name:
            base["name"] = self.name
        if self.originating_system:
            base["originatingSystem"] = self.originating_system
        if self.problem_escalation:
            base["problemEscalation"] = self.problem_escalation
        if self.status_change_reason:
            base["statusChangeReason"] = self.status_change_reason
        if self.impact_importance_factor:
            base["impactImportanceFactor"] = self.impact_importance_factor
        if self.affected_number_of_services is not None:
            base["affectedNumberOfServices"] = self.affected_number_of_services

        if self.creation_date:
            base["creationDate"] = self.creation_date.isoformat()
        if self.last_update:
            base["lastUpdate"] = self.last_update.isoformat()
        if self.resolution_date:
            base["resolutionDate"] = self.resolution_date.isoformat()
        if self.status_change_date:
            base["statusChangeDate"] = self.status_change_date.isoformat()

        # Complex fields: enforce array/object cardinalities
        op = _as_object(_json_load(self.originator_party_json))
        if isinstance(op, dict) and "@type" not in op:
            op["@type"] = "RelatedPartyRefOrPartyRoleRef"
        base["originatorParty"] = op

        base["affectedLocation"] = _as_array(_json_load(self.affected_location_json))
        base["affectedResource"] = _as_array(_json_load(self.affected_resource_json))
        base["affectedService"] = _as_array(_json_load(self.affected_service_json))
        base["characteristic"] = _as_array(_json_load(self.characteristic_json))
        base["externalIdentifier"] = _as_array(_json_load(self.external_identifier_json))
        base["note"] = _as_array(_json_load(self.note_json))
        base["parentProblem"] = _as_array(_json_load(self.parent_problem_json))
        base["relatedEntity"] = _as_array(_json_load(self.related_entity_json))
        base["relatedEvent"] = _as_array(_json_load(self.related_event_json))
        base["relatedParty"] = _as_array(_json_load(self.related_party_json))
        base["rootCauseResource"] = _as_array(_json_load(self.root_cause_resource_json))
        base["rootCauseService"] = _as_array(_json_load(self.root_cause_service_json))
        base["slaViolation"] = _as_array(_json_load(self.sla_violation_json))
        base["troubleTicket"] = _as_array(_json_load(self.trouble_ticket_json))
        base["underlyingAlarm"] = _as_array(_json_load(self.underlying_alarm_json))
        base["underlyingProblem"] = _as_array(_json_load(self.underlying_problem_json))
        base["errorMessage"] = _as_array(_json_load(self.error_message_json))
        base["trackingRecord"] = _as_array(_json_load(self.tracking_record_json))

        fa = _as_object(_json_load(self.first_alert_json))
        if isinstance(fa, dict):
            base["firstAlert"] = fa

        rp = _as_object(_json_load(self.responsible_party_json))
        if isinstance(rp, dict):
            base["responsibleParty"] = rp

        ip = _as_object(_json_load(self.impact_pattern_json))
        if isinstance(ip, dict):
            base["impactPattern"] = ip


        return base

    @api.model_create_multi
    def create(self, vals_list):
        now = fields.Datetime.now()
        for vals in vals_list:
            vals.setdefault("creation_date", now)
            vals.setdefault("last_update", now)
            vals.setdefault("status_change_date", now)
            vals.setdefault("tmf_type", "ServiceProblem")
        recs = super().create(vals_list)
        recs._sync_helpdesk_ticket()
        recs._notify("create")
        return recs

    def write(self, vals):
        # keep lastUpdate consistent on any update
        vals = dict(vals or {})
        vals.setdefault("last_update", fields.Datetime.now())
        res = super().write(vals)
        self._sync_helpdesk_ticket()
        self._notify("update")
        return res

    def unlink(self):
        payloads = [rec.to_tmf_json() for rec in self]
        res = super().unlink()
        self._notify("delete", payloads=payloads)
        return res


# ============================================================
# ProblemAcknowledgement (TMF656)
# - problem: 1..*
# - ackProblem: 0..*
# - trackingRecord: 0..1
# - @type mandatory
# ============================================================
class TMFProblemAcknowledgement(models.Model):
    _name = "tmf.problem.acknowledgement"
    _description = "TMF656 ProblemAcknowledgement"
    _inherit = ["tmf.model.mixin"]

    tmf_type = fields.Char(string="@type", required=True, default="ProblemAcknowledgement")
    state = fields.Selection(TMF_TASK_STATE, default="acknowledged")

    problem_json = fields.Text(string="problem", required=True)       # array 1..*
    ack_problem_json = fields.Text(string="ackProblem")               # array 0..*
    tracking_record_json = fields.Text(string="trackingRecord")       # object 0..1

    def _notify(self, action, payloads=None):
        event_map = {
            "create": "ProblemAcknowledgementCreateEvent",
            "update": "ProblemAcknowledgementAttributeValueChangeEvent",
            "delete": "ProblemAcknowledgementDeleteEvent",
        }
        if payloads is None:
            payloads = [rec.to_tmf_json() for rec in self]
        event_name = event_map.get(action)
        if event_name:
            _notify_records(self, "problemAcknowledgement", event_name, payloads)

    def _get_tmf_api_path(self):
        return "/tmf-api/serviceProblemManagement/v5/problemAcknowledgement"

    def to_tmf_json(self):
        self.ensure_one()
        base = {
            "id": self.tmf_id,
            "href": self.href,
            "@type": self.tmf_type,
            "state": self.state,
            "problem": _as_array(_json_load(self.problem_json)),
            "ackProblem": _as_array(_json_load(self.ack_problem_json)),
        }
        tr = _json_load(self.tracking_record_json)
        if tr is not None:
            base["trackingRecord"] = _as_object(tr)
        return base

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
        payloads = [rec.to_tmf_json() for rec in self]
        res = super().unlink()
        self._notify("delete", payloads=payloads)
        return res


# ============================================================
# ProblemUnacknowledgement (TMF656)
# - problem: 1..*
# - unackProblem: 0..*
# - trackingRecord: 0..1
# - @type mandatory
# ============================================================
class TMFProblemUnacknowledgement(models.Model):
    _name = "tmf.problem.unacknowledgement"
    _description = "TMF656 ProblemUnacknowledgement"
    _inherit = ["tmf.model.mixin"]

    tmf_type = fields.Char(string="@type", required=True, default="ProblemUnacknowledgement")
    state = fields.Selection(TMF_TASK_STATE, default="acknowledged")

    problem_json = fields.Text(string="problem", required=True)         # array 1..*
    unack_problem_json = fields.Text(string="unackProblem")             # array 0..*
    tracking_record_json = fields.Text(string="trackingRecord")         # object 0..1

    def _notify(self, action, payloads=None):
        event_map = {
            "create": "ProblemUnacknowledgementCreateEvent",
            "update": "ProblemUnacknowledgementAttributeValueChangeEvent",
            "delete": "ProblemUnacknowledgementDeleteEvent",
        }
        if payloads is None:
            payloads = [rec.to_tmf_json() for rec in self]
        event_name = event_map.get(action)
        if event_name:
            _notify_records(self, "problemUnacknowledgement", event_name, payloads)

    def _get_tmf_api_path(self):
        return "/tmf-api/serviceProblemManagement/v5/problemUnacknowledgement"

    def to_tmf_json(self):
        self.ensure_one()
        base = {
            "id": self.tmf_id,
            "href": self.href,
            "@type": self.tmf_type,
            "state": self.state,
            "problem": _as_array(_json_load(self.problem_json)),
            "unackProblem": _as_array(_json_load(self.unack_problem_json)),
        }
        tr = _json_load(self.tracking_record_json)
        if tr is not None:
            base["trackingRecord"] = _as_object(tr)
        return base

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
        payloads = [rec.to_tmf_json() for rec in self]
        res = super().unlink()
        self._notify("delete", payloads=payloads)
        return res


# ============================================================
# ProblemGroup (TMF656)
# - childProblem: 1..* (array)
# - parentProblem: 1 (object)
# - @type mandatory
# ============================================================
class TMFProblemGroup(models.Model):
    _name = "tmf.problem.group"
    _description = "TMF656 ProblemGroup"
    _inherit = ["tmf.model.mixin"]

    tmf_type = fields.Char(string="@type", required=True, default="ProblemGroup")
    state = fields.Selection(TMF_TASK_STATE, default="acknowledged")

    child_problem_json = fields.Text(string="childProblem", required=True)  # array 1..*
    parent_problem_json = fields.Text(string="parentProblem", required=True)  # object 1

    def _notify(self, action, payloads=None):
        event_map = {
            "create": "ProblemGroupCreateEvent",
            "update": "ProblemGroupAttributeValueChangeEvent",
            "delete": "ProblemGroupDeleteEvent",
        }
        if payloads is None:
            payloads = [rec.to_tmf_json() for rec in self]
        event_name = event_map.get(action)
        if event_name:
            _notify_records(self, "problemGroup", event_name, payloads)

    def _get_tmf_api_path(self):
        return "/tmf-api/serviceProblemManagement/v5/problemGroup"

    def to_tmf_json(self):
        self.ensure_one()
        return {
            "id": self.tmf_id,
            "href": self.href,
            "@type": self.tmf_type,
            "state": self.state,
            "childProblem": _as_array(_json_load(self.child_problem_json)),
            "parentProblem": _as_object(_json_load(self.parent_problem_json)),
        }

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
        payloads = [rec.to_tmf_json() for rec in self]
        res = super().unlink()
        self._notify("delete", payloads=payloads)
        return res


# ============================================================
# ProblemUngroup (TMF656)
# - childProblem: 1..* (array)
# - parentProblem: 1 (object)
# - @type mandatory
# ============================================================
class TMFProblemUngroup(models.Model):
    _name = "tmf.problem.ungroup"
    _description = "TMF656 ProblemUngroup"
    _inherit = ["tmf.model.mixin"]

    tmf_type = fields.Char(string="@type", required=True, default="ProblemUngroup")
    state = fields.Selection(TMF_TASK_STATE, default="acknowledged")

    child_problem_json = fields.Text(string="childProblem", required=True)  # array 1..*
    parent_problem_json = fields.Text(string="parentProblem", required=True)  # object 1

    def _notify(self, action, payloads=None):
        event_map = {
            "create": "ProblemUngroupCreateEvent",
            "update": "ProblemUngroupAttributeValueChangeEvent",
            "delete": "ProblemUngroupDeleteEvent",
        }
        if payloads is None:
            payloads = [rec.to_tmf_json() for rec in self]
        event_name = event_map.get(action)
        if event_name:
            _notify_records(self, "problemUngroup", event_name, payloads)

    def _get_tmf_api_path(self):
        return "/tmf-api/serviceProblemManagement/v5/problemUngroup"

    def to_tmf_json(self):
        self.ensure_one()
        return {
            "id": self.tmf_id,
            "href": self.href,
            "@type": self.tmf_type,
            "state": self.state,
            "childProblem": _as_array(_json_load(self.child_problem_json)),
            "parentProblem": _as_object(_json_load(self.parent_problem_json)),
        }

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
        payloads = [rec.to_tmf_json() for rec in self]
        res = super().unlink()
        self._notify("delete", payloads=payloads)
        return res
