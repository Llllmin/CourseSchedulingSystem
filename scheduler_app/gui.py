import tkinter as tk
from tkinter import ttk

from scheduler_app.auth import hash_password
from scheduler_app.config import DAYS, PERIODS, ROLE_ADMIN, ROLE_TEACHER
from scheduler_app.database import connect
from scheduler_app.scheduler import TimetableScheduler, timetable_rows


class SchedulingApp(tk.Tk):
    def __init__(self, db_path: str):
        super().__init__()
        self.db_path = db_path
        self.scheduler = TimetableScheduler(db_path)
        self.title("Ulink IB Course Scheduling System")
        self.geometry("1120x720")
        self.minsize(960, 620)
        self.current_user = None
        self._show_login()

    def _clear(self) -> None:
        for child in self.winfo_children():
            child.destroy()

    def _show_login(self) -> None:
        self._clear()
        frame = ttk.Frame(self, padding=36)
        frame.pack(expand=True)

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
            with connect(self.db_path) as conn:
                row = conn.execute(
                    "SELECT * FROM users WHERE username = ? AND password_hash = ?",
                    (username.get().strip(), hash_password(password.get())),
                ).fetchone()
            if not row:
                status.configure(text="Invalid username or password.")
                return
            self.current_user = dict(row)
            if row["role"] == ROLE_ADMIN:
                self._show_admin()
            else:
                self._show_user_timetable()

        ttk.Button(frame, text="Login", command=login).grid(row=3, column=0, columnspan=2, pady=16)
        username.focus_set()
        self.bind("<Return>", lambda _event: login())

    def _header(self, parent: tk.Widget, title: str) -> None:
        bar = ttk.Frame(parent, padding=(16, 12))
        bar.pack(fill="x")
        ttk.Label(bar, text=title, font=("Arial", 16, "bold")).pack(side="left")
        ttk.Button(bar, text="Logout", command=self._show_login).pack(side="right")

    def _show_admin(self) -> None:
        self._clear()
        self._header(self, "Administrator Dashboard")
        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=16, pady=12)

        generate_tab = ttk.Frame(notebook, padding=16)
        timetable_tab = ttk.Frame(notebook, padding=16)
        manual_tab = ttk.Frame(notebook, padding=16)
        data_tab = ttk.Frame(notebook, padding=16)
        notebook.add(generate_tab, text="Generate")
        notebook.add(timetable_tab, text="All Timetables")
        notebook.add(manual_tab, text="Manual Edit")
        notebook.add(data_tab, text="Data Management")

        self._build_generate_tab(generate_tab, timetable_tab, manual_tab)
        self._build_timetable_tab(timetable_tab, ROLE_ADMIN)
        self._build_manual_tab(manual_tab)
        self._build_data_tab(data_tab)

    def _show_user_timetable(self) -> None:
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
        info = ttk.Label(
            parent,
            text="Generate a complete timetable from the stored students, teachers, rooms, course sections, enrollments, and blocked periods.",
            wraplength=760,
        )
        info.pack(anchor="w", pady=(0, 12))
        output = tk.Text(parent, height=14, wrap="word")
        output.pack(fill="both", expand=True)

        def generate() -> None:
            ok, message = self.scheduler.generate()
            output.insert("end", message + "\n")
            output.see("end")
            if ok:
                self._refresh_timetable(timetable_tab, ROLE_ADMIN)
                self._refresh_manual_options(manual_tab)

        ttk.Button(parent, text="Generate Timetable", command=generate).pack(anchor="w", pady=12)

    def _build_timetable_tab(self, parent: ttk.Frame, role: str, student_id: int | None = None, teacher_id: int | None = None) -> None:
        ttk.Button(parent, text="Refresh", command=lambda: self._refresh_timetable(parent, role, student_id, teacher_id)).pack(anchor="w", pady=(0, 8))
        tree = ttk.Treeview(parent, columns=("day", "period", "duration", "section", "course", "teacher", "room"), show="headings")
        for key, title, width in [
            ("day", "Day", 100),
            ("period", "Period", 70),
            ("duration", "Duration", 80),
            ("section", "Section", 120),
            ("course", "Course", 220),
            ("teacher", "Teacher", 150),
            ("room", "Room", 90),
        ]:
            tree.heading(key, text=title)
            tree.column(key, width=width, anchor="w")
        tree.pack(fill="both", expand=True)
        parent._tree = tree
        self._refresh_timetable(parent, role, student_id, teacher_id)

    def _refresh_timetable(self, parent: ttk.Frame, role: str, student_id: int | None = None, teacher_id: int | None = None) -> None:
        tree = getattr(parent, "_tree", None)
        if tree is None:
            return
        for item in tree.get_children():
            tree.delete(item)
        for row in timetable_rows(self.db_path, role, student_id, teacher_id):
            tree.insert(
                "",
                "end",
                values=(row["day"], row["period"], row["duration"], row["section_code"], row["course_name"], row["teacher_name"], row["room_code"]),
            )

    def _build_manual_tab(self, parent: ttk.Frame) -> None:
        form = ttk.Frame(parent)
        form.pack(anchor="nw", fill="x")
        parent._section_var = tk.StringVar()
        parent._day_var = tk.StringVar(value=DAYS[0])
        parent._period_var = tk.StringVar(value="1")
        parent._room_var = tk.StringVar()
        parent._message = ttk.Label(parent, text="Choose a section, day, period, and room, then validate or save.")
        parent._message.pack(anchor="w", pady=(18, 0))

        labels = ["Section", "Day", "Period", "Room"]
        vars_ = [parent._section_var, parent._day_var, parent._period_var, parent._room_var]
        values = [[], DAYS, [str(p) for p in PERIODS], []]
        widgets = []
        for column, (label, var, combo_values) in enumerate(zip(labels, vars_, values)):
            ttk.Label(form, text=label).grid(row=0, column=column, sticky="w", padx=(0, 12))
            combo = ttk.Combobox(form, textvariable=var, values=combo_values, width=24, state="readonly")
            combo.grid(row=1, column=column, sticky="w", padx=(0, 12), pady=4)
            widgets.append(combo)
        parent._section_combo = widgets[0]
        parent._room_combo = widgets[3]

        button_row = ttk.Frame(parent)
        button_row.pack(anchor="w", pady=16)

        def selected_ids() -> tuple[int, int] | None:
            try:
                section_id = int(parent._section_var.get().split(" | ", 1)[0])
                room_id = int(parent._room_var.get().split(" | ", 1)[0])
                return section_id, room_id
            except (ValueError, IndexError):
                parent._message.configure(text="Select both a section and a room.")
                return None

        def validate() -> None:
            ids = selected_ids()
            if ids is None:
                return
            result = self.scheduler.validate_assignment(ids[0], parent._day_var.get(), int(parent._period_var.get()), ids[1])
            parent._message.configure(text=result.message)

        def save() -> None:
            ids = selected_ids()
            if ids is None:
                return
            result = self.scheduler.save_manual_assignment(ids[0], parent._day_var.get(), int(parent._period_var.get()), ids[1])
            parent._message.configure(text=result.message)

        ttk.Button(button_row, text="Validate", command=validate).pack(side="left", padx=(0, 8))
        ttk.Button(button_row, text="Save Assignment", command=save).pack(side="left")
        self._refresh_manual_options(parent)

    def _refresh_manual_options(self, parent: ttk.Frame) -> None:
        if not hasattr(parent, "_section_combo"):
            return
        with connect(self.db_path) as conn:
            sections = conn.execute(
                """
                SELECT cs.id, cs.section_code, c.name
                FROM course_sections cs JOIN courses c ON c.id = cs.course_id
                ORDER BY cs.section_code
                """
            ).fetchall()
            rooms = conn.execute("SELECT id, room_code, room_type, capacity FROM rooms ORDER BY room_code").fetchall()
        section_values = [f"{row['id']} | {row['section_code']} | {row['name']}" for row in sections]
        room_values = [f"{row['id']} | {row['room_code']} | {row['room_type']} | cap {row['capacity']}" for row in rooms]
        parent._section_combo.configure(values=section_values)
        parent._room_combo.configure(values=room_values)
        if section_values and not parent._section_var.get():
            parent._section_var.set(section_values[0])
        if room_values and not parent._room_var.get():
            parent._room_var.set(room_values[0])

    def _build_data_tab(self, parent: ttk.Frame) -> None:
        summary = ttk.Frame(parent)
        summary.pack(fill="x", pady=(0, 12))
        with connect(self.db_path) as conn:
            counts = {
                "Students": conn.execute("SELECT COUNT(*) FROM students").fetchone()[0],
                "Teachers": conn.execute("SELECT COUNT(*) FROM teachers").fetchone()[0],
                "Rooms": conn.execute("SELECT COUNT(*) FROM rooms").fetchone()[0],
                "Course sections": conn.execute("SELECT COUNT(*) FROM course_sections").fetchone()[0],
                "Enrollments": conn.execute("SELECT COUNT(*) FROM student_enrollments").fetchone()[0],
            }
        for index, (label, value) in enumerate(counts.items()):
            ttk.Label(summary, text=f"{label}: {value}", font=("Arial", 11, "bold")).grid(row=0, column=index, padx=(0, 18), sticky="w")

        ttk.Label(parent, text="Data management is stored in SQLite. Duplicate IDs and invalid references are rejected by database constraints.").pack(anchor="w")
        ttk.Button(parent, text="Show Sample Records", command=lambda: self._show_sample_records(parent)).pack(anchor="w", pady=12)
        text = tk.Text(parent, height=22, wrap="none")
        text.pack(fill="both", expand=True)
        parent._data_text = text
        self._show_sample_records(parent)

    def _show_sample_records(self, parent: ttk.Frame) -> None:
        text = parent._data_text
        text.delete("1.0", "end")
        with connect(self.db_path) as conn:
            for title, query in [
                ("Students", "SELECT student_code, name, grade FROM students LIMIT 8"),
                ("Teachers", "SELECT teacher_code, name, department FROM teachers LIMIT 8"),
                ("Rooms", "SELECT room_code, capacity, room_type FROM rooms"),
                ("Course Sections", "SELECT section_code, duration FROM course_sections LIMIT 12"),
                ("Blocked Periods", "SELECT day, period, reason FROM blocked_periods"),
            ]:
                text.insert("end", title + "\n")
                for row in conn.execute(query):
                    text.insert("end", "  " + " | ".join(str(value) for value in row) + "\n")
                text.insert("end", "\n")
