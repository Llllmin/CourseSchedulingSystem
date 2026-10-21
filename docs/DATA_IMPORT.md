# School Data Import Guide

## Start With an Example

In Data Management, use Load Demo Data, then Export Excel to get a complete,
valid fictional example. Excel Template instead saves an empty workbook with
the correct headers. Keep all eight sheet names and column headers unchanged.
Enter plain values, not formulas. Use codes as text, especially leading zeros.

| Sheet | Columns | Notes |
| --- | --- | --- |
| Students | student_code, name, grade | One row per student; code must be unique. |
| Teachers | teacher_code, name, department | One row per teacher, across all grades. |
| Rooms | room_code, capacity, room_type | Positive integer capacity; standard or lab. |
| Courses | course_code, name, requires_room_type | Base subject, such as MATH; standard or lab. |
| Sections | section_code, course_code, teacher_code, grade, level, duration | Level: HL, SL, PE, TOK or EE. Duration: 1 or 2. |
| Enrollments | student_code, section_code | One row per student's section membership. |
| TeacherAvailability | teacher_code, day, period, available | Monday-Friday; period 1-11; 0 unavailable, 1 available. Missing rows mean available. |
| BlockedPeriods | day, period, reason | School-wide bans, not individual student lunch. |

TeacherAvailability and BlockedPeriods may have no data rows, but retain headers.

## Subjects, Sections and Weekly Counts

Courses describe subjects. Sections describe specific student groups with a
teacher, grade and HL/SL/core level. A teacher may appear in many section rows,
including sections in different grades. The timetable prevents teacher overlap.

For example, Courses can contain MATH, Mathematics AA, standard. Sections can
then contain MATH-HL-12A, MATH, T01, G12, HL, 1. Each student in this section
gets six 40-minute meetings, not one meeting. There is no need to repeat its
enrollment row six times.

Every student needs nine enrollment rows: six distinct academic subjects
(three HL and three SL), plus PE, TOK and EE. A student cannot join two sections
of the same base subject. Student and section grade labels must match exactly.
Core sections have separate codes, for example PE-12A, TOK-12A and EE-12A, even
when they share the same student list. These core sections can have different
teachers. No form-class meeting is required.

Duration 1 gives HL six single lessons, SL four, PE one, TOK two, EE one.
Duration 2 gives HL three double lessons, SL two doubles, TOK one double;
PE and EE must use duration 1. Mixed single/double meeting patterns within the
same section are not yet configurable. Each section is limited to two teaching
periods per day, and the algorithm prefers spreading them across the week.

## Import

1. Finish all sheets and save as .xlsx.
2. Select Import Excel. The application validates headers, duplicates,
   references, grades, 3HL/3SL/core selections and room suitability first.
3. Review the record counts, then confirm replacement. This replaces the school
   dataset; it does not merge only the selected Excel rows.
4. A backup is saved in backups/. If validation or a database constraint fails,
   existing data and the current timetable remain unchanged.
5. Successful import clears the old timetable. Open Generate to create a new one.

Existing login accounts are retained when their person code matches. New
student/teacher passwords are random and listed in a local data/new_accounts_*.csv
file. Keep this file private. Admin accounts are not replaced by the workbook.

## Edit in the App

Select a table, then New, Edit or Delete. Double-click also opens Edit.
Entity codes are immutable after creation so references cannot silently break.
Change names, capacity, teacher assignments, levels or duration in the forms.
To change a code, remove dependent records first, or update the complete Excel
workbook and import it. Referenced students, teachers, courses and sections
cannot be deleted until their dependent records have been removed.

Forms allow incomplete draft enrollments so records can be entered step by step.
Use Validate All before generating. All successful record saves clear the
schedule and create backups; regenerate only after finishing your data edits.

Keep real workbooks in the ignored data/ directory. Git ignores databases,
backups and credential files, but an Excel workbook placed elsewhere in the
repository is not automatically private.
