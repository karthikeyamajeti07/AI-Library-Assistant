import sqlite3
import os
from werkzeug.security import generate_password_hash

try:
    import psycopg2
except Exception:
    psycopg2 = None

DATABASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "database.db")
DATABASE_URL = os.getenv("DATABASE_URL")


def create_database():
    if DATABASE_URL:
        if psycopg2 is None:
            raise RuntimeError("psycopg2 is required when DATABASE_URL is set.")
        conn = psycopg2.connect(DATABASE_URL, sslmode="require")
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'student',
                student_id TEXT UNIQUE,
                department TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        admin_email = os.getenv("LIBRARY_ADMIN_EMAIL", "admin@library.com").strip().lower()
        admin_password = os.getenv("LIBRARY_ADMIN_PASSWORD")

        cursor.execute(
            "SELECT id FROM users WHERE email = %s",
            (admin_email,)
        )

        admin_exists = cursor.fetchone()

        if not admin_exists and admin_password:
            hashed_password = generate_password_hash(admin_password)

            cursor.execute("""
                INSERT INTO users
                (name, email, password, role, student_id, department)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (
                "Library Admin",
                admin_email,
                hashed_password,
                "admin",
                None,
                "Library"
            ))

        conn.commit()
        conn.close()

        print("Database created successfully!")
        if not admin_exists and not admin_password:
            print("No admin account was created. Set LIBRARY_ADMIN_PASSWORD and run again.")
        return

    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'student',
            student_id TEXT UNIQUE,
            department TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Create default admin account
    admin_email = os.getenv("LIBRARY_ADMIN_EMAIL", "admin@library.com").strip().lower()
    admin_password = os.getenv("LIBRARY_ADMIN_PASSWORD")

    cursor.execute(
        "SELECT id FROM users WHERE email = ?",
        (admin_email,)
    )

    admin_exists = cursor.fetchone()

    if not admin_exists and admin_password:
        hashed_password = generate_password_hash(admin_password)

        cursor.execute("""
            INSERT INTO users
            (name, email, password, role, student_id, department)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            "Library Admin",
            admin_email,
            hashed_password,
            "admin",
            None,
            "Library"
        ))

    conn.commit()
    conn.close()

    print("Database created successfully!")
    if not admin_exists and not admin_password:
        print("No admin account was created. Set LIBRARY_ADMIN_PASSWORD and run again.")


if __name__ == "__main__":
    create_database()