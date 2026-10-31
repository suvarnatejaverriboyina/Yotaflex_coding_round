
from database.connectionDB import DatabaseConnection


def CreateTables():
    db_config = None
    cursor = None

    try:
        # Establish database connection
        db_config = DatabaseConnection()

        if db_config is None:
            return "Database connection failed. Tables were not created."

        cursor = db_config.cursor()

        # 1. Departments
        departments_table = """
            CREATE TABLE IF NOT EXISTS departments (
                department_id INT AUTO_INCREMENT PRIMARY KEY,
                department_name VARCHAR(100) NOT NULL UNIQUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """

        # 2. Job requisitions
        requisitions_table = """
            CREATE TABLE IF NOT EXISTS job_requisitions (
                requisition_id INT AUTO_INCREMENT PRIMARY KEY,
                requisition_code VARCHAR(30) NOT NULL UNIQUE,
                department_id INT NOT NULL,
                job_title VARCHAR(150) NOT NULL,
                description TEXT,
                employment_type VARCHAR(30) NOT NULL DEFAULT 'FULL_TIME',
                openings INT NOT NULL DEFAULT 1,
                min_salary DECIMAL(12,2) NOT NULL,
                max_salary DECIMAL(12,2) NOT NULL,
                status VARCHAR(30) NOT NULL DEFAULT 'DRAFT',
                requested_by VARCHAR(100) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                opened_at DATE,
                closed_at DATE,
                FOREIGN KEY (department_id)
                    REFERENCES departments(department_id),
                CHECK (openings > 0),
                CHECK (min_salary >= 0 AND max_salary >= min_salary),
                CHECK (status IN (
                    'DRAFT', 'PENDING_APPROVAL', 'APPROVED',
                    'OPEN', 'ON_HOLD', 'CLOSED', 'CANCELLED'
                ))
            )
        """

        # 3. Requisition approvals
        requisition_approvals_table = """
            CREATE TABLE IF NOT EXISTS requisition_approvals (
                approval_id INT AUTO_INCREMENT PRIMARY KEY,
                requisition_id INT NOT NULL,
                approver_name VARCHAR(100) NOT NULL,
                decision VARCHAR(20) NOT NULL DEFAULT 'PENDING',
                comments TEXT,
                decided_at DATETIME,
                FOREIGN KEY (requisition_id)
                    REFERENCES job_requisitions(requisition_id),
                CHECK (decision IN ('PENDING', 'APPROVED', 'REJECTED'))
            )
        """

        # 4. Candidates
        candidates_table = """
            CREATE TABLE IF NOT EXISTS candidates (
                candidate_id INT AUTO_INCREMENT PRIMARY KEY,
                candidate_code VARCHAR(30) NOT NULL UNIQUE,
                full_name VARCHAR(150) NOT NULL,
                email VARCHAR(254) NOT NULL,
                phone VARCHAR(30),
                experience_years DECIMAL(4,1) NOT NULL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                CHECK (experience_years >= 0)
            )
        """

        # 5. Skills
        skills_table = """
            CREATE TABLE IF NOT EXISTS skills (
                skill_id INT AUTO_INCREMENT PRIMARY KEY,
                skill_name VARCHAR(100) NOT NULL UNIQUE
            )
        """

        # 6. Candidate skills: many-to-many relationship
        candidate_skills_table = """
            CREATE TABLE IF NOT EXISTS candidate_skills (
                candidate_id INT NOT NULL,
                skill_id INT NOT NULL,
                proficiency VARCHAR(20) NOT NULL DEFAULT 'INTERMEDIATE',
                years_experience DECIMAL(4,1) NOT NULL DEFAULT 0,
                PRIMARY KEY (candidate_id, skill_id),
                FOREIGN KEY (candidate_id)
                    REFERENCES candidates(candidate_id),
                FOREIGN KEY (skill_id)
                    REFERENCES skills(skill_id),
                CHECK (proficiency IN (
                    'BEGINNER', 'INTERMEDIATE', 'ADVANCED', 'EXPERT'
                )),
                CHECK (years_experience >= 0)
            )
        """

        # 7. Skills required for a job
        required_skills_table = """
            CREATE TABLE IF NOT EXISTS required_skills (
                requisition_id INT NOT NULL,
                skill_id INT NOT NULL,
                is_mandatory BOOLEAN NOT NULL DEFAULT TRUE,
                weight DECIMAL(5,2) NOT NULL DEFAULT 1.00,
                PRIMARY KEY (requisition_id, skill_id),
                FOREIGN KEY (requisition_id)
                    REFERENCES job_requisitions(requisition_id),
                FOREIGN KEY (skill_id)
                    REFERENCES skills(skill_id),
                CHECK (weight >= 0)
            )
        """

        # 8. Applications
        applications_table = """
            CREATE TABLE IF NOT EXISTS applications (
                application_id INT AUTO_INCREMENT PRIMARY KEY,
                application_code VARCHAR(70) NOT NULL UNIQUE,
                requisition_id INT NOT NULL,
                candidate_id INT NOT NULL,
                applied_at DATETIME NOT NULL,
                source VARCHAR(50) DEFAULT 'CAREER_PORTAL',
                status VARCHAR(30) NOT NULL DEFAULT 'APPLIED',
                screening_score DECIMAL(5,2),
                withdrawn_at DATETIME,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (requisition_id)
                    REFERENCES job_requisitions(requisition_id),
                FOREIGN KEY (candidate_id)
                    REFERENCES candidates(candidate_id),
                UNIQUE (requisition_id, candidate_id),
                CHECK (status IN (
                    'APPLIED', 'SCREENING', 'SHORTLISTED', 'INTERVIEW',
                    'OFFER', 'HIRED', 'REJECTED', 'WITHDRAWN'
                )),
                CHECK (
                    screening_score IS NULL
                    OR screening_score BETWEEN 0 AND 100
                )
            )
        """

        # 9. Resume artifacts
        resume_artifacts_table = """
            CREATE TABLE IF NOT EXISTS resume_artifacts (
                resume_id INT AUTO_INCREMENT PRIMARY KEY,
                candidate_id INT NOT NULL,
                application_id INT,
                file_name VARCHAR(255) NOT NULL,
                file_type VARCHAR(50),
                version_number INT NOT NULL DEFAULT 1,
                uploaded_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (candidate_id)
                    REFERENCES candidates(candidate_id),
                FOREIGN KEY (application_id)
                    REFERENCES applications(application_id),
                UNIQUE (candidate_id, version_number),
                CHECK (version_number > 0)
            )
        """

        # 10. Screening rules
        screening_rules_table = """
            CREATE TABLE IF NOT EXISTS screening_rules (
                rule_id INT AUTO_INCREMENT PRIMARY KEY,
                requisition_id INT NOT NULL,
                rule_name VARCHAR(100) NOT NULL,
                rule_type VARCHAR(30) NOT NULL,
                rule_value VARCHAR(255) NOT NULL,
                weight DECIMAL(5,2) NOT NULL DEFAULT 1.00,
                is_active BOOLEAN NOT NULL DEFAULT TRUE,
                effective_from DATE NOT NULL,
                effective_to DATE,
                FOREIGN KEY (requisition_id)
                    REFERENCES job_requisitions(requisition_id),
                CHECK (weight >= 0),
                CHECK (
                    effective_to IS NULL
                    OR effective_to >= effective_from
                )
            )
        """

        # 11. Interviewers
        interviewers_table = """
            CREATE TABLE IF NOT EXISTS interviewers (
                interviewer_id INT AUTO_INCREMENT PRIMARY KEY,
                interviewer_code VARCHAR(30) NOT NULL UNIQUE,
                interviewer_name VARCHAR(150) NOT NULL,
                email VARCHAR(254) NOT NULL UNIQUE,
                department_id INT,
                is_active BOOLEAN NOT NULL DEFAULT TRUE,
                FOREIGN KEY (department_id)
                    REFERENCES departments(department_id)
            )
        """

        # 12. Interviewer availability
        interviewer_availability_table = """
            CREATE TABLE IF NOT EXISTS interviewer_availability (
                availability_id INT AUTO_INCREMENT PRIMARY KEY,
                interviewer_id INT NOT NULL,
                start_at DATETIME NOT NULL,
                end_at DATETIME NOT NULL,
                availability_status VARCHAR(20) NOT NULL,
                notes VARCHAR(255),
                FOREIGN KEY (interviewer_id)
                    REFERENCES interviewers(interviewer_id),
                CHECK (end_at > start_at),
                CHECK (
                    availability_status IN ('AVAILABLE', 'UNAVAILABLE')
                )
            )
        """

        # 13. Interviews
        interviews_table = """
            CREATE TABLE IF NOT EXISTS interviews (
                interview_id INT AUTO_INCREMENT PRIMARY KEY,
                interview_code VARCHAR(30) NOT NULL UNIQUE,
                application_id INT NOT NULL,
                interview_round INT NOT NULL DEFAULT 1,
                interview_type VARCHAR(30) NOT NULL DEFAULT 'TECHNICAL',
                scheduled_start DATETIME NOT NULL,
                scheduled_end DATETIME NOT NULL,
                status VARCHAR(25) NOT NULL DEFAULT 'SCHEDULED',
                meeting_details VARCHAR(500),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (application_id)
                    REFERENCES applications(application_id),
                CHECK (interview_round > 0),
                CHECK (scheduled_end > scheduled_start),
                CHECK (status IN (
                    'SCHEDULED', 'COMPLETED', 'CANCELLED',
                    'RESCHEDULED', 'NO_SHOW'
                ))
            )
        """

        # 14. Interview panel: many-to-many relationship
        interview_panel_table = """
            CREATE TABLE IF NOT EXISTS interview_panel (
                interview_id INT NOT NULL,
                interviewer_id INT NOT NULL,
                panel_role VARCHAR(30) NOT NULL DEFAULT 'INTERVIEWER',
                PRIMARY KEY (interview_id, interviewer_id),
                FOREIGN KEY (interview_id)
                    REFERENCES interviews(interview_id),
                FOREIGN KEY (interviewer_id)
                    REFERENCES interviewers(interviewer_id),
                CHECK (panel_role IN ('LEAD', 'INTERVIEWER', 'OBSERVER'))
            )
        """

        # 15. Interview feedback
        feedback_table = """
            CREATE TABLE IF NOT EXISTS feedback (
                feedback_id INT AUTO_INCREMENT PRIMARY KEY,
                feedback_code VARCHAR(70) NOT NULL UNIQUE,
                interview_id INT NOT NULL,
                interviewer_id INT NOT NULL,
                rating DECIMAL(3,1) NOT NULL,
                recommendation VARCHAR(25) NOT NULL,
                comments TEXT,
                submitted_at DATETIME,
                FOREIGN KEY (interview_id, interviewer_id)
                    REFERENCES interview_panel(interview_id, interviewer_id),
                UNIQUE (interview_id, interviewer_id),
                CHECK (rating BETWEEN 1 AND 5),
                CHECK (recommendation IN (
                    'STRONG_YES', 'YES', 'MAYBE', 'NO', 'STRONG_NO'
                ))
            )
        """

        # 16. Offers
        offers_table = """
            CREATE TABLE IF NOT EXISTS offers (
                offer_id INT AUTO_INCREMENT PRIMARY KEY,
                offer_code VARCHAR(30) NOT NULL UNIQUE,
                application_id INT NOT NULL,
                offered_salary DECIMAL(12,2) NOT NULL,
                currency CHAR(3) NOT NULL DEFAULT 'INR',
                status VARCHAR(25) NOT NULL DEFAULT 'DRAFT',
                issued_at DATETIME,
                expires_at DATETIME,
                responded_at DATETIME,
                FOREIGN KEY (application_id)
                    REFERENCES applications(application_id),
                CHECK (offered_salary >= 0),
                CHECK (status IN (
                    'DRAFT', 'PENDING_APPROVAL', 'APPROVED', 'ISSUED',
                    'ACCEPTED', 'REJECTED', 'EXPIRED', 'WITHDRAWN'
                )),
                CHECK (
                    expires_at IS NULL
                    OR issued_at IS NULL
                    OR expires_at > issued_at
                )
            )
        """

        # 17. Offer approvals
        offer_approvals_table = """
            CREATE TABLE IF NOT EXISTS offer_approvals (
                offer_approval_id INT AUTO_INCREMENT PRIMARY KEY,
                offer_id INT NOT NULL,
                approver_name VARCHAR(100) NOT NULL,
                decision VARCHAR(20) NOT NULL DEFAULT 'PENDING',
                comments TEXT,
                decided_at DATETIME,
                FOREIGN KEY (offer_id) REFERENCES offers(offer_id),
                CHECK (decision IN ('PENDING', 'APPROVED', 'REJECTED'))
            )
        """

        # 18. Application stage history
        application_history_table = """
            CREATE TABLE IF NOT EXISTS application_status_history (
                history_id BIGINT AUTO_INCREMENT PRIMARY KEY,
                application_id INT NOT NULL,
                previous_status VARCHAR(30),
                new_status VARCHAR(30) NOT NULL,
                changed_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                changed_by VARCHAR(100) NOT NULL,
                reason VARCHAR(500),
                FOREIGN KEY (application_id)
                    REFERENCES applications(application_id)
            )
        """

        # 19. Audit events
        audit_events_table = """
            CREATE TABLE IF NOT EXISTS audit_events (
                audit_id BIGINT AUTO_INCREMENT PRIMARY KEY,
                event_type VARCHAR(100) NOT NULL,
                entity_type VARCHAR(50) NOT NULL,
                entity_id VARCHAR(70) NOT NULL,
                actor VARCHAR(100) NOT NULL DEFAULT 'SYSTEM',
                event_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                details JSON
            )
        """

        # Create tables in dependency order
        tables = [
            departments_table,
            requisitions_table,
            requisition_approvals_table,
            candidates_table,
            skills_table,
            candidate_skills_table,
            required_skills_table,
            applications_table,
            resume_artifacts_table,
            screening_rules_table,
            interviewers_table,
            interviewer_availability_table,
            interviews_table,
            interview_panel_table,
            feedback_table,
            offers_table,
            offer_approvals_table,
            application_history_table,
            audit_events_table
        ]

        for table_query in tables:
            cursor.execute(table_query)

        # Create indexes for common queries
        indexes = [
            """
            CREATE INDEX idx_requisition_status
            ON job_requisitions(status, department_id)
            """,
            """
            CREATE INDEX idx_application_status
            ON applications(status, applied_at)
            """,
            """
            CREATE INDEX idx_application_candidate
            ON applications(candidate_id)
            """,
            """
            CREATE INDEX idx_interview_schedule
            ON interviews(scheduled_start, scheduled_end, status)
            """,
            """
            CREATE INDEX idx_offer_status
            ON offers(status, issued_at)
            """,
            """
            CREATE INDEX idx_history_application
            ON application_status_history(application_id, changed_at)
            """
        ]

        for index_query in indexes:
            try:
                cursor.execute(index_query)
            except Exception as index_error:
                # An index may already exist if the app is restarted.
                if "Duplicate key name" not in str(index_error):
                    raise

        db_config.commit()
        return "All 19 RMS tables created successfully!"

    except Exception as e:
        if db_config is not None:
            db_config.rollback()

        return f"Error in CreateTables(): {e}"

    finally:
        if cursor is not None:
            cursor.close()

        if db_config is not None and db_config.is_connected():
            db_config.close()
