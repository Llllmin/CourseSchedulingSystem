# Ulink IB Course Scheduling System

Python Tkinter + SQLite IA project for a realistic school timetable system.

## Run in PyCharm

1. Open this folder as a PyCharm project:
   `CourseSchedulingSystem`
2. Open `main.py`.
3. Click Run.

The app creates `school_schedule.db` automatically and seeds anonymous demo data:

- 60 students
- 20 teachers
- 10 rooms
- 25 course sections

Demo logins:

- Admin: `admin` / `admin123`
- Teacher: `teacher01` / `teacher123`
- Student: `student001` / `student123`

## Test

```bash
python3 -m unittest discover -s tests
```

## IA Features

- Role-based login for admin, teacher, and student views.
- SQLite persistence for users, students, teachers, rooms, course sections, enrollments, blocked periods, and timetable assignments.
- Automatic timetable generation using constraint checking and backtracking.
- Validation for student, teacher, room, capacity, room type, blocked period, and double-period constraints.
- Administrator manual reassignment screen with immediate conflict feedback.
