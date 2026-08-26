"""Application entry point for the Ulink IB course scheduling system.

This file is intentionally small. It prepares the SQLite database, inserts
anonymous demo data if the database is empty, and then starts the Tkinter GUI.
Keeping startup code here makes it easy for PyCharm users to run the whole
project by pressing Run on this single file.
"""

from scheduler_app.database import initialize_database
from scheduler_app.gui import SchedulingApp
from scheduler_app.seed_data import seed_demo_data


def main() -> None:
    """Create the database and launch the desktop application."""
    # The database file is stored beside main.py so the app stays portable.
    db_path = "school_schedule.db"

    # Create all tables before any feature tries to query them.
    initialize_database(db_path)

    # Populate the project with anonymous school-like data for IA testing.
    seed_demo_data(db_path)

    # Start the Tkinter event loop. All user interaction happens inside it.
    app = SchedulingApp(db_path)
    app.mainloop()


if __name__ == "__main__":
    main()
