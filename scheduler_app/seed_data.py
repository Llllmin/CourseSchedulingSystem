from scheduler_app.auth import hash_password
from scheduler_app.config import DAYS, ROLE_ADMIN, ROLE_STUDENT, ROLE_TEACHER, ROOM_LAB, ROOM_STANDARD
from scheduler_app.database import connect, table_count


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
    with connect(db_path) as conn:
        if table_count(conn, "students") > 0:
            return

        conn.execute(
            "INSERT INTO users(username, password_hash, role) VALUES (?, ?, ?)",
            ("admin", hash_password("admin123"), ROLE_ADMIN),
        )

        for i in range(1, 21):
            conn.execute(
                "INSERT INTO teachers(teacher_code, name, department) VALUES (?, ?, ?)",
                (f"T{i:02d}", f"Teacher {i:02d}", ["Math", "Science", "Humanities", "Languages"][i % 4]),
            )

        for i in range(1, 61):
            cur = conn.execute(
                "INSERT INTO students(student_code, name, grade) VALUES (?, ?, ?)",
                (f"S{i:03d}", f"Student {i:03d}", "G11" if i <= 30 else "G12"),
            )
            conn.execute(
                "INSERT INTO users(username, password_hash, role, student_id) VALUES (?, ?, ?, ?)",
                (f"student{i:03d}", hash_password("student123"), ROLE_STUDENT, cur.lastrowid),
            )

        teacher_rows = conn.execute("SELECT id FROM teachers ORDER BY id").fetchall()
        for i, teacher in enumerate(teacher_rows, start=1):
            conn.execute(
                "INSERT INTO users(username, password_hash, role, teacher_id) VALUES (?, ?, ?, ?)",
                (f"teacher{i:02d}", hash_password("teacher123"), ROLE_TEACHER, teacher["id"]),
            )

        for i in range(1, 11):
            room_type = ROOM_LAB if i in (2, 5, 8) else ROOM_STANDARD
            capacity = 28 if room_type == ROOM_LAB else 34
            conn.execute(
                "INSERT INTO rooms(room_code, capacity, room_type) VALUES (?, ?, ?)",
                (f"R{i:02d}", capacity, room_type),
            )

        for code, name, required_type in COURSE_NAMES:
            conn.execute(
                "INSERT INTO courses(course_code, name, requires_room_type) VALUES (?, ?, ?)",
                (code, name, required_type),
            )

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

        students = conn.execute("SELECT id FROM students ORDER BY id").fetchall()
        for index, student in enumerate(students):
            choices = [(index + offset * 5) % len(section_ids) for offset in range(5)]
            for section_index in choices:
                conn.execute(
                    "INSERT INTO student_enrollments(student_id, section_id) VALUES (?, ?)",
                    (student["id"], section_ids[section_index]),
                )

        for day in DAYS:
            conn.execute(
                "INSERT INTO blocked_periods(day, period, reason) VALUES (?, ?, ?)",
                (day, 4, "Lunch"),
            )
        conn.execute(
            "INSERT INTO blocked_periods(day, period, reason) VALUES (?, ?, ?)",
            ("Friday", 8, "Club time"),
        )

        for teacher_id in [1, 4, 7, 10, 13, 16, 19]:
            conn.execute(
                "INSERT INTO teacher_availability(teacher_id, day, period, available) VALUES (?, ?, ?, 0)",
                (teacher_id, "Wednesday", 1),
            )
