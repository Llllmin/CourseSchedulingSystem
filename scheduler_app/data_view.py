"""Administrator data tables, record forms and validated Excel workflows."""

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from scheduler_app.config import DAYS, PERIODS
from scheduler_app.school_data import (FIELDS, KEYS, export_workbook, read_workbook,
                                       replace_data, save_credentials, snapshot, validate_data)
from scheduler_app.seed_data import load_demo_data


class DataManager(ttk.Frame):
    def __init__(self, parent, db_path, on_change, can_edit=lambda: True):
        super().__init__(parent)
        self.db_path, self.on_change = db_path, on_change
        self.can_edit = can_edit
        self.pack(fill="both", expand=True)
        self.sheet = tk.StringVar(value="Students")
        bar = ttk.Frame(self)
        bar.pack(fill="x", pady=(0, 8))
        selector = ttk.Combobox(bar, values=list(FIELDS), textvariable=self.sheet, state="readonly", width=23)
        selector.pack(side="left", padx=(0, 12))
        selector.bind("<<ComboboxSelected>>", lambda _e: self.refresh())
        for title, action in (("New", lambda: self.edit()), ("Edit", lambda: self.edit(True)),
                              ("Delete", self.delete), ("Validate All", self.validate)):
            ttk.Button(bar, text=title, command=action).pack(side="left", padx=3)
        files = ttk.Frame(self)
        files.pack(fill="x", pady=(0, 10))
        for title, action in (("Excel Template", self.template), ("Export Excel", self.export),
                              ("Import Excel", self.import_excel), ("Load Demo Data", self.demo)):
            ttk.Button(files, text=title, command=action).pack(side="left", padx=(0, 8))
        self.status = ttk.Label(self, wraplength=900)
        self.status.pack(fill="x", pady=(0, 8))
        frame = ttk.Frame(self)
        frame.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(frame, show="headings", selectmode="browse")
        vertical = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        horizontal = ttk.Scrollbar(frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal.grid(row=1, column=0, sticky="ew")
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        self.tree.bind("<Double-1>", lambda _e: self.edit(True))
        self.refresh()

    def refresh(self):
        self.data = snapshot(self.db_path)
        fields = FIELDS[self.sheet.get()]
        self.tree.configure(columns=fields)
        for field in fields:
            self.tree.heading(field, text=field.replace("_", " ").title())
            self.tree.column(field, width=155, minwidth=100)
        self.tree.delete(*self.tree.get_children())
        for index, row in enumerate(self.data[self.sheet.get()]):
            self.tree.insert("", "end", iid=str(index), values=[row[field] for field in fields])
        self.status.configure(text=f"{self.sheet.get()}: {len(self.data[self.sheet.get()])} records")

    def selected(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showinfo("Select a record", "Select a record first.", parent=self)
            return None
        return int(selected[0])

    def commit(self, data, strict=False):
        if not self.can_edit():
            raise ValueError("Wait for timetable generation to finish before editing data.")
        backup, credentials = replace_data(self.db_path, data, strict)
        credential_path = save_credentials(self.db_path, credentials)
        self.refresh()
        self.on_change()
        text = f"Saved. Schedule cleared; generate again. Backup: {backup}"
        if credential_path:
            text += f"\nNew login details: {credential_path}"
        self.status.configure(text=text)

    def edit(self, existing=False):
        index = self.selected() if existing else None
        if existing and index is None:
            return
        sheet = self.sheet.get()
        original = self.data[sheet][index] if existing else {}
        dialog = tk.Toplevel(self)
        dialog.title(("Edit " if existing else "New ") + sheet)
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()
        form = ttk.Frame(dialog, padding=20)
        form.pack(fill="both", expand=True)
        variables = {}
        references = {"student_code": "Students", "teacher_code": "Teachers",
                      "course_code": "Courses", "section_code": "Sections"}
        choices = {"level": ["HL", "SL", "PE", "TOK", "EE"], "duration": [1, 2],
                   "room_type": ["standard", "lab"], "requires_room_type": ["standard", "lab"],
                   "day": DAYS, "period": PERIODS, "available": [0, 1]}
        for number, field in enumerate(FIELDS[sheet]):
            ttk.Label(form, text=field.replace("_", " ").title()).grid(row=number, column=0, sticky="w", padx=(0, 18), pady=6)
            var = tk.StringVar(value=str(original.get(field, "")))
            variables[field] = var
            values = choices.get(field)
            target = references.get(field)
            if target and target != sheet:
                values = [r[field] for r in self.data[target]]
            if values is not None:
                widget = ttk.Combobox(form, textvariable=var, values=values, state="readonly", width=32)
            else:
                widget = ttk.Entry(form, textvariable=var, width=34)
            if existing and len(KEYS[sheet]) == 1 and field in KEYS[sheet]:
                widget.configure(state="disabled")
            widget.grid(row=number, column=1, sticky="ew", pady=6)
        error = ttk.Label(form, foreground="#a12a3d", wraplength=420)
        error.grid(row=len(variables), column=0, columnspan=2, pady=8)
        def save():
            data = snapshot(self.db_path)
            record = {key: var.get() for key, var in variables.items()}
            if existing:
                data[sheet][index] = record
            else:
                data[sheet].append(record)
            try:
                self.commit(data)
            except Exception as exc:
                # Keep the form open so invalid references can be corrected.
                error.configure(text=str(exc))
                return
            dialog.destroy()
        ttk.Button(form, text="Save", command=save).grid(row=len(variables)+1, column=1, sticky="e")

    def delete(self):
        index = self.selected()
        if index is None:
            return
        if not messagebox.askyesno("Delete record", "Delete this record and clear the generated schedule? Referenced records must be removed first.", parent=self):
            return
        data = snapshot(self.db_path)
        data[self.sheet.get()].pop(index)
        try:
            self.commit(data)
        except Exception as error:
            messagebox.showerror("Cannot delete", str(error), parent=self)

    def validate(self):
        try:
            validate_data(snapshot(self.db_path))
            self.status.configure(text="Valid: every student has 3 HL + 3 SL + PE/TOK/EE; references and room capacities checked.")
        except ValueError as error:
            messagebox.showerror("Data needs attention", str(error), parent=self)

    def _save_excel(self, data):
        path = filedialog.asksaveasfilename(parent=self, defaultextension=".xlsx", filetypes=[("Excel workbook", "*.xlsx")])
        if path:
            try:
                export_workbook(path, data)
                self.status.configure(text=f"Excel saved: {path}")
            except Exception as error:
                messagebox.showerror("Excel export failed", str(error), parent=self)

    def template(self):
        self._save_excel(None)

    def export(self):
        self._save_excel(snapshot(self.db_path))

    def import_excel(self):
        path = filedialog.askopenfilename(parent=self, filetypes=[("Excel workbook", "*.xlsx")])
        if not path:
            return
        try:
            data = read_workbook(path)
            summary = ", ".join(f"{name}: {len(rows)}" for name, rows in data.items())
            if messagebox.askyesno("Replace school data", f"Validated: {summary}\n\nReplace current school data and clear the schedule? A database backup will be created. Existing accounts with matching codes are retained.", parent=self):
                self.commit(data, strict=True)
        except Exception as error:
            messagebox.showerror("Import rejected", str(error), parent=self)

    def demo(self):
        if not self.can_edit():
            messagebox.showinfo("Generating", "Wait for timetable generation to finish.", parent=self)
            return
        if messagebox.askyesno("Load demo data", "Replace current data with 60 anonymous students and their complete weekly courses? A backup will be created.", parent=self):
            try:
                backup = load_demo_data(self.db_path)
                self.refresh()
                self.on_change()
                self.status.configure(text=f"Demo data loaded. Generate the timetable next. Backup: {backup}")
            except Exception as error:
                messagebox.showerror("Demo load failed", str(error), parent=self)
