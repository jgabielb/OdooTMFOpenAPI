# -*- coding: utf-8 -*-
from odoo import models, fields

class TMFChangeRequest(models.Model):
    _name = "tmf.change.request"
    _description = "TMF655 ChangeRequest"

    # TMF identifiers
    tmf_id = fields.Char(string="id", index=True)     # "id" in payload
    href = fields.Char()

    # Mandatory on POST (per spec)
    priority = fields.Char(required=True)
    request_type = fields.Char(string="requestType", required=True)
    planned_start_time = fields.Datetime(string="plannedStartTime", required=True)
    planned_end_time = fields.Datetime(string="plannedEndTime", required=True)

    # Optional / common
    channel = fields.Char()
    description = fields.Text()
    impact = fields.Char()
    risk = fields.Char()
    risk_mitigation_plan = fields.Text(string="riskMitigationPlan")
    risk_value = fields.Char(string="riskValue")

    request_date = fields.Datetime(string="requestDate")
    scheduled_date = fields.Datetime(string="scheduledDate")
    actual_start_time = fields.Datetime(string="actualStartTime")
    actual_end_time = fields.Datetime(string="actualEndTime")
    completion_date = fields.Datetime(string="completionDate")
    last_update_date = fields.Datetime(string="lastUpdateDate")

    status = fields.Char()  # values per lifecycle in spec
    status_change_date = fields.Datetime(string="statusChangeDate")
    status_change_reason = fields.Char(string="statusChangeReason")

    # Complex structures as JSON
    target_entity_json = fields.Text(string="targetEntity")          # [RelatedEntity 1..*]
    impact_entity_json = fields.Text(string="impactEntity")          # [ImpactEntity *]
    specification_json = fields.Text(string="specification")         # EntitySpecificationRef
    related_party_json = fields.Text(string="relatedParty")          # [RelatedParty *]
    external_reference_json = fields.Text(string="externalReference")# [ExternalReference *]
    note_json = fields.Text(string="note")                          # [Note *]
    attachment_json = fields.Text(string="attachment")              # [AttachmentRefOrValue *]
    change_relationship_json = fields.Text(string="changeRelationship")  # [ChangeRequestRelationship *]
    characteristic_json = fields.Text(string="changeRequestCharacteristic") # [Characteristic *]
    problem_ticket_json = fields.Text(string="problemTicket")        # [ServiceProblemRef *]
    trouble_ticket_json = fields.Text(string="troubleTicket")        # [TroubleTicketRef *]
    work_log_json = fields.Text(string="workLog")                    # [WorkLog *]
    resolution_json = fields.Text(string="resolution")               # Resolution
    budget_json = fields.Text(string="budget")                       # Money
    location_json = fields.Text(string="location")                   # RelatedPlaceRefOrValue
    sla_json = fields.Text(string="sla")                             # [SLARef *]
