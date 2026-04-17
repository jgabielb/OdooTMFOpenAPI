"""Shared pytest fixtures for TMF/Odoo integration tests."""
import os
import pytest
from helpers.api_client import TMFClient
from helpers.odoo_xmlrpc import OdooClient

BASE_URL = os.environ.get("TMF_BASE_URL", "http://localhost:8069")
ODOO_DB = os.environ.get("ODOO_DB", "TMF_Odoo_DB")
ODOO_USER = os.environ.get("ODOO_USER", "admin")
ODOO_PASS = os.environ.get("ODOO_PASS", "admin")


@pytest.fixture(scope="session")
def tmf():
    """TMF API client shared across the test session."""
    client = TMFClient(BASE_URL)
    yield client
    client.cleanup()


@pytest.fixture(scope="session")
def odoo():
    """Odoo XML-RPC client for server-side validation."""
    return OdooClient(BASE_URL, ODOO_DB, ODOO_USER, ODOO_PASS)


@pytest.fixture(scope="module")
def tmf_module():
    """TMF API client with per-module cleanup."""
    client = TMFClient(BASE_URL)
    yield client
    client.cleanup()
