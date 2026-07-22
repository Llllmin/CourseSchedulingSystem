# IA Alignment Notes

## Criterion A

The project directly addresses the Ulink IB scheduling problem described in the planning document. It adds explicit administrator data management through SQLite tables and database constraints, then evaluates success using measurable outcomes such as generation time, role-based access, conflict-free assignments, and rejected invalid edits.

## Criterion B

Recommended decomposition:

1. Authentication and role authorization.
2. Scheduling data management.
3. Automatic timetable generation.
4. Timetable viewing for admin, teacher, and student.
5. Manual editing and immediate validation.
6. SQLite persistence.

## Criterion C

Recommended diagrams and tables:

- System architecture: Tkinter GUI -> application logic -> scheduler/validator -> SQLite database.
- DFD Level 0: users submit login/data/generation/edit requests; system returns filtered timetables and validation messages.
- ERD: users, students, teachers, rooms, courses, course_sections, student_enrollments, teacher_availability, blocked_periods, schedule_assignments.
- UML/module diagram: SchedulingApp, TimetableScheduler, database helpers, seed data module.
- Algorithms: generate timetable, validate assignment, role-filtered timetable retrieval.
- Test table: login, data validation, generation time, blocked periods, conflict detection, manual edits, persistence.

## Criterion D Evidence Candidates

- `TimetableScheduler.generate()` for backtracking and time limit handling.
- `TimetableScheduler._validate_assignment()` for conflict detection.
- `SchedulingApp._show_login()` for authentication and role routing.
- `SchedulingApp._build_manual_tab()` for immediate manual edit validation.

## Criterion E Evaluation Ideas

- Compare each success criterion against test output and GUI demonstration.
- Improvements: spreadsheet import/export, stronger password storage with salted hashes, optimization for larger datasets, automatic repair suggestions after teacher absence, and multi-campus room constraints.
