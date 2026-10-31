
def calculate_skill_match(required_skills, candidate_skills):
    """
    Calculate a candidate's weighted skill-match percentage.

    required_skills: list of dictionaries containing:
        skill_id, skill_name, is_mandatory, weight

    candidate_skills: list of dictionaries containing:
        skill_id, proficiency, years_experience
    """

    if not required_skills:
        return {
            "match_score": 0.0,
            "matched_skills": [],
            "missing_skills": [],
            "missing_mandatory_skills": [],
        }

    # Convert candidate skills into a dictionary for quick lookup.
    candidate_skill_map = {
        skill["skill_id"]: skill
        for skill in candidate_skills
    }

    total_weight = 0.0
    matched_weight = 0.0

    matched_skills = []
    missing_skills = []
    missing_mandatory_skills = []

    for required in required_skills:
        skill_id = required["skill_id"]
        skill_name = required["skill_name"]
        weight = float(required["weight"])
        is_mandatory = bool(required["is_mandatory"])

        total_weight += weight

        candidate_skill = candidate_skill_map.get(skill_id)

        if candidate_skill:
            matched_weight += weight
            matched_skills.append(skill_name)
        else:
            missing_skills.append(skill_name)

            if is_mandatory:
                missing_mandatory_skills.append(skill_name)

    score = (
        matched_weight / total_weight * 100
        if total_weight > 0
        else 0.0
    )

    return {
        "match_score": round(score, 2),
        "matched_skills": matched_skills,
        "missing_skills": missing_skills,
        "missing_mandatory_skills": missing_mandatory_skills,
    }



from database.connectionDB import DatabaseConnection


def get_screening_data(requisition_id, candidate_id):
    """Fetch required job skills and a candidate's skills from MySQL."""

    db = DatabaseConnection()

    if db is None:
        raise ConnectionError("Could not connect to the database.")

    cursor = None

    try:
        cursor = db.cursor(dictionary=True)

        cursor.execute("""
            SELECT
                s.skill_id,
                s.skill_name,
                rs.is_mandatory,
                rs.weight
            FROM required_skills AS rs
            JOIN skills AS s
                ON s.skill_id = rs.skill_id
            WHERE rs.requisition_id = %s
            ORDER BY s.skill_name
        """, (requisition_id,))

        required_skills = cursor.fetchall()

        cursor.execute("""
            SELECT
                cs.skill_id,
                cs.proficiency,
                cs.years_experience
            FROM candidate_skills AS cs
            WHERE cs.candidate_id = %s
        """, (candidate_id,))

        candidate_skills = cursor.fetchall()

        return required_skills, candidate_skills

    finally:
        if cursor:
            cursor.close()
        db.close()

def evaluate_screening(requisition_id, required_skills, candidate_skills):
    """Calculate the match score and evaluate active screening rules."""

    from datetime import date
    from database.connectionDB import DatabaseConnection

    db = DatabaseConnection()

    if db is None:
        raise ConnectionError("Could not connect to the database.")

    cursor = None

    try:
        cursor = db.cursor(dictionary=True)

        cursor.execute("""
            SELECT rule_type, rule_value
            FROM screening_rules
            WHERE requisition_id = %s
              AND is_active = 1
              AND effective_from <= %s
              AND (effective_to IS NULL OR effective_to >= %s)
        """, (requisition_id, date.today(), date.today()))

        rules = cursor.fetchall()

    finally:
        if cursor:
            cursor.close()
        db.close()

    result = calculate_skill_match(required_skills, candidate_skills)

    rule_map = {
        rule["rule_type"]: rule["rule_value"]
        for rule in rules
    }

    minimum_match = float(rule_map.get("SKILL_MATCH", 60))
    minimum_experience = float(rule_map.get("MIN_EXPERIENCE", 0))

    total_experience = max(
        (float(skill["years_experience"]) for skill in candidate_skills),
        default=0.0
    )

    result["minimum_match_required"] = minimum_match
    result["minimum_experience_required"] = minimum_experience
    result["experience_years"] = total_experience

    result["meets_skill_threshold"] = (
        result["match_score"] >= minimum_match
    )

    result["meets_experience_requirement"] = (
        total_experience >= minimum_experience
    )

    result["eligible_for_shortlisting"] = (
        result["meets_skill_threshold"]
        and result["meets_experience_requirement"]
        and not result["missing_mandatory_skills"]
    )

    return result

def screen_candidate(requisition_id, candidate_id):
    """Screen one candidate against one job requisition."""

    from database.connectionDB import DatabaseConnection

    required_skills, candidate_skills = get_screening_data(
        requisition_id,
        candidate_id
    )

    if not required_skills:
        raise ValueError(
            "This job requisition has no required skills configured."
        )

    db = DatabaseConnection()

    if db is None:
        raise ConnectionError("Could not connect to the database.")

    cursor = None

    try:
        cursor = db.cursor(dictionary=True)

        cursor.execute("""
            SELECT experience_years
            FROM candidates
            WHERE candidate_id = %s
        """, (candidate_id,))

        candidate = cursor.fetchone()

        if candidate is None:
            raise ValueError("Candidate not found.")

        actual_experience = float(candidate["experience_years"] or 0)

    finally:
        if cursor:
            cursor.close()
        db.close()

    result = evaluate_screening(
        requisition_id,
        required_skills,
        candidate_skills
    )

    # Use the candidate's actual overall experience.
    result["experience_years"] = actual_experience
    result["meets_experience_requirement"] = (
        actual_experience >= result["minimum_experience_required"]
    )

    result["eligible_for_shortlisting"] = (
        result["meets_skill_threshold"]
        and result["meets_experience_requirement"]
        and not result["missing_mandatory_skills"]
    )

    result["requisition_id"] = requisition_id
    result["candidate_id"] = candidate_id

    return result


def save_screening_result(requisition_id, candidate_id):
    """Save the screening score for an existing application."""

    from database.connectionDB import DatabaseConnection

    # Calculate the screening result first.
    result = screen_candidate(requisition_id, candidate_id)

    db = DatabaseConnection()
    if db is None:
        raise ConnectionError("Could not connect to the database.")

    cursor = None

    try:
        cursor = db.cursor(dictionary=True)

        # Find the application for this candidate and job.
        cursor.execute("""
            SELECT application_id, status
            FROM applications
            WHERE requisition_id = %s
              AND candidate_id = %s
        """, (requisition_id, candidate_id))

        application = cursor.fetchone()

        if application is None:
            raise ValueError(
                "No application exists for this candidate and requisition."
            )

        # Update only the screening score.
        # The existing application status remains unchanged.
        cursor.execute("""
            UPDATE applications
            SET screening_score = %s
            WHERE application_id = %s
        """, (
            result["match_score"],
            application["application_id"]
        ))

        db.commit()

        result["application_id"] = application["application_id"]
        result["application_status"] = application["status"]
        result["saved_screening_score"] = result["match_score"]

        return result

    except Exception:
        db.rollback()
        raise

    finally:
        if cursor:
            cursor.close()
        db.close()
