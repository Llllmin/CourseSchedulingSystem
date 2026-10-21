"""Anonymous 3HL/3SL dataset with independent PE, TOK and EE sections."""

from scheduler_app.auth import hash_password
from scheduler_app.database import connect
from scheduler_app.school_data import FIELDS, replace_data


def demo_data():
    data = {name: [] for name in FIELDS}
    for i in range(1, 61):
        data["Students"].append(dict(student_code=f"S{i:03d}", name=f"Student {i:03d}", grade="G11" if i <= 20 else "G12"))
    for i in range(1, 21):
        data["Teachers"].append(dict(teacher_code=f"T{i:02d}", name=f"Teacher {i:02d}", department="IB"))
    for i in range(1, 11):
        data["Rooms"].append(dict(room_code=f"R{i:02d}", capacity=30,
                                  room_type="lab" if i in (2, 5, 8) else "standard"))
    subjects = [("MATH", "Mathematics AA", "standard"), ("CS", "Computer Science", "lab"),
                ("ENG", "English B", "standard"), ("CHN", "Chinese A", "standard"),
                ("ECON", "Economics", "standard"), ("PHYS", "Physics", "lab"),
                ("PE", "Physical Education", "standard"), ("TOK", "Theory of Knowledge", "standard"),
                ("EE", "Extended Essay", "standard")]
    for code, name, room in subjects:
        data["Courses"].append(dict(course_code=code, name=name, requires_room_type=room))
    for group in range(3):
        for index, (code, _, _) in enumerate(subjects):
            # Cohorts have different HL/SL choices, with no mixed-level sections.
            level = ("HL" if (index + group) % 6 < 3 else "SL") if index < 6 else code
            section_code = f"{code}-{level}-{group+1}"
            data["Sections"].append(dict(section_code=section_code, course_code=code,
                teacher_code=f"T{(group*9+index)%20+1:02d}", grade="G11" if group == 0 else "G12",
                level=level, duration=1))
            for student in range(group*20+1, group*20+21):
                data["Enrollments"].append(dict(student_code=f"S{student:03d}", section_code=section_code))
    data["TeacherAvailability"].append(dict(teacher_code="T01", day="Wednesday", period=1, available=0))
    return data


def load_demo_data(db_path):
    """Explicit demo reset; replace_data backs up the old database first."""
    result = replace_data(db_path, demo_data())
    with connect(db_path) as conn:
        for role, table in (("student", "students"), ("teacher", "teachers")):
            conn.execute("DELETE FROM users WHERE role=?", (role,))
            for number, row in enumerate(conn.execute(f"SELECT id FROM {table} ORDER BY id").fetchall(), 1):
                username = f"student{number:03d}" if role == "student" else f"teacher{number:02d}"
                conn.execute(f"INSERT INTO users(username,password_hash,role,{role}_id) VALUES (?,?,?,?)",
                             (username, hash_password(role + "123"), role, row["id"]))
    return result[0]


def seed_demo_data(db_path):
    with connect(db_path) as conn:
        if conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]:
            return
        conn.execute("INSERT INTO users(username,password_hash,role) VALUES (?,?,?)",
                     ("admin", hash_password("admin123"), "admin"))
    load_demo_data(db_path)
