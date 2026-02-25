from odoo import api, fields, models


class TMFEventTopic(models.Model):
    _name = "tmf.event.topic"
    _description = "TMF688 Topic"
    _inherit = ["tmf.model.mixin"]

    name = fields.Char(string="name")
    content_query = fields.Char(string="contentQuery")
    header_query = fields.Char(string="headerQuery")
    extra_json = fields.Json(default=dict)

    def _get_tmf_api_path(self):
        return "/event/v4/topic"

    def to_tmf_json(self):
        self.ensure_one()
        payload = {
            "id": self.tmf_id,
            "href": self.href,
            "@type": "Topic",
        }
        if self.name:
            payload["name"] = self.name
        if self.content_query:
            payload["contentQuery"] = self.content_query
        if self.header_query:
            payload["headerQuery"] = self.header_query
        if isinstance(self.extra_json, dict):
            for key, value in self.extra_json.items():
                if key not in payload:
                    payload[key] = value
        return self._tmf_normalize_payload(payload)

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        for rec in recs:
            self._notify("topic", "create", rec)
        return recs

    def write(self, vals):
        res = super().write(vals)
        for rec in self:
            self._notify("topic", "update", rec)
        return res

    def unlink(self):
        payloads = [rec.to_tmf_json() for rec in self]
        res = super().unlink()
        for resource in payloads:
            try:
                self.env["tmf.hub.subscription"]._notify_subscribers(
                    api_name="topic",
                    event_type="delete",
                    resource_json=resource,
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


class TMFEvent(models.Model):
    _name = "tmf.event"
    _description = "TMF688 Event"
    _inherit = ["tmf.model.mixin"]

    topic_id = fields.Many2one("tmf.event.topic", required=False, ondelete="cascade", index=True)
    correlation_id = fields.Char(string="correlationId")
    description = fields.Char(string="description")
    domain = fields.Char(string="domain")
    event_id = fields.Char(string="eventId")
    event_time = fields.Datetime(string="eventTime")
    event_type = fields.Char(string="eventType")
    priority = fields.Char(string="priority")
    time_occurred = fields.Datetime(string="timeOccurred")
    title = fields.Char(string="title")
    analytic_characteristic = fields.Json(default=list)
    event_payload = fields.Json(default=dict)
    related_party = fields.Json(default=list)
    reporting_system = fields.Json(default=dict)
    source = fields.Json(default=dict)
    extra_json = fields.Json(default=dict)

    def _get_tmf_api_path(self):
        return "/event/v4/topic/event"

    def _build_event_href(self):
        self.ensure_one()
        if not self.topic_id:
            return self.href
        base_url = self.env["ir.config_parameter"].sudo().get_param("web.base.url")
        return f"{base_url}/tmf-api/event/v4/topic/{self.topic_id.tmf_id}/event/{self.tmf_id}"

    def to_tmf_json(self):
        self.ensure_one()
        payload = {
            "id": self.tmf_id,
            "href": self._build_event_href(),
            "@type": "Event",
            "topicId": self.topic_id.tmf_id if self.topic_id else None,
        }
        if self.correlation_id:
            payload["correlationId"] = self.correlation_id
        if self.description:
            payload["description"] = self.description
        if self.domain:
            payload["domain"] = self.domain
        if self.event_id:
            payload["eventId"] = self.event_id
        if self.event_time:
            payload["eventTime"] = self.event_time.isoformat()
        if self.event_type:
            payload["eventType"] = self.event_type
        if self.priority:
            payload["priority"] = self.priority
        if self.time_occurred:
            payload["timeOccurred"] = self.time_occurred.isoformat()
        if self.title:
            payload["title"] = self.title
        if self.analytic_characteristic:
            payload["analyticCharacteristic"] = self.analytic_characteristic
        if self.event_payload:
            payload["event"] = self.event_payload
        if self.related_party:
            payload["relatedParty"] = self.related_party
        if self.reporting_system:
            payload["reportingSystem"] = self.reporting_system
        if self.source:
            payload["source"] = self.source
        if isinstance(self.extra_json, dict):
            for key, value in self.extra_json.items():
                if key not in payload:
                    payload[key] = value
        return self._tmf_normalize_payload(payload)

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        for rec in recs:
            self._notify("event", "create", rec)
        return recs

    def write(self, vals):
        res = super().write(vals)
        for rec in self:
            self._notify("event", "update", rec)
        return res

    def unlink(self):
        payloads = [rec.to_tmf_json() for rec in self]
        res = super().unlink()
        for resource in payloads:
            try:
                self.env["tmf.hub.subscription"]._notify_subscribers(
                    api_name="event",
                    event_type="delete",
                    resource_json=resource,
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
