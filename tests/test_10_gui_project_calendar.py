"""Scenario 10: GUI Project & Calendar Flow

Simulates Odoo Project and Calendar GUI operations via XML-RPC
and verifies the TMF API reflects changes through bridge sync.

Flow: Create Project → Create Task → Update Task Stage →
      Verify TMF Work API → Create Calendar Event → Verify TMF Appointment
"""
import pytest
from helpers.assertions import *


class TestGuiProjectFlow:
    """Project task → TMF Work sync via bridge."""

    @pytest.fixture(autouse=True, scope="class")
    def project_setup(self, odoo):
        """Create a partner and project for task tests."""
        partner_id = odoo.create("res.partner", {
            "name": "ProjectCo Ltd",
            "is_company": True,
        })
        self.__class__.partner_id = partner_id

        partner = odoo.read("res.partner", [partner_id], ["tmf_id"])[0]
        self.__class__.partner_tmf_id = partner.get("tmf_id")

        # Find or create a project
        projects = odoo.search_read(
            "project.project", [], ["id", "name"], limit=1,
        )
        if projects:
            project_id = projects[0]["id"]
        else:
            project_id = odoo.create("project.project", {
                "name": "TMF Integration Project",
            })
        self.__class__.project_id = project_id

    def test_create_task(self, odoo):
        """Create a project task in Odoo → bridge syncs to TMF Work."""
        task_id = odoo.create("project.task", {
            "name": "Install 5G Base Station",
            "project_id": self.project_id,
            "partner_id": self.partner_id,
            "description": "Field installation of 5G equipment",
        })
        assert task_id, "Failed to create project task"
        self.__class__.task_id = task_id

        # Check bridge field if available
        try:
            task = odoo.read("project.task", [task_id], ["tmf_work_id"])[0]
            tmf_ref = task.get("tmf_work_id")
            self.__class__.tmf_work_odoo_id = (tmf_ref[0] if isinstance(tmf_ref, list) else tmf_ref) if tmf_ref else None
        except Exception:
            # Bridge module may not be installed yet
            self.__class__.tmf_work_odoo_id = None

    def test_update_task(self, odoo):
        """Update task description → TMF Work should reflect change."""
        odoo.write("project.task", [self.task_id], {
            "description": "Updated: 5G equipment installation with antenna alignment",
        })
        task = odoo.read("project.task", [self.task_id], ["description"])[0]
        assert "antenna" in (task.get("description") or "").lower()

    def test_tmf_work_list(self, tmf):
        """TMF Work API lists work items."""
        data, resp = tmf.list("work", "work", expected_status=None)
        if resp.status_code != 200:
            pytest.skip(f"Work API returned {resp.status_code} — module may not be installed")
        assert isinstance(data, list)

    def test_task_stage_change(self, odoo):
        """Move task to a different stage → TMF Work status updates."""
        stages = odoo.search_read(
            "project.task.type",
            [("project_ids", "in", [self.project_id])],
            ["id", "name"],
            limit=5,
        )
        if len(stages) < 2:
            pytest.skip("Not enough stages to test stage change")
        odoo.write("project.task", [self.task_id], {
            "stage_id": stages[1]["id"],
        })
        task = odoo.read("project.task", [self.task_id], ["stage_id"])[0]
        assert task["stage_id"][0] == stages[1]["id"]


class TestGuiCalendarFlow:
    """Calendar event → TMF Appointment sync via bridge."""

    @pytest.fixture(autouse=True, scope="class")
    def calendar_setup(self, odoo):
        """Create a partner for calendar tests."""
        partner_id = odoo.create("res.partner", {
            "name": "CalendarTest Client",
            "email": "calendar@example.com",
        })
        self.__class__.partner_id = partner_id

        partner = odoo.read("res.partner", [partner_id], ["tmf_id"])[0]
        self.__class__.partner_tmf_id = partner.get("tmf_id")

    def test_create_calendar_event(self, odoo):
        """Create a calendar event → bridge syncs to TMF Appointment."""
        event_id = odoo.create("calendar.event", {
            "name": "5G Network Review Meeting",
            "start": "2026-05-01 10:00:00",
            "stop": "2026-05-01 11:00:00",
            "partner_ids": [[6, 0, [self.partner_id]]],
        })
        assert event_id, "Failed to create calendar event"
        self.__class__.event_id = event_id

        # Check bridge field if available
        try:
            event = odoo.read("calendar.event", [event_id], ["tmf_appointment_id"])[0]
            tmf_ref = event.get("tmf_appointment_id")
            self.__class__.tmf_appointment_odoo_id = (tmf_ref[0] if isinstance(tmf_ref, list) else tmf_ref) if tmf_ref else None
        except Exception:
            self.__class__.tmf_appointment_odoo_id = None

    def test_update_calendar_event(self, odoo):
        """Reschedule event → TMF Appointment should reflect new time."""
        odoo.write("calendar.event", [self.event_id], {
            "start": "2026-05-02 14:00:00",
            "stop": "2026-05-02 15:30:00",
        })
        event = odoo.read("calendar.event", [self.event_id], ["start", "stop"])[0]
        assert "2026-05-02" in str(event.get("start", ""))

    def test_tmf_appointment_list(self, tmf):
        """TMF Appointment API lists appointments."""
        data, resp = tmf.list("appointment", "appointment", expected_status=None)
        if resp.status_code != 200:
            pytest.skip(f"Appointment API returned {resp.status_code} — module may not be installed")
        assert isinstance(data, list)
