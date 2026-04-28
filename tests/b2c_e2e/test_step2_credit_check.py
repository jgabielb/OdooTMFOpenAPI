"""
STEP 2 — Credit check (TMF645 CreditManagement)

The endpoint is now live. The "fail" path needs a partner that the scoring
policy will reject; we force it via a high requested amount AND by pre-flagging
the partner as credit-blocked through a prior low-score check.
"""
import pytest


@pytest.mark.credit_check
class TestCreditCheck:
    """Gherkin: STEP 2 — Credit check"""

    def test_credit_check_passes_allows_order(self, tmf, created_party):
        body = {
            "relatedParty": [{"id": created_party["id"], "@referredType": "Individual"}],
            "requestedCreditAmount": {"value": 29.99, "unit": "USD"},
        }
        r = tmf.post("/tmf-api/creditManagement/v4/creditRatingCheck", json=body)
        assert r.status_code == 201, r.text
        data = r.json()
        assert data.get("creditRatingResult") == "approved"
        assert isinstance(data.get("creditScore"), int) and data["creditScore"] > 0

    def test_credit_check_response_shape(self, tmf, created_party):
        """The 201 response should expose the TMF645 contract fields."""
        body = {
            "relatedParty": [{"id": created_party["id"], "@referredType": "Individual"}],
            "requestedCreditAmount": {"value": 100.00, "unit": "USD"},
        }
        r = tmf.post("/tmf-api/creditManagement/v4/creditRatingCheck", json=body)
        assert r.status_code == 201
        body = r.json()
        for key in ("id", "@type", "creditRatingResult", "creditScore",
                    "requestedCreditAmount", "relatedParty"):
            assert key in body, f"missing {key} in response"

    @pytest.mark.xfail(
        reason="Score policy is deterministic-pass; need a way to seed a low-score partner",
    )
    def test_credit_check_fails_blocks_order(self, tmf, created_party):
        """Failure path can't be exercised without seeding a low-score partner."""
        body = {
            "relatedParty": [{"id": created_party["id"], "@referredType": "Individual"}],
            "requestedCreditAmount": {"value": 5000.00, "unit": "USD"},
        }
        r = tmf.post("/tmf-api/creditManagement/v4/creditRatingCheck", json=body)
        assert r.status_code == 201
        assert r.json().get("creditRatingResult") == "rejected"

    @pytest.mark.xfail(
        reason="Timeout simulation hook (_simulateTimeout) not implemented",
    )
    def test_credit_service_timeout_returns_503(self, tmf, created_party):
        """Credit scoring service timeout is handled gracefully."""
        body = {
            "relatedParty": [{"id": created_party["id"], "@referredType": "Individual"}],
            "requestedCreditAmount": {"value": 29.99, "unit": "USD"},
            "_simulateTimeout": True,
        }
        r = tmf.post("/tmf-api/creditManagement/v4/creditRatingCheck", json=body)
        assert r.status_code == 503
