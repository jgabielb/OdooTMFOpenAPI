"""
Feature: Device exchange — swap a faulty CPE without interrupting service.

The service stays "active" throughout; only its resource reference changes.
Warranty rules determine whether a charge is posted.
"""
import pytest


@pytest.mark.device_exchange
class TestDeviceExchange:

    @pytest.mark.xfail(reason="Device-exchange order action not yet defined in controllers")
    def test_exchange_keeps_service_active(self, tmf):
        pytest.xfail("device-exchange pending")

    @pytest.mark.xfail(reason="Warranty check + RMA state transitions not implemented")
    def test_in_warranty_exchange_is_free(self, tmf):
        pytest.xfail("warranty logic pending")

    @pytest.mark.xfail(reason="Warranty check + one-time charge not implemented")
    def test_out_of_warranty_exchange_is_charged(self, tmf):
        pytest.xfail("warranty logic pending")
