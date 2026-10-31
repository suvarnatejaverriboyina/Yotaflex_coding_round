# Recruitment Management System (RMS)

A web-based Recruitment Management System built using **Python, Flask, and MySQL** to manage the recruitment lifecycle, from job requisitions and candidate applications to resume screening, interviews, feedback, and offer management.

## Features

- **User Authentication:** Login and role-based access control.
- **Job Requisitions:** Create, view, and manage job requisitions and approvals.
- **Candidate Management:** Maintain candidate records and search candidates.
- **Application Tracking:** Track application statuses and view status history.
- **Resume Screening:** Evaluate candidates using skill-based screening rules and scores.
- **Interview Management:** Schedule interviews, assign interviewers, and record feedback.
- **Offer Management:** Create offers, manage approvals, issue offers, and record candidate responses.
- **Recruitment Reports:** View application and offer statistics through interactive charts.
- **Dashboard:** Monitor recruitment activity from a central dashboard.

## Technologies Used

- **Backend:** Python, Flask
- **Database:** MySQL
- **Database Connectivity:** MySQL Connector/Python
- **Frontend:** HTML, CSS, JavaScript, Jinja2
- **Data Visualization:** Chart.js
- **Configuration:** Environment variables using `.env`

## Project Structure

```text
RMS/
├── database/
│   ├── __init__.py
│   ├── connectionDB.py
│   └── tablesDB.py
├── generator/
│   ├── data_generator.py
│   ├── validate_data.py
│   └── resume_screening.py
├── data/
├── templates/
├── static/
│   └── css/
│       └── style.css
├── app.py
├── requirements.txt
├── .env
├── .gitignore
└── README.md
```

## Prerequisites

Install the following before running the application:

- Python 3.12 or another compatible Python version
- MySQL Server
- MySQL Workbench (optional, for managing the database)
- Visual Studio Code

## Installation and Setup

### 1. Clone or Download the Project

If the project is on GitHub, clone it using:

```bash
git clone YOUR_GITHUB_REPOSITORY_URL
cd RMS
```

Alternatively, open your existing project folder in VS Code.

### 2. Create and Activate a Virtual Environment

Open the VS Code terminal and navigate to the project directory:

```powershell
cd D:\RMS
```

Create the virtual environment if you do not already have one:

```powershell
python -m venv rms_env
```

Activate it in PowerShell:

```powershell
.\rms_env\Scripts\Activate.ps1
```

If PowerShell blocks activation, you can use Command Prompt:

```cmd
rms_env\Scripts\activate.bat
```

### 3. Install Dependencies

Install the required packages:

```bash
python -m pip install -r requirements.txt
```

If `requirements.txt` is missing or outdated, install the dependencies used by your project and update the file.

### 4. Configure the MySQL Database

1. Start your MySQL Server.
2. Open MySQL Workbench or your preferred MySQL client.
3. Create the database using the database name configured in `database/connectionDB.py`.
4. Run the required table-creation SQL or the project's database initialization code in `database/tablesDB.py`, if your application does not create the tables automatically.
5. Make sure the MySQL account has permission to access the database.

Use the database name, host, port, and credentials expected by your connection code.

### 5. Configure Environment Variables

Create a `.env` file in the root directory, alongside `app.py`, if your application uses environment variables.

Example configuration:

```env
DB_HOST=localhost
DB_PORT=3306
DB_USER=your_mysql_username
DB_PASSWORD=your_mysql_password
DB_NAME=your_database_name
SECRET_KEY=replace_with_a_secure_random_secret
```

**Important:** These variable names are examples. Use the exact names expected by your existing `connectionDB.py` and `app.py` code.

Never commit your real database password, secret key, or other credentials to GitHub.

### 6. Run the Application

With the virtual environment activated, execute:

```bash
python app.py
```

Open the local URL displayed in the terminal, usually:

```text
http://127.0.0.1:5000/
```

If your Flask application specifies a different port, use the URL and port shown in the terminal.

### 7. Log In

Open the application in your browser and sign in using a valid account already configured in the database.

Use the appropriate role to access the available recruitment modules. If no initial account exists, create one using your project's supported user-creation or registration process.

## Application Workflow

The main recruitment workflow is:

**Job Requisition → Application → Resume Screening → Shortlisting → Interview → Feedback → Offer → Candidate Response**

The system also provides recruitment analytics and application-status history to help monitor recruitment activity.

## Security Notes

- Keep `.env` and credentials out of version control.
- Use secure password hashing and role-based authorization.
- Use a strong, unique Flask secret key.
- Do not use development settings such as Flask debug mode in production.
- Validate user input and database operations before deploying the application.

## Future Enhancements

- Candidate self-service portal.
- Secure candidate offer acceptance and rejection links.
- Email notifications for interviews and offers.
- Advanced recruitment analytics and exportable reports.
- Automated deployment and production configuration.

## Author

Developed as a Python Flask and MySQL project to demonstrate recruitment workflow management, database integration, role-based access control, and reporting.
