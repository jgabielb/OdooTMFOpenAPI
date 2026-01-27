import logging
import uuid
from datetime import datetime
import requests
import re
import traceback
from odoo import api, fields, models

_logger = logging.getLogger(__name__)

# Regex for parsing query filters (e.g., eventType=ProductOrderCreateEvent)
_RE_EQ = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.+?)\s*$")
_RE_IN = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s+in\s*\((.+?)\)\s*$", re.IGNORECASE)

# =========================================================
# TMF Event Name Mapping
# Keys match the 'api_name' passed from your models.
# =========================================================
TMF_EVENT_NAME_MAP = {

    # TMF632 - Party
    'party': {
        'create': 'PartyCreateEvent',
        'update': 'PartyAttributeValueChangeEvent',
        'delete': 'PartyDeleteEvent',
    },

    # TMF629 - Customer
    'customer': {
        'create': 'CustomerCreateEvent',
        'update': 'CustomerAttributeValueChangeEvent',
        'delete': 'CustomerDeleteEvent',
    },

    # TMF622 - Product Ordering (resource: productOrder)
    'productOrder': {
        'create': 'ProductOrderCreateEvent',
        'update': 'ProductOrderAttributeValueChangeEvent',
        'state_change': 'ProductOrderStateChangeEvent',
        'delete': 'ProductOrderDeleteEvent',
    },

    # TMF620 - Product Catalog
    # Usa fallback si no distingues offering/specification
    'productCatalog': {
        'create': 'ProductOfferingCreateEvent',
        'update': 'ProductOfferingAttributeValueChangeEvent',
        'delete': 'ProductOfferingDeleteEvent',
    },

    # Opcional: separación fina TMF620
    'productOffering': {
        'create': 'ProductOfferingCreateEvent',
        'update': 'ProductOfferingAttributeValueChangeEvent',
        'delete': 'ProductOfferingDeleteEvent',
    },
    'productSpecification': {
        'create': 'ProductSpecificationCreateEvent',
        'update': 'ProductSpecificationAttributeValueChangeEvent',
        'delete': 'ProductSpecificationDeleteEvent',
    },

    # TMF638 - Service Inventory (resource: service)
    'service': {
        'create': 'ServiceCreateEvent',
        'update': 'ServiceAttributeValueChangeEvent',
        'state_change': 'ServiceStateChangeEvent',
        'delete': 'ServiceDeleteEvent',
    },

    # TMF639 - Resource Inventory (resource: resource)
    'resource': {
        'create': 'ResourceCreateEvent',
        'update': 'ResourceAttributeValueChangeEvent',
        'state_change': 'ResourceStateChangeEvent',
        'delete': 'ResourceDeleteEvent',
    },

    # TMF621 - Trouble Ticket (resource: troubleTicket)
    'troubleTicket': {
        'create': 'TroubleTicketCreateEvent',
        'update': 'TroubleTicketAttributeValueChangeEvent',
        # TMF621 define cambio de estado como StatusChange (no StateChange)
        'state_change': 'TroubleTicketStatusChangeEvent',
        'delete': 'TroubleTicketDeleteEvent',
    },

    # TMF666 - Account Management
    'account': {
        'create': 'AccountCreateEvent',
        'update': 'AccountAttributeValueChangeEvent',
        'state_change': 'AccountStateChangeEvent',
        'delete': 'AccountDeleteEvent',
    },

    # TMF678 - Customer Bill Management
    'customerBill': {
        'create': 'CustomerBillCreateEvent',
        'update': 'CustomerBillAttributeValueChangeEvent',
        'state_change': 'CustomerBillStateChangeEvent',
        'delete': 'CustomerBillDeleteEvent',
    },
}

def _strip_quotes(s: str) -> str:
    s = s.strip()
    if (len(s) >= 2) and ((s[0] == s[-1]) and s[0] in ("'", '"')):
        return s[1:-1].strip()
    return s

def _split_csv_list(s: str) -> list[str]:
    parts = [p.strip() for p in s.split(",")]
    return [_strip_quotes(p) for p in parts if p.strip()]

def _normalize_query(q: str) -> list[str]:
    if not q:
        return []
    q = q.strip()
    clauses = [c.strip() for c in q.split("&") if c.strip()]
    return clauses

def _query_matches_payload(query: str, payload: dict) -> bool:
    """
    Evaluates subscription queries against the event payload.
    Supports: key=value AND key in (a,b)
    """
    if not query:
        return True

    def get_value(key: str):
        # 1. Check top level (eventId, eventType)
        if key in payload:
            return payload.get(key)
        # 2. Check 'event' object
        ev = payload.get("event") or {}
        if isinstance(ev, dict) and key in ev:
            return ev.get(key)
        # 3. Check 'resource' inside event (common TMF pattern)
        res = ev.get("resource") if isinstance(ev, dict) else None
        if isinstance(res, dict) and key in res:
            return res.get(key)
        return None

    for clause in _normalize_query(query):
        # Handle IN operator
        m_in = _RE_IN.match(clause)
        if m_in:
            key = m_in.group(1)
            values = _split_csv_list(m_in.group(2))
            actual = get_value(key)
            if actual is None or str(actual) not in values:
                return False
            continue

        # Handle EQUALS operator
        m_eq = _RE_EQ.match(clause)
        if m_eq:
            key = m_eq.group(1)
            expected = _strip_quotes(m_eq.group(2))
            actual = get_value(key)
            if actual is None or str(actual) != expected:
                return False
            continue

        _logger.warning("Unsupported TMF query clause: %r", clause)
        return False

    return True


class TMFHubSubscription(models.Model):
    _name = 'tmf.hub.subscription'
    _description = 'TMF Event Hub Subscription'

    name = fields.Char(string="Name", required=True)
    api_name = fields.Char(string="API Resource Name", required=True, help="e.g. troubleTicket, productOrder, party")
    callback = fields.Char(string="Callback URL", required=True)
    query = fields.Char(string="Query Filter")
    
    # Internal Action mapping
    event_type = fields.Selection([
        ('create', 'Create'),
        ('update', 'Update'),
        ('delete', 'Delete'),
        ('any', 'Any'),
    ], default='any', required=True, string="Trigger Action")
    
    content_type = fields.Selection([
        ('application/json', 'JSON'),
    ], default='application/json')
    
    secret = fields.Char(string="Secret / Token")
    active = fields.Boolean(default=True)
    last_status = fields.Char()

    @api.model
    def _resolve_event_names(self, api_name, input_event_type):
        """
        Helper to normalize inputs.
        Input: api_name='troubleTicket', input_event_type='TroubleTicketCreateEvent'
        Output: action='create', tmf_string='TroubleTicketCreateEvent'
        """
        mapping = TMF_EVENT_NAME_MAP.get(api_name, {})
        
        # Case 1: Input is already a raw action ('create', 'update')
        if input_event_type in mapping:
            return input_event_type, mapping[input_event_type]
        
        # Case 2: Input is a TMF String ('TroubleTicketCreateEvent') -> Reverse lookup the action
        for action, tmf_string in mapping.items():
            if tmf_string == input_event_type:
                # Map specific state changes to 'update' for subscription filtering
                internal_action = 'update' if 'change' in action.lower() else action
                return internal_action, tmf_string
                
        # Case 3: Unknown / Fallback
        return 'update', input_event_type

    @api.model
    def _notify_subscribers(self, api_name, event_type, resource_json):
        """
        Main Dispatcher.
        api_name: 'troubleTicket', 'productOrder', etc.
        event_type: Can be 'create' OR 'TroubleTicketCreateEvent'
        resource_json: The TMF JSON representation of the object.
        """
        
        # 1. Resolve to Internal Action (for DB Search) and TMF String (for JSON payload)
        action, tmf_event_name = self._resolve_event_names(api_name, event_type)

        # 2. Find matching subscriptions
        domain = [
            ("active", "=", True),
            ("api_name", "=", api_name),
            "|",
                ("event_type", "=", action), # Matches 'create', 'update', 'delete'
                ("event_type", "=", "any"),
        ]
        
        subs = self.search(domain)
        if not subs:
            return

        # 3. Construct Payload
        payload = {
            "eventId": str(uuid.uuid4()),
            "eventTime": datetime.utcnow().isoformat() + "Z",
            "eventType": tmf_event_name,
            "@type": tmf_event_name,
            "event": resource_json if isinstance(resource_json, dict) else {"resource": resource_json},
        }

        # 4. Dispatch
        for sub in subs:
            # Apply Query Filter (e.g. status=Resolved)
            if sub.query and not _query_matches_payload(sub.query, payload):
                continue

            headers = {"Content-Type": sub.content_type or "application/json"}
            if sub.secret:
                headers["X-Hub-Signature"] = sub.secret

            try:
                resp = requests.post(sub.callback, json=payload, headers=headers, timeout=5)
                sub.sudo().write({'last_status': f"{resp.status_code} {resp.reason}"})
            except Exception as e:
                _logger.error(f"TMF Hub Error ({sub.callback}): {e}")
                sub.sudo().write({'last_status': f"Error: {str(e)}"})