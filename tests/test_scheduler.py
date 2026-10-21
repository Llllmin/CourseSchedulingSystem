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
        # Isolate the database and its automatic backups together.
        self.folder = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.folder.name, "school.db")

        # Each test starts with the same schema and anonymous demo dataset.
        initialize_database(self.db_path)
        seed_demo_data(self.db_path)
        self.scheduler = TimetableScheduler(self.db_path)

    def tearDown(self):
        """Delete the temporary database after each test finishes."""
        self.folder.cleanup()

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
            sections = 102
            assignments = conn.execute("SELECT COUNT(*) FROM schedule_assignments").fetchone()[0]
        self.assertEqual(sections, assignments)

    def test_blocked_period_rejected(self):
        """School-wide blocks still apply independently of flexible lunch."""
        with connect(self.db_path) as conn:
            conn.execute("INSERT INTO blocked_periods VALUES ('Monday', 4, 'Assembly')")
            section_id = conn.execute("SELECT id FROM course_sections LIMIT 1").fetchone()[0]
            room_id = conn.execute("SELECT id FROM rooms WHERE room_type = 'standard' LIMIT 1").fetchone()[0]
        result = self.scheduler.validate_assignment(section_id, "Monday", 4, room_id)
        self.assertFalse(result.valid)
        self.assertIn("Assembly", result.message)

    def _lunch_sections(self):
        """Two standard-room classes sharing a student, but different teachers."""
        with connect(self.db_path) as conn:
            for section in (1, 3):
                conn.execute("INSERT OR IGNORE INTO student_enrollments VALUES (1, ?)", (section,))
        return 1, 3

    def test_lunch_either_period_allowed_but_not_both(self):
        first, second = self._lunch_sections()
        self.assertTrue(self.scheduler.save_manual_assignment(first, "Monday", 5, 1).valid)
        result = self.scheduler.save_manual_assignment(second, "Monday", 6, 3)
        self.assertFalse(result.valid)
        self.assertIn("Student 001", result.message)
        self.assertIn("lunch", result.message)
        # A different day is independent, and freeing P5 permits P6.
        self.assertTrue(self.scheduler.validate_assignment(second, "Tuesday", 6, 3).valid)
        self.assertTrue(self.scheduler.save_manual_assignment(first, "Monday", 3, 1).valid)
        self.assertTrue(self.scheduler.save_manual_assignment(second, "Monday", 6, 3).valid)
        self.assertFalse(self.scheduler.validate_assignment(first, "Monday", 5, 1).valid)

    def test_double_lesson_cannot_consume_both_lunch_periods(self):
        self._lunch_sections()
        with connect(self.db_path) as conn:
            conn.execute("UPDATE course_sections SET duration = 2 WHERE id = 1")
        self.assertFalse(self.scheduler.validate_assignment(1, "Monday", 5, 1).valid)
        self.assertTrue(self.scheduler.validate_assignment(1, "Monday", 4, 1).valid)
        self.assertTrue(self.scheduler.validate_assignment(1, "Monday", 6, 1).valid)

    def test_lunch_independent_students_and_manual_self_replacement(self):
        self._lunch_sections()
        with connect(self.db_path) as conn:
            conn.execute("DELETE FROM student_enrollments WHERE section_id = 3")
        self.assertTrue(self.scheduler.save_manual_assignment(1, "Monday", 5, 1).valid)
        self.assertTrue(self.scheduler.save_manual_assignment(3, "Monday", 6, 3).valid)
        self.assertTrue(self.scheduler.save_manual_assignment(1, "Monday", 6, 1).valid)

    def test_legacy_lunch_migration_is_one_time(self):
        with connect(self.db_path) as conn:
            conn.execute("DELETE FROM schema_migrations")
            conn.execute("INSERT INTO blocked_periods VALUES ('Monday', 4, 'Lunch')")
            conn.execute("INSERT INTO blocked_periods VALUES ('Tuesday', 4, 'Assembly')")
        initialize_database(self.db_path)
        with connect(self.db_path) as conn:
            self.assertIsNone(conn.execute("SELECT 1 FROM blocked_periods WHERE day = 'Monday' AND period = 4").fetchone())
            self.assertIsNotNone(conn.execute("SELECT 1 FROM blocked_periods WHERE day = 'Tuesday' AND period = 4").fetchone())
            conn.execute("INSERT INTO blocked_periods VALUES ('Monday', 4, 'Lunch')")
        initialize_database(self.db_path)
        with connect(self.db_path) as conn:
            self.assertIsNotNone(conn.execute("SELECT 1 FROM blocked_periods WHERE day = 'Monday' AND period = 4").fetchone())

    def test_generated_students_keep_lunch(self):
        self.assertTrue(self.scheduler.generate()[0])
        with connect(self.db_path) as conn:
            students = [r[0] for r in conn.execute("SELECT id FROM students")]
        for student in students:
            occupied = {}
            for lesson in timetable_rows(self.db_path, "student", student_id=student):
                occupied.setdefault(lesson["day"], set()).update(
                    range(lesson["period"], lesson["period"] + lesson["duration"]))
            self.assertTrue(all(not {5, 6}.issubset(slots) for slots in occupied.values()))

    def test_last_period_and_overflow(self):
        self.assertTrue(self.scheduler.validate_assignment(1, "Monday", 11, 1).valid)
        with connect(self.db_path) as conn:
            conn.execute("UPDATE course_sections SET duration = 2 WHERE id = 1")
        self.assertFalse(self.scheduler.validate_assignment(1, "Monday", 11, 1).valid)

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
