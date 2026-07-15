# -*- coding: utf-8 -*-
"""TMF633 serviceCategory / serviceCandidate / importJob / exportJob routes."""
import logging

from odoo import http
from odoo.http import request

from odoo.addons.tmf_base.controllers.base_controller import TMFBaseController

_logger = logging.getLogger(__name__)

API_BASE = "/tmf-api/serviceCatalogManagement/v4"

RESOURCES = {
    "serviceCategory": {
        "model": "tmf.service.category",
        "path": f"{API_BASE}/serviceCategory",
        "required": [],
    },
    "serviceCandidate": {
        "model": "tmf.service.candidate",
        "path": f"{API_BASE}/serviceCandidate",
        "required": [],
    },
    "importJob": {
        "model": "tmf.service.catalog.import.job",
        "path": f"{API_BASE}/importJob",
        "required": [],
    },
    "exportJob": {
        "model": "tmf.service.catalog.export.job",
        "path": f"{API_BASE}/exportJob",
        "required": [],
    },
}


class TMF633CatalogResourcesController(TMFBaseController):

    @http.route(RESOURCES["serviceCategory"]["path"], type="http", auth="public",
                methods=["GET", "POST"], csrf=False)
    def service_category_collection(self, **kw):
        if request.httprequest.method == "POST":
            return self._tmf_do_create(RESOURCES["serviceCategory"])
        return self._tmf_do_list(RESOURCES["serviceCategory"], **kw)

    @http.route(RESOURCES["serviceCategory"]["path"] + "/<string:rid>", type="http",
                auth="public", methods=["GET", "PATCH", "DELETE"], csrf=False)
    def service_category_individual(self, rid, **kw):
        return self._tmf_do_individual(RESOURCES["serviceCategory"], rid, **kw)

    @http.route(RESOURCES["serviceCandidate"]["path"], type="http", auth="public",
                methods=["GET", "POST"], csrf=False)
    def service_candidate_collection(self, **kw):
        if request.httprequest.method == "POST":
            return self._tmf_do_create(RESOURCES["serviceCandidate"])
        return self._tmf_do_list(RESOURCES["serviceCandidate"], **kw)

    @http.route(RESOURCES["serviceCandidate"]["path"] + "/<string:rid>", type="http",
                auth="public", methods=["GET", "PATCH", "DELETE"], csrf=False)
    def service_candidate_individual(self, rid, **kw):
        return self._tmf_do_individual(RESOURCES["serviceCandidate"], rid, **kw)

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
