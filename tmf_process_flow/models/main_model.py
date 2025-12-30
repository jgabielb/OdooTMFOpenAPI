from odoo import models, fields, api
import json

class TMFModel(models.Model):
    _name = 'tmf.process.flow'
    _description = 'ProcessFlow'
    _inherit = ['tmf.model.mixin']

    process_flow_date = fields.Datetime(string="processFlowDate", help="Is the date when the processFlow was created in basse (timestamp)")
    process_flow_specification = fields.Char(string="processFlowSpecification", help="Identifier of the Process flow specification")
    channel = fields.Char(string="channel", help="A list of channel(s) where this processFlow is executed")
    characteristic = fields.Char(string="characteristic", help="A list of characteristic(s) associated to this processFlow")
    process_flow_specification_ref = fields.Char(string="processFlowSpecificationRef", help="")
    related_entity = fields.Char(string="relatedEntity", help="A list of related entity(ies) to this processFlow")
    related_party = fields.Char(string="relatedParty", help="A list of related party(ies) to this processFlow")
    state = fields.Char(string="state", help="State of the ProcessFlow: described in the state machine diagram.")
    task_flow = fields.Char(string="taskFlow", help="A list of taskflow related to this processFlow")

    def _get_tmf_api_path(self):
        return "/process_flowManagement/v4/ProcessFlow"

    def to_tmf_json(self):
        self.ensure_one()
        return {
            "id": self.tmf_id,
            "href": self.href,
            "@type": "ProcessFlow",
            "processFlowDate": self.process_flow_date.isoformat() if self.process_flow_date else None,
            "processFlowSpecification": self.process_flow_specification,
            "channel": self.channel,
            "characteristic": self.characteristic,
            "processFlowSpecificationRef": self.process_flow_specification_ref,
            "relatedEntity": self.related_entity,
            "relatedParty": self.related_party,
            "state": self.state,
            "taskFlow": self.task_flow,

        }

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        for rec in recs:
            self._notify('processFlow', 'create', rec)
        return recs

    def write(self, vals):
        res = super().write(vals)
        for rec in self:
            self._notify('processFlow', 'update', rec)
        return res

    def unlink(self):
        payloads = [r.to_tmf_json() for r in self]
        res = super().unlink()
        for resource in payloads:
            try:
                self.env['tmf.hub.subscription']._notify_subscribers(
                    api_name='processFlow',
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
