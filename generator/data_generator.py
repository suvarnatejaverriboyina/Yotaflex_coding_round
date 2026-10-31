"""
Reproducible synthetic data generator for the Recruitment Lifecycle Management System (RMS).

Run from D:\\RMS with:
    python -m generator.data_generator

Writes clean baseline datasets to data/*.csv and data/*.json.
Writes labelled test anomalies separately to anomaly_cases.* and ground_truth.*.
No pandas dependency is required.

Important:
- The clean baseline is designed to match the database schema described in tablesDB.py.
- Explicit IDs are included so CSV relationships are easy to inspect and load.
- Anomaly cases are test payloads, not part of the clean baseline tables.
"""

import csv
import hashlib
import json
import random
from datetime import date, datetime, time, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
RANDOM_SEED = 20261022

DEPARTMENT_NAMES = [
    "Engineering", "Human Resources", "Finance", "Marketing", "Sales",
    "Operations", "Data Science", "Information Technology",
    "Customer Support", "Product Management",
]
JOB_TITLES = [
    "Python Developer", "Data Analyst", "Machine Learning Engineer",
    "AI Engineer", "Flask Developer", "Software Engineer", "SQL Developer",
    "HR Executive", "Business Analyst", "QA Engineer",
]
FIRST_NAMES = [
    "Aarav", "Aditya", "Ananya", "Divya", "Ishaan", "Kavya", "Meera",
    "Neha", "Rahul", "Rohan", "Sneha", "Priya", "Vikram", "Varun",
    "Aditi", "Arjun", "Nisha", "Kiran", "Pooja", "Sanjay",
]
LAST_NAMES = [
    "Sharma", "Reddy", "Kumar", "Patel", "Rao", "Verma", "Gupta",
    "Singh", "Nair", "Das", "Mehta", "Iyer", "Joshi", "Naidu", "Roy",
]
SKILL_NAMES = [
    "Python", "SQL", "Flask", "Java", "JavaScript", "HTML", "CSS",
    "Machine Learning", "NLP", "Generative AI", "MySQL", "Git",
    "REST APIs", "Data Analysis", "Docker",
]
ACTIVE_APPLICATION_STATUSES = {
    "APPLIED", "SCREENING", "SHORTLISTED", "INTERVIEW", "OFFER"
}


def dt_text(value):
    """Format date/datetime values in MySQL-compatible text form."""
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(value, date):
        return value.strftime("%Y-%m-%d")
    return value


def write_dataset(name, records):
    """Write records to CSV and JSON. Empty datasets get an empty CSV header."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    csv_path = DATA_DIR / f"{name}.csv"
    json_path = DATA_DIR / f"{name}.json"

    if records:
        fields = list(records[0].keys())
    else:
        fields = []

    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        if fields:
            writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="raise")
            writer.writeheader()
            for record in records:
                writer.writerow({
                    key: json.dumps(value, ensure_ascii=False)
                    if isinstance(value, (dict, list)) else value
                    for key, value in record.items()
                })

    with json_path.open("w", encoding="utf-8") as handle:
        json.dump(records, handle, indent=2, ensure_ascii=False, default=dt_text)

    print(f"{name}: {len(records)} records")


def make_departments():
    return [
        {"department_id": i, "department_name": name, "created_at": "2026-01-01 09:00:00"}
        for i, name in enumerate(DEPARTMENT_NAMES, 1)
    ]


def make_requisitions(rng, departments):
    rows = []
    statuses = ["OPEN"] * 75 + ["CLOSED"] * 15 + ["DRAFT"] * 5 + ["ON_HOLD"] * 5
    rng.shuffle(statuses)
    for i in range(1, 101):
        min_salary = rng.choice([300000, 400000, 500000, 600000])
        max_salary = min_salary + rng.choice([200000, 300000, 400000])
        status = statuses[i - 1]
        created = date(2026, 1, 1) + timedelta(days=rng.randint(0, 90))
        opened = created + timedelta(days=rng.randint(1, 10)) if status in {"OPEN", "CLOSED", "ON_HOLD"} else None
        closed = (
            opened + timedelta(days=rng.randint(10, 100))
            if status == "CLOSED" and opened else None
        )
        rows.append({
            "requisition_id": i,
            "requisition_code": f"REQ-2026-{i:06d}",
            "department_id": rng.choice(departments)["department_id"],
            "job_title": rng.choice(JOB_TITLES),
            "description": "Synthetic job requisition for RMS testing.",
            "employment_type": rng.choice(["FULL_TIME", "CONTRACT", "INTERNSHIP"]),
            "openings": rng.randint(1, 5),
            "min_salary": min_salary,
            "max_salary": max_salary,
            "status": status,
            "requested_by": f"requester{rng.randint(1, 20)}",
            "created_at": dt_text(datetime.combine(created, time(9, 0))),
            "opened_at": dt_text(opened) if opened else None,
            "closed_at": dt_text(closed) if closed else None,
        })
    return rows


def make_candidates(rng):
    rows = []
    for i in range(1, 2001):
        full_name = f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}"
        rows.append({
            "candidate_id": i,
            "candidate_code": f"CAND-{i:06d}",
            "full_name": full_name,
            "email": f"candidate{i:06d}@example.com",
            "phone": f"9{i:09d}",
            "experience_years": round(rng.uniform(0, 15), 1),
            "created_at": dt_text(datetime(2026, 1, 1) + timedelta(days=rng.randint(0, 270))),
        })
    return rows


def make_skills():
    return [
        {"skill_id": i, "skill_name": name}
        for i, name in enumerate(SKILL_NAMES, 1)
    ]


def make_candidate_skills(rng, candidates, skills):
    rows = []
    for candidate in candidates:
        selected = rng.sample(skills, rng.randint(2, 5))
        for skill in selected:
            rows.append({
                "candidate_id": candidate["candidate_id"],
                "skill_id": skill["skill_id"],
                "proficiency": rng.choice(["BEGINNER", "INTERMEDIATE", "ADVANCED", "EXPERT"]),
                "years_experience": round(rng.uniform(0, max(0.1, candidate["experience_years"])), 1),
            })
    return rows


def make_required_skills(rng, requisitions, skills):
    rows = []
    for req in requisitions:
        for skill in rng.sample(skills, rng.randint(2, 4)):
            rows.append({
                "requisition_id": req["requisition_id"],
                "skill_id": skill["skill_id"],
                "is_mandatory": rng.choice([True, True, False]),
                "weight": rng.randint(1, 5),
            })
    return rows


def make_approvals(requisitions):
    rows = []
    for req in requisitions:
        decision = "APPROVED" if req["status"] in {"OPEN", "CLOSED", "ON_HOLD"} else "PENDING"
        rows.append({
            "approval_id": req["requisition_id"],
            "requisition_id": req["requisition_id"],
            "approver_name": f"approver{(req['requisition_id'] % 10) + 1}",
            "decision": decision,
            "comments": "Synthetic requisition approval.",
            "decided_at": "2026-04-01 12:00:00" if decision == "APPROVED" else None,
        })
    return rows


def make_applications(rng, requisitions, candidates):
    """Create 3,000 unique candidate/requisition pairs only for OPEN requisitions."""
    open_reqs = [r for r in requisitions if r["status"] == "OPEN"]
    all_pairs = [(r["requisition_id"], c["candidate_id"]) for r in open_reqs for c in candidates]
    pairs = rng.sample(all_pairs, 3000)
    statuses = (
        ["APPLIED"] * 700 + ["SCREENING"] * 500 + ["SHORTLISTED"] * 500
        + ["INTERVIEW"] * 650 + ["REJECTED"] * 450 + ["WITHDRAWN"] * 200
    )
    rng.shuffle(statuses)
    rows = []
    for i, ((req_id, candidate_id), status) in enumerate(zip(pairs, statuses), 1):
        applied = datetime(2026, rng.randint(1, 9), rng.randint(1, 28), rng.randint(8, 17), rng.choice([0, 15, 30, 45]))
        rows.append({
            "application_id": i,
            "application_code": f"APP-REQ-2026-{req_id:06d}-CAND-{candidate_id:06d}",
            "requisition_id": req_id,
            "candidate_id": candidate_id,
            "applied_at": dt_text(applied),
            "source": rng.choice(["CAREER_PORTAL", "REFERRAL", "JOB_BOARD", "RECRUITER"]),
            "status": status,
            "screening_score": round(rng.uniform(45, 100), 2) if status not in {"APPLIED", "WITHDRAWN"} else None,
            "withdrawn_at": dt_text(applied + timedelta(days=5)) if status == "WITHDRAWN" else None,
            "created_at": dt_text(applied),
        })
    return rows


def make_resumes(rng, candidates, applications):
    app_by_candidate = {}
    for app in applications:
        app_by_candidate.setdefault(app["candidate_id"], []).append(app)
    rows = []
    resume_id = 1
    for candidate in candidates:
        rows.append({
            "resume_id": resume_id,
            "candidate_id": candidate["candidate_id"],
            "application_id": None,
            "file_name": f"{candidate['candidate_code']}_resume.pdf",
            "file_type": "PDF",
            "version_number": 1,
            "uploaded_at": "2026-06-01 10:00:00",
        })
        resume_id += 1
    return rows


def make_screening_rules(requisitions):
    rows = []
    rule_id = 1
    for req in requisitions:
        rows.append({
            "rule_id": rule_id,
            "requisition_id": req["requisition_id"],
            "rule_name": "Minimum experience",
            "rule_type": "MIN_EXPERIENCE",
            "rule_value": "0",
            "weight": 2,
            "is_active": True,
            "effective_from": "2026-01-01",
            "effective_to": None,
        })
        rule_id += 1
        rows.append({
            "rule_id": rule_id,
            "requisition_id": req["requisition_id"],
            "rule_name": "Required skill match",
            "rule_type": "SKILL_MATCH",
            "rule_value": "60",
            "weight": 5,
            "is_active": True,
            "effective_from": "2026-01-01",
            "effective_to": None,
        })
        rule_id += 1
    return rows


def make_interviewers(rng, departments):
    return [{
        "interviewer_id": i,
        "interviewer_code": f"INTV-{i:04d}",
        "interviewer_name": f"Interviewer {i}",
        "email": f"interviewer{i:04d}@example.com",
        "department_id": rng.choice(departments)["department_id"],
        "is_active": True,
    } for i in range(1, 51)]


def make_availability(rng, interviewers):
    rows = []
    for interviewer in interviewers:
        for day in range(1, 29):
            # One whole-day availability window per interviewer/day.
            available = rng.random() < 0.8
            rows.append({
                "availability_id": len(rows) + 1,
                "interviewer_id": interviewer["interviewer_id"],
                "start_at": f"2026-10-{day:02d} 09:00:00",
                "end_at": f"2026-10-{day:02d} 17:00:00",
                "availability_status": "AVAILABLE" if available else "UNAVAILABLE",
                "notes": "Synthetic availability record",
            })
    return rows


def make_interviews(rng, applications, interviewers, availability):
    eligible = [a for a in applications if a["status"] in {"SHORTLISTED", "INTERVIEW"}]
    if len(eligible) < 600:
        raise ValueError(f"Need 600 eligible applications; found {len(eligible)}.")

    available_lookup = {
        (r["interviewer_id"], r["start_at"][:10]): r["availability_status"] == "AVAILABLE"
        for r in availability
    }
    selected_apps = rng.sample(eligible, 600)
    interviews, panel = [], []
    for i, app in enumerate(selected_apps, 1):
        # Application was submitted no later than September; interviews occur in October.
        day = rng.randint(1, 28)
        date_text = f"2026-10-{day:02d}"
        possible = [
            p for p in interviewers
            if available_lookup.get((p["interviewer_id"], date_text), False)
        ]
        if len(possible) < 2:
            # Ensure clean baseline: mark the first two interviewers available that day.
            for p in interviewers:
                if len(possible) >= 2:
                    break
                if p not in possible:
                    possible.append(p)
                    for av in availability:
                        if av["interviewer_id"] == p["interviewer_id"] and av["start_at"].startswith(date_text):
                            av["availability_status"] = "AVAILABLE"
                            available_lookup[(p["interviewer_id"], date_text)] = True
                            break
        panel_members = rng.sample(possible, 2)
        start = rng.choice([9, 10, 11, 14])
        start_dt = datetime(2026, 10, day, start, 0)
        end_dt = start_dt + timedelta(hours=1)
        status = rng.choice(["SCHEDULED", "COMPLETED", "CANCELLED"])
        interviews.append({
            "interview_id": i,
            "interview_code": f"INT-2026-{i:06d}",
            "application_id": app["application_id"],
            "interview_round": {
    "ROUND_1": 1,
    "ROUND_2": 2,
    "FINAL": 3
}[rng.choice(["ROUND_1", "ROUND_2", "FINAL"])],
            "interview_type": rng.choice(["TECHNICAL", "HR", "MANAGERIAL"]),
            "scheduled_start": dt_text(start_dt),
            "scheduled_end": dt_text(end_dt),
            "status": status,
            "meeting_details": f"Synthetic meeting room {i}",
            "created_at": dt_text(start_dt - timedelta(days=2)),
        })
        for j, member in enumerate(panel_members):
            panel.append({
                "interview_id": i,
                "interviewer_id": member["interviewer_id"],
                "panel_role": "LEAD" if j == 0 else "INTERVIEWER",
            })
    return interviews, panel


def make_feedback(rng, interviews, panel):
    panel_by_interview = {}
    for member in panel:
        panel_by_interview.setdefault(member["interview_id"], []).append(member)
    rows = []
    for interview in interviews:
        if interview["status"] != "COMPLETED":
            continue
        for member in panel_by_interview[interview["interview_id"]]:
            rating = rng.randint(1, 5)
            recommendation = (
                "STRONG_YES" if rating == 5 else
                "YES" if rating == 4 else
                "MAYBE" if rating == 3 else
                "NO" if rating == 2 else "STRONG_NO"
            )
            rows.append({
                "feedback_id": len(rows) + 1,
                "feedback_code": f"FB-{interview['interview_id']:06d}-{member['interviewer_id']:04d}",
                "interview_id": interview["interview_id"],
                "interviewer_id": member["interviewer_id"],
                "rating": float(rating),
                "recommendation": recommendation,
                "comments": "Synthetic interview feedback.",
                "submitted_at": dt_text(datetime.strptime(interview["scheduled_end"], "%Y-%m-%d %H:%M:%S") + timedelta(hours=1)),
            })
    return rows


def make_offers(rng, applications, requisitions, interviews, feedback):
    """Create 150 valid offers within requisition salary bands, after October interviews."""
    req_by_id = {r["requisition_id"]: r for r in requisitions}
    app_by_id = {a["application_id"]: a for a in applications}
    interviewed_apps = {
        i["application_id"] for i in interviews
        if i["status"] == "COMPLETED"
    }
    feedback_interviews = {f["interview_id"] for f in feedback}
    eligible_app_ids = []
    for interview in interviews:
        if interview["status"] == "COMPLETED" and interview["interview_id"] in feedback_interviews:
            app_id = interview["application_id"]
            if app_id not in eligible_app_ids:
                eligible_app_ids.append(app_id)
    if len(eligible_app_ids) < 150:
        raise ValueError(
            f"Need at least 150 completed-interview applications for offers; found {len(eligible_app_ids)}. "
            "Increase the completed interview proportion."
        )
    chosen = rng.sample(eligible_app_ids, 150)
    offers, approvals = [], []
    for i, app_id in enumerate(chosen, 1):
        app = app_by_id[app_id]
        req = req_by_id[app["requisition_id"]]
        salary = rng.randrange(req["min_salary"], req["max_salary"] + 1, 10000)
        issued = datetime(2026, 11, rng.randint(1, 20), 12, 0)
        expiry = issued + timedelta(days=14)
        status = rng.choice(["PENDING_APPROVAL", "APPROVED", "ISSUED", "ACCEPTED", "REJECTED"])
        responded = issued + timedelta(days=rng.randint(1, 10)) if status in {"ACCEPTED", "REJECTED"} else None
        offers.append({
            "offer_id": i,
            "offer_code": f"OFF-2026-{i:06d}",
            "application_id": app_id,
            "offered_salary": salary,
            "currency": "INR",
            "status": status,
            "issued_at": dt_text(issued) if status in {"ISSUED", "ACCEPTED", "REJECTED"} else None,
            "expires_at": dt_text(expiry) if status in {"ISSUED", "ACCEPTED", "REJECTED"} else None,
            "responded_at": dt_text(responded) if responded else None,
        })
        decision = "PENDING" if status == "PENDING_APPROVAL" else (
            "REJECTED" if status == "REJECTED" else "APPROVED"
        )
        approvals.append({
            "offer_approval_id": i,
            "offer_id": i,
            "approver_name": f"approver{rng.randint(1, 10)}",
            "decision": decision,
            "comments": "Synthetic offer approval.",
            "decided_at": dt_text(issued - timedelta(days=1)) if decision != "PENDING" else None,
        })
        app["status"] = "OFFER" if status not in {"ACCEPTED"} else "HIRED"
    return offers, approvals


def make_status_history(applications):
    rows = []
    history_id = 1
    for app in applications:
        applied_at = datetime.strptime(app["applied_at"], "%Y-%m-%d %H:%M:%S")
        stages = ["APPLIED"]
        final_status = app["status"]
        if final_status not in {"APPLIED", "WITHDRAWN"}:
            stages.append("SCREENING")
        if final_status in {"SHORTLISTED", "INTERVIEW", "OFFER", "HIRED"}:
            if "SHORTLISTED" not in stages:
                stages.append("SHORTLISTED")
        if final_status in {"INTERVIEW", "OFFER", "HIRED"}:
            stages.append("INTERVIEW")
        if final_status in {"OFFER", "HIRED"}:
            stages.append("OFFER")
        if final_status not in stages:
            stages.append(final_status)
        previous = None
        for index, status in enumerate(stages):
            rows.append({
                "history_id": history_id,
                "application_id": app["application_id"],
                "previous_status": previous,
                "new_status": status,
                "changed_at": dt_text(applied_at + timedelta(hours=index)),
                "changed_by": "SYSTEM" if index == 0 else f"recruiter{(app['application_id'] % 20) + 1}",
                "reason": "Application submitted" if index == 0 else "Synthetic stage transition",
            })
            history_id += 1
            previous = status
    return rows


def make_audit_events(requisitions, applications, offers):
    rows = []
    event_id = 1
    for req in requisitions:
        rows.append({
            "audit_id": event_id, "event_type": "CREATE",
            "entity_type": "JOB_REQUISITION", "entity_id": req["requisition_id"],
            "actor": req["requested_by"], "event_time": req["created_at"],
            "details": json.dumps({"requisition_code": req["requisition_code"], "status": req["status"]}),
        })
        event_id += 1
    for app in applications:
        rows.append({
            "audit_id": event_id, "event_type": "CREATE",
            "entity_type": "APPLICATION", "entity_id": app["application_id"],
            "actor": "SYSTEM", "event_time": app["applied_at"],
            "details": json.dumps({"application_code": app["application_code"], "status": app["status"]}),
        })
        event_id += 1
    for offer in offers:
        event_time = offer["issued_at"] or "2026-11-01 12:00:00"
        rows.append({
            "audit_id": event_id, "event_type": "CREATE",
            "entity_type": "OFFER", "entity_id": offer["offer_id"],
            "actor": "RECRUITER", "event_time": event_time,
            "details": json.dumps({"offer_code": offer["offer_code"], "status": offer["status"]}),
        })
        event_id += 1
    return rows


def make_anomalies(requisitions, applications, interviews, panel, availability, offers):
    """Create isolated labelled test payloads; never append these to baseline tables."""
    req_by_id = {r["requisition_id"]: r for r in requisitions}
    app_by_id = {a["application_id"]: a for a in applications}
    panel_by_interview = {}
    for row in panel:
        panel_by_interview.setdefault(row["interview_id"], []).append(row)
    availability_lookup = {
        (row["interviewer_id"], row["start_at"][:10]): row["availability_status"]
        for row in availability
    }
    cases = []

    # 1: force a specific unavailable interviewer for an otherwise valid interview.
    interview = interviews[0]
    member = panel_by_interview[interview["interview_id"]][0]
    day = interview["scheduled_start"][:10]
    availability_lookup[(member["interviewer_id"], day)] = "UNAVAILABLE"
    cases.append({
        "anomaly_id": "ANOM-001", "anomaly_type": "INTERVIEWER_UNAVAILABLE",
        "description": "Panel member is unavailable during the scheduled interview.",
        "related_ids": json.dumps({"interview_id": interview["interview_id"], "interviewer_id": member["interviewer_id"]}),
        "injected_record_json": json.dumps({"scheduled_start": interview["scheduled_start"], "availability_status": "UNAVAILABLE"}),
        "expected_detection": True,
    })

    # 2: duplicate candidate + requisition pair.
    original = applications[0]
    duplicate = dict(original)
    duplicate["application_id"] = max(a["application_id"] for a in applications) + 1
    duplicate["application_code"] = "ANOM-DUPLICATE-APPLICATION"
    cases.append({
        "anomaly_id": "ANOM-002", "anomaly_type": "DUPLICATE_APPLICATION",
        "description": "Candidate applies twice to the same requisition.",
        "related_ids": json.dumps({"original_application_id": original["application_id"], "requisition_id": original["requisition_id"], "candidate_id": original["candidate_id"]}),
        "injected_record_json": json.dumps(duplicate),
        "expected_detection": True,
    })

    # 3: advanced application with deliberately absent feedback.
    app = next(a for a in applications if a["status"] == "INTERVIEW")
    cases.append({
        "anomaly_id": "ANOM-003", "anomaly_type": "MISSING_INTERVIEW_FEEDBACK",
        "description": "Application is at interview stage but required feedback is missing.",
        "related_ids": json.dumps({"application_id": app["application_id"]}),
        "injected_record_json": json.dumps({"application_id": app["application_id"], "new_status": "INTERVIEW", "feedback_exists": False}),
        "expected_detection": True,
    })

    # 4: offer salary outside the approved band.
    offer = offers[0]
    offer_app = app_by_id[offer["application_id"]]
    req = req_by_id[offer_app["requisition_id"]]
    cases.append({
        "anomaly_id": "ANOM-004", "anomaly_type": "SALARY_OUTSIDE_APPROVED_BAND",
        "description": "Offer exceeds the requisition maximum salary.",
        "related_ids": json.dumps({"offer_id": offer["offer_id"], "requisition_id": req["requisition_id"]}),
        "injected_record_json": json.dumps({"offered_salary": req["max_salary"] + 100000, "min_salary": req["min_salary"], "max_salary": req["max_salary"]}),
        "expected_detection": True,
    })

    # 5: closed requisition + active application, represented as a test payload.
    closed_req = next(r for r in requisitions if r["status"] == "CLOSED")
    related = next((a for a in applications if a["requisition_id"] == closed_req["requisition_id"]), None)
    cases.append({
        "anomaly_id": "ANOM-005", "anomaly_type": "CLOSED_JOB_ACTIVE_APPLICATION",
        "description": "Closed requisition has an active application.",
        "related_ids": json.dumps({"requisition_id": closed_req["requisition_id"], "application_id": related["application_id"] if related else None}),
        "injected_record_json": json.dumps({"requisition_status": "CLOSED", "application_status": "APPLIED"}),
        "expected_detection": True,
    })
    return cases


def validate_all(data):
    """Validate core counts, key references, enums, intervals, and clean baseline rules."""
    departments = data["departments"]
    reqs = data["job_requisitions"]
    candidates = data["candidates"]
    apps = data["applications"]
    interviewers = data["interviewers"]
    availability = data["interviewer_availability"]
    interviews = data["interviews"]
    panel = data["interview_panel"]
    feedback = data["feedback"]
    offers = data["offers"]

    req_ids = {r["requisition_id"] for r in reqs}
    dept_ids = {d["department_id"] for d in departments}
    candidate_ids = {c["candidate_id"] for c in candidates}
    app_ids = {a["application_id"] for a in apps}
    interviewer_ids = {i["interviewer_id"] for i in interviewers}
    interview_ids = {i["interview_id"] for i in interviews}
    offer_app_ids = [o["application_id"] for o in offers]
    req_by_id = {r["requisition_id"]: r for r in reqs}
    app_by_id = {a["application_id"]: a for a in apps}
    checks = {
        "departments_count_10": len(departments) == 10,
        "requisitions_count_100": len(reqs) == 100,
        "candidates_count_2000": len(candidates) == 2000,
        "applications_count_3000": len(apps) == 3000,
        "interviews_count_600": len(interviews) == 600,
        "offers_count_150": len(offers) == 150,
        "requisition_department_fks_valid": all(r["department_id"] in dept_ids for r in reqs),
        "application_fks_valid": all(a["requisition_id"] in req_ids and a["candidate_id"] in candidate_ids for a in apps),
        "application_pairs_unique": len({(a["requisition_id"], a["candidate_id"]) for a in apps}) == len(apps),
        "application_statuses_valid": all(a["status"] in {"APPLIED", "SCREENING", "SHORTLISTED", "INTERVIEW", "OFFER", "HIRED", "REJECTED", "WITHDRAWN"} for a in apps),
        "interview_application_fks_valid": all(i["application_id"] in app_ids for i in interviews),
        "interviewers_fks_valid": all(p["interviewer_id"] in interviewer_ids and p["interview_id"] in interview_ids for p in panel),
        "interview_times_valid": all(i["scheduled_end"] > i["scheduled_start"] for i in interviews),
        "offer_application_fks_valid": all(o["application_id"] in app_ids for o in offers),
        "offer_applications_unique": len(offer_app_ids) == len(set(offer_app_ids)),
        "offer_salaries_in_band": all(
            req_by_id[app_by_id[o["application_id"]]["requisition_id"]]["min_salary"]
            <= o["offered_salary"]
            <= req_by_id[app_by_id[o["application_id"]]["requisition_id"]]["max_salary"]
            for o in offers
        ),
        "candidate_skill_fk_valid": all(r["candidate_id"] in candidate_ids for r in data["candidate_skills"]),
        "required_skill_fk_valid": all(r["requisition_id"] in req_ids for r in data["required_skills"]),
        "interview_feedback_panel_fk_valid": all(
            (f["interview_id"], f["interviewer_id"]) in {(p["interview_id"], p["interviewer_id"]) for p in panel}
            for f in feedback
        ),
    }
    report = {
        "seed": RANDOM_SEED,
        "checks_passed": sum(checks.values()),
        "checks_total": len(checks),
        "all_checks_passed": all(checks.values()),
        "checks": checks,
        "record_counts": {name: len(records) for name, records in data.items()},
    }
    write_dataset("validation_report", [report])
    report_path = DATA_DIR / "validation_report.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("\nValidation report:")
    for name, passed in checks.items():
        print(f"{'PASS' if passed else 'FAIL'}: {name}")
    print(f"Passed {report['checks_passed']}/{report['checks_total']} checks.")
    if not report["all_checks_passed"]:
        raise ValueError("Validation failed. Do not load these files into MySQL.")
    return report


def write_manifest(data):
    manifest = {
        "project": "Recruitment Lifecycle Management System",
        "seed": RANDOM_SEED,
        "generator": "generator/data_generator.py",
        "baseline_is_synthetic": True,
        "anomaly_cases_separate": True,
        "files": {},
    }
    for name in data:
        path = DATA_DIR / f"{name}.csv"
        if path.exists():
            manifest["files"][path.name] = {
                "records": len(data[name]),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
    (DATA_DIR / "source_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    rng = random.Random(RANDOM_SEED)

    data = {}
    data["departments"] = make_departments()
    data["job_requisitions"] = make_requisitions(rng, data["departments"])
    data["candidates"] = make_candidates(rng)
    data["skills"] = make_skills()
    data["candidate_skills"] = make_candidate_skills(rng, data["candidates"], data["skills"])
    data["required_skills"] = make_required_skills(rng, data["job_requisitions"], data["skills"])
    data["requisition_approvals"] = make_approvals(data["job_requisitions"])
    data["applications"] = make_applications(rng, data["job_requisitions"], data["candidates"])
    data["resume_artifacts"] = make_resumes(rng, data["candidates"], data["applications"])
    data["screening_rules"] = make_screening_rules(data["job_requisitions"])
    data["interviewers"] = make_interviewers(rng, data["departments"])
    data["interviewer_availability"] = make_availability(rng, data["interviewers"])
    data["interviews"], data["interview_panel"] = make_interviews(
        rng, data["applications"], data["interviewers"], data["interviewer_availability"]
    )
    data["feedback"] = make_feedback(rng, data["interviews"], data["interview_panel"])
    data["offers"], data["offer_approvals"] = make_offers(
        rng, data["applications"], data["job_requisitions"], data["interviews"], data["feedback"]
    )
    data["application_status_history"] = make_status_history(data["applications"])
    data["audit_events"] = make_audit_events(
        data["job_requisitions"], data["applications"], data["offers"]
    )

    # Export all clean baseline tables first.
    for name, records in data.items():
        write_dataset(name, records)

    validate_all(data)

    # Anomalies and labels are separate test files, not baseline table rows.
    anomalies = make_anomalies(
        data["job_requisitions"], data["applications"], data["interviews"],
        data["interview_panel"], data["interviewer_availability"], data["offers"]
    )
    write_dataset("anomaly_cases", anomalies)
    write_dataset("ground_truth", [
        {"anomaly_id": row["anomaly_id"], "anomaly_type": row["anomaly_type"],
         "expected_detection": row["expected_detection"]}
        for row in anomalies
    ])
    write_manifest(data)
    print("\nGeneration complete. Baseline data and anomaly test cases are separate.")
    print(f"Output directory: {DATA_DIR}")


if __name__ == "__main__":
    main()
