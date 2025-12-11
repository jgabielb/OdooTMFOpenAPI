import logging
import uuid
from datetime import datetime

import requests

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

TMF_EVENT_NAME_MAP = {
    'party': {
        'create': 'PartyCreateEvent',
        'update': 'PartyAttributeValueChangeEvent',
        'delete': 'PartyDeleteEvent',
    },
    'productOrdering': {
        'create': 'ProductOrderCreateEvent',
        'update': 'ProductOrderStateChangeEvent',
        'delete': 'ProductOrderDeleteEvent',
    },
    'serviceInventory': {
        'create': 'ServiceCreateEvent',
        'update': 'ServiceAttributeValueChangeEvent',
        'delete': 'ServiceDeleteEvent',
    },
    'resourceInventory': {
        'create': 'ResourceCreateEvent',
        'update': 'ResourceAttributeValueChangeEvent',
        'delete': 'ResourceDeleteEvent',
    },
}

class TMFHubSubscription(models.Model):
    _name = 'tmf.hub.subscription'
    _description = 'TMF Event Hub Subscription'

    name = fields.Char(string="Name", required=True)
    
    api_name = fields.Char(string="API Name", required=True)  # ej: 'individual', 'organization'
    callback = fields.Char(string="Callback URL", required=True)
    query = fields.Char(string="Query")
    event_type = fields.Selection([
        ('create', 'Create'),
        ('update', 'Update'),
        ('delete', 'Delete'),
        ('any', 'Any'),
    ], default='any', required=True)
    content_type = fields.Selection([
        ('application/json', 'JSON'),
    ], default='application/json')
    secret = fields.Char(string="Secret / Token")
    active = fields.Boolean(default=True)
    last_status = fields.Char()



    @api.model
    def _notify_subscribers(self, api_name, event_type, resource_json):
        """Send TMF-style event to all subscribers of a given API."""
        domain = [
            ('active', '=', True),
            ('api_name', '=', api_name),
            '|', ('event_type', '=', event_type),
                 ('event_type', '=', 'any'),
        ]
        subs = self.search(domain)
        if not subs:
            _logger.info("No TMF subscriptions for %s (%s)", api_name, event_type)
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
            headers = {
                'Content-Type': sub.content_type or 'application/json',
            }
            if sub.secret:
                # puedes cambiar el header si tu hub lo define distinto
                headers['X-Hub-Signature'] = sub.secret

            try:
                resp = requests.post(sub.callback, json=payload, headers=headers, timeout=5)
                _logger.info(
                    "TMF notify -> %s [%s] %s : %s",
                    sub.api_name, sub.event_type, sub.callback, resp.status_code
                )
            except Exception as e:
                _logger.exception(
                    "Error sending TMF hub notification to %s: %s",
                    sub.callback, e
                )
