#!/usr/bin/env python3
"""
Demo Data Seed Script
=====================
Creates a realistic telecom customer scenario via Odoo XML-RPC:

  - 1 Customer (Party): "Empresa Demo SpA" (RUT: 76.123.456-7)
  - 3 Accounts (PartyAccount) with different addresses:
      1. Casa Matriz (Santiago) — Internet + TV + Voice
      2. Sucursal Viña (Viña del Mar) — Internet + Mobile
      3. Oficina Digital (Remote) — OTT + Mobile
  - Each account has a BillingAccount
  - Service Specifications + Resource Specifications for each service type
  - Product Specifications linking services to resources
  - Product Offerings (product.template) with prices
  - Sale Orders per account → auto-provisions services
  - Services start in 'feasabilityChecked' → ready for mock OSS

Usage:
  python seed_demo_data.py                          # localhost:8069
  python seed_demo_data.py --host 192.168.1.5       # custom host
  python seed_demo_data.py --db TMF_Odoo_DB         # custom database

Requires: Odoo running with all TMF modules installed.
"""

import argparse
import json
import logging
import os
import sys
import xmlrpc.client

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [SEED] %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("seed")

# ---------------------------------------------------------------------------
# Service catalog definition
# ---------------------------------------------------------------------------
# Each entry: (service_type, service_spec_name, resource_spec_name, device_name)
SERVICE_CATALOG = {
    "internet": {
        "svc_spec": "Internet Access CFS",
        "res_spec": "GPON ONT HG8245H",
        "device": "Huawei ONT HG8245H",
        "product_spec": "Internet Hogar Plan",
        "offerings": [
            ("Internet 200Mbps", 24990),
            ("Internet 500Mbps", 34990),
        ],
    },
    "tv": {
        "svc_spec": "IPTV Multiscreen CFS",
        "res_spec": "IPTV STB ZTE-B860H",
        "device": "ZTE Set-Top Box B860H",
        "product_spec": "TV Digital Plan",
        "offerings": [
            ("TV Full HD 120ch", 14990),
        ],
    },
    "voice": {
        "svc_spec": "Fixed Voice CFS",
        "res_spec": "VoIP ATA Grandstream HT801",
        "device": "Grandstream HT801 ATA",
        "product_spec": "Telefonia Fija Plan",
        "offerings": [
            ("Telefonia Fija Ilimitada", 7990),
        ],
    },
    "mobile": {
        "svc_spec": "Mobile Data+Voice CFS",
        "res_spec": "SIM Card Triple-Cut",
        "device": "SIM Card Triple-Cut",
        "product_spec": "Plan Movil",
        "offerings": [
            ("Movil 50GB + Llamadas", 19990),
        ],
    },
    "ott": {
        "svc_spec": "OTT Streaming CFS",
        "res_spec": "Streaming Chromecast Dongle",
        "device": "Google Chromecast 4K",
        "product_spec": "Streaming Digital Plan",
        "offerings": [
            ("Pack Streaming Premium", 9990),
        ],
    },
}

# Account definitions with addresses and service mix
ACCOUNTS = [
    {
        "name": "Casa Matriz - Santiago",
        "address": "Av. Providencia 1234, Piso 15, Providencia, Santiago",
        "services": ["internet", "tv", "voice"],
        "offering_picks": {
            "internet": "Internet 500Mbps",
            "tv": "TV Full HD 120ch",
            "voice": "Telefonia Fija Ilimitada",
        },
    },
    {
        "name": "Sucursal Viña del Mar",
        "address": "Av. Libertad 567, Viña del Mar, Valparaíso",
        "services": ["internet", "mobile"],
        "offering_picks": {
            "internet": "Internet 200Mbps",
            "mobile": "Movil 50GB + Llamadas",
        },
    },
    {
        "name": "Oficina Digital (Remoto)",
        "address": "Trabajo remoto, sin dirección física",
        "services": ["ott", "mobile"],
        "offering_picks": {
            "ott": "Pack Streaming Premium",
            "mobile": "Movil 50GB + Llamadas",
        },
    },
]


class OdooRPC:
    """Thin XML-RPC wrapper for Odoo."""

    def __init__(self, host, port, db, user, password):
        self.url = f"http://{host}:{port}"
        self.db = db
        self.user = user
        self.password = password
        self.uid = None
        self.common = xmlrpc.client.ServerProxy(f"{self.url}/xmlrpc/2/common")
        self.models = xmlrpc.client.ServerProxy(f"{self.url}/xmlrpc/2/object")

    def authenticate(self):
        self.uid = self.common.authenticate(self.db, self.user, self.password, {})
        if not self.uid:
            raise RuntimeError(f"Authentication failed for {self.user}@{self.db}")
        log.info("Authenticated as uid=%s on %s", self.uid, self.db)
        return self.uid

    def execute(self, model, method, *args, **kwargs):
        return self.models.execute_kw(
            self.db, self.uid, self.password, model, method, args, kwargs
        )

    def search(self, model, domain, limit=0):
        kw = {}
        if limit:
            kw["limit"] = limit
        return self.execute(model, "search", domain, **kw)

    def search_read(self, model, domain, fields, limit=0):
        kw = {"fields": fields}
        if limit:
            kw["limit"] = limit
        return self.execute(model, "search_read", domain, **kw)

    def create(self, model, vals):
        return self.execute(model, "create", vals)

    def write(self, model, ids, vals):
        return self.execute(model, "write", ids, vals)

    def find_or_create(self, model, domain, vals, name_field="name"):
        """Find by domain or create. Returns (id, created)."""
        existing = self.search(model, domain, limit=1)
        if existing:
            label = vals.get(name_field, vals.get("name", "?"))
            log.info("  Found existing %s: %s (id=%s)", model, label, existing[0])
            return existing[0], False
        rec_id = self.create(model, vals)
        label = vals.get(name_field, vals.get("name", "?"))
        log.info("  Created %s: %s (id=%s)", model, label, rec_id)
        return rec_id, True


def _ensure_sales_journal(rpc):
    """Ensure a Sales journal exists (required for invoice creation)."""
    journals = rpc.search("account.journal", [("type", "=", "sale")], limit=1)
    if journals:
        log.info("  Sales journal already exists (id=%s)", journals[0])
        return journals[0]
    company_ids = rpc.search("res.company", [], limit=1)
    journal_id = rpc.create("account.journal", {
        "name": "Customer Invoices",
        "type": "sale",
        "code": "INV",
        "company_id": company_ids[0] if company_ids else 1,
    })
    log.info("  Created Sales journal (id=%s)", journal_id)
    return journal_id


def seed(rpc):
    """Main seeding logic."""

    # ------------------------------------------------------------------
    # 0. Accounting prerequisites
    # ------------------------------------------------------------------
    log.info("=" * 60)
    log.info("STEP 0: Ensuring accounting setup")
    log.info("=" * 60)
    _ensure_sales_journal(rpc)

    # ------------------------------------------------------------------
    # 1. Create Customer (res.partner)
    # ------------------------------------------------------------------
    log.info("=" * 60)
    log.info("STEP 1: Creating customer")
    log.info("=" * 60)

    partner_id, _ = rpc.find_or_create(
        "res.partner",
        [("vat", "=", "76086428-5")],
        {
            "name": "Empresa Demo SpA",
            "vat": "76086428-5",
            "is_company": True,
            "email": "contacto@empresademo.cl",
            "phone": "+56 2 2345 6789",
            "street": "Av. Providencia 1234",
            "city": "Santiago",
            "country_id": _get_country_id(rpc, "CL"),
            "customer_rank": 1,
        },
    )

    # ------------------------------------------------------------------
    # 2. Create Service Specifications + Resource Specifications
    # ------------------------------------------------------------------
    log.info("=" * 60)
    log.info("STEP 2: Creating Service & Resource Specifications")
    log.info("=" * 60)

    svc_spec_ids = {}
    res_spec_ids = {}

    for svc_key, catalog in SERVICE_CATALOG.items():
        # Service Specification
        svc_spec_id, _ = rpc.find_or_create(
            "tmf.service.specification",
            [("name", "=", catalog["svc_spec"])],
            {
                "name": catalog["svc_spec"],
                "description": f"Customer-facing {svc_key} service",
                "lifecycle_status": "active",
                "version": "1.0",
            },
        )
        svc_spec_ids[svc_key] = svc_spec_id

        # Resource Specification
        res_spec_id, _ = rpc.find_or_create(
            "tmf.resource.specification",
            [("name", "=", catalog["res_spec"])],
            {
                "name": catalog["res_spec"],
                "description": f"Device: {catalog['device']}",
                "lifecycle_status": "active",
                "version": "1.0",
            },
        )
        res_spec_ids[svc_key] = res_spec_id

    # ------------------------------------------------------------------
    # 3. Create Product Specifications (linking svc + res specs)
    # ------------------------------------------------------------------
    log.info("=" * 60)
    log.info("STEP 3: Creating Product Specifications")
    log.info("=" * 60)

    prod_spec_ids = {}
    for svc_key, catalog in SERVICE_CATALOG.items():
        spec_id, created = rpc.find_or_create(
            "tmf.product.specification",
            [("name", "=", catalog["product_spec"])],
            {
                "name": catalog["product_spec"],
                "lifecycle_status": "active",
            },
        )
        prod_spec_ids[svc_key] = spec_id

        # Link service + resource specifications via Many2many
        if created:
            try:
                rpc.write("tmf.product.specification", [spec_id], {
                    "service_specification_ids": [(4, svc_spec_ids[svc_key])],
                    "resource_specification_ids": [(4, res_spec_ids[svc_key])],
                })
                log.info("    Linked specs to %s", catalog["product_spec"])
            except Exception as e:
                log.warning("    Could not link specs (fields may not exist): %s", e)

    # ------------------------------------------------------------------
    # 4. Create Product Offerings (product.template) with prices
    # ------------------------------------------------------------------
    log.info("=" * 60)
    log.info("STEP 4: Creating Product Offerings")
    log.info("=" * 60)

    offering_ids = {}  # name -> product.template id
    for svc_key, catalog in SERVICE_CATALOG.items():
        for offering_name, price in catalog["offerings"]:
            tmpl_id, created = rpc.find_or_create(
                "product.template",
                [("name", "=", offering_name)],
                {
                    "name": offering_name,
                    "list_price": price,
                    "type": "service",
                    "sale_ok": True,
                    "purchase_ok": False,
                },
            )
            offering_ids[offering_name] = tmpl_id

            # Link to product specification
            if created:
                try:
                    rpc.write("product.template", [tmpl_id], {
                        "product_specification_id": prod_spec_ids[svc_key],
                    })
                    log.info("    Linked %s -> %s", offering_name, catalog["product_spec"])
                except Exception as e:
                    log.warning("    Could not link spec: %s", e)

    # ------------------------------------------------------------------
    # 5. Create Accounts (PartyAccount + BillingAccount per location)
    # ------------------------------------------------------------------
    log.info("=" * 60)
    log.info("STEP 5: Creating Accounts")
    log.info("=" * 60)

    account_data = []
    for acct_def in ACCOUNTS:
        # PartyAccount
        party_acct_id, _ = rpc.find_or_create(
            "tmf.account",
            [("name", "=", f"Empresa Demo SpA - {acct_def['name']}"),
             ("resource_type", "=", "PartyAccount")],
            {
                "name": f"Empresa Demo SpA - {acct_def['name']}",
                "resource_type": "PartyAccount",
                "partner_id": partner_id,
                "state": "active",
                "description": acct_def["address"],
            },
        )

        # BillingAccount
        billing_acct_id, _ = rpc.find_or_create(
            "tmf.account",
            [("name", "=", f"Billing - {acct_def['name']}"),
             ("resource_type", "=", "BillingAccount")],
            {
                "name": f"Billing - {acct_def['name']}",
                "resource_type": "BillingAccount",
                "partner_id": partner_id,
                "state": "active",
                "description": f"Billing for {acct_def['address']}",
            },
        )

        account_data.append({
            "def": acct_def,
            "party_account_id": party_acct_id,
            "billing_account_id": billing_acct_id,
        })

    # ------------------------------------------------------------------
    # 6. Create Sale Orders per Account and Confirm
    # ------------------------------------------------------------------
    log.info("=" * 60)
    log.info("STEP 6: Creating & Confirming Sale Orders")
    log.info("=" * 60)

    for acct in account_data:
        acct_def = acct["def"]
        acct_name = acct_def["name"]
        party_acct_id = acct["party_account_id"]

        log.info("--- Account: %s ---", acct_name)

        # Build order lines
        order_lines = []
        for svc_key in acct_def["services"]:
            offering_name = acct_def["offering_picks"][svc_key]
            tmpl_id = offering_ids[offering_name]

            # Get product.product id from product.template
            product_ids = rpc.search("product.product", [("product_tmpl_id", "=", tmpl_id)], limit=1)
            if not product_ids:
                log.warning("  No product.product found for template %s, skipping", offering_name)
                continue

            order_lines.append((0, 0, {
                "product_id": product_ids[0],
                "product_uom_qty": 1,
            }))
            log.info("  + %s", offering_name)

        if not order_lines:
            log.warning("  No order lines for %s, skipping", acct_name)
            continue

        # Create sale order
        so_vals = {
            "partner_id": partner_id,
            "order_line": order_lines,
        }

        # Try to set tmf_account_id (from provisioning bridge) — may not exist yet
        try:
            so_vals["tmf_account_id"] = party_acct_id
            so_id = rpc.create("sale.order", so_vals)
        except Exception:
            log.warning("  tmf_account_id not available, creating SO without account link")
            del so_vals["tmf_account_id"]
            so_id = rpc.create("sale.order", so_vals)
        log.info("  Created SO id=%s", so_id)

        # Read SO name
        so_data = rpc.search_read("sale.order", [("id", "=", so_id)], ["name"], limit=1)
        so_name = so_data[0]["name"] if so_data else f"SO#{so_id}"

        # Confirm the sale order
        try:
            rpc.execute("sale.order", "action_confirm", [so_id])
            log.info("  Confirmed %s -> services will be provisioned", so_name)
        except Exception as e:
            log.error("  Failed to confirm %s: %s", so_name, e)

    # ------------------------------------------------------------------
    # 7. Create Resource (device) records in inventory
    # ------------------------------------------------------------------
    log.info("=" * 60)
    log.info("STEP 7: Creating Device Resources in Inventory")
    log.info("=" * 60)

    # Find the services we just created
    services = rpc.search_read(
        "tmf.service",
        [("partner_id", "=", partner_id)],
        ["id", "name", "state", "account_id", "tmf_id"],
    )
    log.info("Found %d services for Empresa Demo SpA", len(services))

    for svc in services:
        # Determine which service type this is
        svc_name = svc["name"]
        device_name = None
        for svc_key, catalog in SERVICE_CATALOG.items():
            if catalog["svc_spec"] in svc_name:
                device_name = catalog["device"]
                res_spec_name = catalog["res_spec"]
                break

        if not device_name:
            continue

        # Create a stock.lot (serial number) as the device
        serial = f"SN-{svc['tmf_id'][:8].upper()}" if svc.get("tmf_id") else f"SN-SVC{svc['id']}"

        # Find the product for this device (resource spec creates one)
        device_product = rpc.search(
            "product.product",
            [("name", "ilike", device_name)],
            limit=1,
        )
        if not device_product:
            # Create a storable product for the device
            tmpl_id = rpc.create("product.template", {
                "name": device_name,
                "type": "consu",
                "sale_ok": False,
                "purchase_ok": True,
                "list_price": 0,
            })
            device_product = rpc.search("product.product", [("product_tmpl_id", "=", tmpl_id)], limit=1)
            log.info("  Created device product: %s", device_name)

        if device_product:
            # Create lot/serial
            try:
                lot_id, created = rpc.find_or_create(
                    "stock.lot",
                    [("name", "=", serial), ("product_id", "=", device_product[0])],
                    {
                        "name": serial,
                        "product_id": device_product[0],
                        "company_id": 1,
                    },
                )
                if created:
                    # Link device to service
                    rpc.write("tmf.service", [svc["id"]], {"resource_id": lot_id})
                    log.info("  Linked device %s -> service %s", serial, svc_name)
            except Exception as e:
                log.warning("  Could not create lot for %s: %s", device_name, e)

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    log.info("=" * 60)
    log.info("SEED COMPLETE")
    log.info("=" * 60)
    log.info("Customer: Empresa Demo SpA (RUT 76.123.456-7)")
    log.info("Accounts: %d", len(ACCOUNTS))
    for acct_def in ACCOUNTS:
        log.info("  - %s: %s", acct_def["name"], ", ".join(acct_def["services"]))
    log.info("")
    log.info("Services are in 'feasabilityChecked' state.")
    log.info("Run the mock OSS to advance them:")
    log.info("  python oss_provisioner.py --host localhost --port 8069")


def _get_country_id(rpc, code):
    """Get country id by ISO code."""
    ids = rpc.search("res.country", [("code", "=", code)], limit=1)
    return ids[0] if ids else False


def main():
    parser = argparse.ArgumentParser(description="Seed demo telecom data into Odoo")
    parser.add_argument("--host", default=os.getenv("OSS_HOST", "localhost"))
    parser.add_argument("--port", default=int(os.getenv("OSS_PORT", "8069")), type=int)
    parser.add_argument("--db", default=os.getenv("ODOO_DB", "TMF_Odoo_DB"))
    parser.add_argument("--user", default=os.getenv("ODOO_USER", "admin"))
    parser.add_argument("--password", default=os.getenv("ODOO_PASSWORD", "admin"))
    args = parser.parse_args()

    rpc = OdooRPC(args.host, args.port, args.db, args.user, args.password)
    rpc.authenticate()
    seed(rpc)


if __name__ == "__main__":
    main()
