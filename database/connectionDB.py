
import os
import mysql.connector as SQLC
from dotenv import load_dotenv

load_dotenv()


def DatabaseConnection():
    try:
        db_config = SQLC.connect(
            host=os.getenv("DB_HOST", "localhost"),
            user=os.getenv("DB_USER", "root"),
            password=os.getenv("DB_PASSWORD"),
            database=os.getenv("DB_NAME", "rms_db")
        )

        print("Database connected successfully")
        return db_config

    except SQLC.Error as e:
        print("Database connection failed:", e)
        return None


# if __name__ == "__main__":
#     connection = DatabaseConnection()

#     if connection:
#         print("Connection test successful!")
#         connection.close()