"""
STEP 2 — Credit check (TMF645 CreditManagement)

All scenarios here are xfail until the /creditRatingCheck endpoint
is implemented. Keeping them so the suite documents the contract.
"""
import pytest


@pytest.mark.credit_check
class TestCreditCheck:
    """Gherkin: STEP 2 — Credit check"""

    @pytest.mark.xfail(reason="TMF645 creditRatingCheck endpoint not yet implemented")
    def test_credit_check_passes_allows_order(self, tmf, created_party):
        body = {
            "relatedParty": [{"id": created_party["id"], "@referredType": "Individual"}],
            "requestedCreditAmount": {"value": 29.99, "unit": "USD"},
        }
        r = tmf.post("/tmf-api/creditManagement/v4/creditRatingCheck", json=body)
        assert r.status_code == 201
        data = r.json()
        assert data.get("creditRatingResult") == "approved"

    @pytest.mark.xfail(reason="TMF645 creditRatingCheck endpoint not yet implemented")
    def test_credit_check_fails_blocks_order(self, tmf, created_party):
        body = {
            "relatedParty": [{"id": created_party["id"], "@referredType": "Individual"}],
            "requestedCreditAmount": {"value": 5000.00, "unit": "USD"},
        }
        r = tmf.post("/tmf-api/creditManagement/v4/creditRatingCheck", json=body)
        assert r.status_code == 201
        assert r.json().get("creditRatingResult") == "rejected"

    @pytest.mark.xfail(reason="TMF645 creditRatingCheck endpoint not yet implemented")
    def test_credit_service_timeout_returns_503(self, tmf, created_party):
        """Credit scoring service timeout is handled gracefully."""
        body = {
            "relatedParty": [{"id": created_party["id"], "@referredType": "Individual"}],
            "requestedCreditAmount": {"value": 29.99, "unit": "USD"},
            "_simulateTimeout": True,
        }
        r = tmf.post("/tmf-api/creditManagement/v4/creditRatingCheck", json=body)
        assert r.status_code == 503
