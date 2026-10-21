"""Scrollable weekly schedule shared by all three user roles."""

import tkinter as tk
from tkinter import ttk

from scheduler_app.config import DAYS, PERIODS, PERIOD_TIMES, LUNCH_PERIODS


class WeeklyTimetable(ttk.Frame):
    """Keep weekday columns aligned while expanding crowded period rows."""

    COLORS = [("#e3f2ef", "#165c50"), ("#e8eefb", "#294b86"),
              ("#fbe9ee", "#923b56"), ("#fff1cf", "#795c16"),
              ("#eee9fa", "#62458b"), ("#e5f1fa", "#285e7c")]

    def __init__(self, parent):
        super().__init__(parent)
        self.canvas = tk.Canvas(self, background="#ffffff", highlightthickness=0)
        vertical = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        horizontal = ttk.Scrollbar(self, orient="horizontal", command=self.canvas.xview)
        self.canvas.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal.grid(row=1, column=0, sticky="ew")
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        self.body = tk.Frame(self.canvas, background="#dce2e8")
        self.window = self.canvas.create_window(0, 0, window=self.body, anchor="nw")
        self.body.bind("<Configure>", self._update_scrollregion)
        self.canvas.bind("<Configure>", self._resize)
        self.labels = []

    def _update_scrollregion(self, _event=None):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _resize(self, event):
        # A minimum width preserves readable columns on smaller school laptops.
        width = max(860, event.width)
        self.canvas.itemconfigure(self.window, width=width)
        for label in self.labels:
            label.configure(wraplength=max(120, (width - 72) // 5 - 28))

    def render(self, rows, blocked, student_view=False):
        """Render every occupied period, including double-lesson continuations."""
        for widget in self.body.winfo_children():
            widget.destroy()
        self.labels = []
        self.cells = {}
        self.body.columnconfigure(0, minsize=66)
        for column in range(1, 6):
            self.body.columnconfigure(column, weight=1, uniform="days")
        for column, title in enumerate(["Period"] + DAYS):
            tk.Label(self.body, text=title, bg="#f1f4f7", fg="#283640",
                     font=("Arial", 11, "bold"), pady=14).grid(
                         row=0, column=column, sticky="nsew", padx=1, pady=1)

        course_names = sorted({row["course_name"] for row in rows})
        # Stable colors let the same course remain recognizable across filters.
        colors = {name: self.COLORS[sum(name.encode("utf-8")) % len(self.COLORS)]
                  for name in course_names}
        for period in PERIODS:
            start, end = PERIOD_TIMES[period]
            tk.Label(self.body, text=f"P{period}\n{start}\n{end}", bg="#f1f4f7", fg="#53616d",
                     font=("Arial", 11, "bold")).grid(
                         row=period, column=0, sticky="nsew", padx=1, pady=1)
            self.body.rowconfigure(period, minsize=94)
            for column, day in enumerate(DAYS, 1):
                cell = tk.Frame(self.body, bg="white", padx=5, pady=5)
                cell.grid(row=period, column=column, sticky="nsew", padx=1, pady=1)
                lessons = [row for row in rows if row["day"] == day and
                           row["period"] <= period < row["period"] + row["duration"]]
                self.cells[(day, period)] = lessons
                reason = blocked.get((day, period))
                if reason:
                    cell.configure(bg="#edf0f2")
                    self._label(cell, f"{reason}\nUnavailable", "#edf0f2", "#707b84")
                elif not lessons:
                    if student_view and period in LUNCH_PERIODS:
                        cell.configure(bg="#edf5ed")
                        self._label(cell, "Lunch / Free", "#edf5ed", "#426a43")
                    else:
                        self._label(cell, "Free", "white", "#a2aab1")
                for lesson in lessons:
                    bg, fg = colors[lesson["course_name"]]
                    end = lesson["period"] + lesson["duration"] - 1
                    span = f"P{lesson['period']}" if end == lesson["period"] else f"P{lesson['period']}-{end}"
                    continuation = " (continued)" if period > lesson["period"] else ""
                    text = (f"{lesson['course_name']} {lesson.get('level', '')}{continuation}\n"
                            f"{lesson['section_code']} | {span}\n"
                            f"{lesson['teacher_name']} | {lesson['room_code']}")
                    self._label(cell, text, bg, fg)
        self._resize(type("Size", (), {"width": self.canvas.winfo_width()})())

    def _label(self, parent, text, bg, fg):
        label = tk.Label(parent, text=text, bg=bg, fg=fg, justify="left",
                         anchor="nw", font=("Arial", 10), padx=7, pady=7,
                         wraplength=150)
        label.pack(fill="x", pady=2)
        self.labels.append(label)
