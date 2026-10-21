"""Opt-in real Tkinter workflow tests (RUN_GUI_TESTS=1 on a desktop)."""

import os
import tempfile
import time
import tkinter as tk
import unittest
from pathlib import Path
from tkinter import ttk
from unittest.mock import patch

from scheduler_app.database import connect, initialize_database
from scheduler_app.gui import SchedulingApp
from scheduler_app.school_data import export_workbook, snapshot
from scheduler_app.seed_data import seed_demo_data


@unittest.skipUnless(os.environ.get("RUN_GUI_TESTS") == "1", "requires a desktop Tk session")
class GuiTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.path = str(Path(self.folder.name) / "school.db")
        initialize_database(self.path)
        seed_demo_data(self.path)
        self.app = SchedulingApp(self.path)
        with connect(self.path) as conn:
            self.users = {r["role"]: dict(r) for r in conn.execute(
                "SELECT * FROM users WHERE username IN ('admin','teacher01','student001')")}
        self.app.current_user = self.users["admin"]
        self.app._show_admin()
        self.app.update()

    def tearDown(self):
        self.app.destroy()
        self.folder.cleanup()

    def test_background_generation_and_role_grids(self):
        notebook = next(w for w in self.app.winfo_children() if isinstance(w, ttk.Notebook))
        generate = self.app.nametowidget(notebook.tabs()[1])
        button = next(w for w in generate.winfo_children() if isinstance(w, ttk.Button))
        button.invoke()
        deadline = time.monotonic() + 12
        while self.app._generating and time.monotonic() < deadline:
            self.app.update()
            time.sleep(.01)
        self.assertFalse(self.app._generating)
        for role in ("admin", "student", "teacher"):
            self.app.current_user = self.users[role]
            if role == "admin":
                panel = self.app._admin_timetable
            else:
                self.app._show_user_timetable()
                panel = self.app.winfo_children()[-1]
            self.app.geometry("960x620")
            self.app.update()
            self.assertEqual(len(panel._week.cells), 55)
            if role == "student":
                self.assertIn("34 teaching periods", panel._summary.cget("text"))
                self.assertIn("Lunch / Free", [l.cget("text") for l in panel._week.labels])

    def test_record_form_and_excel_import(self):
        manager = self.app._data_manager
        manager.tree.selection_set("0")
        manager.edit(True)
        self.app.update()
        dialog = next(w for w in manager.winfo_children() if isinstance(w, tk.Toplevel))
        form = dialog.winfo_children()[0]
        name = form.grid_slaves(row=1, column=1)[0]
        name.delete(0, "end")
        name.insert(0, "Edited in GUI")
        next(w for w in form.winfo_children() if isinstance(w, ttk.Button)).invoke()
        self.app.update()
        self.assertEqual(snapshot(self.path)["Students"][0]["name"], "Edited in GUI")
        data = snapshot(self.path)
        data["Students"][0]["name"] = "Imported in GUI"
        workbook = str(Path(self.folder.name) / "input.xlsx")
        export_workbook(workbook, data)
        with patch("scheduler_app.data_view.filedialog.askopenfilename", return_value=workbook), patch("scheduler_app.data_view.messagebox.askyesno", return_value=True):
            manager.import_excel()
        self.assertEqual(snapshot(self.path)["Students"][0]["name"], "Imported in GUI")

    def test_manual_weekly_lesson_selection(self):
        self.assertTrue(self.app.scheduler.generate()[0])
        panel = self.app._admin_manual
        self.app._refresh_manual_options(panel)
        panel._section_var.set(panel._section_combo.cget("values")[0])
        self.app._update_occurrences(panel)
        section = int(panel._section_var.get().split(" | ")[0])
        self.assertGreaterEqual(len(panel._occurrence_combo.cget("values")), 4)
        panel._occurrence_var.set("2")
        self.app._load_manual_assignment(panel)
        with connect(self.path) as conn:
            row = conn.execute("SELECT * FROM schedule_assignments WHERE section_id=? AND occurrence=2", (section,)).fetchone()
        self.assertEqual(panel._day_var.get(), row["day"])
        self.assertEqual(panel._period_var.get(), str(row["period"]))


if __name__ == "__main__":
    unittest.main()
