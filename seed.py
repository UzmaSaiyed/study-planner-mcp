from datetime import date, timedelta

from db import init_db, run_write


def days_from_today(n: int) -> str:
    return (date.today() + timedelta(days=n)).isoformat()


SAMPLES = [
    ("Revise normalization", "Database Systems", "Todo", days_from_today(2),
     "Cover 1NF to BCNF with examples."),
    ("Solve past paper 2023", "Operating Systems", "In progress", days_from_today(4),
     "Focus on scheduling and deadlocks."),
    ("Finish regression notes", "Machine Learning", "Todo", days_from_today(-1),
     "Overdue. Need linear and logistic regression summary."),
    ("Practice SQL joins", "Database Systems", "Done", days_from_today(-3),
     "Finished 20 practice queries."),
    ("Read TCP congestion chapter", "Computer Networks", "Todo", days_from_today(6),
     "Slow start and congestion avoidance."),
    ("Prepare viva questions", "Machine Learning", "In progress", days_from_today(10),
     "Collect common viva questions."),
]

if __name__ == "__main__":
    init_db()
    for title, subject, status, due_on, notes in SAMPLES:
        run_write(
            "INSERT INTO tasks (title, subject, status, due_on, notes) VALUES (?, ?, ?, ?, ?)",
            (title, subject, status, due_on, notes),
        )
    print(f"Added {len(SAMPLES)} sample tasks.")