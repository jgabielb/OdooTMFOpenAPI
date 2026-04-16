from odoo import api, fields, models
import logging

_logger = logging.getLogger(__name__)


class ProjectTaskTMF(models.Model):
    _inherit = "project.task"

    tmf_work_id = fields.Many2one(
        "tmf.work", string="TMF Work",
        ondelete="set null", copy=False,
    )

    def _sync_tmf_work(self):
        Work = self.env["tmf.work"].sudo()
        for rec in self:
            if rec.env.context.get("skip_tmf_bridge"):
                continue
            vals = {
                "name": rec.name or "Untitled",
                "description": rec.description or "",
                "state": self._map_stage_to_tmf(rec),
                "partner_id": rec.partner_id.id if rec.partner_id else False,
            }
            if rec.tmf_work_id and rec.tmf_work_id.exists():
                rec.tmf_work_id.with_context(skip_tmf_bridge=True).write(vals)
                continue
            work = Work.with_context(skip_tmf_bridge=True).create(vals)
            rec.with_context(skip_tmf_bridge=True).write({"tmf_work_id": work.id})
            if hasattr(work, "project_task_id"):
                work.with_context(skip_tmf_bridge=True).write({"project_task_id": rec.id})

    @staticmethod
    def _map_stage_to_tmf(rec):
        if not rec.stage_id:
            return "acknowledged"
        name = (rec.stage_id.name or "").lower()
        if "new" in name or "draft" in name:
            return "acknowledged"
        if "progress" in name or "open" in name:
            return "inProgress"
        if "done" in name or "close" in name or "complete" in name:
            return "completed"
        if "cancel" in name:
            return "cancelled"
        return "inProgress"

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        if not self.env.context.get("skip_tmf_bridge"):
            try:
                recs._sync_tmf_work()
            except Exception:
                _logger.warning("TMF bridge sync failed on project.task create", exc_info=True)
        return recs

    def write(self, vals):
        res = super().write(vals)
        trigger = {"name", "description", "partner_id", "stage_id"}
        if not self.env.context.get("skip_tmf_bridge") and trigger & set(vals):
            try:
                self._sync_tmf_work()
            except Exception:
                _logger.warning("TMF bridge sync failed on project.task write", exc_info=True)
        return res
