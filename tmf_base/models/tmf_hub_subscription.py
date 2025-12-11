import logging
import uuid
from datetime import datetime

import requests

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class TMFHubSubscription(models.Model):
    _name = 'tmf.hub.subscription'
    _description = 'TMF Event Hub Subscription'

    api_name = fields.Char(required=True)   # e.g. 'party', 'productOrder', 'service'
    callback = fields.Char(required=True)   # callback URL
    query = fields.Char()                   # optional filter expression

    @api.model
    def _notify_subscribers(self, api_name, event_type, resource_json):
        """Send TMF-style event to all subscribers of a given API."""
        subs = self.sudo().search([('api_name', '=', api_name)])
        if not subs:
            return

        event_id = str(uuid.uuid4())
        event_time = datetime.utcnow().isoformat() + 'Z'

        payload = {
            "eventId": event_id,
            "eventTime": event_time,
            "eventType": event_type,
            "@type": event_type,
            "event": resource_json,  # can be a ProductOrder, Service, etc.
        }

        for sub in subs:
            try:
                requests.post(
                    sub.callback,
                    json=payload,
                    timeout=5,
                )
            except Exception as e:
                _logger.warning(
                    "TMF hub notify failed (%s) for API %s: %s",
                    sub.callback, api_name, e
                )
