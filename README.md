# Ulink IB Course Scheduling System

Python Tkinter + SQLite desktop project for an IB school timetable.

## Run in PyCharm

Open this folder as the project and run `main.py`. Python 3.10+ with Tkinter
is required. Install the Excel dependency into the selected interpreter:

```bash
python3 -m pip install -r requirements.txt
python3 main.py
```

The database always lives beside main.py, independent of PyCharm's working
directory. Closing the program does not erase data.

## Try the complete demo

1. Sign in as `admin` / `admin123`.
2. Open Data Management and select Load Demo Data. This also upgrades an old
   demo to the new weekly model; it backs up existing data before replacement.
3. Open Generate and select Generate Timetable.
4. Open Weekly Schedule, then select Student, Teacher, Room or All sections.

The demo contains 60 fictional students, 20 teachers, 10 rooms and 27 sections.
Every student has 3 HL + 3 SL + PE + TOK + EE: 34 teaching periods per week,
distributed over five weekdays. Demo accounts remain `student001/student123`
and `teacher01/teacher123`.

## Weekly Rules

- HL: 6 periods, SL: 4, PE: 1, TOK: 2, EE: 1 each week.
- Each section has a grade, level and lesson duration (1 or 2). A duration of 2
  means all its meetings are double lessons; the duration must divide its weekly
  total. Use duration 1 for unrestricted single lessons.
- At most two periods of the same section can occur on one day. The generator
  prefers unused weekdays and balances student/teacher daily load.
- Monday-Friday, P1-P11, 08:00-16:30, with school-specific 5/10 minute breaks.
- Every student must retain at least one free period out of P5/P6 every day.
- Teacher, student, room, capacity, lab, availability and school blocks are checked.
- Teachers can teach sections in different grades. Conflicts apply across grades.
- Form meetings are not required. No club blocks are added by the new demo.

Generation runs off the UI thread with a default 10-second search budget. A full
solution replaces the old schedule atomically; failure preserves it and reports
unplaced lessons or data errors. Dense real datasets are not guaranteed solvable.

## Import and Edit Data

See [the import guide](docs/DATA_IMPORT.md) for worksheet fields and an example.

Data Management provides Excel Template, Export Excel, Import Excel, and
New/Edit/Delete for all eight data tables. Double-click a row to edit it.
Imports are validated as a complete school dataset before replacement. Record
forms allow incomplete drafts; Validate All and Generate require a complete
3HL/3SL/core enrollment for every student.

Successful data changes clear the old schedule, which must be regenerated.
Before each change, a timestamped database snapshot is saved in `backups/`.
The original admin account and existing student/teacher accounts with matching
school codes survive an import. New people get usernames such as `student_S001`
and random passwords; their login details are saved locally in `data/new_accounts_*.csv`.
Exports do not contain passwords or login hashes. Passwords currently use the
prototype's SHA-256 storage, so production account security remains future work.

Manual Edit now selects both a section and its Weekly lesson number. The selected
lesson's current day, period and room load automatically. Saving moves only that
occurrence; all other weekly lessons remain unchanged.

## Persistence and Privacy

`school_schedule.db` stores school records and assignments. Keep a copy of this
file or a backup outside the machine for recovery. To restore a backup, close the
app, retain a copy of the current database, and replace school_schedule.db with
the desired backup. Backups, databases, credentials, and the local data directory
are ignored by Git. Keep real-data Excel files under `data/`, not in source folders.
Existing databases are migrated without deleting their people or assignments;
old five-course demo enrollments must be replaced using Load Demo Data or Excel.

## Tests

```bash
python3 -m unittest discover -s tests
```

Coverage includes weekly counts, five-day distribution, lunch, double lessons,
conflicts, role filtering, import validation, rollback, backups, account
preservation, persistence and failed-generation preservation.
