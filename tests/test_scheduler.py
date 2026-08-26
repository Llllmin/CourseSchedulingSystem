"""Automated tests for the scheduling system.

These tests provide evidence for IA success criteria: dataset size, generation
speed, blocked periods, lab-room constraints, role-based timetable views, and
manual conflict rejection.
"""

import os
import tempfile
import time
import unittest

from scheduler_app.database import connect, initialize_database
from scheduler_app.scheduler import TimetableScheduler, timetable_rows
from scheduler_app.seed_data import seed_demo_data


class SchedulerTests(unittest.TestCase):
    """Unit tests that run against a fresh temporary SQLite database."""

    def setUp(self):
        """Create an isolated database before each test."""
        # mkstemp gives a real file path because SQLite needs a file database.
        handle, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(handle)

        # Each test starts with the same schema and anonymous demo dataset.
        initialize_database(self.db_path)
        seed_demo_data(self.db_path)
        self.scheduler = TimetableScheduler(self.db_path)

    def tearDown(self):
        """Delete the temporary database after each test finishes."""
        os.remove(self.db_path)

    def test_demo_dataset_size(self):
        """Check that the seeded data meets the IA scale requirement."""
        with connect(self.db_path) as conn:
            self.assertGreaterEqual(conn.execute("SELECT COUNT(*) FROM students").fetchone()[0], 50)
            self.assertGreaterEqual(conn.execute("SELECT COUNT(*) FROM teachers").fetchone()[0], 20)
            self.assertGreaterEqual(conn.execute("SELECT COUNT(*) FROM rooms").fetchone()[0], 10)
            self.assertGreaterEqual(conn.execute("SELECT COUNT(*) FROM course_sections").fetchone()[0], 25)

    def test_generate_within_success_criterion(self):
        """Generate a full timetable and confirm it finishes within 10 seconds."""
        started = time.perf_counter()
        ok, message = self.scheduler.generate()
        elapsed = time.perf_counter() - started
        self.assertTrue(ok, message)
        self.assertLessEqual(elapsed, 10.0)
        with connect(self.db_path) as conn:
            sections = conn.execute("SELECT COUNT(*) FROM course_sections").fetchone()[0]
            assignments = conn.execute("SELECT COUNT(*) FROM schedule_assignments").fetchone()[0]
        self.assertEqual(sections, assignments)

    def test_blocked_period_rejected(self):
        """Verify that lunch/blocked periods cannot receive class assignments."""
        with connect(self.db_path) as conn:
            section_id = conn.execute("SELECT id FROM course_sections LIMIT 1").fetchone()[0]
            room_id = conn.execute("SELECT id FROM rooms WHERE room_type = 'standard' LIMIT 1").fetchone()[0]
        result = self.scheduler.validate_assignment(section_id, "Monday", 4, room_id)
        self.assertFalse(result.valid)
        self.assertIn("Lunch", result.message)

    def test_room_type_rejected(self):
        """Verify that a lab course cannot be assigned to a standard room."""
        with connect(self.db_path) as conn:
            lab_section = conn.execute(
                """
                SELECT cs.id FROM course_sections cs
                JOIN courses c ON c.id = cs.course_id
                WHERE c.requires_room_type = 'lab'
                LIMIT 1
                """
            ).fetchone()[0]
            standard_room = conn.execute("SELECT id FROM rooms WHERE room_type = 'standard' LIMIT 1").fetchone()[0]
        result = self.scheduler.validate_assignment(lab_section, "Monday", 1, standard_room)
        self.assertFalse(result.valid)
        self.assertIn("requires a lab", result.message)

    def test_role_filtered_timetables(self):
        """Verify that student and teacher timetable queries return filtered rows."""
        ok, message = self.scheduler.generate()
        self.assertTrue(ok, message)
        with connect(self.db_path) as conn:
            student_id = conn.execute("SELECT id FROM students ORDER BY id LIMIT 1").fetchone()[0]
            teacher_id = conn.execute("SELECT id FROM teachers ORDER BY id LIMIT 1").fetchone()[0]
        self.assertGreater(len(timetable_rows(self.db_path, "student", student_id=student_id)), 0)
        self.assertGreater(len(timetable_rows(self.db_path, "teacher", teacher_id=teacher_id)), 0)

    def test_manual_conflict_rejected(self):
        """Verify that a manual edit causing a room or teacher conflict is rejected."""
        ok, message = self.scheduler.generate()
        self.assertTrue(ok, message)
        with connect(self.db_path) as conn:
            first = conn.execute("SELECT * FROM schedule_assignments LIMIT 1").fetchone()
            other = conn.execute(
                "SELECT id FROM course_sections WHERE teacher_id = (SELECT teacher_id FROM course_sections WHERE id = ?) AND id != ? LIMIT 1",
                (first["section_id"], first["section_id"]),
            ).fetchone()
            if other is None:
                other = conn.execute("SELECT id FROM course_sections WHERE id != ? LIMIT 1", (first["section_id"],)).fetchone()
        result = self.scheduler.save_manual_assignment(other["id"], first["day"], first["period"], first["room_id"])
        self.assertFalse(result.valid)


if __name__ == "__main__":
    # Allows this test file to be run directly from PyCharm.
    unittest.main()
