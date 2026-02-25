from datetime import datetime, timezone
from odoo import api, fields, models


class TMFProcessFlowMixin(models.AbstractModel):
    _name = "tmf.process.flow.mixin"
    _description = "TMF701 Process Flow Mixin"
    _inherit = ["tmf.model.mixin"]

    name = fields.Char()
    state = fields.Char(default="inProgress")
    description = fields.Char()
    process_flow_date = fields.Char(string="processFlowDate")
    channel = fields.Json(default=list)
    characteristic = fields.Json(default=list)
    related_entity = fields.Json(default=list)
    related_party = fields.Json(default=list)
    extra_json = fields.Json(default=dict)

    @staticmethod
    def _now_iso():
        return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    def _tmf_api_name(self):
        return "processFlow"

    def _tmf_type_name(self):
        return "ProcessFlow"

    def _base_payload(self):
        self.ensure_one()
        payload = {
            "id": self.tmf_id,
            "href": self.href,
            "@type": self._tmf_type_name(),
            "state": self.state or "inProgress",
        }
        if self.name:
            payload["name"] = self.name
        if self.description:
            payload["description"] = self.description
        if self.process_flow_date:
            payload["processFlowDate"] = self.process_flow_date
        if self.channel:
            payload["channel"] = self.channel
        if self.characteristic:
            payload["characteristic"] = self.characteristic
        if self.related_entity:
            payload["relatedEntity"] = self.related_entity
        if self.related_party:
            payload["relatedParty"] = self.related_party
        if isinstance(self.extra_json, dict):
            for key, value in self.extra_json.items():
                if key not in payload:
                    payload[key] = value
        return self._tmf_normalize_payload(payload)

    def _notify(self, action, rec):
        try:
            self.env["tmf.hub.subscription"]._notify_subscribers(
                api_name=self._tmf_api_name(),
                event_type=action,
                resource_json=rec.to_tmf_json(),
            )
        except Exception:
            pass

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals.setdefault("process_flow_date", vals.get("process_flow_date") or self._now_iso())
        recs = super().create(vals_list)
        for rec in recs:
            self._notify("create", rec)
        return recs

    def write(self, vals):
        previous = {rec.id: rec.state for rec in self}
        res = super().write(vals)
        for rec in self:
            self._notify("update", rec)
            if "state" in vals and previous.get(rec.id) != rec.state:
                self._notify("state_change", rec)
        return res

    def unlink(self):
        payloads = [rec.to_tmf_json() for rec in self]
        api_name = self._tmf_api_name()
        res = super().unlink()
        for resource in payloads:
            try:
                self.env["tmf.hub.subscription"]._notify_subscribers(
                    api_name=api_name,
                    event_type="delete",
                    resource_json=resource,
                )
            except Exception:
                pass
        return res


class TMFProcessFlowSpecification(models.Model):
    _name = "tmf.process.flow.specification"
    _description = "ProcessFlowSpecification"
    _inherit = ["tmf.process.flow.mixin"]

    def _tmf_api_name(self):
        return "processFlowSpecification"

    def _tmf_type_name(self):
        return "ProcessFlowSpecification"

    def _get_tmf_api_path(self):
        return "/processFlowManagement/v4/processFlowSpecification"

    def to_tmf_json(self):
        return self._tmf_normalize_payload(self._base_payload())


class TMFTaskFlowSpecification(models.Model):
    _name = "tmf.task.flow.specification"
    _description = "TaskFlowSpecification"
    _inherit = ["tmf.process.flow.mixin"]

    def _tmf_api_name(self):
        return "taskFlowSpecification"

    def _tmf_type_name(self):
        return "TaskFlowSpecification"

    def _get_tmf_api_path(self):
        return "/processFlowManagement/v4/taskFlowSpecification"

    def to_tmf_json(self):
        return self._tmf_normalize_payload(self._base_payload())


class TMFProcessFlow(models.Model):
    _name = "tmf.process.flow"
    _description = "ProcessFlow"
    _inherit = ["tmf.process.flow.mixin"]

    process_flow_specification_ref = fields.Json(default=dict)
    task_flow_ids = fields.One2many("tmf.task.flow", "process_flow_id")

    def _tmf_api_name(self):
        return "processFlow"

    def _tmf_type_name(self):
        return "ProcessFlow"

    def _get_tmf_api_path(self):
        return "/processFlowManagement/v4/processFlow"

    def to_tmf_json(self):
        payload = self._base_payload()
        if self.process_flow_specification_ref:
            payload["processFlowSpecificationRef"] = self.process_flow_specification_ref
        if self.task_flow_ids:
            payload["taskFlow"] = [task.to_tmf_json() for task in self.task_flow_ids]
        return self._tmf_normalize_payload(payload)


class TMFTaskFlow(models.Model):
    _name = "tmf.task.flow"
    _description = "TaskFlow"
    _inherit = ["tmf.process.flow.mixin"]

    process_flow_id = fields.Many2one("tmf.process.flow", required=True, ondelete="cascade", index=True)
    task_flow_specification_ref = fields.Json(default=dict)
    information_required = fields.Boolean(default=False)

    def _tmf_api_name(self):
        return "taskFlow"

    def _tmf_type_name(self):
        return "TaskFlow"

    def _get_tmf_api_path(self):
        return "/processFlowManagement/v4/processFlow/taskFlow"

    def to_tmf_json(self):
        payload = self._base_payload()
        payload["processFlowId"] = self.process_flow_id.tmf_id if self.process_flow_id else None
        if self.task_flow_specification_ref:
            payload["taskFlowSpecificationRef"] = self.task_flow_specification_ref
        return self._tmf_normalize_payload(payload)

    def write(self, vals):
        previous = {rec.id: rec.state for rec in self}
        info_before = {rec.id: rec.information_required for rec in self}
        res = super().write(vals)
        for rec in self:
            if "information_required" in vals and not info_before.get(rec.id) and rec.information_required:
                rec._notify("information_required", rec)
            if "state" in vals and previous.get(rec.id) != rec.state:
                rec._notify("state_change", rec)
        return res
