"""SQLite database setup and connection utilities.

This module contains all table definitions for the scheduling system. SQLite is
used because it gives real relational tables and SQL constraints without
requiring a separate MySQL server during the IA demonstration.
"""

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


@contextmanager
def connect(db_path: str) -> Iterator[sqlite3.Connection]:
    """Open a SQLite connection and close it safely after use."""
    # row_factory lets code access columns by name, e.g. row["teacher_id"].
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    # SQLite requires this setting per connection to enforce foreign keys.
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn

        # Save all changes if no exception happened inside the with-block.
        conn.commit()
    except Exception:
        # Undo partial changes so invalid operations do not corrupt the data.
        conn.rollback()
        raise
    finally:
        conn.close()


def initialize_database(db_path: str) -> None:
    """Create every table needed by the application if it does not exist."""
    # If db_path includes a folder, create it so SQLite can create the file.
    Path(db_path).parent.mkdir(parents=True, exist_ok=True) if Path(db_path).parent != Path(".") else None
    with connect(db_path) as conn:
        # The schema models the IA entities: users, people, rooms, courses,
        # enrollments, constraints, and generated timetable assignments.
        conn.executescript(
            """
            -- Students are learners who log in to see their own timetable.
            CREATE TABLE IF NOT EXISTS students (
                id INTEGER PRIMARY KEY,
                student_code TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                grade TEXT NOT NULL
            );

            -- Teachers are assigned to course sections and have timetables.
            CREATE TABLE IF NOT EXISTS teachers (
                id INTEGER PRIMARY KEY,
                teacher_code TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                department TEXT NOT NULL
            );

            -- Rooms have capacity and type constraints used by validation.
            CREATE TABLE IF NOT EXISTS rooms (
                id INTEGER PRIMARY KEY,
                room_code TEXT NOT NULL UNIQUE,
                capacity INTEGER NOT NULL CHECK (capacity > 0),
                room_type TEXT NOT NULL CHECK (room_type IN ('standard', 'lab'))
            );

            -- Users connect login credentials to a role and optional person.
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL CHECK (role IN ('admin', 'teacher', 'student')),
                student_id INTEGER,
                teacher_id INTEGER,
                FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
                FOREIGN KEY (teacher_id) REFERENCES teachers(id) ON DELETE CASCADE
            );

            -- Courses describe subject-level information such as lab needs.
            CREATE TABLE IF NOT EXISTS courses (
                id INTEGER PRIMARY KEY,
                course_code TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                requires_room_type TEXT NOT NULL CHECK (requires_room_type IN ('standard', 'lab'))
            );

            -- Course sections are the actual classes that must be scheduled.
            CREATE TABLE IF NOT EXISTS course_sections (
                id INTEGER PRIMARY KEY,
                section_code TEXT NOT NULL UNIQUE,
                course_id INTEGER NOT NULL,
                teacher_id INTEGER NOT NULL,
                duration INTEGER NOT NULL CHECK (duration IN (1, 2)),
                FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE,
                FOREIGN KEY (teacher_id) REFERENCES teachers(id) ON DELETE RESTRICT
            );

            -- This many-to-many table records which students take each class.
            CREATE TABLE IF NOT EXISTS student_enrollments (
                student_id INTEGER NOT NULL,
                section_id INTEGER NOT NULL,
                PRIMARY KEY (student_id, section_id),
                FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
                FOREIGN KEY (section_id) REFERENCES course_sections(id) ON DELETE CASCADE
            );

            -- Unavailable teacher slots prevent assigning a teacher then.
            CREATE TABLE IF NOT EXISTS teacher_availability (
                teacher_id INTEGER NOT NULL,
                day TEXT NOT NULL,
                period INTEGER NOT NULL,
                available INTEGER NOT NULL CHECK (available IN (0, 1)),
                PRIMARY KEY (teacher_id, day, period),
                FOREIGN KEY (teacher_id) REFERENCES teachers(id) ON DELETE CASCADE
            );

            -- School-wide blocked periods, such as lunch, cannot contain class.
            CREATE TABLE IF NOT EXISTS blocked_periods (
                day TEXT NOT NULL,
                period INTEGER NOT NULL,
                reason TEXT NOT NULL,
                PRIMARY KEY (day, period)
            );

            -- Generated or manually edited timetable placements are stored here.
            CREATE TABLE IF NOT EXISTS schedule_assignments (
                id INTEGER PRIMARY KEY,
                section_id INTEGER NOT NULL UNIQUE,
                day TEXT NOT NULL,
                period INTEGER NOT NULL,
                room_id INTEGER NOT NULL,
                FOREIGN KEY (section_id) REFERENCES course_sections(id) ON DELETE CASCADE,
                FOREIGN KEY (room_id) REFERENCES rooms(id) ON DELETE RESTRICT
            );
            """
        )


def table_count(conn: sqlite3.Connection, table: str) -> int:
    """Return the number of rows in a table, used by seed_data.py."""
    return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
