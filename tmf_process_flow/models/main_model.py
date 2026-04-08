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
    partner_id = fields.Many2one("res.partner", string="Partner", ondelete="set null")
    project_task_id = fields.Many2one("project.task", string="Project Task", ondelete="set null")

    @staticmethod
    def _now_iso():
        return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    def _tmf_api_name(self):
        return "processFlow"

    def _tmf_type_name(self):
        return "ProcessFlow"

    def _resolve_partner_from_related_party(self):
        self.ensure_one()
        refs = self.related_party
        if isinstance(refs, dict):
            refs = [refs]
        if not isinstance(refs, list):
            refs = []
        env_partner = self.env["res.partner"].sudo()
        for ref in refs:
            if not isinstance(ref, dict):
                continue
            rid = ref.get("id")
            if rid:
                partner = env_partner.search([("tmf_id", "=", str(rid))], limit=1)
                if not partner and str(rid).isdigit():
                    partner = env_partner.browse(int(rid))
                if partner and partner.exists():
                    return partner
            name = (ref.get("name") or "").strip()
            if name:
                partner = env_partner.search([("name", "=", name)], limit=1)
                if partner:
                    return partner
        return False

    def _sync_native_links(self):
        """Ensure native Odoo links (partner/task) stay in sync with TMF fields.

        Uses a context guard (tmf_process_flow_skip_sync) to avoid infinite
        recursion when writes performed here re-trigger write() on this model.
        """
        if self.env.context.get("tmf_process_flow_skip_sync"):
            return

        env_task = self.env["project.task"].sudo()
        for rec in self:
            partner = rec._resolve_partner_from_related_party()
            ctx = {"tmf_process_flow_skip_sync": True}

            # Keep partner_id aligned with related_party if we can resolve it.
            if partner and rec.partner_id != partner:
                try:
                    rec.with_context(**ctx).write({"partner_id": partner.id})
                except Exception:
                    # Best-effort; do not block flow provisioning on UI sync failures.
                    pass

            # Ensure a backing project.task exists, but do not recreate if already set.
            if rec.project_task_id and rec.project_task_id.exists():
                continue
            try:
                task_name = rec.name or f"{rec._tmf_type_name()}:{rec.tmf_id}"
                domain = [("name", "=", task_name)]
                if rec.partner_id:
                    domain = [("partner_id", "=", rec.partner_id.id), ("name", "=", task_name)]
                task = env_task.search(domain, limit=1)
                if not task:
                    vals = {"name": task_name}
                    if rec.partner_id:
                        vals["partner_id"] = rec.partner_id.id
                    task = env_task.create(vals)
                rec.with_context(**ctx).write({"project_task_id": task.id})
            except Exception:
                # Never fail the orchestration on UI/task sync issues.
                pass

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
        event_map = {
            "processFlow": {
                "create": "processFlowCreateEvent",
                "update": "processFlowAttributeValueChangeEvent",
                "state_change": "processFlowStateChangeEvent",
                "delete": "processFlowDeleteEvent",
            },
            "taskFlow": {
                "create": "taskFlowCreateEvent",
                "update": "taskFlowAttributeValueChangeEvent",
                "state_change": "taskFlowStateChangeEvent",
                "delete": "taskFlowDeleteEvent",
                "information_required": "taskFlowInformationRequiredEvent",
            },
        }
        api_name = self._tmf_api_name()
        mapped = (event_map.get(api_name) or {}).get(action, action)
        try:
            self.env["tmf.hub.subscription"]._notify_subscribers(
                api_name=api_name,
                event_type=mapped,
                resource_json=rec.to_tmf_json(),
            )
        except Exception:
            pass

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals.setdefault("process_flow_date", vals.get("process_flow_date") or self._now_iso())
        recs = super().create(vals_list)
        recs._sync_native_links()
        for rec in recs:
            self._notify("create", rec)
        return recs

    def write(self, vals):
        previous = {rec.id: rec.state for rec in self}
        res = super().write(vals)
        if (
            not self.env.context.get("tmf_process_flow_skip_sync")
            and ("related_party" in vals or "partner_id" in vals or "project_task_id" in vals or "name" in vals)
        ):
            self._sync_native_links()
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
