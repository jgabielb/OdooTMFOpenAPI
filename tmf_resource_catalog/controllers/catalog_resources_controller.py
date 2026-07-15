# -*- coding: utf-8 -*-
"""TMF634 resourceCategory / resourceCandidate / importJob / exportJob routes."""
import logging

from odoo import http
from odoo.http import request

from odoo.addons.tmf_base.controllers.base_controller import TMFBaseController

_logger = logging.getLogger(__name__)

API_BASE = "/tmf-api/resourceCatalogManagement/v5"

RESOURCES = {
    "resourceCategory": {
        "model": "tmf.resource.category",
        "path": f"{API_BASE}/resourceCategory",
        "required": [],
    },
    "resourceCandidate": {
        "model": "tmf.resource.candidate",
        "path": f"{API_BASE}/resourceCandidate",
        "required": [],
    },
    "importJob": {
        "model": "tmf.resource.catalog.import.job",
        "path": f"{API_BASE}/importJob",
        "required": [],
    },
    "exportJob": {
        "model": "tmf.resource.catalog.export.job",
        "path": f"{API_BASE}/exportJob",
        "required": [],
    },
}


class TMF634CatalogResourcesController(TMFBaseController):

    @http.route(RESOURCES["resourceCategory"]["path"], type="http", auth="public",
                methods=["GET", "POST"], csrf=False)
    def resource_category_collection(self, **kw):
        if request.httprequest.method == "POST":
            return self._tmf_do_create(RESOURCES["resourceCategory"])
        return self._tmf_do_list(RESOURCES["resourceCategory"], **kw)

    @http.route(RESOURCES["resourceCategory"]["path"] + "/<string:rid>", type="http",
                auth="public", methods=["GET", "PATCH", "DELETE"], csrf=False)
    def resource_category_individual(self, rid, **kw):
        return self._tmf_do_individual(RESOURCES["resourceCategory"], rid, **kw)

    @http.route(RESOURCES["resourceCandidate"]["path"], type="http", auth="public",
                methods=["GET", "POST"], csrf=False)
    def resource_candidate_collection(self, **kw):
        if request.httprequest.method == "POST":
            return self._tmf_do_create(RESOURCES["resourceCandidate"])
        return self._tmf_do_list(RESOURCES["resourceCandidate"], **kw)

    @http.route(RESOURCES["resourceCandidate"]["path"] + "/<string:rid>", type="http",
                auth="public", methods=["GET", "PATCH", "DELETE"], csrf=False)
    def resource_candidate_individual(self, rid, **kw):
        return self._tmf_do_individual(RESOURCES["resourceCandidate"], rid, **kw)

    @http.route(RESOURCES["importJob"]["path"], type="http", auth="public",
                methods=["GET", "POST"], csrf=False)
    def import_job_collection(self, **kw):
        if request.httprequest.method == "POST":
            return self._tmf_do_create(RESOURCES["importJob"])
        return self._tmf_do_list(RESOURCES["importJob"], **kw)

    @http.route(RESOURCES["importJob"]["path"] + "/<string:rid>", type="http",
                auth="public", methods=["GET", "DELETE"], csrf=False)
    def import_job_individual(self, rid, **kw):
        return self._tmf_do_individual(RESOURCES["importJob"], rid, **kw)

    @http.route(RESOURCES["exportJob"]["path"], type="http", auth="public",
                methods=["GET", "POST"], csrf=False)
    def export_job_collection(self, **kw):
        if request.httprequest.method == "POST":
            return self._tmf_do_create(RESOURCES["exportJob"])
        return self._tmf_do_list(RESOURCES["exportJob"], **kw)

    @http.route(RESOURCES["exportJob"]["path"] + "/<string:rid>", type="http",
                auth="public", methods=["GET", "DELETE"], csrf=False)
    def export_job_individual(self, rid, **kw):
        return self._tmf_do_individual(RESOURCES["exportJob"], rid, **kw)
