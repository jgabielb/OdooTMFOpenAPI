"""Odoo XML-RPC client for verifying bridge sync from the Odoo side."""
import xmlrpc.client


class OdooClient:
    """Minimal XML-RPC client to read Odoo records for test assertions."""

    def __init__(self, url="http://localhost:8069", db="TMF_Odoo_DB",
                 user="admin", password="admin"):
        self.url = url
        self.db = db
        self.uid = None
        self._password = password
        self._common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
        self._object = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")
        self.uid = self._common.authenticate(db, user, password, {})
        assert self.uid, f"Failed to authenticate as {user}"

    def search_read(self, model, domain, fields=None, limit=10):
        return self._object.execute_kw(
            self.db, self.uid, self._password,
            model, "search_read",
            [domain],
            {"fields": fields or [], "limit": limit},
        )

    def search(self, model, domain, limit=10):
        return self._object.execute_kw(
            self.db, self.uid, self._password,
            model, "search",
            [domain],
            {"limit": limit},
        )

    def read(self, model, ids, fields=None):
        return self._object.execute_kw(
            self.db, self.uid, self._password,
            model, "read",
            [ids],
            {"fields": fields or []},
        )

    def write(self, model, ids, vals):
        return self._object.execute_kw(
            self.db, self.uid, self._password,
            model, "write",
            [ids, vals],
        )

    # -- Convenience --

    def find_partner_by_tmf_id(self, tmf_id):
        recs = self.search_read(
            "res.partner",
            [("tmf_id", "=", tmf_id)],
            ["id", "name", "tmf_id", "tmf_status", "email", "phone"],
            limit=1,
        )
        return recs[0] if recs else None

    def find_sale_order_by_tmf_id(self, tmf_id):
        recs = self.search_read(
            "sale.order",
            [("tmf_id", "=", tmf_id)],
            ["id", "name", "state", "tmf_id", "partner_id"],
            limit=1,
        )
        return recs[0] if recs else None

    def find_helpdesk_ticket(self, name_contains):
        recs = self.search_read(
            "helpdesk.ticket",
            [("name", "ilike", name_contains)],
            ["id", "name", "description", "stage_id", "partner_id"],
            limit=5,
        )
        return recs

    def find_project_task(self, name_contains):
        recs = self.search_read(
            "project.task",
            [("name", "ilike", name_contains)],
            ["id", "name", "description", "stage_id", "partner_id"],
            limit=5,
        )
        return recs

    def find_account_payment(self, partner_name):
        recs = self.search_read(
            "account.payment",
            [("partner_id.name", "ilike", partner_name)],
            ["id", "name", "amount", "state", "partner_id"],
            limit=5,
        )
        return recs

    def find_stock_picking(self, name_contains):
        recs = self.search_read(
            "stock.picking",
            [("name", "ilike", name_contains)],
            ["id", "name", "state", "partner_id"],
            limit=5,
        )
        return recs

    def find_calendar_event(self, name_contains):
        recs = self.search_read(
            "calendar.event",
            [("name", "ilike", name_contains)],
            ["id", "name", "start", "stop", "partner_ids"],
            limit=5,
        )
        return recs

    def find_invoice(self, partner_name):
        recs = self.search_read(
            "account.move",
            [("partner_id.name", "ilike", partner_name), ("move_type", "=", "out_invoice")],
            ["id", "name", "state", "amount_total", "partner_id"],
            limit=5,
        )
        return recs
