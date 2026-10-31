
import os



import mysql.connector
from datetime import datetime, timedelta
import uuid
from dotenv import load_dotenv
from flask import (
    Flask, render_template, request, redirect,
    url_for, session, flash
)
from werkzeug.security import check_password_hash,generate_password_hash
from functools import wraps
from database.connectionDB import DatabaseConnection

from generator.resume_screening import screen_candidate
from generator.resume_screening import save_screening_result

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY")

if not app.secret_key:
    raise RuntimeError("Add FLASK_SECRET_KEY to your .env file.")


def role_required(*allowed_roles):
    def decorator(view_function):
        @wraps(view_function)
        def wrapped_view(*args, **kwargs):
            if "user_id" not in session:
                flash("Please log in first.", "error")
                return redirect(url_for("login"))

            if session.get("role") not in allowed_roles:
                flash("You are not authorized to access this page.", "error")
                return redirect(url_for("dashboard"))

            return view_function(*args, **kwargs)

        return wrapped_view
    return decorator

@app.route("/")
def home():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        db = DatabaseConnection()
        if db is None:
            flash("Database connection failed.", "error")
            return render_template("login.html")

        cursor = None
        try:
            cursor = db.cursor(dictionary=True)
            cursor.execute(
                """
                SELECT user_id, full_name, email, password_hash, role
                FROM system_users
                WHERE email = %s AND is_active = TRUE
                """,
                (email,)
            )
            user = cursor.fetchone()

            if user and check_password_hash(
                user["password_hash"], password
            ):
                session.clear()
                session["user_id"] = user["user_id"]
                session["full_name"] = user["full_name"]
                session["email"] = user["email"]
                session["role"] = user["role"]

                return redirect(url_for("dashboard"))

            flash("Invalid email or password.", "error")

        except mysql.connector.Error as error:
            app.logger.error("Login database error: %s", error)
            flash("Unable to log in. Please try again.", "error")

        finally:
            if cursor:
                cursor.close()
            db.close()

    return render_template("login.html")


@app.route("/dashboard")
@role_required(
    "SYSTEM_ADMIN",
    "BUSINESS_REQUESTER",
    "PROCESS_OWNER",
    "APPROVER",
    "OPERATIONS_ANALYST"
)
def dashboard():
    if "user_id" not in session:
        flash("Please log in first.", "error")
        return redirect(url_for("login"))

    db = DatabaseConnection()
    if db is None:
        flash("Database connection failed.", "error")
        return redirect(url_for("login"))

    cursor = None

    try:
        cursor = db.cursor(dictionary=True)
        counts = {}

        tables = [
            "departments",
            "job_requisitions",
            "candidates",
            "applications",
            "interviews",
            "offers"
        ]

        for table in tables:
            cursor.execute(
                f"SELECT COUNT(*) AS total FROM `{table}`"
            )
            counts[table] = cursor.fetchone()["total"]

        return render_template(
            "dashboard.html",
            full_name=session["full_name"],
            role=session["role"].replace("_", " ").title(),
            counts=counts
        )

    except mysql.connector.Error as error:
        app.logger.error("Dashboard database error: %s", error)
        flash("Unable to load dashboard data.", "error")
        return redirect(url_for("login"))

    finally:
        if cursor:
            cursor.close()
        db.close()


@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out successfully.", "success")
    return redirect(url_for("login"))




@app.route("/admin/users")
@role_required("SYSTEM_ADMIN")
def manage_users():
    search = request.args.get("search", "").strip()
    selected_role = request.args.get("role", "").strip()

    roles = [
        "BUSINESS_REQUESTER",
        "PROCESS_OWNER",
        "APPROVER",
        "OPERATIONS_ANALYST",
        "SYSTEM_ADMIN"
    ]

    if selected_role and selected_role not in roles:
        selected_role = ""

    db = DatabaseConnection()
    if db is None:
        flash("Database connection failed.", "error")
        return redirect(url_for("dashboard"))

    cursor = None
    try:
        cursor = db.cursor(dictionary=True)

        query = """
            SELECT user_id, full_name, email, role, is_active
            FROM system_users
            WHERE (full_name LIKE %s OR email LIKE %s)
        """
        params = [f"%{search}%", f"%{search}%"]

        if selected_role:
            query += " AND role = %s"
            params.append(selected_role)

        query += " ORDER BY user_id DESC"

        cursor.execute(query, tuple(params))
        users = cursor.fetchall()

        return render_template(
            "users.html",
            users=users,
            search=search,
            roles=roles,
            selected_role=selected_role
        )

    except mysql.connector.Error:
        app.logger.exception("Could not load users")
        flash("Unable to load employee accounts.", "error")
        return redirect(url_for("dashboard"))

    finally:
        if cursor:
            cursor.close()
        db.close()


@app.route("/admin/users/create", methods=["POST"])
@role_required("SYSTEM_ADMIN")
def create_user():
    full_name = request.form.get("full_name", "").strip()
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")
    role = request.form.get("role", "")

    allowed_roles = {
        "BUSINESS_REQUESTER",
        "PROCESS_OWNER",
        "APPROVER",
        "OPERATIONS_ANALYST",
        "SYSTEM_ADMIN"
    }

    if (
        not full_name
        or len(full_name) > 100
        or not email
        or len(email) > 150
        or len(password) < 12
        or role not in allowed_roles
    ):
        flash("Please enter valid account details.", "error")
        return redirect(url_for("manage_users"))

    db = DatabaseConnection()
    if db is None:
        flash("Database connection failed.", "error")
        return redirect(url_for("manage_users"))

    cursor = None
    try:
        cursor = db.cursor()
        cursor.execute("""
            INSERT INTO system_users
                (full_name, email, password_hash, role, is_active)
            VALUES (%s, %s, %s, %s, TRUE)
        """, (
            full_name,
            email,
            generate_password_hash(password),
            role
        ))
        db.commit()
        flash("Employee account created successfully.", "success")

    except mysql.connector.IntegrityError:
        db.rollback()
        flash("That email address is already registered.", "error")

    except mysql.connector.Error:
        db.rollback()
        app.logger.exception("Could not create employee account")
        flash("Unable to create employee account.", "error")

    finally:
        if cursor:
            cursor.close()
        db.close()

    return redirect(url_for("manage_users"))


@app.route("/admin/users/<int:user_id>/toggle", methods=["POST"])
@role_required("SYSTEM_ADMIN")
def toggle_user(user_id):
    if user_id == session.get("user_id"):
        flash("You cannot deactivate your own account.", "error")
        return redirect(url_for("manage_users"))

    db = DatabaseConnection()
    if db is None:
        flash("Database connection failed.", "error")
        return redirect(url_for("manage_users"))

    cursor = None
    try:
        cursor = db.cursor()
        cursor.execute("""
            UPDATE system_users
            SET is_active = NOT is_active
            WHERE user_id = %s
        """, (user_id,))

        if cursor.rowcount == 0:
            db.rollback()
            flash("Employee account not found.", "error")
        else:
            db.commit()
            flash("Employee account status updated.", "success")

    except mysql.connector.Error:
        db.rollback()
        app.logger.exception("Could not update employee status")
        flash("Unable to update employee status.", "error")

    finally:
        if cursor:
            cursor.close()
        db.close()

    return redirect(url_for("manage_users"))



@app.route("/admin/users/<int:user_id>/edit", methods=["GET", "POST"])
@role_required("SYSTEM_ADMIN")
def edit_user(user_id):
    roles = [
        "BUSINESS_REQUESTER",
        "PROCESS_OWNER",
        "APPROVER",
        "OPERATIONS_ANALYST",
        "SYSTEM_ADMIN"
    ]

    db = DatabaseConnection()
    if db is None:
        flash("Database connection failed.", "error")
        return redirect(url_for("manage_users"))

    cursor = None
    try:
        cursor = db.cursor(dictionary=True)

        cursor.execute("""
            SELECT user_id, full_name, email, role, is_active
            FROM system_users
            WHERE user_id = %s
        """, (user_id,))
        user = cursor.fetchone()

        if not user:
            flash("Employee account not found.", "error")
            return redirect(url_for("manage_users"))

        if request.method == "POST":
            full_name = request.form.get("full_name", "").strip()
            email = request.form.get("email", "").strip().lower()
            role = request.form.get("role", "")

            if (
                not full_name
                or len(full_name) > 100
                or not email
                or len(email) > 150
                or role not in roles
            ):
                flash("Please enter valid employee details.", "error")
                return render_template(
                    "edit_user.html", user=user, roles=roles
                )

            # Prevent removing the last active administrator.
            if user["is_active"] and user["role"] == "SYSTEM_ADMIN":
                if role != "SYSTEM_ADMIN":
                    cursor.execute("""
                        SELECT COUNT(*) AS total
                        FROM system_users
                        WHERE role = 'SYSTEM_ADMIN'
                          AND is_active = TRUE
                    """)
                    if cursor.fetchone()["total"] <= 1:
                        flash(
                            "You cannot demote the last active System Admin.",
                            "error"
                        )
                        return render_template(
                            "edit_user.html", user=user, roles=roles
                        )

            cursor.execute("""
                UPDATE system_users
                SET full_name = %s, email = %s, role = %s
                WHERE user_id = %s
            """, (full_name, email, role, user_id))
            db.commit()

            if user_id == session.get("user_id"):
                session["full_name"] = full_name
                session["email"] = email
                session["role"] = role

            flash("Employee details updated successfully.", "success")
            return redirect(url_for("manage_users"))

        return render_template("edit_user.html", user=user, roles=roles)

    except mysql.connector.IntegrityError:
        db.rollback()
        flash("That email address is already in use.", "error")
        return redirect(url_for("manage_users"))

    except mysql.connector.Error:
        db.rollback()
        app.logger.exception("Could not edit employee")
        flash("Unable to update employee details.", "error")
        return redirect(url_for("manage_users"))

    finally:
        if cursor:
            cursor.close()
        db.close()


@app.route("/requisitions")
@role_required(
    "SYSTEM_ADMIN",
    "BUSINESS_REQUESTER",
    "PROCESS_OWNER",
    "APPROVER",
    "OPERATIONS_ANALYST"
)
def requisitions():
    search = request.args.get("search", "").strip()
    selected_status = request.args.get("status", "").strip().upper()

    allowed_statuses = [
        "DRAFT",
        "PENDING_APPROVAL",
        "APPROVED",
        "OPEN",
        "ON_HOLD",
        "CLOSED",
        "REJECTED"
    ]

    if selected_status not in allowed_statuses:
        selected_status = ""

    db = DatabaseConnection()

    if db is None:
        flash("Database connection failed.", "error")
        return redirect(url_for("dashboard"))

    cursor = None

    try:
        cursor = db.cursor(dictionary=True)

        sql = """
            SELECT
                jr.requisition_id,
                jr.requisition_code,
                jr.job_title,
                jr.employment_type,
                jr.openings,
                jr.min_salary,
                jr.max_salary,
                jr.status,
                jr.requested_by,
                jr.created_at,
                jr.opened_at,
                d.department_name
            FROM job_requisitions AS jr
            JOIN departments AS d
                ON jr.department_id = d.department_id
            WHERE (
                jr.requisition_code LIKE %s
                OR jr.job_title LIKE %s
                OR d.department_name LIKE %s
            )
        """

        search_value = f"%{search}%"
        params = [search_value, search_value, search_value]

        if selected_status:
            sql += " AND jr.status = %s"
            params.append(selected_status)

        sql += " ORDER BY jr.created_at DESC"

        cursor.execute(sql, tuple(params))
        requisition_list = cursor.fetchall()

        cursor.execute("""
            SELECT DISTINCT status
            FROM job_requisitions
            ORDER BY status
        """)
        statuses = [row["status"] for row in cursor.fetchall()]

        return render_template(
            "requisitions.html",
            requisitions=requisition_list,
            search=search,
            selected_status=selected_status,
            statuses=statuses
        )

    except mysql.connector.Error as error:
        app.logger.error("Requisition list error: %s", error)
        flash("Unable to load job requisitions.", "error")
        return redirect(url_for("dashboard"))

    finally:
        if cursor:
            cursor.close()
        db.close()



@app.route("/requisitions/create", methods=["GET", "POST"])
@role_required(
    "SYSTEM_ADMIN",
    "BUSINESS_REQUESTER",
    "PROCESS_OWNER"
)
def create_requisition():
    db = DatabaseConnection()

    if db is None:
        flash("Database connection failed.", "error")
        return redirect(url_for("requisitions"))

    cursor = None

    try:
        cursor = db.cursor(dictionary=True)

        cursor.execute("""
            SELECT department_id, department_name
            FROM departments
            ORDER BY department_name
        """)
        departments = cursor.fetchall()

        if request.method == "POST":
            job_title = request.form.get("job_title", "").strip()
            description = request.form.get("description", "").strip()
            department_id = request.form.get("department_id", "")
            employment_type = request.form.get("employment_type", "")
            openings_text = request.form.get("openings", "")
            min_salary_text = request.form.get("min_salary", "")
            max_salary_text = request.form.get("max_salary", "")

            allowed_types = {
                "FULL_TIME", "PART_TIME", "CONTRACT", "INTERNSHIP"
            }

            try:
                department_id = int(department_id)
                openings = int(openings_text)
                min_salary = float(min_salary_text)
                max_salary = float(max_salary_text)
            except (ValueError, TypeError):
                flash("Please enter valid form values.", "error")
                return render_template(
                    "create_requisition.html",
                    departments=departments
                )

            if not job_title or len(job_title) > 150:
                flash("Enter a valid job title.", "error")
            elif len(description) > 5000:
                flash("Description must not exceed 5000 characters.", "error")
            elif employment_type not in allowed_types:
                flash("Select a valid employment type.", "error")
            elif openings < 1 or openings > 1000:
                flash("Openings must be between 1 and 1000.", "error")
            elif min_salary < 0 or max_salary < min_salary:
                flash("Enter a valid salary range.", "error")
            elif not any(
                d["department_id"] == department_id
                for d in departments
            ):
                flash("Select a valid department.", "error")
            else:
                cursor.execute("""
                    SELECT COALESCE(MAX(requisition_id), 0) + 1 AS next_id
                    FROM job_requisitions
                """)
                next_id = cursor.fetchone()["next_id"]

                requisition_code = f"REQ-{date.today().year}-{next_id:06d}"

                cursor.execute("""
                    INSERT INTO job_requisitions (
                        requisition_code,
                        department_id,
                        job_title,
                        description,
                        employment_type,
                        openings,
                        min_salary,
                        max_salary,
                        status,
                        requested_by
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    requisition_code,
                    department_id,
                    job_title,
                    description or None,
                    employment_type,
                    openings,
                    min_salary,
                    max_salary,
                    "DRAFT",
                    session["email"]
                ))

                db.commit()
                flash(
                    f"Requisition {requisition_code} created successfully.",
                    "success"
                )
                return redirect(url_for("requisitions"))

        return render_template(
            "create_requisition.html",
            departments=departments
        )

    except mysql.connector.Error as error:
        db.rollback()
        app.logger.error("Create requisition error: %s", error)
        flash("Unable to save the requisition.", "error")
        return redirect(url_for("requisitions"))

    finally:
        if cursor:
            cursor.close()
        db.close()



@app.route("/approvals")
@role_required("SYSTEM_ADMIN", "APPROVER")
def approvals():
    db = DatabaseConnection()

    if db is None:
        flash("Database connection failed.", "error")
        return redirect(url_for("dashboard"))

    cursor = None

    try:
        cursor = db.cursor(dictionary=True)

        cursor.execute("""
            SELECT
                ra.approval_id,
                ra.requisition_id,
                ra.approver_name,
                ra.decision,
                jr.requisition_code,
                jr.job_title,
                jr.openings,
                jr.min_salary,
                jr.max_salary,
                jr.requested_by,
                d.department_name
            FROM requisition_approvals AS ra
            JOIN job_requisitions AS jr
                ON ra.requisition_id = jr.requisition_id
            JOIN departments AS d
                ON jr.department_id = d.department_id
            WHERE ra.decision = 'PENDING'
            ORDER BY ra.approval_id
        """)

        pending_approvals = cursor.fetchall()

        return render_template(
            "approvals.html",
            approvals=pending_approvals
        )

    except mysql.connector.Error as error:
        app.logger.error("Approval list error: %s", error)
        flash("Unable to load pending approvals.", "error")
        return redirect(url_for("dashboard"))

    finally:
        if cursor:
            cursor.close()
        db.close()




@app.route("/offers/approvals/<int:approval_id>/review")
@role_required("SYSTEM_ADMIN", "APPROVER")
def review_approval(approval_id):
    db = DatabaseConnection()

    if db is None:
        flash("Database connection failed.", "error")
        return redirect(url_for("dashboard"))

    cursor = None

    try:
        cursor = db.cursor(dictionary=True)

        query = """
            SELECT
                oa.offer_approval_id,
                oa.offer_id,
                oa.approver_name,
                oa.decision,
                oa.comments,
                oa.decided_at,
                o.offer_code,
                o.offered_salary,
                o.currency,
                o.status AS offer_status,
                o.expires_at,
                a.application_code,
                c.full_name,
                c.email,
                jr.job_title
            FROM offer_approvals AS oa
            JOIN offers AS o
                ON oa.offer_id = o.offer_id
            JOIN applications AS a
                ON o.application_id = a.application_id
            JOIN candidates AS c
                ON a.candidate_id = c.candidate_id
            JOIN job_requisitions AS jr
                ON a.requisition_id = jr.requisition_id
            WHERE oa.offer_approval_id = %s
        """

        cursor.execute(query, (approval_id,))
        approval = cursor.fetchone()

        if not approval:
            flash("Approval record not found.", "error")
            return redirect(url_for("offer_approvals"))

        return render_template(
            "review_approval.html",
            approval=approval
        )

    except mysql.connector.Error:
        app.logger.exception("Unable to load approval record")
        flash("Unable to load approval record.", "error")
        return redirect(url_for("offer_approvals"))

    finally:
        if cursor:
            cursor.close()
        db.close()





@app.route("/offers/approvals/<int:approval_id>/decide", methods=["POST"])
@role_required("SYSTEM_ADMIN", "APPROVER")
def decide_offer_approval(approval_id):
    decision = request.form.get("decision", "").strip().upper()
    comments = request.form.get("comments", "").strip()
    username = session.get("username")  # Match this to your login session key.

    if decision not in ("APPROVED", "REJECTED"):
        flash("Invalid approval decision.", "error")
        return redirect(url_for("review_approval", approval_id=approval_id))

    db = DatabaseConnection()
    if db is None:
        flash("Database connection failed.", "error")
        return redirect(url_for("offer_approvals"))

    cursor = None
    try:
        cursor = db.cursor(dictionary=True)
        db.start_transaction()

        cursor.execute("""
            SELECT oa.offer_id, oa.approver_name, oa.decision,
                   o.status AS offer_status
            FROM offer_approvals oa
            JOIN offers o ON oa.offer_id = o.offer_id
            WHERE oa.offer_approval_id = %s
            FOR UPDATE
        """, (approval_id,))
        approval = cursor.fetchone()

        if not approval:
            db.rollback()
            flash("Approval record not found.", "error")
            return redirect(url_for("offer_approvals"))

        # Only the assigned approver or a system admin may decide.
        role = session.get("role")
        if role != "SYSTEM_ADMIN" and (
            not username or username != approval["approver_name"]
        ):
            db.rollback()
            flash("You are not authorized to decide this approval.", "error")
            return redirect(url_for("offer_approvals"))

        if (approval["decision"] != "PENDING"
                or approval["offer_status"] != "PENDING_APPROVAL"):
            db.rollback()
            flash("This offer has already been processed.", "error")
            return redirect(url_for("offer_approvals"))

        cursor.execute("""
            UPDATE offer_approvals
            SET decision = %s,
                comments = %s,
                decided_at = CURRENT_TIMESTAMP
            WHERE offer_approval_id = %s
              AND decision = 'PENDING'
        """, (decision, comments or None, approval_id))

        cursor.execute("""
            UPDATE offers
            SET status = %s
            WHERE offer_id = %s
              AND status = 'PENDING_APPROVAL'
        """, (decision, approval["offer_id"]))

        db.commit()
        flash(f"Offer {decision.lower()} successfully.", "success")
        return redirect(url_for("offer_approvals"))

    except mysql.connector.Error:
        db.rollback()
        app.logger.exception("Unable to process offer approval")
        flash("Unable to save the decision. Please try again.", "error")
        return redirect(url_for("offer_approvals"))

    finally:
        if cursor:
            cursor.close()
        db.close()


@app.route("/candidates")
@role_required(
    "SYSTEM_ADMIN",
    "BUSINESS_REQUESTER",
    "PROCESS_OWNER",
    "APPROVER",
    "OPERATIONS_ANALYST"
)
def candidates():
    search = request.args.get("search", "").strip()

    db = DatabaseConnection()
    if db is None:
        flash("Database connection failed.", "error")
        return redirect(url_for("dashboard"))

    cursor = None

    try:
        cursor = db.cursor(dictionary=True)

        query = """
            SELECT
                candidate_id,
                candidate_code,
                full_name,
                email,
                phone,
                experience_years,
                created_at
            FROM candidates
        """

        params = []

        if search:
            query += """
                WHERE candidate_code LIKE %s
                   OR full_name LIKE %s
                   OR email LIKE %s
                   OR phone LIKE %s
            """
            search_value = f"%{search}%"
            params = [
                search_value,
                search_value,
                search_value,
                search_value
            ]

        query += " ORDER BY created_at DESC"

        cursor.execute(query, params)
        candidate_list = cursor.fetchall()

        return render_template(
            "candidates.html",
            candidates=candidate_list,
            search=search
        )

    except mysql.connector.Error as error:
        app.logger.error("Candidate directory error: %s", error)
        flash("Unable to load candidates.", "error")
        return redirect(url_for("dashboard"))

    finally:
        if cursor:
            cursor.close()
        db.close()



@app.route("/applications")
@role_required(
    "SYSTEM_ADMIN",
    "BUSINESS_REQUESTER",
    "PROCESS_OWNER",
    "APPROVER",
    "OPERATIONS_ANALYST"
)
def applications():
    search = request.args.get("search", "").strip()
    status = request.args.get("status", "").strip().upper()

    allowed_statuses = {
        "APPLIED",
        "SCREENING",
        "SHORTLISTED",
        "REJECTED",
        "INTERVIEW",
        "OFFER",
        "HIRED",
        "WITHDRAWN"
    }

    if status not in allowed_statuses:
        status = ""

    db = DatabaseConnection()

    if db is None:
        flash("Database connection failed.", "error")
        return redirect(url_for("dashboard"))

    cursor = None

    try:
        cursor = db.cursor(dictionary=True)

        query = """
            SELECT
                a.application_id,
                a.application_code,
                a.applied_at,
                a.source,
                a.status,
                a.screening_score,
                c.candidate_code,
                c.full_name,
                c.email,
                jr.requisition_code,
                jr.job_title
            FROM applications AS a
            JOIN candidates AS c
                ON a.candidate_id = c.candidate_id
            JOIN job_requisitions AS jr
                ON a.requisition_id = jr.requisition_id
            WHERE 1 = 1
        """

        params = []

        if search:
            query += """
                AND (
                    a.application_code LIKE %s
                    OR c.full_name LIKE %s
                    OR c.email LIKE %s
                    OR jr.job_title LIKE %s
                    OR jr.requisition_code LIKE %s
                )
            """
            search_value = f"%{search}%"
            params.extend([search_value] * 5)

        if status:
            query += " AND a.status = %s"
            params.append(status)

        query += " ORDER BY a.applied_at DESC"

        cursor.execute(query, tuple(params))
        application_list = cursor.fetchall()

        return render_template(
            "applications.html",
            applications=application_list,
            search=search,
            selected_status=status,
            statuses=sorted(allowed_statuses)
        )

    except mysql.connector.Error as error:
        app.logger.error("Application tracking error: %s", error)
        flash("Unable to load applications.", "error")
        return redirect(url_for("dashboard"))

    finally:
        if cursor:
            cursor.close()
        db.close()


@app.route("/applications/<int:application_id>/status", methods=["POST"])
@role_required(
    "SYSTEM_ADMIN",
    "PROCESS_OWNER",
    "OPERATIONS_ANALYST"
)
def update_application_status(application_id):
    allowed_statuses = {
        "APPLIED",
        "SCREENING",
        "SHORTLISTED",
        "REJECTED",
        "INTERVIEW",
        "OFFER",
        "HIRED",
        "WITHDRAWN"
    }

    new_status = request.form.get("status", "").strip().upper()
    reason = request.form.get("reason", "").strip()

    if new_status not in allowed_statuses:
        flash("Please select a valid application status.", "error")
        return redirect(url_for("applications"))

    if len(reason) > 500:
        flash("Reason must not exceed 500 characters.", "error")
        return redirect(url_for("applications"))

    if new_status in {"REJECTED", "WITHDRAWN"} and not reason:
        flash("Please provide a reason for rejection or withdrawal.", "error")
        return redirect(url_for("applications"))

    db = DatabaseConnection()

    if db is None:
        flash("Database connection failed.", "error")
        return redirect(url_for("applications"))

    cursor = None

    try:
        cursor = db.cursor(dictionary=True)

        # Lock the application row while updating it.
        cursor.execute("""
            SELECT application_id, status
            FROM applications
            WHERE application_id = %s
            FOR UPDATE
        """, (application_id,))

        application = cursor.fetchone()

        if not application:
            db.rollback()
            flash("Application not found.", "error")
            return redirect(url_for("applications"))

        previous_status = application["status"]

        if previous_status == new_status:
            db.rollback()
            flash("The application already has that status.", "error")
            return redirect(url_for("applications"))

        # Only permit forward movement through the workflow,
        # plus rejection or withdrawal from non-terminal states.
        transitions = {
            "APPLIED": {"SCREENING", "REJECTED", "WITHDRAWN"},
            "SCREENING": {"SHORTLISTED", "REJECTED", "WITHDRAWN"},
            "SHORTLISTED": {"INTERVIEW", "REJECTED", "WITHDRAWN"},
            "INTERVIEW": {"OFFER", "REJECTED", "WITHDRAWN"},
            "OFFER": {"HIRED", "REJECTED", "WITHDRAWN"},
            "HIRED": set(),
            "REJECTED": set(),
            "WITHDRAWN": set()
        }

        if new_status not in transitions.get(previous_status, set()):
            db.rollback()
            flash(
                f"Status cannot change from {previous_status} to {new_status}.",
                "error"
            )
            return redirect(url_for("applications"))

        cursor.execute("""
            UPDATE applications
            SET status = %s,
                withdrawn_at = CASE
                    WHEN %s = 'WITHDRAWN' THEN NOW()
                    ELSE NULL
                END
            WHERE application_id = %s
        """, (new_status, new_status, application_id))

        cursor.execute("""
            INSERT INTO application_status_history (
                application_id,
                previous_status,
                new_status,
                changed_by,
                reason
            )
            VALUES (%s, %s, %s, %s, %s)
        """, (
            application_id,
            previous_status,
            new_status,
            session.get("email", session.get("full_name", "UNKNOWN")),
            reason or None
        ))

        db.commit()
        flash("Application status updated successfully.", "success")

    except mysql.connector.Error as error:
        db.rollback()
        app.logger.error("Application status update failed: %s", error)
        flash("Unable to update application status.", "error")

    finally:
        if cursor:
            cursor.close()
        db.close()

    return redirect(url_for("applications"))



@app.route("/applications/<int:application_id>/history")
@role_required(
    "SYSTEM_ADMIN",
    "BUSINESS_REQUESTER",
    "PROCESS_OWNER",
    "APPROVER",
    "OPERATIONS_ANALYST"
)
def application_history(application_id):
    db = DatabaseConnection()

    if db is None:
        flash("Database connection failed.", "error")
        return redirect(url_for("applications"))

    cursor = None

    try:
        cursor = db.cursor(dictionary=True)

        cursor.execute("""
            SELECT
                a.application_id,
                a.application_code,
                a.status AS current_status,
                c.candidate_code,
                c.full_name,
                c.email,
                jr.requisition_code,
                jr.job_title
            FROM applications AS a
            JOIN candidates AS c
                ON a.candidate_id = c.candidate_id
            JOIN job_requisitions AS jr
                ON a.requisition_id = jr.requisition_id
            WHERE a.application_id = %s
        """, (application_id,))

        application = cursor.fetchone()

        if not application:
            flash("Application not found.", "error")
            return redirect(url_for("applications"))

        cursor.execute("""
            SELECT
                history_id,
                previous_status,
                new_status,
                changed_at,
                changed_by,
                reason
            FROM application_status_history
            WHERE application_id = %s
            ORDER BY changed_at DESC, history_id DESC
        """, (application_id,))

        history = cursor.fetchall()

        return render_template(
            "application_history.html",
            application=application,
            history=history
        )

    except mysql.connector.Error as error:
        app.logger.error("Application history error: %s", error)
        flash("Unable to load application history.", "error")
        return redirect(url_for("applications"))

    finally:
        if cursor:
            cursor.close()
        db.close()



@app.route("/applications/<int:application_id>/screen", methods=["POST"])
@role_required(
    "SYSTEM_ADMIN",
    "PROCESS_OWNER",
    "OPERATIONS_ANALYST"
)
def screen_application(application_id):
    db = DatabaseConnection()

    if db is None:
        flash("Database connection failed.", "error")
        return redirect(url_for("applications"))

    cursor = None

    try:
        cursor = db.cursor(dictionary=True)

        cursor.execute("""
            SELECT
                application_id,
                requisition_id,
                candidate_id,
                status
            FROM applications
            WHERE application_id = %s
        """, (application_id,))

        application = cursor.fetchone()

        if not application:
            flash("Application not found.", "error")
            return redirect(url_for("applications"))

        if application["status"] not in {"APPLIED", "SCREENING"}:
            flash(
                "Only applications in APPLIED or SCREENING status "
                "can be screened.",
                "error"
            )
            return redirect(url_for("applications"))

        requisition_id = application["requisition_id"]
        candidate_id = application["candidate_id"]

    except mysql.connector.Error as error:
        app.logger.error("Unable to find application: %s", error)
        flash("Unable to load the application.", "error")
        return redirect(url_for("applications"))

    finally:
        if cursor:
            cursor.close()
        db.close()

    try:
        result = save_screening_result(
            requisition_id=requisition_id,
            candidate_id=candidate_id
        )

        return render_template(
            "screening_result.html",
            result=result,
            application_id=application_id
        )

    except (ValueError, ConnectionError) as error:
        flash(str(error), "error")
        return redirect(url_for("applications"))

    except Exception:
        app.logger.exception("Resume screening failed.")
        flash("Unable to screen this application.", "error")
        return redirect(url_for("applications"))




@app.route("/interviews/schedule", methods=["GET", "POST"])
@role_required("SYSTEM_ADMIN", "PROCESS_OWNER", "OPERATIONS_ANALYST")
def schedule_interview():

    db = DatabaseConnection()

    if db is None:
        flash("Database connection failed.", "error")
        return redirect(url_for("dashboard"))

    cursor = None

    try:
        cursor = db.cursor(dictionary=True)

        if request.method == "POST":
            application_id = request.form.get("application_id", type=int)
            interviewer_id = request.form.get("interviewer_id", type=int)
            interview_round = request.form.get("interview_round", type=int)
            interview_type = request.form.get("interview_type", "").strip().upper()
            scheduled_start = request.form.get("scheduled_start", "").strip()
            scheduled_end = request.form.get("scheduled_end", "").strip()
            meeting_details = request.form.get("meeting_details", "").strip()

            if not all([
                application_id,
                interviewer_id,
                interview_round,
                scheduled_start,
                scheduled_end
            ]):
                flash("Please fill in all required fields.", "error")

            elif interview_round < 1:
                flash("Interview round must be at least 1.", "error")

            elif interview_type not in {
                "TECHNICAL", "HR", "MANAGERIAL", "FINAL"
            }:
                flash("Invalid interview type.", "error")

            else:
                try:
                    start_at = datetime.strptime(
                        scheduled_start, "%Y-%m-%dT%H:%M"
                    )
                    end_at = datetime.strptime(
                        scheduled_end, "%Y-%m-%dT%H:%M"
                    )
                except ValueError:
                    flash("Please enter valid interview dates and times.", "error")
                else:
                    if start_at <= datetime.now():
                        flash("Interview must be scheduled in the future.", "error")

                    elif end_at <= start_at:
                        flash("End time must be after start time.", "error")

                    else:
                        cursor.execute("""
                            SELECT application_id
                            FROM applications
                            WHERE application_id = %s
                              AND status = 'SHORTLISTED'
                        """, (application_id,))

                        application = cursor.fetchone()

                        cursor.execute("""
                            SELECT interviewer_id
                            FROM interviewers
                            WHERE interviewer_id = %s
                              AND is_active = 1
                        """, (interviewer_id,))

                        interviewer = cursor.fetchone()

                        if not application:
                            flash(
                                "Select a valid shortlisted application.",
                                "error"
                            )

                        elif not interviewer:
                            flash("Select an active interviewer.", "error")

                        else:
                            cursor.execute("""
                                SELECT availability_id
                                FROM interviewer_availability
                                WHERE interviewer_id = %s
                                  AND availability_status = 'AVAILABLE'
                                  AND start_at <= %s
                                  AND end_at >= %s
                                LIMIT 1
                            """, (interviewer_id, start_at, end_at))

                            availability = cursor.fetchone()

                            cursor.execute("""
                                SELECT i.interview_id
                                FROM interviews i
                                JOIN interview_panel p
                                  ON i.interview_id = p.interview_id
                                WHERE p.interviewer_id = %s
                                  AND i.status IN ('SCHEDULED', 'IN_PROGRESS')
                                  AND i.scheduled_start < %s
                                  AND i.scheduled_end > %s
                                LIMIT 1
                            """, (interviewer_id, end_at, start_at))

                            conflict = cursor.fetchone()

                            if not availability:
                                flash(
                                    "The interviewer has no matching AVAILABLE time slot.",
                                    "error"
                                )

                            elif conflict:
                                flash(
                                    "The interviewer already has an overlapping interview.",
                                    "error"
                                )

                            else:
                                interview_code = (
                                    "INT-" + uuid.uuid4().hex[:12].upper()
                                )

                                try:
                                    cursor.execute("""
                                        INSERT INTO interviews (
                                            interview_code,
                                            application_id,
                                            interview_round,
                                            interview_type,
                                            scheduled_start,
                                            scheduled_end,
                                            status,
                                            meeting_details
                                        )
                                        VALUES (%s, %s, %s, %s, %s, %s, 'SCHEDULED', %s)
                                    """, (
                                        interview_code,
                                        application_id,
                                        interview_round,
                                        interview_type,
                                        start_at,
                                        end_at,
                                        meeting_details or None
                                    ))

                                    interview_id = cursor.lastrowid

                                    cursor.execute("""
                                        INSERT INTO interview_panel (
                                            interview_id,
                                            interviewer_id,
                                            panel_role
                                        )
                                        VALUES (%s, %s, 'INTERVIEWER')
                                    """, (interview_id, interviewer_id))

                                    db.commit()

                                    flash(
                                        f"Interview {interview_code} scheduled successfully.",
                                        "success"
                                    )
                                    return redirect(url_for("list_interviews"))

                                except mysql.connector.Error:
                                    db.rollback()
                                    raise

        cursor.execute("""
            SELECT application_id, application_code
            FROM applications
            WHERE status = 'SHORTLISTED'
            ORDER BY application_id DESC
        """)
        applications_list = cursor.fetchall()

        cursor.execute("""
            SELECT interviewer_id, interviewer_code, interviewer_name
            FROM interviewers
            WHERE is_active = 1
            ORDER BY interviewer_name
        """)
        interviewers_list = cursor.fetchall()

        return render_template(
            "schedule_interview.html",
            applications=applications_list,
            interviewers=interviewers_list
        )

    except mysql.connector.Error as error:
        db.rollback()
        app.logger.exception("Interview scheduling error: %s", error)
        flash("Unable to schedule the interview.", "error")
        return redirect(url_for("dashboard"))

    finally:
        if cursor:
            cursor.close()
        db.close()



@app.route("/interviews")
@role_required(
    "SYSTEM_ADMIN",
    "BUSINESS_REQUESTER",
    "PROCESS_OWNER",
    "APPROVER",
    "OPERATIONS_ANALYST"
)
def list_interviews():

    db = DatabaseConnection()

    if db is None:
        flash("Database connection failed.", "error")
        return redirect(url_for("dashboard"))

    cursor = None

    try:
        cursor = db.cursor(dictionary=True)

        query = """
            SELECT
                i.interview_id,
                i.interview_code,
                i.application_id,
                i.interview_round,
                i.interview_type,
                i.scheduled_start,
                i.scheduled_end,
                i.status,
                i.meeting_details,
                a.application_code,
                c.full_name,
                c.email,
                GROUP_CONCAT(
                    DISTINCT iv.interviewer_name
                    ORDER BY iv.interviewer_name
                    SEPARATOR ', '
                ) AS interviewer_names
            FROM interviews AS i
            JOIN applications AS a
                ON i.application_id = a.application_id
            JOIN candidates AS c
                ON a.candidate_id = c.candidate_id
            LEFT JOIN interview_panel AS ip
                ON i.interview_id = ip.interview_id
            LEFT JOIN interviewers AS iv
                ON ip.interviewer_id = iv.interviewer_id
            GROUP BY
                i.interview_id,
                i.interview_code,
                i.application_id,
                i.interview_round,
                i.interview_type,
                i.scheduled_start,
                i.scheduled_end,
                i.status,
                i.meeting_details,
                a.application_code,
                c.full_name,
                c.email
            ORDER BY i.scheduled_start DESC
        """

        cursor.execute(query)
        interview_list = cursor.fetchall()

        return render_template(
            "interviews.html",
            interviews=interview_list
        )

    except mysql.connector.Error:
        app.logger.exception("Unable to load interviews")
        flash("Unable to load interviews.", "error")
        return redirect(url_for("dashboard"))

    finally:
        if cursor:
            cursor.close()
        db.close()


@app.route("/shortlisted-candidates")
@role_required(
    "SYSTEM_ADMIN",
    "BUSINESS_REQUESTER",
    "PROCESS_OWNER",
    "APPROVER",
    "OPERATIONS_ANALYST"
)
def shortlisted_candidates():
    db = DatabaseConnection()

    if db is None:
        flash("Database connection failed.", "error")
        return redirect(url_for("dashboard"))

    cursor = None

    try:
        cursor = db.cursor(dictionary=True)

        query = """
            SELECT
                a.application_id,
                a.application_code,
                a.status,
                a.screening_score,
                c.full_name,
                c.email,
                jr.job_title
            FROM applications AS a
            JOIN candidates AS c
                ON a.candidate_id = c.candidate_id
            JOIN job_requisitions AS jr
                ON a.requisition_id = jr.requisition_id
            WHERE a.status = 'SHORTLISTED'
            ORDER BY a.application_id DESC
        """

        cursor.execute(query)
        candidates = cursor.fetchall()

        return render_template(
            "shortlisted_candidates.html",
            candidates=candidates
        )

    except mysql.connector.Error:
        app.logger.exception(
            "Unable to load shortlisted candidates"
        )
        flash("Unable to load shortlisted candidates.", "error")
        return redirect(url_for("dashboard"))

    finally:
        if cursor:
            cursor.close()
        db.close()


@app.route("/interviews/<int:interview_id>/feedback", methods=["GET", "POST"])
@role_required(
    "SYSTEM_ADMIN",
    "PROCESS_OWNER",
    "OPERATIONS_ANALYST"
)
def submit_interview_feedback(interview_id):
    db = DatabaseConnection()

    if db is None:
        flash("Database connection failed.", "error")
        return redirect(url_for("dashboard"))

    cursor = None

    try:
        cursor = db.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT
                i.interview_id,
                i.interview_code,
                i.status,
                i.interview_type,
                i.interview_round,
                i.scheduled_start,
                a.application_code,
                c.full_name
            FROM interviews AS i
            JOIN applications AS a
                ON i.application_id = a.application_id
            JOIN candidates AS c
                ON a.candidate_id = c.candidate_id
            WHERE i.interview_id = %s
            """,
            (interview_id,)
        )
        interview = cursor.fetchone()

        if not interview:
            flash("Interview not found.", "error")
            return redirect(url_for("list_interviews"))

        if request.method == "POST":
            interviewer_id = request.form.get("interviewer_id", type=int)
            rating = request.form.get("rating", type=float)
            recommendation = request.form.get("recommendation", "").strip()
            comments = request.form.get("comments", "").strip()

            if (
                interviewer_id is None
                or rating is None
                or not 1 <= rating <= 5
                or recommendation not in ("SELECT", "REJECT", "HOLD")
            ):
                flash("Please enter valid feedback details.", "error")
            else:
                cursor.execute(
                    """
                    SELECT interviewer_id
                    FROM interview_panel
                    WHERE interview_id = %s
                      AND interviewer_id = %s
                    """,
                    (interview_id, interviewer_id)
                )

                if not cursor.fetchone():
                    flash(
                        "This interviewer is not assigned to this interview.",
                        "error"
                    )
                else:
                    cursor.execute(
                        """
                        SELECT feedback_id
                        FROM feedback
                        WHERE interview_id = %s
                          AND interviewer_id = %s
                        """,
                        (interview_id, interviewer_id)
                    )

                    if cursor.fetchone():
                        flash(
                            "Feedback has already been submitted by this interviewer.",
                            "error"
                        )
                    else:
                        feedback_code = (
                            "FDB-" + uuid.uuid4().hex[:12].upper()
                        )

                        cursor.execute(
                            """
                            INSERT INTO feedback (
                                feedback_code,
                                interview_id,
                                interviewer_id,
                                rating,
                                recommendation,
                                comments,
                                submitted_at
                            )
                            VALUES (%s, %s, %s, %s, %s, %s, %s)
                            """,
                            (
                                feedback_code,
                                interview_id,
                                interviewer_id,
                                rating,
                                recommendation,
                                comments or None,
                                datetime.now()
                            )
                        )
                        db.commit()

                        flash("Interview feedback submitted successfully.", "success")
                        return redirect(url_for("list_interviews"))

        cursor.execute(
            """
            SELECT interviewer_id, interviewer_name
            FROM interviewers
            WHERE is_active = 1
              AND interviewer_id IN (
                  SELECT interviewer_id
                  FROM interview_panel
                  WHERE interview_id = %s
              )
            ORDER BY interviewer_name
            """,
            (interview_id,)
        )
        interviewers = cursor.fetchall()

        return render_template(
            "interview_feedback.html",
            interview=interview,
            interviewers=interviewers
        )

    except mysql.connector.Error:
        db.rollback()
        app.logger.exception("Unable to process interview feedback")
        flash("Unable to process feedback.", "error")
        return redirect(url_for("list_interviews"))

    finally:
        if cursor:
            cursor.close()
        db.close()



@app.route("/interviews/<int:interview_id>/feedback/view")
@role_required(
    "SYSTEM_ADMIN",
    "PROCESS_OWNER",
    "OPERATIONS_ANALYST"
)
def view_interview_feedback(interview_id):
    db = DatabaseConnection()

    if db is None:
        flash("Database connection failed.", "error")
        return redirect(url_for("dashboard"))

    cursor = None

    try:
        cursor = db.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT
                i.interview_id,
                i.interview_code,
                i.interview_type,
                i.interview_round,
                a.application_code,
                c.full_name
            FROM interviews AS i
            JOIN applications AS a
                ON i.application_id = a.application_id
            JOIN candidates AS c
                ON a.candidate_id = c.candidate_id
            WHERE i.interview_id = %s
            """,
            (interview_id,)
        )

        interview = cursor.fetchone()

        if not interview:
            flash("Interview not found.", "error")
            return redirect(url_for("list_interviews"))

        cursor.execute(
            """
            SELECT
                f.feedback_code,
                f.rating,
                f.recommendation,
                f.comments,
                f.submitted_at,
                iv.interviewer_name
            FROM feedback AS f
            JOIN interviewers AS iv
                ON f.interviewer_id = iv.interviewer_id
            WHERE f.interview_id = %s
            ORDER BY f.submitted_at DESC
            """,
            (interview_id,)
        )

        feedback_list = cursor.fetchall()

        return render_template(
            "feedback_review.html",
            interview=interview,
            feedback_list=feedback_list
        )

    except mysql.connector.Error:
        app.logger.exception("Unable to load interview feedback")
        flash("Unable to load interview feedback.", "error")
        return redirect(url_for("list_interviews"))

    finally:
        if cursor:
            cursor.close()
        db.close()


@app.route("/offers/create", methods=["GET", "POST"])
@role_required(
    "SYSTEM_ADMIN",
    "PROCESS_OWNER",
    "OPERATIONS_ANALYST"
)
def create_offer():
    db = DatabaseConnection()

    if db is None:
        flash("Database connection failed.", "error")
        return redirect(url_for("dashboard"))

    cursor = None

    try:
        cursor = db.cursor(dictionary=True)

        if request.method == "POST":
            application_id = request.form.get(
                "application_id", type=int
            )
            offered_salary = request.form.get(
                "offered_salary", type=float
            )
            currency = request.form.get(
                "currency", "INR"
            ).strip().upper()
            expires_at_input = request.form.get("expires_at", "").strip()

            if (
                application_id is None
                or offered_salary is None
                or offered_salary <= 0
                or currency not in ("INR", "USD", "EUR", "GBP")
                or not expires_at_input
            ):
                flash("Please enter valid offer details.", "error")
            else:
                try:
                    expires_at = datetime.strptime(
                        expires_at_input, "%Y-%m-%dT%H:%M"
                    )
                except ValueError:
                    expires_at = None

                if expires_at is None or expires_at <= datetime.now():
                    flash("Offer expiry must be in the future.", "error")
                else:
                    cursor.execute(
                        """
                        SELECT application_id
                        FROM applications
                        WHERE application_id = %s
                          AND status = 'HIRED'
                        """,
                        (application_id,)
                    )

                    if not cursor.fetchone():
                        flash(
                            "An offer can only be created for a hired application.",
                            "error"
                        )
                    else:
                        cursor.execute(
                            """
                            SELECT offer_id
                            FROM offers
                            WHERE application_id = %s
                            """,
                            (application_id,)
                        )

                        if cursor.fetchone():
                            flash(
                                "An offer already exists for this application.",
                                "error"
                            )
                        else:
                            offer_code = (
                                "OFF-" + uuid.uuid4().hex[:12].upper()
                            )

                            cursor.execute(
                                """
                                INSERT INTO offers (
                                    offer_code,
                                    application_id,
                                    offered_salary,
                                    currency,
                                    status,
                                    expires_at
                                )
                                VALUES (%s, %s, %s, %s, 'DRAFT', %s)
                                """,
                                (
                                    offer_code,
                                    application_id,
                                    offered_salary,
                                    currency,
                                    expires_at
                                )
                            )

                            db.commit()
                            flash(
                                f"Offer {offer_code} created successfully.",
                                "success"
                            )
                            return redirect(url_for("list_offers"))

        cursor.execute(
            """
            SELECT
                a.application_id,
                a.application_code,
                c.full_name,
                jr.job_title
            FROM applications AS a
            JOIN candidates AS c
                ON a.candidate_id = c.candidate_id
            JOIN job_requisitions AS jr
                ON a.requisition_id = jr.requisition_id
            WHERE a.status = 'HIRED'
              AND NOT EXISTS (
                  SELECT 1
                  FROM offers AS o
                  WHERE o.application_id = a.application_id
              )
            ORDER BY a.application_id DESC
            """
        )

        hired_candidates = cursor.fetchall()

        return render_template(
            "create_offer.html",
            candidates=hired_candidates
        )

    except mysql.connector.Error:
        db.rollback()
        app.logger.exception("Unable to create offer")
        flash("Unable to create the offer.", "error")
        return redirect(url_for("dashboard"))

    finally:
        if cursor:
            cursor.close()
        db.close()


@app.route("/offers")
@role_required(
    "SYSTEM_ADMIN",
    "BUSINESS_REQUESTER",
    "PROCESS_OWNER",
    "APPROVER",
    "OPERATIONS_ANALYST"
)
def list_offers():
    db = DatabaseConnection()

    if db is None:
        flash("Database connection failed.", "error")
        return redirect(url_for("dashboard"))

    cursor = None

    try:
        cursor = db.cursor(dictionary=True)

        query = """
            SELECT
                o.offer_id,
                o.offer_code,
                o.offered_salary,
                o.currency,
                o.status,
                o.issued_at,
                o.expires_at,
                o.responded_at,
                a.application_code,
                c.full_name,
                jr.job_title
            FROM offers AS o
            JOIN applications AS a
                ON o.application_id = a.application_id
            JOIN candidates AS c
                ON a.candidate_id = c.candidate_id
            JOIN job_requisitions AS jr
                ON a.requisition_id = jr.requisition_id
            ORDER BY o.offer_id DESC
        """

        cursor.execute(query)
        offers = cursor.fetchall()

        return render_template("offers.html", offers=offers)

    except mysql.connector.Error:
        app.logger.exception("Unable to load offers")
        flash("Unable to load offers.", "error")
        return redirect(url_for("dashboard"))

    finally:
        if cursor:
            cursor.close()
        db.close()


@app.route("/offers/approvals")
@role_required("SYSTEM_ADMIN", "APPROVER")
def offer_approvals():
    db = DatabaseConnection()

    if db is None:
        flash("Database connection failed.", "error")
        return redirect(url_for("dashboard"))

    cursor = None

    try:
        cursor = db.cursor(dictionary=True)

        query = """
            SELECT
                oa.offer_approval_id,
                oa.offer_id,
                oa.approver_name,
                oa.decision,
                oa.comments,
                o.offer_code,
                o.offered_salary,
                o.currency,
                o.expires_at,
                a.application_code,
                c.full_name,
                jr.job_title
            FROM offer_approvals AS oa
            JOIN offers AS o
                ON oa.offer_id = o.offer_id
            JOIN applications AS a
                ON o.application_id = a.application_id
            JOIN candidates AS c
                ON a.candidate_id = c.candidate_id
            JOIN job_requisitions AS jr
                ON a.requisition_id = jr.requisition_id
            WHERE oa.decision = 'PENDING'
              AND o.status = 'PENDING_APPROVAL'
            ORDER BY o.offer_id DESC
        """

        cursor.execute(query)
        approvals = cursor.fetchall()

        return render_template(
            "offer_approvals.html",
            approvals=approvals
        )

    except mysql.connector.Error:
        app.logger.exception("Unable to load offer approvals")
        flash("Unable to load offer approvals.", "error")
        return redirect(url_for("dashboard"))

    finally:
        if cursor:
            cursor.close()
        db.close()


@app.route("/offers/<int:offer_id>")
@role_required("SYSTEM_ADMIN", "APPROVER", "PROCESS_OWNER",
              "OPERATIONS_ANALYST")
def offer_details(offer_id):
    db = DatabaseConnection()

    if db is None:
        flash("Database connection failed.", "error")
        return redirect(url_for("offers"))

    cursor = None
    try:
        cursor = db.cursor(dictionary=True)

        cursor.execute("""
            SELECT
                o.offer_id, o.offer_code, o.offered_salary,
                o.currency, o.status, o.issued_at, o.expires_at,
                o.responded_at,
                a.application_code,
                c.full_name, c.email,
                jr.job_title
            FROM offers o
            JOIN applications a ON o.application_id = a.application_id
            JOIN candidates c ON a.candidate_id = c.candidate_id
            JOIN job_requisitions jr
                ON a.requisition_id = jr.requisition_id
            WHERE o.offer_id = %s
        """, (offer_id,))

        offer = cursor.fetchone()

        if not offer:
            flash("Offer not found.", "error")
            return redirect(url_for("offers"))

        cursor.execute("""
            SELECT approver_name, decision, comments, decided_at
            FROM offer_approvals
            WHERE offer_id = %s
            ORDER BY offer_approval_id DESC
        """, (offer_id,))

        approvals = cursor.fetchall()

        return render_template(
            "offer_details.html",
            offer=offer,
            approvals=approvals
        )

    except mysql.connector.Error:
        app.logger.exception("Unable to load offer details")
        flash("Unable to load offer details.", "error")
        return redirect(url_for("offers"))

    finally:
        if cursor:
            cursor.close()
        db.close()



@app.route("/offers/<int:offer_id>/issue", methods=["POST"])
@role_required("SYSTEM_ADMIN", "PROCESS_OWNER", "OPERATIONS_ANALYST")
def issue_offer(offer_id):
    db = DatabaseConnection()

    if db is None:
        flash("Database connection failed.", "error")
        return redirect(url_for("list_offers"))

    cursor = None

    try:
        cursor = db.cursor()
        cursor.execute("""
            UPDATE offers
            SET status = 'ISSUED',
                issued_at = CURRENT_TIMESTAMP
            WHERE offer_id = %s
              AND status = 'APPROVED'
        """, (offer_id,))

        if cursor.rowcount == 0:
            db.rollback()
            flash(
                "Offer cannot be issued. It may not be approved "
                "or may already have been issued.",
                "error"
            )
            return redirect(
                url_for("offer_details", offer_id=offer_id)
            )

        db.commit()
        flash("Offer issued successfully.", "success")

    except mysql.connector.Error:
        db.rollback()
        app.logger.exception("Unable to issue offer")
        flash("Unable to issue offer. Please try again.", "error")

    finally:
        if cursor:
            cursor.close()
        db.close()

    return redirect(url_for("offer_details", offer_id=offer_id))



@app.route("/offers/<int:offer_id>/respond", methods=["POST"])
@role_required("SYSTEM_ADMIN", "PROCESS_OWNER", "OPERATIONS_ANALYST")
def respond_to_offer(offer_id):
    decision = request.form.get("decision", "").upper()

    if decision not in ("ACCEPTED", "REJECTED"):
        flash("Invalid offer response.", "error")
        return redirect(url_for("offer_details", offer_id=offer_id))

    db = DatabaseConnection()
    if db is None:
        flash("Database connection failed.", "error")
        return redirect(url_for("offer_details", offer_id=offer_id))

    cursor = None

    try:
        cursor = db.cursor()
        cursor.execute("""
            UPDATE offers
            SET status = %s,
                responded_at = CURRENT_TIMESTAMP
            WHERE offer_id = %s
              AND status = 'ISSUED'
        """, (decision, offer_id))

        if cursor.rowcount == 0:
            db.rollback()
            flash(
                "This offer cannot be responded to. "
                "It may not be issued or may already have a response.",
                "error"
            )
        else:
            db.commit()
            flash(
                f"Offer marked as {decision}.",
                "success"
            )

    except mysql.connector.Error:
        db.rollback()
        app.logger.exception("Unable to record offer response")
        flash("Unable to record the offer response.", "error")

    finally:
        if cursor:
            cursor.close()
        db.close()

    return redirect(url_for("offer_details", offer_id=offer_id))



@app.route("/reports")
@role_required(
    "SYSTEM_ADMIN",
    "PROCESS_OWNER",
    "OPERATIONS_ANALYST",
    "APPROVER"
)
def recruitment_reports():
    db = DatabaseConnection()

    if db is None:
        flash("Database connection failed.", "error")
        return redirect(url_for("dashboard"))

    cursor = None

    try:
        cursor = db.cursor(dictionary=True)

        cursor.execute("""
            SELECT status, COUNT(*) AS total
            FROM applications
            GROUP BY status
            ORDER BY status
        """)
        application_stats = cursor.fetchall()

        cursor.execute("""
            SELECT status, COUNT(*) AS total
            FROM offers
            GROUP BY status
            ORDER BY status
        """)
        offer_stats = cursor.fetchall()

        cursor.execute("""
            SELECT COUNT(*) AS total
            FROM candidates
        """)
        candidate_count = cursor.fetchone()["total"]

        cursor.execute("""
            SELECT COUNT(*) AS total
            FROM applications
        """)
        application_count = cursor.fetchone()["total"]

        cursor.execute("""
            SELECT COUNT(*) AS total
            FROM offers
        """)
        offer_count = cursor.fetchone()["total"]

        return render_template(
            "reports.html",
            application_stats=application_stats,
            offer_stats=offer_stats,
            candidate_count=candidate_count,
            application_count=application_count,
            offer_count=offer_count
        )

    except mysql.connector.Error:
        app.logger.exception("Unable to load recruitment reports")
        flash("Unable to load recruitment reports.", "error")
        return redirect(url_for("dashboard"))

    finally:
        if cursor:
            cursor.close()
        db.close()


if __name__ == "__main__":
    app.run(debug=True)
