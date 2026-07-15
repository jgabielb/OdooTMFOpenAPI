import json

from odoo import api, fields, models


def _resolve_ids(env, model, items, id_field="tmf_id"):
    """Batch-search model by tmf_id for all item dicts. Returns list of record IDs."""
    ref_ids = []
    for item in (items or []):
        if not isinstance(item, dict):
            continue
        ref_id = str(item.get("id") or "").strip()
        if ref_id:
            ref_ids.append(ref_id)
    if not ref_ids:
        return []
    return env[model].sudo().search([(id_field, "in", ref_ids)]).ids


def _refs_contain(items, ref_id):
    """True when any dict entry in a TMF ref list carries the given id."""
    for item in (items or []):
        if isinstance(item, dict) and str(item.get("id") or "").strip() == ref_id:
            return True
    return False


PARTY_ROLE_TYPES = ("PartyRole", "PartyRoleRef")

PLACE_TYPE_MODELS = {
    "GeographicAddress": "tmf.geographic.address",
    "GeographicAddressRef": "tmf.geographic.address",
    "GeographicSite": "tmf.geographic.site",
    "GeographicSiteRef": "tmf.geographic.site",
    "GeographicLocation": "tmf.geographic.location",
    "GeographicLocationRef": "tmf.geographic.location",
}

PLACE_FIELD_MODELS = (
    ("geographic_address_id", "tmf.geographic.address"),
    ("geographic_site_id", "tmf.geographic.site"),
    ("geographic_location_id", "tmf.geographic.location"),
)


class ProductOfferingTMFC001Wiring(models.Model):
    """TMFC001 dependent API wiring for ProductOffering (product.template)."""
    _inherit = "product.template"

    # Raw JSON storage (carries the wire-format payload for cross-API refs)
    related_party_json = fields.Json(default=list, string="Related Parties JSON (TMF632/669)")
    place_json = fields.Json(default=list, string="Place refs JSON (TMF673/674/675)")
    agreement_json = fields.Json(default=list, string="Agreement refs JSON (TMF651)")
    agreement_specification_json = fields.Json(
        default=list, string="Agreement Spec refs JSON (TMF651)")
    service_specification_json = fields.Json(default=list, string="Service Spec refs JSON (TMF633)")
    resource_specification_json = fields.Json(default=list, string="Resource Spec refs JSON (TMF634)")
    # TMF662: holds EntitySpecificationRef and AssociationSpecificationRef entries;
    # only entitySpecification resolves relationally (no local associationSpecification model).
    entity_specification_json = fields.Json(
        default=list, string="Entity/Association Spec refs JSON (TMF662)")

    # Resolved relational fields (populated by _resolve_tmf_refs)
    related_partner_ids = fields.Many2many(
        "res.partner", "tmf_offering_partner_rel",
        "offering_id", "partner_id", string="Related Parties (TMF632)"
    )
    related_party_role_ids = fields.Many2many(
        "tmf.party.role", "tmf_offering_party_role_rel",
        "offering_id", "role_id", string="Party Roles (TMF669)"
    )
    service_specification_ids = fields.Many2many(
        "tmf.service.specification", "tmf_offering_service_spec_rel",
        "offering_id", "spec_id", string="Service Specifications (TMF633)"
    )
    resource_specification_ids = fields.Many2many(
        "tmf.resource.specification", "tmf_offering_resource_spec_rel",
        "offering_id", "spec_id", string="Resource Specifications (TMF634)"
    )
    agreement_ids = fields.Many2many(
        "tmf.agreement", "tmf_offering_agreement_rel",
        "offering_id", "agreement_id", string="Agreements (TMF651)"
    )
    agreement_specification_ids = fields.Many2many(
        "tmf.agreement.specification", "tmf_offering_agreement_spec_rel",
        "offering_id", "spec_id", string="Agreement Specifications (TMF651)"
    )
    entity_specification_ids = fields.Many2many(
        "tmf.entity.specification", "tmf_offering_entity_spec_rel",
        "offering_id", "spec_id", string="Entity Specifications (TMF662)"
    )
    geographic_address_id = fields.Many2one(
        "tmf.geographic.address", string="Geographic Address (TMF673)",
        index=True, ondelete="set null"
    )
    geographic_site_id = fields.Many2one(
        "tmf.geographic.site", string="Geographic Site (TMF674)",
        index=True, ondelete="set null"
    )
    geographic_location_id = fields.Many2one(
        "tmf.geographic.location", string="Geographic Location (TMF675)",
        index=True, ondelete="set null"
    )

    # (json_field, m2m_field, target model) pairs resolved 1:1 by tmf_id
    _TMFC001_SIMPLE_REFS = (
        ("service_specification_json", "service_specification_ids", "tmf.service.specification"),
        ("resource_specification_json", "resource_specification_ids", "tmf.resource.specification"),
        ("agreement_json", "agreement_ids", "tmf.agreement"),
        ("agreement_specification_json", "agreement_specification_ids",
         "tmf.agreement.specification"),
        ("entity_specification_json", "entity_specification_ids", "tmf.entity.specification"),
    )

    _TMFC001_WIRING_KEYS = frozenset((
        "related_party_json", "place_json", "agreement_json", "agreement_specification_json",
        "service_specification_json", "resource_specification_json", "entity_specification_json",
    ))

    def _resolve_tmf_refs(self, changed_keys=None):
        """Rebuild relational links from the raw TMF JSON refs.

        JSON is the source of truth: when a JSON field was explicitly written
        (its key is in ``changed_keys``) the matching relational field is rebuilt
        even if that clears it. When called without ``changed_keys`` (record
        creation, bulk reconciliation) empty JSON leaves relational links
        untouched so manually curated links survive.
        """
        ctx = {"skip_tmf_wiring": True}
        for rec in self:
            updates = {}

            def _rebuild(json_field, m2m_field, model, items=None):
                data = rec[json_field] or []
                if not data and (changed_keys is None or json_field not in changed_keys):
                    return
                if items is None:
                    items = [i for i in data if isinstance(i, dict)]
                ids = _resolve_ids(self.env, model, items)
                if set(ids) != set(rec[m2m_field].ids):
                    updates[m2m_field] = [(6, 0, ids)]

            # TMF632 relatedParty → res.partner / TMF669 partyRole entries → tmf.party.role
            party_data = [i for i in (rec.related_party_json or []) if isinstance(i, dict)]
            _rebuild("related_party_json", "related_partner_ids", "res.partner",
                     [i for i in party_data if i.get("@type") not in PARTY_ROLE_TYPES])
            _rebuild("related_party_json", "related_party_role_ids", "tmf.party.role",
                     [i for i in party_data if i.get("@type") in PARTY_ROLE_TYPES])

            for json_field, m2m_field, model in self._TMFC001_SIMPLE_REFS:
                _rebuild(json_field, m2m_field, model)

            # TMF673/674/675 place → one Many2one per geographic model (first match)
            place = rec.place_json or []
            if place or (changed_keys and "place_json" in changed_keys):
                buckets = {model: [] for _, model in PLACE_FIELD_MODELS}
                for item in place:
                    if not isinstance(item, dict):
                        continue
                    ref_id = str(item.get("id") or "").strip()
                    model = PLACE_TYPE_MODELS.get(item.get("@type", ""))
                    if ref_id and model:
                        buckets[model].append(ref_id)
                for m2o_field, model in PLACE_FIELD_MODELS:
                    ids = buckets[model]
                    match = (self.env[model].sudo().search([("tmf_id", "in", ids)], limit=1)
                             if ids else self.env[model].sudo())
                    new_id = match.id if match else False
                    if ids and not match and (changed_keys is None
                                              or "place_json" not in changed_keys):
                        continue  # unresolvable yet; keep whatever is there
                    if new_id != rec[m2o_field].id:
                        updates[m2o_field] = new_id

            if updates:
                rec.with_context(**ctx).write(updates)

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        if not self.env.context.get("skip_tmf_wiring"):
            recs._resolve_tmf_refs()
        return recs

    def write(self, vals):
        res = super().write(vals)
        if not self.env.context.get("skip_tmf_wiring"):
            changed = self._TMFC001_WIRING_KEYS & set(vals.keys())
            if changed:
                self._resolve_tmf_refs(changed_keys=changed)
        return res


class ProductSpecificationTMFC001Wiring(models.Model):
    """TMFC001 dependent API wiring for ProductSpecification (tmf.product.specification)."""
    _inherit = "tmf.product.specification"

    related_party_json = fields.Json(default=list, string="Related Parties JSON (TMF632)")
    service_specification_json = fields.Json(default=list, string="Service Spec refs JSON (TMF633)")
    resource_specification_json = fields.Json(default=list, string="Resource Spec refs JSON (TMF634)")
    entity_specification_json = fields.Json(
        default=list, string="Entity/Association Spec refs JSON (TMF662)")

    related_partner_ids = fields.Many2many(
        "res.partner", "tmf_product_spec_partner_rel",
        "spec_id", "partner_id", string="Related Parties (TMF632)"
    )
    service_specification_ids = fields.Many2many(
        "tmf.service.specification", "tmf_product_spec_service_spec_rel",
        "spec_id", "svc_id", string="Service Specifications (TMF633)"
    )
    resource_specification_ids = fields.Many2many(
        "tmf.resource.specification", "tmf_product_spec_resource_spec_rel",
        "spec_id", "res_id", string="Resource Specifications (TMF634)"
    )
    entity_specification_ids = fields.Many2many(
        "tmf.entity.specification", "tmf_product_spec_entity_spec_rel",
        "spec_id", "ent_id", string="Entity Specifications (TMF662)"
    )

    _TMFC001_SIMPLE_REFS = (
        ("related_party_json", "related_partner_ids", "res.partner"),
        ("service_specification_json", "service_specification_ids", "tmf.service.specification"),
        ("resource_specification_json", "resource_specification_ids", "tmf.resource.specification"),
        ("entity_specification_json", "entity_specification_ids", "tmf.entity.specification"),
    )

    _TMFC001_WIRING_KEYS = frozenset((
        "related_party_json", "service_specification_json", "resource_specification_json",
        "entity_specification_json",
    ))

    def _resolve_tmf_refs(self, changed_keys=None):
        """Rebuild relational links from raw TMF JSON refs (see ProductOffering wiring)."""
        ctx = {"skip_tmf_wiring": True}
        for rec in self:
            updates = {}
            for json_field, m2m_field, model in self._TMFC001_SIMPLE_REFS:
                data = rec[json_field] or []
                if not data and (changed_keys is None or json_field not in changed_keys):
                    continue
                ids = _resolve_ids(self.env, model,
                                   [i for i in data if isinstance(i, dict)])
                if set(ids) != set(rec[m2m_field].ids):
                    updates[m2m_field] = [(6, 0, ids)]
            if updates:
                rec.with_context(**ctx).write(updates)

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        if not self.env.context.get("skip_tmf_wiring"):
            recs._resolve_tmf_refs()
        return recs

    def write(self, vals):
        res = super().write(vals)
        if not self.env.context.get("skip_tmf_wiring"):
            changed = self._TMFC001_WIRING_KEYS & set(vals.keys())
            if changed:
                self._resolve_tmf_refs(changed_keys=changed)
        return res


class TMFC001WiringTools(models.AbstractModel):
    _name = "tmfc001.wiring.tools"
    _description = "TMFC001 Wiring Reconciliation Tools"

    def _loads(self, value):
        if not value:
            return None
        if isinstance(value, (dict, list)):
            return value
        try:
            return json.loads(value)
        except Exception:
            return None

    def _extract_event_resource(self, payload):
        if not isinstance(payload, dict):
            return {}
        if isinstance(payload.get("event"), dict):
            event = payload["event"]
            if isinstance(event.get("resource"), dict):
                return event["resource"]
            # TMF event envelopes may key the resource by its type name
            for value in event.values():
                if isinstance(value, dict) and value.get("id"):
                    return value
        if isinstance(payload.get("resource"), dict):
            return payload["resource"]
        return payload

    def _extract_resource_id(self, payload):
        resource = self._extract_event_resource(payload)
        ref_id = str(resource.get("id") or payload.get("id") or "").strip()
        return ref_id

    # ------------------------------------------------------------------
    # Generic reconciliation
    # ------------------------------------------------------------------

    def _referencing_records(self, model_name, json_field, m2m_field, ref_id):
        """Records linking ref_id through the relational field or the raw JSON."""
        Model = self.env[model_name].sudo().with_context(active_test=False)
        recs = Model.search([(m2m_field + ".tmf_id", "=", ref_id)])
        candidates = Model.search([(json_field, "!=", False)]) - recs
        recs |= candidates.filtered(lambda r: _refs_contain(r[json_field], ref_id))
        return recs

    def _reconcile_simple(self, ref_model, ref_id, targets):
        """Re-resolve (resource exists) or prune (resource deleted) TMF refs.

        targets: iterable of (model_name, json_field, m2m_field).
        """
        exists = bool(self.env[ref_model].sudo().search([("tmf_id", "=", ref_id)], limit=1))
        for model_name, json_field, m2m_field in targets:
            recs = self._referencing_records(model_name, json_field, m2m_field, ref_id)
            if exists:
                recs._resolve_tmf_refs(changed_keys={json_field})
                continue
            for rec in recs:
                json_refs = [item for item in (rec[json_field] or [])
                             if str((item or {}).get("id") or "").strip() != ref_id]
                kept = rec[m2m_field].filtered(lambda r: (r.tmf_id or str(r.id)) != ref_id)
                rec.with_context(skip_tmf_wiring=True).write({
                    m2m_field: [(6, 0, kept.ids)],
                    json_field: json_refs,
                })

    # ------------------------------------------------------------------
    # Event handlers (invoked from the TMFC001 listener routes)
    # ------------------------------------------------------------------

    def _reconcile_service_specification_refs(self, payload=None):
        ref_id = self._extract_resource_id(payload or {})
        if not ref_id:
            return
        self._reconcile_simple("tmf.service.specification", ref_id, (
            ("product.template", "service_specification_json", "service_specification_ids"),
            ("tmf.product.specification", "service_specification_json",
             "service_specification_ids"),
        ))

    def _reconcile_resource_specification_refs(self, payload=None):
        ref_id = self._extract_resource_id(payload or {})
        if not ref_id:
            return
        self._reconcile_simple("tmf.resource.specification", ref_id, (
            ("product.template", "resource_specification_json", "resource_specification_ids"),
            ("tmf.product.specification", "resource_specification_json",
             "resource_specification_ids"),
        ))

    def _reconcile_entity_specification_refs(self, payload=None):
        ref_id = self._extract_resource_id(payload or {})
        if not ref_id:
            return
        self._reconcile_simple("tmf.entity.specification", ref_id, (
            ("product.template", "entity_specification_json", "entity_specification_ids"),
            ("tmf.product.specification", "entity_specification_json",
             "entity_specification_ids"),
        ))

    def _reconcile_related_party_refs(self, payload=None):
        """TMF632 individual/organization delete events: prune party links."""
        ref_id = self._extract_resource_id(payload or {})
        if not ref_id:
            return
        for model_name in ("product.template", "tmf.product.specification"):
            Model = self.env[model_name].sudo().with_context(active_test=False)
            recs = Model.search([("related_partner_ids.tmf_id", "=", ref_id)])
            candidates = Model.search([("related_party_json", "!=", False)]) - recs
            recs |= candidates.filtered(lambda r: any(
                isinstance(i, dict)
                and str(i.get("id") or "").strip() == ref_id
                and i.get("@type") not in PARTY_ROLE_TYPES
                for i in (r.related_party_json or [])
            ))
            for rec in recs:
                json_refs = [item for item in (rec.related_party_json or [])
                             if not (isinstance(item, dict)
                                     and str(item.get("id") or "").strip() == ref_id
                                     and item.get("@type") not in PARTY_ROLE_TYPES)]
                kept = rec.related_partner_ids.filtered(
                    lambda p: (p.tmf_id or str(p.id)) != ref_id)
                rec.with_context(skip_tmf_wiring=True).write({
                    "related_partner_ids": [(6, 0, kept.ids)],
                    "related_party_json": json_refs,
                })

    def _reconcile_party_role_refs(self, payload=None):
        """TMF669 partyRole delete events: prune role links on offerings."""
        ref_id = self._extract_resource_id(payload or {})
        if not ref_id:
            return
        Model = self.env["product.template"].sudo().with_context(active_test=False)
        recs = Model.search([("related_party_role_ids.tmf_id", "=", ref_id)])
        candidates = Model.search([("related_party_json", "!=", False)]) - recs
        recs |= candidates.filtered(lambda r: any(
            isinstance(i, dict)
            and str(i.get("id") or "").strip() == ref_id
            and i.get("@type") in PARTY_ROLE_TYPES
            for i in (r.related_party_json or [])
        ))
        for rec in recs:
            json_refs = [item for item in (rec.related_party_json or [])
                         if not (isinstance(item, dict)
                                 and str(item.get("id") or "").strip() == ref_id
                                 and item.get("@type") in PARTY_ROLE_TYPES)]
            kept = rec.related_party_role_ids.filtered(
                lambda role: (role.tmf_id or str(role.id)) != ref_id)
            rec.with_context(skip_tmf_wiring=True).write({
                "related_party_role_ids": [(6, 0, kept.ids)],
                "related_party_json": json_refs,
            })
