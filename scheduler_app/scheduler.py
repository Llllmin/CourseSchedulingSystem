"""Weekly lesson scheduling with shared validation for generation and editing."""

import random
import time
from dataclasses import dataclass

from scheduler_app.config import DAYS, PERIODS, LUNCH_PERIODS, WEEKLY_PERIODS
from scheduler_app.database import connect


@dataclass
class ValidationResult:
    valid: bool
    message: str


def _period_span(period, duration):
    return set(range(period, period + duration))


def _overlaps(start_a, duration_a, start_b, duration_b):
    return bool(_period_span(start_a, duration_a) & _period_span(start_b, duration_b))


def _load_context(conn):
    """Cache relational data once, avoiding SQL inside the search loop."""
    sections = {}
    for row in conn.execute("""SELECT cs.*,c.name AS course_name,c.requires_room_type,
            t.name AS teacher_name FROM course_sections cs
            JOIN courses c ON c.id=cs.course_id JOIN teachers t ON t.id=cs.teacher_id"""):
        section = dict(row)
        section["students"] = set()
        section["weekly"] = WEEKLY_PERIODS[section["level"]]
        sections[section["id"]] = section
    for row in conn.execute("SELECT * FROM student_enrollments"):
        sections[row["section_id"]]["students"].add(row["student_id"])
    return {
        "sections": sections,
        "rooms": {r["id"]: dict(r) for r in conn.execute("SELECT * FROM rooms")},
        "blocked": {(r["day"], r["period"]): r["reason"] for r in conn.execute("SELECT * FROM blocked_periods")},
        "unavailable": {(r["teacher_id"], r["day"], r["period"]) for r in conn.execute("SELECT * FROM teacher_availability WHERE available=0")},
        "students": {r["id"]: r["name"] for r in conn.execute("SELECT * FROM students")},
    }


def _check(context, placed, section_id, occurrence, day, period, room_id):
    """Validate one occurrence against all others, including its own section."""
    section = context["sections"].get(section_id)
    if section is None:
        return ValidationResult(False, f"Section id {section_id} does not exist.")
    if occurrence not in range(1, section["weekly"] // section["duration"] + 1):
        return ValidationResult(False, "Invalid weekly lesson number.")
    if day not in DAYS or period not in PERIODS or period + section["duration"] - 1 > max(PERIODS):
        return ValidationResult(False, f"{section['section_code']} cannot fit at {day} P{period}.")
    room = context["rooms"].get(room_id)
    if room is None:
        return ValidationResult(False, f"Room id {room_id} does not exist.")
    if room["capacity"] < len(section["students"]):
        return ValidationResult(False, f"Room {room['room_code']} capacity is too small for {section['section_code']}.")
    if section["requires_room_type"] == "lab" and room["room_type"] != "lab":
        return ValidationResult(False, f"{section['section_code']} requires a lab, but {room['room_code']} is standard.")
    slots = _period_span(period, section["duration"])
    for slot in slots:
        if (day, slot) in context["blocked"]:
            return ValidationResult(False, f"{day} P{slot} is unavailable for {context['blocked'][(day, slot)]}.")
        if (section["teacher_id"], day, slot) in context["unavailable"]:
            return ValidationResult(False, f"Teacher {section['teacher_name']} is unavailable at {day} P{slot}.")
    same_day = [p for p in placed if p["day"] == day and
                (p["section_id"], p["occurrence"]) != (section_id, occurrence)]
    daily = section["duration"] + sum(context["sections"][p["section_id"]]["duration"]
            for p in same_day if p["section_id"] == section_id)
    if daily > 2:
        return ValidationResult(False, f"{section['section_code']} can have at most 2 teaching periods on {day}.")
    lunch = {student: set(slots & LUNCH_PERIODS) for student in section["students"]}
    for other in same_day:
        existing = context["sections"][other["section_id"]]
        existing_slots = _period_span(other["period"], existing["duration"])
        shared = section["students"] & existing["students"]
        for student in shared:
            lunch[student].update(existing_slots & LUNCH_PERIODS)
        if not slots & existing_slots:
            continue
        label = f"{day} P{max(period, other['period'])}"
        if existing["teacher_id"] == section["teacher_id"]:
            return ValidationResult(False, f"Teacher {section['teacher_name']} already teaches {existing['section_code']} at {label}.")
        if other["room_id"] == room_id:
            return ValidationResult(False, f"Room {room['room_code']} is already used by {existing['section_code']} at {label}.")
        if shared:
            student = context["students"][min(shared)]
            return ValidationResult(False, f"Student {student} has a clash with {existing['section_code']} at {label}.")
    for student, occupied in lunch.items():
        if LUNCH_PERIODS <= occupied:
            return ValidationResult(False, f"Student {context['students'][student]} must have P5 or P6 free for lunch on {day}.")
    return ValidationResult(True, "Valid assignment.")


class TimetableScheduler:
    def __init__(self, db_path):
        self.db_path = db_path

    def clear_schedule(self):
        with connect(self.db_path) as conn:
            conn.execute("DELETE FROM schedule_assignments")

    def generate(self, time_limit_seconds=10.0):
        """Build in memory; publish atomically only after a full solution exists."""
        from scheduler_app.school_data import snapshot, validate_data
        try:
            validate_data(snapshot(self.db_path))
        except ValueError as error:
            return False, f"Data validation failed: {error}"
        started = time.perf_counter()
        deadline = started + time_limit_seconds
        with connect(self.db_path) as conn:
            context = _load_context(conn)
            sections = list(context["sections"].values())
            candidates = {}
            for section in sections:
                candidates[section["id"]] = [
                    (day, period, room) for day in DAYS for period in PERIODS
                    for room in context["rooms"] if _check(context, [], section["id"], 1, day, period, room).valid]
                if not candidates[section["id"]]:
                    return False, f"No feasible slots for {section['section_code']}; check rooms, capacity and availability. Existing schedule preserved."
            # heuristic backtracking: constrained classes first, then balanced days.
            tasks = [(s, n) for s in sections for n in range(1, s["weekly"] // s["duration"] + 1)]
            rng = random.Random(17)
            best = []
            while time.perf_counter() < deadline:
                placed = []
                priorities = {s["id"]: rng.random() for s in sections}
                ordered = sorted(tasks, key=lambda task: (
                    task[1], len(candidates[task[0]["id"]]), -len(task[0]["students"]), priorities[task[0]["id"]]))
                # Bound each branch so a restart can explore a different ordering.
                nodes = [0]
                def search(index):
                    if time.perf_counter() >= deadline or nodes[0] > 2000:
                        return False
                    if index == len(ordered):
                        return True
                    section, occurrence = ordered[index]
                    nodes[0] += 1
                    day_load = {day: 0 for day in DAYS}
                    own_load = {day: 0 for day in DAYS}
                    for p in placed:
                        other = context["sections"][p["section_id"]]
                        if other["students"] & section["students"] or other["teacher_id"] == section["teacher_id"]:
                            day_load[p["day"]] += other["duration"]
                        if p["section_id"] == section["id"]:
                            own_load[p["day"]] += other["duration"]
                    options = list(candidates[section["id"]])
                    rng.shuffle(options)
                    options.sort(key=lambda slot: (own_load[slot[0]], day_load[slot[0]], slot[1]))
                    for day, period, room in options:
                        if time.perf_counter() >= deadline:
                            return False
                        if not _check(context, placed, section["id"], occurrence, day, period, room).valid:
                            continue
                        placed.append(dict(section_id=section["id"], occurrence=occurrence, day=day, period=period, room_id=room))
                        if len(placed) > len(best):
                            best[:] = placed
                        if search(index + 1):
                            return True
                        placed.pop()
                    return False
                if search(0):
                    conn.execute("DELETE FROM schedule_assignments")
                    conn.executemany("INSERT INTO schedule_assignments(section_id,occurrence,day,period,room_id) VALUES (:section_id,:occurrence,:day,:period,:room_id)", placed)
                    return True, f"Generated {len(placed)} weekly lessons ({sum(s['weekly'] for s in sections)} teaching periods) in {time.perf_counter()-started:.2f} seconds."
            remaining = [f"{s['section_code']} lesson {n}" for s, n in tasks
                         if not any(p["section_id"] == s["id"] and p["occurrence"] == n for p in best)]
            return False, "Time limit reached; existing schedule preserved. Unplaced: " + ", ".join(remaining[:15])

    def validate_assignment(self, section_id, day, period, room_id, occurrence=1):
        with connect(self.db_path) as conn:
            return self._validate_assignment(conn, section_id, day, period, room_id, occurrence)

    def _validate_assignment(self, conn, section_id, day, period, room_id, occurrence=1):
        return _check(_load_context(conn), [dict(r) for r in conn.execute("SELECT * FROM schedule_assignments")],
                      section_id, occurrence, day, period, room_id)

    def save_manual_assignment(self, section_id, day, period, room_id, occurrence=1):
        with connect(self.db_path) as conn:
            result = self._validate_assignment(conn, section_id, day, period, room_id, occurrence)
            if result.valid:
                conn.execute("""INSERT INTO schedule_assignments(section_id,occurrence,day,period,room_id) VALUES (?,?,?,?,?)
                    ON CONFLICT(section_id,occurrence) DO UPDATE SET day=excluded.day,period=excluded.period,room_id=excluded.room_id""",
                    (section_id, occurrence, day, period, room_id))
                return ValidationResult(True, "Assignment saved.")
            return result


def timetable_rows(db_path, role="admin", student_id=None, teacher_id=None):
    query = """SELECT sa.*,cs.duration,cs.level,cs.grade,cs.section_code,c.name AS course_name,
        t.name AS teacher_name,r.room_code FROM schedule_assignments sa
        JOIN course_sections cs ON cs.id=sa.section_id JOIN courses c ON c.id=cs.course_id
        JOIN teachers t ON t.id=cs.teacher_id JOIN rooms r ON r.id=sa.room_id"""
    params = []
    if role == "student":
        query += " JOIN student_enrollments se ON se.section_id=cs.id WHERE se.student_id=?"
        params.append(student_id or -1)
    elif role == "teacher":
        query += " WHERE cs.teacher_id=?"
        params.append(teacher_id or -1)
    elif role != "admin":
        raise ValueError("Unknown timetable role")
    with connect(db_path) as conn:
        rows = [dict(r) for r in conn.execute(query, params)]
    return sorted(rows, key=lambda r: (DAYS.index(r["day"]), r["period"], r["section_code"]))
