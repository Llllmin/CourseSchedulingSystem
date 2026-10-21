"""Tkinter graphical user interface for the scheduling system.

The GUI is deliberately written with standard-library Tkinter so the IA project
can run in PyCharm without installing extra packages. The interface demonstrates
the required user roles: admin, teacher, and student.
"""

import tkinter as tk
import queue
import threading
from tkinter import ttk

from scheduler_app.auth import hash_password
from scheduler_app.config import DAYS, PERIODS, ROLE_ADMIN, ROLE_TEACHER, WEEKLY_PERIODS
from scheduler_app.database import connect
from scheduler_app.scheduler import TimetableScheduler, timetable_rows
from scheduler_app.timetable_view import WeeklyTimetable


class SchedulingApp(tk.Tk):
    """Main desktop window and all screen-building methods."""

    def __init__(self, db_path: str):
        """Initialize the window, connect the scheduler, and show login first."""
        super().__init__()
        self.db_path = db_path
        self.scheduler = TimetableScheduler(db_path)

        # Basic window settings make the app usable on a school laptop screen.
        self.title("Ulink IB Course Scheduling System")
        self.geometry("1120x720")
        self.minsize(960, 620)

        # current_user stores the logged-in database row as a dictionary.
        self.current_user = None
        self._show_login()

    def _clear(self) -> None:
        """Remove every widget so the next screen can be built cleanly."""
        self.unbind("<Return>")
        for child in self.winfo_children():
            child.destroy()

    def _show_login(self) -> None:
        """Build the login form and route users based on their role."""
        self._clear()
        frame = ttk.Frame(self, padding=36)
        frame.pack(expand=True)

        # Username and password fields collect credentials for database lookup.
        ttk.Label(frame, text="Ulink IB Course Scheduling System", font=("Arial", 20, "bold")).grid(row=0, column=0, columnspan=2, pady=(0, 24))
        ttk.Label(frame, text="Username").grid(row=1, column=0, sticky="e", padx=8, pady=8)
        username = ttk.Entry(frame, width=28)
        username.grid(row=1, column=1, pady=8)
        ttk.Label(frame, text="Password").grid(row=2, column=0, sticky="e", padx=8, pady=8)
        password = ttk.Entry(frame, width=28, show="*")
        password.grid(row=2, column=1, pady=8)
        status = ttk.Label(frame, text="Demo: admin/admin123, teacher01/teacher123, student001/student123")
        status.grid(row=4, column=0, columnspan=2, pady=(16, 0))

        def login() -> None:
            """Check credentials, store the user, and open the correct screen."""
            with connect(self.db_path) as conn:
                row = conn.execute(
                    "SELECT * FROM users WHERE username = ? AND password_hash = ?",
                    (username.get().strip(), hash_password(password.get())),
                ).fetchone()
            if not row:
                status.configure(text="Invalid username or password.")
                return
            self.current_user = dict(row)

            # Admins receive editing tools; students/teachers receive filtered views.
            if row["role"] == ROLE_ADMIN:
                self._show_admin()
            else:
                self._show_user_timetable()

        ttk.Button(frame, text="Login", command=login).grid(row=3, column=0, columnspan=2, pady=16)
        username.focus_set()
        self.bind("<Return>", lambda _event: login())

    def _header(self, parent: tk.Widget, title: str) -> None:
        """Create a consistent title bar and logout button for each screen."""
        bar = ttk.Frame(parent, padding=(16, 12))
        bar.pack(fill="x")
        ttk.Label(bar, text=title, font=("Arial", 16, "bold")).pack(side="left")
        ttk.Button(bar, text="Logout", command=self._show_login).pack(side="right")

    def _show_admin(self) -> None:
        """Build the administrator dashboard with multiple feature tabs."""
        self._clear()
        self._header(self, "Administrator Dashboard")
        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=16, pady=12)

        # Separate tabs match the admin workflows: generate, inspect, edit, data.
        generate_tab = ttk.Frame(notebook, padding=16)
        timetable_tab = ttk.Frame(notebook, padding=16)
        manual_tab = ttk.Frame(notebook, padding=16)
        data_tab = ttk.Frame(notebook, padding=16)
        notebook.add(timetable_tab, text="Weekly Schedule")
        notebook.add(generate_tab, text="Generate")
        notebook.add(manual_tab, text="Manual Edit")
        notebook.add(data_tab, text="Data Management")

        self._build_generate_tab(generate_tab, timetable_tab, manual_tab)
        self._build_timetable_tab(timetable_tab, ROLE_ADMIN)
        self._build_manual_tab(manual_tab)
        self._admin_timetable = timetable_tab
        self._admin_manual = manual_tab
        self._build_data_tab(data_tab)

    def _show_user_timetable(self) -> None:
        """Show a role-filtered timetable for a student or teacher account."""
        self._clear()
        role = self.current_user["role"]
        title = "Teacher Timetable" if role == ROLE_TEACHER else "Student Timetable"
        self._header(self, title)
        frame = ttk.Frame(self, padding=16)
        frame.pack(fill="both", expand=True)
        self._build_timetable_tab(
            frame,
            role,
            student_id=self.current_user["student_id"],
            teacher_id=self.current_user["teacher_id"],
        )

    def _build_generate_tab(self, parent: ttk.Frame, timetable_tab: ttk.Frame, manual_tab: ttk.Frame) -> None:
        """Create the tab that runs the automatic timetable generator."""
        info = ttk.Label(
            parent,
            text="Generate a complete timetable from the stored students, teachers, rooms, course sections, enrollments, and blocked periods.",
            wraplength=760,
        )
        info.pack(anchor="w", pady=(0, 12))
        output = tk.Text(parent, height=14, wrap="word")
        output.pack(fill="both", expand=True)

        def generate() -> None:
            """Generate the timetable and refresh dependent tabs after success."""
            button.configure(state="disabled")
            self._generating = True
            results = queue.Queue()
            output.insert("end", "Generating weekly lessons...\n")
            def worker():
                try:
                    results.put(self.scheduler.generate())
                except Exception as error:
                    results.put((False, str(error)))
            def poll():
                try:
                    ok, message = results.get_nowait()
                except queue.Empty:
                    self.after(100, poll)
                    return
                self._generating = False
                if not output.winfo_exists():
                    return
                button.configure(state="normal")
                output.insert("end", message + "\n")
                output.see("end")
                if ok:
                    self._refresh_timetable(timetable_tab, ROLE_ADMIN)
                    self._refresh_manual_options(manual_tab)
            threading.Thread(target=worker, daemon=True).start()
            self.after(100, poll)

        button = ttk.Button(parent, text="Generate Timetable", command=generate)
        button.pack(anchor="w", pady=12)

    def _build_timetable_tab(self, parent: ttk.Frame, role: str, student_id: int | None = None, teacher_id: int | None = None) -> None:
        """Build a week grid; only administrators receive other-user filters."""
        toolbar = ttk.Frame(parent)
        toolbar.pack(fill="x", pady=(0, 12))
        if role == ROLE_ADMIN:
            parent._scope = tk.StringVar(value="All sections")
            scope = ttk.Combobox(toolbar, textvariable=parent._scope, state="readonly",
                                 values=["All sections", "Teacher", "Student", "Room"], width=16)
            scope.pack(side="left", padx=(0, 8))
            parent._entity = tk.StringVar()
            parent._entity_combo = ttk.Combobox(toolbar, textvariable=parent._entity,
                                                state="disabled", width=30)
            parent._entity_combo.pack(side="left")
            def change_scope(_event=None):
                # Table and columns come from this fixed allowlist, never input.
                entities = {"Teacher": ("teachers", "teacher_code"),
                            "Student": ("students", "student_code"),
                            "Room": ("rooms", "room_code")}
                selected = entities.get(parent._scope.get())
                parent._entity_ids = {}
                if selected:
                    table, code = selected
                    with connect(self.db_path) as conn:
                        records = conn.execute(f"SELECT * FROM {table} ORDER BY {code}").fetchall()
                    for record in records:
                        label = record[code] if table == "rooms" else f"{record[code]} | {record['name']}"
                        parent._entity_ids[label] = record["id"]
                values = list(parent._entity_ids)
                parent._entity_combo.configure(values=values, state="readonly" if values else "disabled")
                parent._entity.set(values[0] if values else "")
                self._refresh_timetable(parent, role)
            scope.bind("<<ComboboxSelected>>", change_scope)
            parent._entity_combo.bind("<<ComboboxSelected>>", lambda _event: self._refresh_timetable(parent, role))
            parent._entity_ids = {}
        ttk.Button(toolbar, text="Refresh", command=lambda: self._refresh_timetable(parent, role, student_id, teacher_id)).pack(side="right")
        parent._summary = ttk.Label(parent)
        parent._summary.pack(anchor="w", pady=(0, 8))
        parent._week = WeeklyTimetable(parent)
        parent._week.pack(fill="both", expand=True)
        self._refresh_timetable(parent, role, student_id, teacher_id)

    def _refresh_timetable(self, parent: ttk.Frame, role: str, student_id: int | None = None, teacher_id: int | None = None) -> None:
        """Reload authorized rows and blocked periods into the weekly grid."""
        if not hasattr(parent, "_week"):
            return
        scope = parent._scope.get() if role == ROLE_ADMIN else "My schedule"
        entity_id = parent._entity_ids.get(parent._entity.get()) if role == ROLE_ADMIN else None
        query_role = role
        if role == ROLE_ADMIN and scope == "Student":
            query_role, student_id = "student", entity_id
        elif role == ROLE_ADMIN and scope == "Teacher":
            query_role, teacher_id = ROLE_TEACHER, entity_id
        rows = timetable_rows(self.db_path, query_role, student_id, teacher_id)
        with connect(self.db_path) as conn:
            blocked = {(r["day"], r["period"]): r["reason"] for r in conn.execute("SELECT * FROM blocked_periods")}
            if role == ROLE_ADMIN and scope == "Room":
                room = conn.execute("SELECT room_code FROM rooms WHERE id = ?", (entity_id,)).fetchone()
                rows = [r for r in rows if room and r["room_code"] == room["room_code"]]
            total = conn.execute("SELECT COUNT(*) FROM schedule_assignments").fetchone()[0]
        message = f"{len(rows)} lessons | {sum(r['duration'] for r in rows)} teaching periods | Weekly schedule"
        if not total:
            message = "No timetable generated yet." + (" Open Generate to create the schedule." if role == ROLE_ADMIN else " Contact your administrator.")
        elif not rows:
            message = "No lessons assigned to this selection."
        parent._summary.configure(text=message)
        parent._week.render(rows, blocked, student_view=query_role == "student")

    def _build_manual_tab(self, parent: ttk.Frame) -> None:
        """Create controls for validating and saving manual timetable edits."""
        form = ttk.Frame(parent)
        form.pack(anchor="nw", fill="x")

        # Tkinter StringVars keep combobox selections in sync with code.
        parent._section_var = tk.StringVar()
        parent._day_var = tk.StringVar(value=DAYS[0])
        parent._period_var = tk.StringVar(value="1")
        parent._room_var = tk.StringVar()
        parent._occurrence_var = tk.StringVar(value="1")
        parent._message = ttk.Label(parent, text="Choose a section, day, period, and room, then validate or save.")
        parent._message.pack(anchor="w", pady=(18, 0))

        labels = ["Section", "Day", "Period", "Room"]
        vars_ = [parent._section_var, parent._day_var, parent._period_var, parent._room_var]
        values = [[], DAYS, [str(p) for p in PERIODS], []]
        widgets = []

        # Build the four comboboxes using one loop to avoid repeated UI code.
        for column, (label, var, combo_values) in enumerate(zip(labels, vars_, values)):
            ttk.Label(form, text=label).grid(row=0, column=column, sticky="w", padx=(0, 12))
            combo = ttk.Combobox(form, textvariable=var, values=combo_values, width=19, state="readonly")
            combo.grid(row=1, column=column, sticky="w", padx=(0, 12), pady=4)
            widgets.append(combo)
        parent._section_combo = widgets[0]
        parent._room_combo = widgets[3]
        ttk.Label(form, text="Weekly lesson").grid(row=0, column=4, sticky="w")
        parent._occurrence_combo = ttk.Combobox(form, textvariable=parent._occurrence_var,
                                               state="readonly", width=9)
        parent._occurrence_combo.grid(row=1, column=4, sticky="w")
        parent._section_combo.bind("<<ComboboxSelected>>", lambda _e: self._update_occurrences(parent))
        parent._occurrence_combo.bind("<<ComboboxSelected>>", lambda _e: self._load_manual_assignment(parent))

        button_row = ttk.Frame(parent)
        button_row.pack(anchor="w", pady=16)

        def selected_ids() -> tuple[int, int] | None:
            """Extract numeric section and room IDs from combobox labels."""
            try:
                section_id = int(parent._section_var.get().split(" | ", 1)[0])
                room_id = int(parent._room_var.get().split(" | ", 1)[0])
                return section_id, room_id
            except (ValueError, IndexError):
                parent._message.configure(text="Select both a section and a room.")
                return None

        def validate() -> None:
            """Check a proposed edit without saving it."""
            ids = selected_ids()
            if ids is None:
                return
            result = self.scheduler.validate_assignment(ids[0], parent._day_var.get(), int(parent._period_var.get()), ids[1], int(parent._occurrence_var.get()))
            parent._message.configure(text=result.message)

        def save() -> None:
            """Validate and then store a proposed edit if it is legal."""
            ids = selected_ids()
            if ids is None:
                return
            if getattr(self, "_generating", False):
                parent._message.configure(text="Wait for timetable generation to finish.")
                return
            result = self.scheduler.save_manual_assignment(ids[0], parent._day_var.get(), int(parent._period_var.get()), ids[1], int(parent._occurrence_var.get()))
            parent._message.configure(text=result.message)
            if result.valid:
                self._refresh_timetable(self._admin_timetable, ROLE_ADMIN)

        ttk.Button(button_row, text="Validate", command=validate).pack(side="left", padx=(0, 8))
        ttk.Button(button_row, text="Save Assignment", command=save).pack(side="left")
        self._refresh_manual_options(parent)

    def _refresh_manual_options(self, parent: ttk.Frame) -> None:
        """Load current sections and rooms into the manual-edit comboboxes."""
        if not hasattr(parent, "_section_combo"):
            return

        # Sections and rooms are read from the database so new seed data appears.
        with connect(self.db_path) as conn:
            sections = conn.execute(
                """
                SELECT cs.id, cs.section_code, cs.level, cs.duration, c.name
                FROM course_sections cs JOIN courses c ON c.id = cs.course_id
                ORDER BY cs.section_code
                """
            ).fetchall()
            rooms = conn.execute("SELECT id, room_code, room_type, capacity FROM rooms ORDER BY room_code").fetchall()

        # Store the database ID at the start of each label for easy parsing.
        section_values = [f"{row['id']} | {row['section_code']} | {row['name']}" for row in sections]
        parent._lesson_counts = {row['id']: WEEKLY_PERIODS[row['level']] // row['duration'] for row in sections}
        room_values = [f"{row['id']} | {row['room_code']} | {row['room_type']} | cap {row['capacity']}" for row in rooms]
        parent._section_combo.configure(values=section_values)
        parent._room_combo.configure(values=room_values)
        if parent._section_var.get() not in section_values:
            parent._section_var.set(section_values[0] if section_values else "")
        if parent._room_var.get() not in room_values:
            parent._room_var.set(room_values[0] if room_values else "")
        self._update_occurrences(parent)

    def _update_occurrences(self, parent):
        try:
            section_id = int(parent._section_var.get().split(" | ")[0])
        except ValueError:
            section_id = None
        values = [str(n) for n in range(1, parent._lesson_counts.get(section_id, 0) + 1)]
        parent._occurrence_combo.configure(values=values)
        if parent._occurrence_var.get() not in values:
            parent._occurrence_var.set(values[0] if values else "1")
        self._load_manual_assignment(parent)

    def _load_manual_assignment(self, parent):
        """Pre-fill the chosen occurrence without moving any other weekly lesson."""
        try:
            section_id = int(parent._section_var.get().split(" | ")[0])
            occurrence = int(parent._occurrence_var.get())
        except ValueError:
            return
        with connect(self.db_path) as conn:
            row = conn.execute("SELECT * FROM schedule_assignments WHERE section_id=? AND occurrence=?",
                               (section_id, occurrence)).fetchone()
        if row:
            parent._day_var.set(row["day"])
            parent._period_var.set(str(row["period"]))
            for value in parent._room_combo.cget("values"):
                if value.startswith(f"{row['room_id']} | "):
                    parent._room_var.set(value)
                    break
            parent._message.configure(text=f"Weekly lesson {occurrence}: {row['day']} P{row['period']}")
        else:
            parent._message.configure(text=f"Weekly lesson {occurrence} has not been scheduled.")

    def _build_data_tab(self, parent):
        """Mount editable school data and refresh dependent schedule controls."""
        from scheduler_app.data_view import DataManager

        def changed():
            self._refresh_timetable(self._admin_timetable, ROLE_ADMIN)
            self._refresh_manual_options(self._admin_manual)

        self._data_manager = DataManager(parent, self.db_path, changed,
                                        can_edit=lambda: not getattr(self, "_generating", False))
