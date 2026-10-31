
import csv
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"


def read_csv(filename):
    path = DATA_DIR / filename

    if not path.exists():
        raise FileNotFoundError(f"Missing dataset: {path}")

    with open(path, "r", newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))


def validate_datasets():
    departments = read_csv("departments.csv")
    requisitions = read_csv("job_requisitions.csv")
    candidates = read_csv("candidates.csv")
    applications = read_csv("applications.csv")
    interviews = read_csv("interviews.csv")
    offers = read_csv("offers.csv")

    checks = {}

    # Expected baseline record counts
    checks["departments_count"] = len(departments) == 10
    checks["requisitions_count"] = len(requisitions) == 100
    checks["candidates_count"] = len(candidates) == 2000
    checks["applications_count"] = len(applications) == 3000
    checks["interviews_count"] = len(interviews) == 600
    checks["offers_count"] = len(offers) == 150

    # Primary/business key uniqueness
    checks["department_ids_unique"] = len({
        row["department_id"] for row in departments
    }) == len(departments)

    checks["requisition_ids_unique"] = len({
        row["requisition_id"] for row in requisitions
    }) == len(requisitions)

    checks["candidate_ids_unique"] = len({
        row["candidate_id"] for row in candidates
    }) == len(candidates)

    checks["application_ids_unique"] = len({
        row["application_id"] for row in applications
    }) == len(applications)

    # Foreign-key references
    department_ids = {row["department_id"] for row in departments}
    requisition_ids = {row["requisition_id"] for row in requisitions}
    candidate_ids = {row["candidate_id"] for row in candidates}
    application_ids = {row["application_id"] for row in applications}

    checks["requisition_departments_valid"] = all(
        row["department_id"] in department_ids
        for row in requisitions
    )

    checks["application_requisitions_valid"] = all(
        row["requisition_id"] in requisition_ids
        for row in applications
    )

    checks["application_candidates_valid"] = all(
        row["candidate_id"] in candidate_ids
        for row in applications
    )

    checks["offer_applications_valid"] = all(
        row["application_id"] in application_ids
        for row in offers
    )

    # A candidate must not apply twice to the same requisition
    application_pairs = [
        (row["requisition_id"], row["candidate_id"])
        for row in applications
    ]

    checks["application_pairs_unique"] = (
        len(application_pairs) == len(set(application_pairs))
    )

    # Requisition salary ranges must be valid
    checks["salary_ranges_valid"] = all(
        float(row["min_salary"]) <= float(row["max_salary"])
        for row in requisitions
    )

    report = {
        "checks_passed": sum(checks.values()),
        "checks_total": len(checks),
        "all_checks_passed": all(checks.values()),
        "checks": checks,
    }

    report_path = DATA_DIR / "validation_report.json"

    with open(report_path, "w", encoding="utf-8") as file:
        json.dump(report, file, indent=2)

    print("\n===== RMS DATA VALIDATION =====")

    for check_name, passed in checks.items():
        status = "PASS" if passed else "FAIL"
        print(f"{status}: {check_name}")

    print(
        f"\nResult: {report['checks_passed']}/"
        f"{report['checks_total']} checks passed."
    )

    print(f"Report saved to: {report_path}")

    return report


if __name__ == "__main__":
    validate_datasets()
