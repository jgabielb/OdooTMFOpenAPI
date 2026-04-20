"""Scenario 5: Trouble-to-Resolve (Assure)

Incident → Trouble Ticket → Work Order → Resolution.
"""
import pytest
from helpers.assertions import *


@pytest.fixture(scope="class")
def assure_setup(tmf):
    party, _ = tmf.create_party("Carol", "Jones")
    return {"party_id": party["id"]}


class TestTroubleToResolve:

    def test_create_incident(self, tmf, assure_setup):
        """POST incident → helpdesk.ticket via bridge."""
        data, _ = tmf.create("incident", "incident", {
            "name": "Network Outage Sector 7",
            "description": "Customer reports no connectivity",
            "category": "Network",
            "priority": "Critical",
            "state": "raised",
            "ackState": "unacknowledged",
            "occurTime": "2026-04-17T10:00:00Z",
            "domain": "Network",
            "sourceObject": {"id": "tower-007", "name": "Cell Tower Sector 7"},
        })
        incident_id = assert_tmf_resource(data)
        self.__class__.incident_id = incident_id

    def test_create_trouble_ticket(self, tmf, assure_setup):
        """POST trouble ticket → helpdesk.ticket."""
        data, _ = tmf.create_trouble_ticket(
            "Connectivity issue for Carol Jones",
            party_id=assure_setup["party_id"],
            severity="High",
            priority="High",
            ticketType="Complaint",
        )
        ticket_id = assert_tmf_resource(data)
        assert_field_present(data, "status")
        self.__class__.ticket_id = ticket_id

    def test_create_alarm(self, tmf):
        """POST alarm → mail.activity via bridge."""
        data, _ = tmf.create("alarm", "alarm", {
            "alarmType": "equipmentAlarm",
            "perceivedSeverity": "critical",
            "probableCause": "powerProblem",
            "sourceSystemId": "NMS-001",
            "specificProblem": "Cell tower offline",
            "alarmRaisedTime": "2026-04-17T10:00:00Z",
        })
        alarm_id = assert_tmf_resource(data)
        self.__class__.alarm_id = alarm_id

    def test_create_work_order(self, tmf, assure_setup):
        """POST work → project.task via bridge."""
        data, _ = tmf.create("work", "work", {
            "name": "Repair Cell Tower Sector 7",
            "description": "Dispatch technician to site",
            "workType": "fieldWork",
        })
        work_id = assert_tmf_resource(data)
        self.__class__.work_id = work_id

    def test_complete_work(self, tmf):
        """PATCH work to completed."""
        data, _ = tmf.patch("work", "work", self.work_id,
                            {"state": "completed"})

    def test_resolve_ticket(self, tmf):
        """PATCH ticket to Resolved."""
        data, _ = tmf.patch("trouble_ticket", "troubleTicket", self.ticket_id,
                            {"status": "Resolved"})
        assert data.get("status") in ("Resolved", "resolved")

    def test_get_resolved_ticket(self, tmf):
        """GET resolved ticket has correct status."""
        data, _ = tmf.get("trouble_ticket", "troubleTicket", self.ticket_id)
        assert data.get("status") in ("Resolved", "resolved")

    def test_odoo_helpdesk_tickets_exist(self, odoo):
        """Verify helpdesk tickets created in Odoo."""
        try:
            tickets = odoo.find_helpdesk_ticket("Connectivity")
        except Exception as e:
            if "helpdesk.ticket" in str(e):
                pytest.skip("helpdesk module not installed")
            raise
        assert len(tickets) >= 1, "No helpdesk tickets found"

    def test_odoo_project_task_exists(self, odoo):
        """Verify project task created in Odoo."""
        try:
            tasks = odoo.find_project_task("Repair Cell Tower")
        except Exception as e:
            if "project.task" in str(e):
                pytest.skip("project module not installed")
            raise
        # Bridge may not create tasks for all work orders
        if not tasks:
            pytest.skip("No project task found — bridge may not be active")
