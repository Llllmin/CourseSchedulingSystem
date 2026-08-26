"""Create anonymous demonstration data for the IA project.

The system needs enough data to prove it can schedule a realistic school-sized
dataset. These records are fictional, so the public GitHub repository does not
contain any private student information.
"""

from scheduler_app.auth import hash_password
from scheduler_app.config import DAYS, ROLE_ADMIN, ROLE_STUDENT, ROLE_TEACHER, ROOM_LAB, ROOM_STANDARD
from scheduler_app.database import connect, table_count


# Each tuple stores course code, readable name, and required room type.
COURSE_NAMES = [
    ("MATHAAHL", "Mathematics AA HL", ROOM_STANDARD),
    ("MATHAASL", "Mathematics AA SL", ROOM_STANDARD),
    ("ENGA", "English A", ROOM_STANDARD),
    ("PHYSHL", "Physics HL", ROOM_LAB),
    ("CHEMHL", "Chemistry HL", ROOM_LAB),
    ("BIOHL", "Biology HL", ROOM_LAB),
    ("ECONHL", "Economics HL", ROOM_STANDARD),
    ("HISTHL", "History HL", ROOM_STANDARD),
    ("CSHL", "Computer Science HL", ROOM_LAB),
    ("ARTSL", "Visual Arts SL", ROOM_STANDARD),
]


def seed_demo_data(db_path: str) -> None:
    """Insert a complete anonymous dataset if the database is empty."""
    with connect(db_path) as conn:
        # Avoid duplicating data every time main.py starts the application.
        if table_count(conn, "students") > 0:
            return

        # Create one administrator account that can generate and edit all data.
        conn.execute(
            "INSERT INTO users(username, password_hash, role) VALUES (?, ?, ?)",
            ("admin", hash_password("admin123"), ROLE_ADMIN),
        )

        # Insert twenty fictional teachers across several departments.
        for i in range(1, 21):
            conn.execute(
                "INSERT INTO teachers(teacher_code, name, department) VALUES (?, ?, ?)",
                (f"T{i:02d}", f"Teacher {i:02d}", ["Math", "Science", "Humanities", "Languages"][i % 4]),
            )

        # Insert sixty fictional students and one login account per student.
        for i in range(1, 61):
            cur = conn.execute(
                "INSERT INTO students(student_code, name, grade) VALUES (?, ?, ?)",
                (f"S{i:03d}", f"Student {i:03d}", "G11" if i <= 30 else "G12"),
            )
            conn.execute(
                "INSERT INTO users(username, password_hash, role, student_id) VALUES (?, ?, ?, ?)",
                (f"student{i:03d}", hash_password("student123"), ROLE_STUDENT, cur.lastrowid),
            )

        # Create login accounts for all teachers after their teacher IDs exist.
        teacher_rows = conn.execute("SELECT id FROM teachers ORDER BY id").fetchall()
        for i, teacher in enumerate(teacher_rows, start=1):
            conn.execute(
                "INSERT INTO users(username, password_hash, role, teacher_id) VALUES (?, ?, ?, ?)",
                (f"teacher{i:02d}", hash_password("teacher123"), ROLE_TEACHER, teacher["id"]),
            )

        # Create ten rooms; three are labs with slightly smaller capacity.
        for i in range(1, 11):
            room_type = ROOM_LAB if i in (2, 5, 8) else ROOM_STANDARD
            capacity = 28 if room_type == ROOM_LAB else 34
            conn.execute(
                "INSERT INTO rooms(room_code, capacity, room_type) VALUES (?, ?, ?)",
                (f"R{i:02d}", capacity, room_type),
            )

        # Insert subjects before creating specific class sections.
        for code, name, required_type in COURSE_NAMES:
            conn.execute(
                "INSERT INTO courses(course_code, name, requires_room_type) VALUES (?, ?, ?)",
                (code, name, required_type),
            )

        # Create twenty-five sections, including some double-period classes.
        courses = conn.execute("SELECT id, course_code FROM courses ORDER BY id").fetchall()
        teachers = conn.execute("SELECT id FROM teachers ORDER BY id").fetchall()
        section_ids = []
        for i in range(25):
            course = courses[i % len(courses)]
            duration = 2 if i in (3, 7, 12, 18, 22) else 1
            cur = conn.execute(
                """
                INSERT INTO course_sections(section_code, course_id, teacher_id, duration)
                VALUES (?, ?, ?, ?)
                """,
                (f"{course['course_code']}-{i // len(courses) + 1}", course["id"], teachers[i % len(teachers)]["id"], duration),
            )
            section_ids.append(cur.lastrowid)

        # Give each student five course sections so student clashes can be tested.
        students = conn.execute("SELECT id FROM students ORDER BY id").fetchall()
        for index, student in enumerate(students):
            choices = [(index + offset * 5) % len(section_ids) for offset in range(5)]
            for section_index in choices:
                conn.execute(
                    "INSERT INTO student_enrollments(student_id, section_id) VALUES (?, ?)",
                    (student["id"], section_ids[section_index]),
                )

        # Block lunch on every day and club time on Friday afternoon.
        for day in DAYS:
            conn.execute(
                "INSERT INTO blocked_periods(day, period, reason) VALUES (?, ?, ?)",
                (day, 4, "Lunch"),
            )
        conn.execute(
            "INSERT INTO blocked_periods(day, period, reason) VALUES (?, ?, ?)",
            ("Friday", 8, "Club time"),
        )

        # Mark several teachers unavailable for one period to test constraints.
        for teacher_id in [1, 4, 7, 10, 13, 16, 19]:
            conn.execute(
                "INSERT INTO teacher_availability(teacher_id, day, period, available) VALUES (?, ?, ?, 0)",
                (teacher_id, "Wednesday", 1),
            )
