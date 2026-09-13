import sqlite3
from werkzeug.security import generate_password_hash

DATABASE = "database.db"


def create_database():
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
    admin_email = "admin@library.com"
    admin_password = "admin123"

    cursor.execute(
        "SELECT id FROM users WHERE email = ?",
        (admin_email,)
    )

    admin_exists = cursor.fetchone()

    if not admin_exists:
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
    print("Default admin:")
    print("Email: admin@library.com")
    print("Password: admin123")


if __name__ == "__main__":
    create_database()