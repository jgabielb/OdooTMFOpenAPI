# -*- coding: utf-8 -*-
import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class TMFC006ServiceSpecification(models.Model):
    """TMFC006 side-car fields on tmf.service.specification.

    These fields were previously declared on the ``tmfc006.wiring.tools``
    AbstractModel, which meant they were never materialized on real records
    and the feature-detection in ``tmf_service_catalog`` always skipped
    them. Moving them to an ``_inherit`` model makes the TMFC006 wiring
    actually persist TMF634/TMF632/TMF669/TMF662 reference fragments and
    their resolved relational links.
    """

    _inherit = "tmf.service.specification"

    service_spec_related_party_json = fields.Json(
        string="Service Spec RelatedParty (raw)",
        help="Raw TMF632/TMF669 relatedParty fragment from TMF633 serviceSpecification payload.",
    )
    service_spec_resource_spec_json = fields.Json(
        string="Service Spec ResourceSpecification (raw)",
        help="Raw TMF634 resourceSpecification fragment from TMF633 serviceSpecification payload.",
    )
    service_spec_entity_spec_json = fields.Json(
        string="Service Spec EntitySpecification (raw)",
        help="Raw TMF662 entitySpecification/associationSpecification fragment from TMF633 serviceSpecification payload.",
    )

    related_partner_ids = fields.Many2many(
        comodel_name="res.partner",
        relation="tmfc006_service_spec_partner_rel",
        column1="service_spec_id",
        column2="partner_id",
        string="Related Partners",
        help="Resolved TMF632 individuals/organizations referenced from serviceSpecification.relatedParty.",
    )
    party_role_ids = fields.Many2many(
        comodel_name="tmf.party.role",
        relation="tmfc006_service_spec_party_role_rel",
        column1="service_spec_id",
        column2="party_role_id",
        string="Party Roles",
        help="Resolved TMF669 partyRoles linked to the service specification.",
    )
    resource_specification_ids = fields.Many2many(
        comodel_name="tmf.resource.specification",
        relation="tmfc006_service_spec_resource_spec_rel",
        column1="service_spec_id",
        column2="resource_spec_id",
        string="Resource Specifications",
        help="Resolved TMF634 resourceSpecification records used by this service specification.",
    )
    entity_specification_ids = fields.Many2many(
        comodel_name="tmf.entity.specification",
        relation="tmfc006_service_spec_entity_spec_rel",
        column1="service_spec_id",
        column2="entity_spec_id",
        string="Entity Specifications",
        help="Resolved TMF662 entitySpecification records used by this service specification.",
    )

    # TMF701 lifecycle workflow linkage (TMFC006 exposed processFlow/taskFlow)
    tmfc006_process_flow_ids = fields.Many2many(
        comodel_name="tmf.process.flow",
        relation="tmfc006_service_spec_process_flow_rel",
        column1="service_spec_id",
        column2="process_flow_id",
        string="Process Flows (TMF701)",
    )
    tmfc006_task_flow_ids = fields.Many2many(
        comodel_name="tmf.task.flow",
        relation="tmfc006_service_spec_task_flow_rel",
        column1="service_spec_id",
        column2="task_flow_id",
        string="Task Flows (TMF701)",
    )

    def _tmfc006_ensure_process_flows(self):
        """Provision a TMF701 lifecycle flow per service specification.

        Mirrors the TMFC005/TMFC027 pattern: one process flow + one task flow
        keyed on the spec's tmf_id, created idempotently and linked via the
        side-car Many2many fields.
        """
        ProcessFlow = self.env["tmf.process.flow"].sudo()
        TaskFlow = self.env["tmf.task.flow"].sudo()
        for rec in self:
            key = rec.tmf_id or str(rec.id)
            process_flow = rec.tmfc006_process_flow_ids[:1] or ProcessFlow.search(
                [("tmf_id", "=", f"tmfc006-spec-{key}")], limit=1)
            if not process_flow:
                process_flow = ProcessFlow.create({
                    "tmf_id": f"tmfc006-spec-{key}",
                    "name": f"ServiceSpecification flow {rec.name or key}",
                    "description": f"Auto-generated TMFC006 lifecycle flow for serviceSpecification {key}",
                    "state": "inProgress",
                })
            task_flow = rec.tmfc006_task_flow_ids[:1] or TaskFlow.search(
                [("tmf_id", "=", f"tmfc006-spec-task-{key}")], limit=1)
            if not task_flow:
                task_flow = TaskFlow.create({
                    "tmf_id": f"tmfc006-spec-task-{key}",
                    "name": f"ServiceSpecification task {rec.name or key}",
                    "description": f"Auto-generated TMFC006 task flow for serviceSpecification {key}",
                    "state": "inProgress",
                    "process_flow_id": process_flow.id,
                })
            updates = {}
            if process_flow and process_flow.id not in rec.tmfc006_process_flow_ids.ids:
                updates["tmfc006_process_flow_ids"] = [(4, process_flow.id)]
            if task_flow and task_flow.id not in rec.tmfc006_task_flow_ids.ids:
                updates["tmfc006_task_flow_ids"] = [(4, task_flow.id)]
            if updates:
                rec.with_context(skip_tmf_wiring=True).write(updates)

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        if not self.env.context.get("skip_tmf_wiring"):
            try:
                recs._tmfc006_ensure_process_flows()
            except Exception:
                _logger.exception("TMFC006: process flow provisioning failed")
        return recs
