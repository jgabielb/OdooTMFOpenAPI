"""
Feature: SVAs (Servicios de Valor Agregado / value-added services)

Add-ons like STATIC_IP, INT_CALLS_100, STREAMING_BUNDLE attach to a parent
broadband service as child services (CFS → child CFS/RFS hierarchy).
"""
import pytest


@pytest.mark.sva
class TestSVA:

    @pytest.mark.xfail(reason="Modify-order to add SVA as child_service_id not implemented")
    def test_add_sva_to_active_service(self, tmf):
        pytest.xfail("add SVA pending")

    @pytest.mark.xfail(reason="Modify-order to add multiple SVAs in one request not implemented")
    def test_add_multiple_svas_in_one_order(self, tmf):
        pytest.xfail("multi-SVA pending")

    @pytest.mark.xfail(reason="Removing an SVA without terminating parent not implemented")
    def test_remove_sva_keeps_parent_active(self, tmf):
        pytest.xfail("remove SVA pending")
