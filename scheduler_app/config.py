"""Shared constants used by the scheduling system.

Putting role names, room types, days, and periods in one file avoids repeated
string literals across the database, scheduler, and GUI modules.
"""

# The weekly timetable has five school days.
DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]

# Bell times follow the school's supplied timetable, including short breaks.
PERIOD_TIMES = {
    1: ("08:00", "08:40"), 2: ("08:45", "09:25"),
    3: ("09:35", "10:15"), 4: ("10:25", "11:05"),
    5: ("11:10", "11:50"), 6: ("11:55", "12:35"),
    7: ("12:40", "13:20"), 8: ("13:30", "14:10"),
    9: ("14:15", "14:55"), 10: ("15:05", "15:45"),
    11: ("15:50", "16:30"),
}
PERIODS = list(PERIOD_TIMES)
LUNCH_PERIODS = frozenset({5, 6})
WEEKLY_PERIODS = {"HL": 6, "SL": 4, "PE": 1, "TOK": 2, "EE": 1}

# Role names determine what the logged-in user is allowed to see.
ROLE_ADMIN = "admin"
ROLE_TEACHER = "teacher"
ROLE_STUDENT = "student"

# Room types are used to stop lab courses being placed in normal classrooms.
ROOM_STANDARD = "standard"
ROOM_LAB = "lab"
