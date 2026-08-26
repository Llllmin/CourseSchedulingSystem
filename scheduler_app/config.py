"""Shared constants used by the scheduling system.

Putting role names, room types, days, and periods in one file avoids repeated
string literals across the database, scheduler, and GUI modules.
"""

# The weekly timetable has five school days.
DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]

# Each day has eight teaching periods in this IA prototype.
PERIODS = list(range(1, 9))

# Role names determine what the logged-in user is allowed to see.
ROLE_ADMIN = "admin"
ROLE_TEACHER = "teacher"
ROLE_STUDENT = "student"

# Room types are used to stop lab courses being placed in normal classrooms.
ROOM_STANDARD = "standard"
ROOM_LAB = "lab"
