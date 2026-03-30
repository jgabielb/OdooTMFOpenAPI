import logging
import re

from odoo import api, models


_logger = logging.getLogger(__name__)


class TMFUiNormalizer(models.AbstractModel):
    _name = "tmf.ui.normalizer"
    _description = "TMF UI Label Normalizer"

    _ACRONYMS = {
        "api": "API",
        "apis": "APIs",
        "tmf": "TMF",
        "ctk": "CTK",
        "sla": "SLA",
        "ai": "AI",
        "iot": "IoT",
        "id": "ID",
        "ids": "IDs",
        "5g": "5G",
    }
    _DOMAIN_MENUS = [
        ("catalog", "Catalog"),
        ("customer_party", "Customer & Party"),
        ("orders_sales", "Orders & Sales"),
        ("inventory_resource", "Inventory & Resource"),
        ("assurance", "Assurance"),
        ("billing_revenue", "Billing & Revenue"),
        ("testing_quality", "Testing & Quality"),
        ("platform_identity", "Platform & Identity"),
        ("other", "Other"),
    ]
    _MODULE_DOMAIN_MAP = {
        "tmf_account": "billing_revenue",
        "tmf_customer_bill_management": "billing_revenue",
        "tmf_prepay_balance_management": "billing_revenue",
        "tmf_usage": "billing_revenue",
        "tmf_usage_consumption": "billing_revenue",
        "tmf_recommendation_management": "orders_sales",
        "tmf_quote_management": "orders_sales",
        "tmf_product_ordering": "orders_sales",
        "tmf_shopping_cart": "orders_sales",
        "tmf_base": "platform_identity",
        "tmf_service_activation_configuration": "assurance",
        "tmf_userinfo": "platform_identity",
        "tmf_private_optimized_binding": "platform_identity",
        "tmf_iot_agent_device_management": "platform_identity",
        "tmf_iot_service_management": "platform_identity",
    }

    @api.model
    def _normalize_label(self, label):
        if not label:
            return label

        text = str(label).strip()
        if not text:
            return label

        # Remove noisy TMF numeric prefixes/suffixes from UI labels.
        text = re.sub(r"\(\s*TMF\d+\s*\)", "", text, flags=re.IGNORECASE)
        text = re.sub(r"^\s*TMF\d+\s*", "", text, flags=re.IGNORECASE)

        # Split camelCase / PascalCase and normalize separators.
        text = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", text)
        text = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", text)
        text = text.replace("_", " ")
        text = re.sub(r"\s+", " ", text).strip(" -")

        words = []
        for raw in text.split(" "):
            token = raw.strip()
            if not token:
                continue

            lower = token.lower()
            if lower in self._ACRONYMS:
                words.append(self._ACRONYMS[lower])
            elif token.isupper() and len(token) <= 4:
                words.append(token)
            else:
                words.append(token.capitalize())

        normalized = " ".join(words)

        # Common phrase fixups.
        normalized = normalized.replace("AP Is", "APIs")
        normalized = normalized.replace("Io T", "IoT")
        normalized = normalized.replace("Open Apis", "Open APIs")
        normalized = normalized.replace("Open AP Is", "Open APIs")

        return normalized or label

    @api.model
    def _normalize_ui_records(self):
        imd = self.env["ir.model.data"].sudo()
        menu_model = self.env["ir.ui.menu"].sudo()
        action_model = self.env["ir.actions.act_window"].sudo()

        menu_imd = imd.search([
            ("model", "=", "ir.ui.menu"),
            ("module", "like", "tmf_%"),
        ])
        action_imd = imd.search([
            ("model", "=", "ir.actions.act_window"),
            ("module", "like", "tmf_%"),
        ])

        menu_ids = {rec.res_id for rec in menu_imd if rec.res_id}
        action_ids = {rec.res_id for rec in action_imd if rec.res_id}

        changed_menus = 0
        for menu in menu_model.browse(list(menu_ids)).exists():
            normalized = self._normalize_label(menu.name)
            if normalized and normalized != menu.name:
                menu.write({"name": normalized})
                changed_menus += 1

        changed_actions = 0
        for action in action_model.browse(list(action_ids)).exists():
            normalized = self._normalize_label(action.name)
            if normalized and normalized != action.name:
                action.write({"name": normalized})
                changed_actions += 1

        _logger.info(
            "TMF UI normalization completed: %s menus, %s actions updated",
            changed_menus,
            changed_actions,
        )

    @api.model
    def _tmf_model_names(self):
        model_rows = self.env["ir.model"].sudo().search([("model", "like", "tmf.%")])
        return {m.model for m in model_rows}

    @api.model
    def _field_names(self, model_name):
        if model_name not in self.env.registry:
            return set()
        return set(self.env[model_name]._fields.keys())

    @api.model
    def _create_filter_if_missing(self, model_name, name, domain):
        filters = self.env["ir.filters"].sudo()
        filters_fields = set(filters._fields.keys())
        search_domain = [
            ("model_id", "=", model_name),
            ("name", "=", name),
        ]
        if "user_id" in filters_fields:
            search_domain.append(("user_id", "=", False))

        existing = filters.search(search_domain, limit=1)
        if existing:
            return False

        create_vals = {
            "name": name,
            "model_id": model_name,
            "domain": domain,
            "sort": "[]",
        }
        if "user_id" in filters_fields:
            create_vals["user_id"] = False
        if "is_default" in filters_fields:
            create_vals["is_default"] = False

        filters.create(create_vals)
        return True

    @api.model
    def _ensure_shared_tmf_filters(self):
        created = 0
        for model_name in self._tmf_model_names():
            field_names = self._field_names(model_name)

            if "create_uid" in field_names:
                if self._create_filter_if_missing(
                    model_name, "My Records", "[('create_uid', '=', uid)]"
                ):
                    created += 1

            if "create_date" in field_names:
                if self._create_filter_if_missing(
                    model_name,
                    "Last 30 Days",
                    "[('create_date', '>=', (context_today() - relativedelta(days=30)).strftime('%Y-%m-%d 00:00:00'))]",
                ):
                    created += 1

            if "lifecycle_status" in field_names:
                lifecycle_filters = [
                    ("In Design", "[('lifecycle_status', '=', 'design')]"),
                    ("Active", "[('lifecycle_status', '=', 'active')]"),
                    ("Retired", "[('lifecycle_status', '=', 'retired')]"),
                ]
                for name, domain in lifecycle_filters:
                    if self._create_filter_if_missing(model_name, name, domain):
                        created += 1

            if "status" in field_names:
                if self._create_filter_if_missing(
                    model_name, "Status Set", "[('status', '!=', False)]"
                ):
                    created += 1

            if "state" in field_names:
                if self._create_filter_if_missing(
                    model_name, "State Set", "[('state', '!=', False)]"
                ):
                    created += 1

        _logger.info("TMF shared filters ensured: %s created", created)

    @api.model
    def _ensure_action_help(self):
        imd = self.env["ir.model.data"].sudo()
        action_model = self.env["ir.actions.act_window"].sudo()
        action_imd = imd.search(
            [
                ("model", "=", "ir.actions.act_window"),
                ("module", "like", "tmf_%"),
            ]
        )
        action_ids = {rec.res_id for rec in action_imd if rec.res_id}
        updated = 0
        for action in action_model.browse(list(action_ids)).exists():
            if action.help:
                continue
            label = self._normalize_label(action.name or "record")
            action.write(
                {
                    "help": (
                        '<p class="o_view_nocontent_smiling_face">'
                        f"Create your first {label}."
                        "</p>"
                        "<p>Use TMF APIs or the Odoo UI to manage these records.</p>"
                    )
                }
            )
            updated += 1
        _logger.info("TMF action help updated: %s", updated)

    @api.model
    def _get_tmf_root_menu(self):
        root = self.env.ref("tmf_product_catalog.menu_tmf_root", raise_if_not_found=False)
        if root:
            return root
        return self.env.ref("tmf_base.menu_tmf_root", raise_if_not_found=False)

    @api.model
    def _get_or_create_domain_menu(self, root_menu, key, label):
        menu_model = self.env["ir.ui.menu"].sudo()
        domain = [
            ("parent_id", "=", root_menu.id),
            ("name", "=", label),
        ]
        rec = menu_model.search(domain, limit=1)
        if rec:
            return rec
        sequence = 20 + (10 * [k for k, _ in self._DOMAIN_MENUS].index(key))
        return menu_model.create(
            {
                "name": label,
                "parent_id": root_menu.id,
                "sequence": sequence,
            }
        )

    @api.model
    def _guess_menu_domain_key(self, menu_name, module_name=None):
        if module_name and module_name in self._MODULE_DOMAIN_MAP:
            return self._MODULE_DOMAIN_MAP[module_name]

        name = (menu_name or "").lower()
        compact = re.sub(r"[^a-z0-9]", "", name)

        if any(k in name for k in ["catalog", "specification", "offering", "product usage"]):
            return "catalog"
        if any(k in name for k in ["customer", "party", "agreement", "role", "interaction", "privacy"]):
            return "customer_party"
        if any(k in name for k in ["order", "quote", "sales", "shopping cart", "promotion", "appointment"]):
            return "orders_sales"
        if any(
            k in name
            for k in [
                "inventory",
                "resource",
                "stock",
                "shipment",
                "shipping",
                "geographic",
                "device",
                "entity",
                "reservation",
                "pool",
            ]
        ):
            return "inventory_resource"
        if any(
            k in name
            for k in [
                "alarm",
                "incident",
                "trouble",
                "problem",
                "outage",
                "risk",
                "qualification",
                "performance",
                "monitor",
            ]
        ):
            return "assurance"
        if any(k in name for k in ["payment", "bill", "billing", "cost", "revenue", "dunning", "balance", "cdr"]):
            return "billing_revenue"
        if any(
            k in name
            for k in ["test", "scenario", "execution", "environment", "artifact", "quality", "service level"]
        ):
            return "testing_quality"
        if any(
            k in name
            for k in [
                "identity",
                "permission",
                "userinfo",
                "open gateway",
                "intent",
                "ai",
                "process flow",
                "communication",
                "self care",
                "network as a service",
                "installed services",
            ]
        ):
            return "platform_identity"
        if any(k in compact for k in ["iot", "opengateway", "5g", "dcs5g"]):
            return "platform_identity"
        return "other"

    @api.model
    def _group_tmf_menus(self):
        root = self._get_tmf_root_menu()
        if not root:
            _logger.info("TMF root menu not found; skipping domain grouping")
            return

        imd = self.env["ir.model.data"].sudo()
        menu_model = self.env["ir.ui.menu"].sudo()

        tmf_menu_imd = imd.search(
            [
                ("model", "=", "ir.ui.menu"),
                ("module", "like", "tmf_%"),
            ]
        )
        tmf_menu_ids = {rec.res_id for rec in tmf_menu_imd if rec.res_id}
        menu_module_map = {rec.res_id: rec.module for rec in tmf_menu_imd if rec.res_id and rec.module}
        if not tmf_menu_ids:
            return

        # Build/get domain buckets first.
        buckets = {
            key: self._get_or_create_domain_menu(root, key, label)
            for key, label in self._DOMAIN_MENUS
        }
        bucket_ids = {m.id for m in buckets.values()}

        # Re-parent TMF menus directly under TMF root OR any domain bucket.
        moved = 0
        reclass_parents = [root.id] + list(bucket_ids)
        candidate_menus = menu_model.search([("parent_id", "in", reclass_parents)])
        for menu in candidate_menus:
            if menu.id in bucket_ids:
                continue
            if menu.id not in tmf_menu_ids:
                continue

            key = self._guess_menu_domain_key(menu.name, menu_module_map.get(menu.id))
            target = buckets.get(key) or buckets["other"]
            if menu.parent_id.id != target.id:
                menu.write({"parent_id": target.id})
                moved += 1

        _logger.info("TMF menu domain grouping completed: %s menus moved", moved)

    @api.model
    def _sequence_tmf_domain_menus(self):
        root = self._get_tmf_root_menu()
        if not root:
            return

        menu_model = self.env["ir.ui.menu"].sudo()
        sequenced = 0

        # Enforce domain bucket order.
        for idx, (_, label) in enumerate(self._DOMAIN_MENUS, start=1):
            bucket = menu_model.search(
                [("parent_id", "=", root.id), ("name", "=", label)],
                limit=1,
            )
            if not bucket:
                continue
            target_seq = idx * 10
            if bucket.sequence != target_seq:
                bucket.write({"sequence": target_seq})
                sequenced += 1

            # Alphabetize submenus under each bucket.
            children = menu_model.search(
                [("parent_id", "=", bucket.id)],
                order="name asc, id asc",
            )
            for child_idx, child in enumerate(children, start=1):
                child_seq = child_idx * 10
                if child.sequence != child_seq:
                    child.write({"sequence": child_seq})
                    sequenced += 1

        _logger.info("TMF menu sequencing completed: %s menus updated", sequenced)

    def _register_hook(self):
        res = super()._register_hook()
        try:
            self._normalize_ui_records()
            self._group_tmf_menus()
            self._sequence_tmf_domain_menus()
            self._ensure_action_help()
            self._ensure_shared_tmf_filters()
        except Exception:
            _logger.exception("TMF UI normalization failed")
        return res
