
import csv
import json
from pathlib import Path

from database.connectionDB import DatabaseConnection


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"

# Load parent tables before their dependent tables.
LOAD_ORDER = [
    ("departments.csv", "departments"),
    ("job_requisitions.csv", "job_requisitions"),
    ("requisition_approvals.csv", "requisition_approvals"),
    ("candidates.csv", "candidates"),
    ("skills.csv", "skills"),
    ("candidate_skills.csv", "candidate_skills"),
    ("required_skills.csv", "required_skills"),
    ("applications.csv", "applications"),
    ("resume_artifacts.csv", "resume_artifacts"),
    ("screening_rules.csv", "screening_rules"),
    ("interviewers.csv", "interviewers"),
    ("interviewer_availability.csv", "interviewer_availability"),
    ("interviews.csv", "interviews"),
    ("interview_panel.csv", "interview_panel"),
    ("feedback.csv", "feedback"),
    ("offers.csv", "offers"),
    ("offer_approvals.csv", "offer_approvals"),
    ("application_status_history.csv", "application_status_history"),
    ("audit_events.csv", "audit_events"),
]

# Tables that use automatically generated IDs, which the CSV already supplies.
# We explicitly insert these IDs to preserve relationships between CSV datasets.
DATE_COLUMNS = {
    "job_requisitions": {"opened_at", "closed_at"},
    "requisition_approvals": {"decided_at"},
    "applications": {"applied_at", "withdrawn_at", "created_at"},
    "resume_artifacts": {"uploaded_at"},
    "screening_rules": {"effective_from", "effective_to"},
    "interviewer_availability": {"start_at", "end_at"},
    "interviews": {
        "scheduled_start", "scheduled_end", "created_at"
    },
    "feedback": {"submitted_at"},
    "offers": {"issued_at", "expires_at", "responded_at"},
    "offer_approvals": {"decided_at"},
    "application_status_history": {"changed_at"},
    "audit_events": {"event_time"},
}


def convert_value(table, column, value):
    """Convert CSV text to the appropriate Python value for MySQL."""
    if value is None or value.strip() == "":
        return None

    value = value.strip()

    if column in DATE_COLUMNS.get(table, set()):
        return value

    if table == "interviews" and column == "interview_round":
        try:
            round_number = int(value)
        except ValueError:
            round_mapping = {
                "ROUND_1": 1,
                "ROUND_2": 2,
                "FINAL": 3,
            }
            if value.upper() not in round_mapping:
                raise ValueError(
                    f"Unknown interview round: {value}"
                )
            round_number = round_mapping[value.upper()]

        if round_number <= 0:
            raise ValueError("interview_round must be positive")

        return round_number

    if column in {"department_id", "requisition_id", "candidate_id",
                  "skill_id", "application_id", "interviewer_id",
                  "interview_id", "offer_id", "resume_id", "rule_id",
                  "availability_id", "feedback_id", "history_id",
                  "audit_id", "approval_id", "offer_approval_id",
                  "interview_round", "version_number", "openings"}:
        return int(value)

    if column in {"is_active", "is_mandatory"}:
        if value.lower() in {"1", "true", "yes"}:
            return 1
        if value.lower() in {"0", "false", "no"}:
            return 0
        raise ValueError(f"Invalid boolean for {column}: {value}")

    if column in {"experience_years", "years_experience", "min_salary",
                  "max_salary", "screening_score", "weight",
                  "rating", "offered_salary"}:
        return value

    if table == "audit_events" and column == "details":
        json.loads(value)  # Fail early if the JSON is invalid.
        return value

    return value


def load_csv(cursor, table, csv_name):
    csv_path = DATA_DIR / csv_name

    if not csv_path.exists():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    with csv_path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        columns = reader.fieldnames

        if not columns:
            raise ValueError(f"CSV has no header: {csv_name}")

        rows = list(reader)

    if not rows:
        print(f"{table}: 0 rows (empty CSV)")
        return 0

    converted_rows = []

    for line_number, row in enumerate(rows, start=2):
        try:
            converted_rows.append(
                tuple(
                    convert_value(table, column, row.get(column))
                    for column in columns
                )
            )
        except Exception as exc:
            raise ValueError(
                f"{csv_name}, line {line_number}: {exc}"
            ) from exc

    column_sql = ", ".join(f"`{column}`" for column in columns)
    placeholders = ", ".join(["%s"] * len(columns))

    query = (
        f"INSERT INTO `{table}` ({column_sql}) "
        f"VALUES ({placeholders})"
    )

    cursor.executemany(query, converted_rows)

    print(f"{table}: {cursor.rowcount} rows inserted")
    return len(converted_rows)


def main():
    db = DatabaseConnection()

    if db is None:
        print("Could not connect to MySQL. Check your .env settings.")
        return

    cursor = None

    try:
        cursor = db.cursor()
        total_rows = 0

        for csv_name, table in LOAD_ORDER:
            total_rows += load_csv(cursor, table, csv_name)

        db.commit()
        print("\nAll baseline datasets loaded successfully.")
        print(f"Total rows inserted: {total_rows}")
        print("Anomaly and ground-truth CSVs were not loaded.")

    except Exception as exc:
        db.rollback()
        print("\nLoading failed. Changes from this run were rolled back.")
        print("Reason:", exc)

    finally:
        if cursor is not None:
            cursor.close()
        if db.is_connected():
            db.close()


if __name__ == "__main__":
    main()
