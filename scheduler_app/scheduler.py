from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Iterable

from scheduler_app.config import DAYS, PERIODS
from scheduler_app.database import connect


@dataclass
class ValidationResult:
    valid: bool
    message: str


def _overlaps(start_a: int, duration_a: int, start_b: int, duration_b: int) -> bool:
    return start_a < start_b + duration_b and start_b < start_a + duration_a


def _period_span(period: int, duration: int) -> list[int]:
    return list(range(period, period + duration))


class TimetableScheduler:
    def __init__(self, db_path: str):
        self.db_path = db_path

    def clear_schedule(self) -> None:
        with connect(self.db_path) as conn:
            conn.execute("DELETE FROM schedule_assignments")

    def generate(self, time_limit_seconds: float = 10.0) -> tuple[bool, str]:
        started = time.perf_counter()
        with connect(self.db_path) as conn:
            sections = self._load_sections(conn)
            rooms = [dict(row) for row in conn.execute("SELECT * FROM rooms ORDER BY room_type, capacity DESC")]
            conn.execute("DELETE FROM schedule_assignments")

            if not self._backtrack(conn, sections, rooms, started, time_limit_seconds):
                conn.execute("DELETE FROM schedule_assignments")
                return False, "Unable to generate a complete timetable within the constraints and time limit."

            elapsed = time.perf_counter() - started
            return True, f"Generated {len(sections)} course sections in {elapsed:.2f} seconds."

    def validate_assignment(self, section_id: int, day: str, period: int, room_id: int) -> ValidationResult:
        with connect(self.db_path) as conn:
            return self._validate_assignment(conn, section_id, day, period, room_id)

    def save_manual_assignment(self, section_id: int, day: str, period: int, room_id: int) -> ValidationResult:
        with connect(self.db_path) as conn:
            result = self._validate_assignment(conn, section_id, day, period, room_id)
            if not result.valid:
                return result
            conn.execute(
                """
                INSERT INTO schedule_assignments(section_id, day, period, room_id)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(section_id) DO UPDATE SET day=excluded.day, period=excluded.period, room_id=excluded.room_id
                """,
                (section_id, day, period, room_id),
            )
            return ValidationResult(True, "Assignment saved.")

    def _load_sections(self, conn) -> list[dict]:
        rows = conn.execute(
            """
            SELECT
                cs.id,
                cs.section_code,
                cs.teacher_id,
                cs.duration,
                c.name AS course_name,
                c.requires_room_type,
                COUNT(se.student_id) AS enrollment_count
            FROM course_sections cs
            JOIN courses c ON c.id = cs.course_id
            LEFT JOIN student_enrollments se ON se.section_id = cs.id
            GROUP BY cs.id
            """
        ).fetchall()
        sections = [dict(row) for row in rows]
        sections.sort(
            key=lambda section: (
                section["duration"],
                section["requires_room_type"] == "lab",
                section["enrollment_count"],
            ),
            reverse=True,
        )
        return sections

    def _backtrack(self, conn, sections: list[dict], rooms: list[dict], started: float, limit: float) -> bool:
        assigned_count = conn.execute("SELECT COUNT(*) FROM schedule_assignments").fetchone()[0]
        if assigned_count == len(sections):
            return True
        if time.perf_counter() - started > limit:
            return False

        section = sections[assigned_count]
        for day, period, room in self._candidate_slots(section, rooms):
            result = self._validate_assignment(conn, section["id"], day, period, room["id"])
            if not result.valid:
                continue
            conn.execute(
                "INSERT INTO schedule_assignments(section_id, day, period, room_id) VALUES (?, ?, ?, ?)",
                (section["id"], day, period, room["id"]),
            )
            if self._backtrack(conn, sections, rooms, started, limit):
                return True
            conn.execute("DELETE FROM schedule_assignments WHERE section_id = ?", (section["id"],))
        return False

    def _candidate_slots(self, section: dict, rooms: Iterable[dict]) -> Iterable[tuple[str, int, dict]]:
        matching_rooms = [
            room
            for room in rooms
            if room["capacity"] >= section["enrollment_count"]
            and (section["requires_room_type"] == "standard" or room["room_type"] == section["requires_room_type"])
        ]
        for day in DAYS:
            for period in PERIODS:
                if period + section["duration"] - 1 > max(PERIODS):
                    continue
                for room in matching_rooms:
                    yield day, period, room

    def _validate_assignment(self, conn, section_id: int, day: str, period: int, room_id: int) -> ValidationResult:
        section = conn.execute(
            """
            SELECT cs.id, cs.section_code, cs.teacher_id, cs.duration, c.name AS course_name,
                   c.requires_room_type, t.name AS teacher_name, COUNT(se.student_id) AS enrollment_count
            FROM course_sections cs
            JOIN courses c ON c.id = cs.course_id
            JOIN teachers t ON t.id = cs.teacher_id
            LEFT JOIN student_enrollments se ON se.section_id = cs.id
            WHERE cs.id = ?
            GROUP BY cs.id
            """,
            (section_id,),
        ).fetchone()
        if section is None:
            return ValidationResult(False, f"Section id {section_id} does not exist.")
        if day not in DAYS:
            return ValidationResult(False, f"{day} is not a valid school day.")
        if period not in PERIODS or period + section["duration"] - 1 > max(PERIODS):
            return ValidationResult(False, f"{section['section_code']} cannot fit starting at period {period}.")

        room = conn.execute("SELECT * FROM rooms WHERE id = ?", (room_id,)).fetchone()
        if room is None:
            return ValidationResult(False, f"Room id {room_id} does not exist.")
        if room["capacity"] < section["enrollment_count"]:
            return ValidationResult(
                False,
                f"Room {room['room_code']} capacity {room['capacity']} is too small for {section['section_code']} ({section['enrollment_count']} students).",
            )
        if section["requires_room_type"] == "lab" and room["room_type"] != "lab":
            return ValidationResult(False, f"{section['section_code']} requires a lab, but {room['room_code']} is {room['room_type']}.")

        for check_period in _period_span(period, section["duration"]):
            blocked = conn.execute(
                "SELECT reason FROM blocked_periods WHERE day = ? AND period = ?",
                (day, check_period),
            ).fetchone()
            if blocked:
                return ValidationResult(False, f"{day} P{check_period} is unavailable for {blocked['reason']}.")

            unavailable = conn.execute(
                """
                SELECT 1 FROM teacher_availability
                WHERE teacher_id = ? AND day = ? AND period = ? AND available = 0
                """,
                (section["teacher_id"], day, check_period),
            ).fetchone()
            if unavailable:
                return ValidationResult(False, f"Teacher {section['teacher_name']} is unavailable at {day} P{check_period}.")

        assignments = conn.execute(
            """
            SELECT sa.section_id, sa.day, sa.period, sa.room_id, cs.duration, cs.teacher_id,
                   cs.section_code, c.name AS course_name, t.name AS teacher_name, r.room_code
            FROM schedule_assignments sa
            JOIN course_sections cs ON cs.id = sa.section_id
            JOIN courses c ON c.id = cs.course_id
            JOIN teachers t ON t.id = cs.teacher_id
            JOIN rooms r ON r.id = sa.room_id
            WHERE sa.day = ? AND sa.section_id != ?
            """,
            (day, section_id),
        ).fetchall()

        current_students = {
            row["student_id"]
            for row in conn.execute("SELECT student_id FROM student_enrollments WHERE section_id = ?", (section_id,))
        }
        for existing in assignments:
            if not _overlaps(period, section["duration"], existing["period"], existing["duration"]):
                continue
            overlap_label = f"{day} P{max(period, existing['period'])}"
            if existing["teacher_id"] == section["teacher_id"]:
                return ValidationResult(
                    False,
                    f"Teacher {section['teacher_name']} already teaches {existing['section_code']} at {overlap_label}.",
                )
            if existing["room_id"] == room_id:
                return ValidationResult(False, f"Room {existing['room_code']} is already used by {existing['section_code']} at {overlap_label}.")
            existing_students = {
                row["student_id"]
                for row in conn.execute("SELECT student_id FROM student_enrollments WHERE section_id = ?", (existing["section_id"],))
            }
            clashing_students = current_students.intersection(existing_students)
            if clashing_students:
                sample = conn.execute("SELECT name FROM students WHERE id = ?", (next(iter(clashing_students)),)).fetchone()
                return ValidationResult(
                    False,
                    f"Student {sample['name']} has a clash between {section['section_code']} and {existing['section_code']} at {overlap_label}.",
                )

        return ValidationResult(True, "Valid assignment.")


def timetable_rows(db_path: str, role: str = "admin", student_id: int | None = None, teacher_id: int | None = None):
    query = """
        SELECT sa.day, sa.period, cs.duration, cs.section_code, c.name AS course_name,
               t.name AS teacher_name, r.room_code
        FROM schedule_assignments sa
        JOIN course_sections cs ON cs.id = sa.section_id
        JOIN courses c ON c.id = cs.course_id
        JOIN teachers t ON t.id = cs.teacher_id
        JOIN rooms r ON r.id = sa.room_id
    """
    params: list[int] = []
    if role == "student":
        query += " JOIN student_enrollments se ON se.section_id = cs.id WHERE se.student_id = ?"
        params.append(student_id or -1)
    elif role == "teacher":
        query += " WHERE cs.teacher_id = ?"
        params.append(teacher_id or -1)
    query += " ORDER BY sa.day, sa.period"
    with connect(db_path) as conn:
        return [dict(row) for row in conn.execute(query, params)]
