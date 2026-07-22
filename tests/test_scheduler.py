import os
import tempfile
import time
import unittest

from scheduler_app.database import connect, initialize_database
from scheduler_app.scheduler import TimetableScheduler, timetable_rows
from scheduler_app.seed_data import seed_demo_data


class SchedulerTests(unittest.TestCase):
    def setUp(self):
        handle, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(handle)
        initialize_database(self.db_path)
        seed_demo_data(self.db_path)
        self.scheduler = TimetableScheduler(self.db_path)

    def tearDown(self):
        os.remove(self.db_path)

    def test_demo_dataset_size(self):
        with connect(self.db_path) as conn:
            self.assertGreaterEqual(conn.execute("SELECT COUNT(*) FROM students").fetchone()[0], 50)
            self.assertGreaterEqual(conn.execute("SELECT COUNT(*) FROM teachers").fetchone()[0], 20)
            self.assertGreaterEqual(conn.execute("SELECT COUNT(*) FROM rooms").fetchone()[0], 10)
            self.assertGreaterEqual(conn.execute("SELECT COUNT(*) FROM course_sections").fetchone()[0], 25)

    def test_generate_within_success_criterion(self):
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
        with connect(self.db_path) as conn:
            section_id = conn.execute("SELECT id FROM course_sections LIMIT 1").fetchone()[0]
            room_id = conn.execute("SELECT id FROM rooms WHERE room_type = 'standard' LIMIT 1").fetchone()[0]
        result = self.scheduler.validate_assignment(section_id, "Monday", 4, room_id)
        self.assertFalse(result.valid)
        self.assertIn("Lunch", result.message)

    def test_room_type_rejected(self):
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
        ok, message = self.scheduler.generate()
        self.assertTrue(ok, message)
        with connect(self.db_path) as conn:
            student_id = conn.execute("SELECT id FROM students ORDER BY id LIMIT 1").fetchone()[0]
            teacher_id = conn.execute("SELECT id FROM teachers ORDER BY id LIMIT 1").fetchone()[0]
        self.assertGreater(len(timetable_rows(self.db_path, "student", student_id=student_id)), 0)
        self.assertGreater(len(timetable_rows(self.db_path, "teacher", teacher_id=teacher_id)), 0)

    def test_manual_conflict_rejected(self):
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
    unittest.main()
