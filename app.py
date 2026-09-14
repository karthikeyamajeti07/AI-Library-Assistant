from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from dotenv import load_dotenv
from google import genai
import os
import re
import sqlite3
import json
import secrets
from werkzeug.security import check_password_hash, generate_password_hash


# ==========================================
# LOAD ENVIRONMENT VARIABLES
# ==========================================

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY") or secrets.token_hex(32)

DATABASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "database.db")


def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_database():
    """Create the application tables and seed the 50 starter books once."""
    conn = get_db_connection()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'student',
            student_id TEXT UNIQUE,
            department TEXT
        )
    """)
    # Add student management fields to existing databases
    try:
        conn.execute("ALTER TABLE users ADD COLUMN registration_date TEXT")
    except sqlite3.OperationalError:
        pass

    try:
        conn.execute("ALTER TABLE users ADD COLUMN account_status TEXT DEFAULT 'Active'")
    except sqlite3.OperationalError:
        pass

    conn.execute("""
        UPDATE users
        SET registration_date = datetime('now')
        WHERE registration_date IS NULL
    """)

    conn.execute("""
        UPDATE users
        SET account_status = 'Active'
        WHERE account_status IS NULL
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS books (
            book_id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            author TEXT NOT NULL,
            main_category TEXT,
            sub_category TEXT,
            isbn TEXT,
            publisher TEXT,
            year INTEGER,
            language TEXT,
            description TEXT,
            keywords TEXT,
            edition TEXT,
            total_copies INTEGER NOT NULL DEFAULT 1,
            available_copies INTEGER NOT NULL DEFAULT 0,
            shelf_location TEXT,
            cover_image TEXT,
            times_borrowed INTEGER NOT NULL DEFAULT 0,
            rating REAL NOT NULL DEFAULT 0,
            difficulty_level TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS borrowings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            book_id TEXT NOT NULL,
            borrowed_at TEXT NOT NULL,
            due_date TEXT NOT NULL,
            returned_at TEXT,
            status TEXT NOT NULL DEFAULT 'borrowed',
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (book_id) REFERENCES books(book_id)
        )
    """)


    count = conn.execute("SELECT COUNT(*) AS count FROM books").fetchone()["count"]
    if count == 0:
        conn.executemany("""
            INSERT INTO books (
                book_id, title, author, main_category, sub_category, isbn,
                publisher, year, language, description, keywords, edition,
                total_copies, available_copies, shelf_location, cover_image,
                times_borrowed, rating, difficulty_level
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            (
                b["book_id"], b["title"], b["author"], b["main_category"],
                b["sub_category"], b["isbn"], b["publisher"], b["year"],
                b["language"], b["description"], json.dumps(b["keywords"]),
                b["edition"], b["total_copies"], b["available_copies"],
                b["shelf_location"], b["cover_image"], b["times_borrowed"],
                b["rating"], b["difficulty_level"]
            ) for b in INITIAL_BOOKS
        ])

    conn.commit()
    conn.close()


def row_to_book(row):
    book = dict(row)
    try:
        book["keywords"] = json.loads(book.get("keywords") or "[]")
    except (TypeError, json.JSONDecodeError):
        book["keywords"] = []
    return book


def get_all_books():
    conn = get_db_connection()
    rows = conn.execute("SELECT * FROM books ORDER BY book_id").fetchall()
    conn.close()
    return [row_to_book(row) for row in rows]


def get_book(book_id):
    conn = get_db_connection()
    row = conn.execute(
        "SELECT * FROM books WHERE UPPER(book_id) = UPPER(?)", (book_id,)
    ).fetchone()
    conn.close()
    return row_to_book(row) if row else None


def current_user():
    return {
        "id": session.get("user_id"),
        "name": session.get("name"),
        "role": session.get("role")
    }


# ==========================================
# GEMINI AI SETUP
# ==========================================

api_key = os.getenv("GEMINI_API_KEY")

if api_key and api_key != "YOUR_API_KEY_HERE":
    client = genai.Client(api_key=api_key)
else:
    client = None


# ==========================================
# LIBRARY BOOK DATABASE
# ==========================================

INITIAL_BOOKS = [{'book_id': 'B001',
  'title': 'Clean Code',
  'author': 'Robert C. Martin',
  'main_category': 'Programming',
  'sub_category': 'Software Development',
  'isbn': '9780132350884',
  'publisher': 'Prentice Hall',
  'year': 2008,
  'language': 'English',
  'description': 'A guide to writing clean, readable and maintainable software.',
  'keywords': ['clean code', 'programming', 'software', 'coding'],
  'edition': '1st Edition',
  'total_copies': 5,
  'available_copies': 3,
  'shelf_location': 'A-12',
  'cover_image': '',
  'times_borrowed': 42,
  'rating': 4.8,
  'difficulty_level': 'Intermediate'},
 {'book_id': 'B002',
  'title': 'Introduction to Algorithms',
  'author': 'Thomas H. Cormen',
  'main_category': 'Computer Science',
  'sub_category': 'Data Structures and Algorithms',
  'isbn': '9780262046305',
  'publisher': 'MIT Press',
  'year': 2022,
  'language': 'English',
  'description': 'A comprehensive introduction to algorithms and data structures.',
  'keywords': ['algorithms', 'data structures', 'sorting', 'searching'],
  'edition': '4th Edition',
  'total_copies': 4,
  'available_copies': 2,
  'shelf_location': 'B-05',
  'cover_image': '',
  'times_borrowed': 58,
  'rating': 4.9,
  'difficulty_level': 'Advanced'},
 {'book_id': 'B003',
  'title': 'Artificial Intelligence: A Modern Approach',
  'author': 'Stuart Russell and Peter Norvig',
  'main_category': 'Artificial Intelligence',
  'sub_category': 'AI Fundamentals',
  'isbn': '9780134610993',
  'publisher': 'Pearson',
  'year': 2021,
  'language': 'English',
  'description': 'A comprehensive textbook covering artificial intelligence concepts and techniques.',
  'keywords': ['AI', 'artificial intelligence', 'agents', 'machine learning'],
  'edition': '4th Edition',
  'total_copies': 3,
  'available_copies': 0,
  'shelf_location': 'C-10',
  'cover_image': '',
  'times_borrowed': 64,
  'rating': 4.9,
  'difficulty_level': 'Advanced'},
 {'book_id': 'B004',
  'title': 'Java: The Complete Reference',
  'author': 'Herbert Schildt',
  'main_category': 'Programming',
  'sub_category': 'Java',
  'isbn': '9781260440232',
  'publisher': 'McGraw Hill',
  'year': 2021,
  'language': 'English',
  'description': 'A complete guide to Java programming from basic to advanced concepts.',
  'keywords': ['Java', 'OOP', 'programming', 'JVM'],
  'edition': '12th Edition',
  'total_copies': 6,
  'available_copies': 4,
  'shelf_location': 'A-15',
  'cover_image': '',
  'times_borrowed': 51,
  'rating': 4.7,
  'difficulty_level': 'Intermediate'},
 {'book_id': 'B005',
  'title': 'Python Crash Course',
  'author': 'Eric Matthes',
  'main_category': 'Programming',
  'sub_category': 'Python',
  'isbn': '9781718502703',
  'publisher': 'No Starch Press',
  'year': 2023,
  'language': 'English',
  'description': 'A beginner-friendly introduction to Python programming.',
  'keywords': ['Python', 'programming', 'beginner', 'automation'],
  'edition': '3rd Edition',
  'total_copies': 5,
  'available_copies': 5,
  'shelf_location': 'A-18',
  'cover_image': '',
  'times_borrowed': 72,
  'rating': 4.8,
  'difficulty_level': 'Beginner'},
 {'book_id': 'B006',
  'title': 'Database System Concepts',
  'author': 'Abraham Silberschatz',
  'main_category': 'Database',
  'sub_category': 'DBMS',
  'isbn': '9780078022159',
  'publisher': 'McGraw Hill',
  'year': 2019,
  'language': 'English',
  'description': 'A textbook covering database systems and database management concepts.',
  'keywords': ['database', 'DBMS', 'SQL', 'transactions'],
  'edition': '7th Edition',
  'total_copies': 4,
  'available_copies': 2,
  'shelf_location': 'D-04',
  'cover_image': '',
  'times_borrowed': 45,
  'rating': 4.6,
  'difficulty_level': 'Intermediate'},
 {'book_id': 'B007',
  'title': 'Computer Networks',
  'author': 'Andrew S. Tanenbaum',
  'main_category': 'Networking',
  'sub_category': 'Computer Networks',
  'isbn': '9780132126953',
  'publisher': 'Pearson',
  'year': 2010,
  'language': 'English',
  'description': 'An introduction to computer networking, protocols and network architecture.',
  'keywords': ['networking', 'TCP/IP', 'protocols', 'internet'],
  'edition': '5th Edition',
  'total_copies': 3,
  'available_copies': 1,
  'shelf_location': 'E-08',
  'cover_image': '',
  'times_borrowed': 39,
  'rating': 4.5,
  'difficulty_level': 'Intermediate'},
 {'book_id': 'B008',
  'title': 'Operating System Concepts',
  'author': 'Abraham Silberschatz',
  'main_category': 'Operating Systems',
  'sub_category': 'OS Fundamentals',
  'isbn': '9781119800361',
  'publisher': 'Wiley',
  'year': 2021,
  'language': 'English',
  'description': 'A textbook covering operating system concepts and principles.',
  'keywords': ['operating systems', 'processes', 'memory', 'files'],
  'edition': '10th Edition',
  'total_copies': 5,
  'available_copies': 3,
  'shelf_location': 'E-12',
  'cover_image': '',
  'times_borrowed': 47,
  'rating': 4.7,
  'difficulty_level': 'Intermediate'},
 {'book_id': 'B009',
  'title': 'Head First Java',
  'author': 'Kathy Sierra and Bert Bates',
  'main_category': 'Programming',
  'sub_category': 'Java',
  'isbn': '9780596009205',
  'publisher': "O'Reilly Media",
  'year': 2005,
  'language': 'English',
  'description': 'A visual and beginner-friendly introduction to Java programming.',
  'keywords': ['Java', 'OOP', 'beginner', 'programming'],
  'edition': '2nd Edition',
  'total_copies': 4,
  'available_copies': 2,
  'shelf_location': 'A-20',
  'cover_image': '',
  'times_borrowed': 55,
  'rating': 4.6,
  'difficulty_level': 'Beginner'},
 {'book_id': 'B010',
  'title': 'Effective Java',
  'author': 'Joshua Bloch',
  'main_category': 'Programming',
  'sub_category': 'Java',
  'isbn': '9780134685991',
  'publisher': 'Addison-Wesley',
  'year': 2018,
  'language': 'English',
  'description': 'Best practices and design patterns for professional Java development.',
  'keywords': ['Java', 'best practices', 'OOP', 'design'],
  'edition': '3rd Edition',
  'total_copies': 3,
  'available_copies': 1,
  'shelf_location': 'A-21',
  'cover_image': '',
  'times_borrowed': 33,
  'rating': 4.8,
  'difficulty_level': 'Advanced'},
 {'book_id': 'B011',
  'title': 'The C Programming Language',
  'author': 'Brian W. Kernighan and Dennis M. Ritchie',
  'main_category': 'Programming',
  'sub_category': 'C Programming',
  'isbn': '9780131103627',
  'publisher': 'Prentice Hall',
  'year': 1988,
  'language': 'English',
  'description': 'A classic guide to the C programming language.',
  'keywords': ['C', 'programming', 'pointers', 'functions'],
  'edition': '2nd Edition',
  'total_copies': 4,
  'available_copies': 2,
  'shelf_location': 'A-05',
  'cover_image': '',
  'times_borrowed': 48,
  'rating': 4.8,
  'difficulty_level': 'Intermediate'},
 {'book_id': 'B012',
  'title': 'C++ Primer',
  'author': 'Stanley B. Lippman',
  'main_category': 'Programming',
  'sub_category': 'C++',
  'isbn': '9780321714114',
  'publisher': 'Addison-Wesley',
  'year': 2012,
  'language': 'English',
  'description': 'A comprehensive guide to modern C++ programming.',
  'keywords': ['C++', 'OOP', 'STL', 'programming'],
  'edition': '5th Edition',
  'total_copies': 4,
  'available_copies': 3,
  'shelf_location': 'A-07',
  'cover_image': '',
  'times_borrowed': 36,
  'rating': 4.7,
  'difficulty_level': 'Intermediate'},
 {'book_id': 'B013',
  'title': 'Eloquent JavaScript',
  'author': 'Marijn Haverbeke',
  'main_category': 'Programming',
  'sub_category': 'JavaScript',
  'isbn': '9781593279509',
  'publisher': 'No Starch Press',
  'year': 2018,
  'language': 'English',
  'description': 'A modern introduction to JavaScript programming and web development.',
  'keywords': ['JavaScript', 'web', 'programming', 'frontend'],
  'edition': '3rd Edition',
  'total_copies': 4,
  'available_copies': 3,
  'shelf_location': 'F-02',
  'cover_image': '',
  'times_borrowed': 44,
  'rating': 4.6,
  'difficulty_level': 'Intermediate'},
 {'book_id': 'B014',
  'title': 'HTML and CSS: Design and Build Websites',
  'author': 'Jon Duckett',
  'main_category': 'Web Development',
  'sub_category': 'HTML and CSS',
  'isbn': '9781118008188',
  'publisher': 'Wiley',
  'year': 2011,
  'language': 'English',
  'description': 'A visual introduction to HTML and CSS for building websites.',
  'keywords': ['HTML', 'CSS', 'web design', 'frontend'],
  'edition': '1st Edition',
  'total_copies': 5,
  'available_copies': 4,
  'shelf_location': 'F-05',
  'cover_image': '',
  'times_borrowed': 61,
  'rating': 4.7,
  'difficulty_level': 'Beginner'},
 {'book_id': 'B015',
  'title': 'Learning Web Design',
  'author': 'Jennifer Niederst Robbins',
  'main_category': 'Web Development',
  'sub_category': 'Web Design',
  'isbn': '9781491960202',
  'publisher': "O'Reilly Media",
  'year': 2018,
  'language': 'English',
  'description': 'A beginner-friendly guide to HTML, CSS, JavaScript and web design.',
  'keywords': ['HTML', 'CSS', 'JavaScript', 'web'],
  'edition': '5th Edition',
  'total_copies': 4,
  'available_copies': 2,
  'shelf_location': 'F-07',
  'cover_image': '',
  'times_borrowed': 41,
  'rating': 4.5,
  'difficulty_level': 'Beginner'},
 {'book_id': 'B016',
  'title': 'Design Patterns',
  'author': 'Erich Gamma and others',
  'main_category': 'Software Engineering',
  'sub_category': 'Design Patterns',
  'isbn': '9780201633610',
  'publisher': 'Addison-Wesley',
  'year': 1994,
  'language': 'English',
  'description': 'A classic reference for reusable object-oriented software design patterns.',
  'keywords': ['design patterns', 'OOP', 'software design'],
  'edition': '1st Edition',
  'total_copies': 3,
  'available_copies': 1,
  'shelf_location': 'G-01',
  'cover_image': '',
  'times_borrowed': 29,
  'rating': 4.8,
  'difficulty_level': 'Advanced'},
 {'book_id': 'B017',
  'title': 'Software Engineering',
  'author': 'Ian Sommerville',
  'main_category': 'Software Engineering',
  'sub_category': 'Software Development',
  'isbn': '9780133943030',
  'publisher': 'Pearson',
  'year': 2015,
  'language': 'English',
  'description': 'A comprehensive textbook on software engineering principles and practices.',
  'keywords': ['software engineering', 'SDLC', 'testing', 'requirements'],
  'edition': '10th Edition',
  'total_copies': 5,
  'available_copies': 3,
  'shelf_location': 'G-04',
  'cover_image': '',
  'times_borrowed': 52,
  'rating': 4.6,
  'difficulty_level': 'Intermediate'},
 {'book_id': 'B018',
  'title': 'Computer Organization and Design',
  'author': 'David A. Patterson and John L. Hennessy',
  'main_category': 'Computer Engineering',
  'sub_category': 'Computer Organization',
  'isbn': '9780124077263',
  'publisher': 'Morgan Kaufmann',
  'year': 2013,
  'language': 'English',
  'description': 'Introduction to computer organization, processors and hardware design.',
  'keywords': ['computer organization', 'CPU', 'hardware', 'architecture'],
  'edition': '5th Edition',
  'total_copies': 4,
  'available_copies': 2,
  'shelf_location': 'H-02',
  'cover_image': '',
  'times_borrowed': 37,
  'rating': 4.7,
  'difficulty_level': 'Advanced'},
 {'book_id': 'B019',
  'title': 'Computer Architecture: A Quantitative Approach',
  'author': 'John L. Hennessy and David A. Patterson',
  'main_category': 'Computer Engineering',
  'sub_category': 'Computer Architecture',
  'isbn': '9780128119051',
  'publisher': 'Morgan Kaufmann',
  'year': 2017,
  'language': 'English',
  'description': 'A detailed study of modern computer architecture and performance.',
  'keywords': ['architecture', 'CPU', 'performance', 'hardware'],
  'edition': '6th Edition',
  'total_copies': 3,
  'available_copies': 1,
  'shelf_location': 'H-04',
  'cover_image': '',
  'times_borrowed': 31,
  'rating': 4.7,
  'difficulty_level': 'Advanced'},
 {'book_id': 'B020',
  'title': 'Modern Operating Systems',
  'author': 'Andrew S. Tanenbaum',
  'main_category': 'Operating Systems',
  'sub_category': 'OS',
  'isbn': '9780133591620',
  'publisher': 'Pearson',
  'year': 2014,
  'language': 'English',
  'description': 'Detailed coverage of modern operating system concepts and implementation.',
  'keywords': ['OS', 'processes', 'memory', 'file systems'],
  'edition': '4th Edition',
  'total_copies': 4,
  'available_copies': 2,
  'shelf_location': 'E-15',
  'cover_image': '',
  'times_borrowed': 34,
  'rating': 4.6,
  'difficulty_level': 'Advanced'},
 {'book_id': 'B021',
  'title': 'Computer Networking: A Top-Down Approach',
  'author': 'James Kurose and Keith Ross',
  'main_category': 'Networking',
  'sub_category': 'Computer Networks',
  'isbn': '9780136681557',
  'publisher': 'Pearson',
  'year': 2021,
  'language': 'English',
  'description': 'A top-down approach to understanding computer networking and protocols.',
  'keywords': ['networking', 'TCP', 'UDP', 'HTTP'],
  'edition': '8th Edition',
  'total_copies': 5,
  'available_copies': 4,
  'shelf_location': 'E-18',
  'cover_image': '',
  'times_borrowed': 49,
  'rating': 4.8,
  'difficulty_level': 'Intermediate'},
 {'book_id': 'B022',
  'title': 'Data Communications and Networking',
  'author': 'Behrouz A. Forouzan',
  'main_category': 'Networking',
  'sub_category': 'Data Communication',
  'isbn': '9780073376226',
  'publisher': 'McGraw Hill',
  'year': 2012,
  'language': 'English',
  'description': 'Fundamentals of data communication and computer networking.',
  'keywords': ['networking', 'communication', 'protocols', 'OSI'],
  'edition': '5th Edition',
  'total_copies': 4,
  'available_copies': 2,
  'shelf_location': 'E-20',
  'cover_image': '',
  'times_borrowed': 35,
  'rating': 4.5,
  'difficulty_level': 'Intermediate'},
 {'book_id': 'B023',
  'title': 'Fundamentals of Database Systems',
  'author': 'Ramez Elmasri and Shamkant Navathe',
  'main_category': 'Database',
  'sub_category': 'DBMS',
  'isbn': '9780133970777',
  'publisher': 'Pearson',
  'year': 2016,
  'language': 'English',
  'description': 'Comprehensive coverage of database design, SQL and database management.',
  'keywords': ['DBMS', 'SQL', 'database design', 'ER model'],
  'edition': '7th Edition',
  'total_copies': 4,
  'available_copies': 3,
  'shelf_location': 'D-08',
  'cover_image': '',
  'times_borrowed': 43,
  'rating': 4.6,
  'difficulty_level': 'Intermediate'},
 {'book_id': 'B024',
  'title': 'Learning SQL',
  'author': 'Alan Beaulieu',
  'main_category': 'Database',
  'sub_category': 'SQL',
  'isbn': '9781492057611',
  'publisher': "O'Reilly Media",
  'year': 2020,
  'language': 'English',
  'description': 'A practical introduction to SQL and relational databases.',
  'keywords': ['SQL', 'database', 'queries', 'relational'],
  'edition': '3rd Edition',
  'total_copies': 4,
  'available_copies': 4,
  'shelf_location': 'D-10',
  'cover_image': '',
  'times_borrowed': 56,
  'rating': 4.7,
  'difficulty_level': 'Beginner'},
 {'book_id': 'B025',
  'title': 'Artificial Intelligence for Dummies',
  'author': 'John Paul Mueller and Luca Massaron',
  'main_category': 'Artificial Intelligence',
  'sub_category': 'AI Basics',
  'isbn': '9781119796763',
  'publisher': 'Wiley',
  'year': 2021,
  'language': 'English',
  'description': 'An easy introduction to artificial intelligence concepts.',
  'keywords': ['AI', 'machine learning', 'artificial intelligence'],
  'edition': '2nd Edition',
  'total_copies': 3,
  'available_copies': 2,
  'shelf_location': 'C-14',
  'cover_image': '',
  'times_borrowed': 38,
  'rating': 4.4,
  'difficulty_level': 'Beginner'},
 {'book_id': 'B026',
  'title': 'Hands-On Machine Learning with Scikit-Learn, Keras, and TensorFlow',
  'author': 'Aurélien Géron',
  'main_category': 'Machine Learning',
  'sub_category': 'Deep Learning',
  'isbn': '9781098125974',
  'publisher': "O'Reilly Media",
  'year': 2022,
  'language': 'English',
  'description': 'Practical guide to machine learning and deep learning using popular Python libraries.',
  'keywords': ['machine learning', 'Python', 'TensorFlow', 'Keras'],
  'edition': '3rd Edition',
  'total_copies': 5,
  'available_copies': 3,
  'shelf_location': 'C-18',
  'cover_image': '',
  'times_borrowed': 63,
  'rating': 4.9,
  'difficulty_level': 'Advanced'},
 {'book_id': 'B027',
  'title': 'Pattern Recognition and Machine Learning',
  'author': 'Christopher M. Bishop',
  'main_category': 'Machine Learning',
  'sub_category': 'Pattern Recognition',
  'isbn': '9780387310732',
  'publisher': 'Springer',
  'year': 2006,
  'language': 'English',
  'description': 'Mathematical treatment of pattern recognition and machine learning.',
  'keywords': ['machine learning', 'statistics', 'pattern recognition'],
  'edition': '1st Edition',
  'total_copies': 3,
  'available_copies': 1,
  'shelf_location': 'C-20',
  'cover_image': '',
  'times_borrowed': 27,
  'rating': 4.8,
  'difficulty_level': 'Advanced'},
 {'book_id': 'B028',
  'title': 'Deep Learning',
  'author': 'Ian Goodfellow, Yoshua Bengio and Aaron Courville',
  'main_category': 'Artificial Intelligence',
  'sub_category': 'Deep Learning',
  'isbn': '9780262035613',
  'publisher': 'MIT Press',
  'year': 2016,
  'language': 'English',
  'description': 'A comprehensive textbook on deep learning and neural networks.',
  'keywords': ['deep learning', 'neural networks', 'AI'],
  'edition': '1st Edition',
  'total_copies': 3,
  'available_copies': 1,
  'shelf_location': 'C-22',
  'cover_image': '',
  'times_borrowed': 32,
  'rating': 4.8,
  'difficulty_level': 'Advanced'},
 {'book_id': 'B029',
  'title': 'Natural Language Processing with Python',
  'author': 'Steven Bird, Ewan Klein and Edward Loper',
  'main_category': 'Artificial Intelligence',
  'sub_category': 'Natural Language Processing',
  'isbn': '9780596516499',
  'publisher': "O'Reilly Media",
  'year': 2009,
  'language': 'English',
  'description': 'Introduction to natural language processing using Python and NLTK.',
  'keywords': ['NLP', 'Python', 'NLTK', 'text processing'],
  'edition': '1st Edition',
  'total_copies': 3,
  'available_copies': 2,
  'shelf_location': 'C-25',
  'cover_image': '',
  'times_borrowed': 28,
  'rating': 4.5,
  'difficulty_level': 'Intermediate'},
 {'book_id': 'B030',
  'title': 'Reinforcement Learning: An Introduction',
  'author': 'Richard S. Sutton and Andrew G. Barto',
  'main_category': 'Artificial Intelligence',
  'sub_category': 'Reinforcement Learning',
  'isbn': '9780262039246',
  'publisher': 'MIT Press',
  'year': 2018,
  'language': 'English',
  'description': 'A fundamental textbook on reinforcement learning algorithms and concepts.',
  'keywords': ['reinforcement learning', 'AI', 'agents', 'RL'],
  'edition': '2nd Edition',
  'total_copies': 3,
  'available_copies': 2,
  'shelf_location': 'C-27',
  'cover_image': '',
  'times_borrowed': 30,
  'rating': 4.8,
  'difficulty_level': 'Advanced'},
 {'book_id': 'B031',
  'title': 'Computer Vision: Algorithms and Applications',
  'author': 'Richard Szeliski',
  'main_category': 'Artificial Intelligence',
  'sub_category': 'Computer Vision',
  'isbn': '9783030343712',
  'publisher': 'Springer',
  'year': 2022,
  'language': 'English',
  'description': 'Comprehensive coverage of computer vision algorithms and applications.',
  'keywords': ['computer vision', 'image processing', 'AI'],
  'edition': '2nd Edition',
  'total_copies': 3,
  'available_copies': 1,
  'shelf_location': 'C-30',
  'cover_image': '',
  'times_borrowed': 24,
  'rating': 4.7,
  'difficulty_level': 'Advanced'},
 {'book_id': 'B032',
  'title': 'Cryptography and Network Security',
  'author': 'William Stallings',
  'main_category': 'Cybersecurity',
  'sub_category': 'Cryptography',
  'isbn': '9780134444284',
  'publisher': 'Pearson',
  'year': 2017,
  'language': 'English',
  'description': 'Introduction to cryptography, network security and secure communication.',
  'keywords': ['cryptography', 'security', 'encryption', 'networks'],
  'edition': '7th Edition',
  'total_copies': 4,
  'available_copies': 3,
  'shelf_location': 'I-02',
  'cover_image': '',
  'times_borrowed': 46,
  'rating': 4.7,
  'difficulty_level': 'Intermediate'},
 {'book_id': 'B033',
  'title': 'Computer Security: Principles and Practice',
  'author': 'William Stallings and Lawrie Brown',
  'main_category': 'Cybersecurity',
  'sub_category': 'Computer Security',
  'isbn': '9780133773927',
  'publisher': 'Pearson',
  'year': 2015,
  'language': 'English',
  'description': 'Fundamentals of computer security, attacks, defense and security management.',
  'keywords': ['cybersecurity', 'security', 'attacks', 'defense'],
  'edition': '3rd Edition',
  'total_copies': 3,
  'available_copies': 2,
  'shelf_location': 'I-05',
  'cover_image': '',
  'times_borrowed': 37,
  'rating': 4.6,
  'difficulty_level': 'Intermediate'},
 {'book_id': 'B034',
  'title': 'Hacking: The Art of Exploitation',
  'author': 'Jon Erickson',
  'main_category': 'Cybersecurity',
  'sub_category': 'Ethical Hacking',
  'isbn': '9781593271442',
  'publisher': 'No Starch Press',
  'year': 2008,
  'language': 'English',
  'description': 'A technical introduction to programming, exploitation and computer security concepts.',
  'keywords': ['hacking', 'security', 'exploitation', 'C'],
  'edition': '2nd Edition',
  'total_copies': 3,
  'available_copies': 1,
  'shelf_location': 'I-08',
  'cover_image': '',
  'times_borrowed': 41,
  'rating': 4.7,
  'difficulty_level': 'Advanced'},
 {'book_id': 'B035',
  'title': 'Web Application Security',
  'author': 'Andrew Hoffman',
  'main_category': 'Cybersecurity',
  'sub_category': 'Web Security',
  'isbn': '9781492053118',
  'publisher': "O'Reilly Media",
  'year': 2020,
  'language': 'English',
  'description': 'Practical concepts for understanding and securing modern web applications.',
  'keywords': ['web security', 'OWASP', 'web applications'],
  'edition': '1st Edition',
  'total_copies': 3,
  'available_copies': 2,
  'shelf_location': 'I-10',
  'cover_image': '',
  'times_borrowed': 34,
  'rating': 4.6,
  'difficulty_level': 'Advanced'},
 {'book_id': 'B036',
  'title': 'Discrete Mathematics and Its Applications',
  'author': 'Kenneth H. Rosen',
  'main_category': 'Mathematics',
  'sub_category': 'Discrete Mathematics',
  'isbn': '9781259676512',
  'publisher': 'McGraw Hill',
  'year': 2019,
  'language': 'English',
  'description': 'A comprehensive introduction to discrete mathematics for computer science students.',
  'keywords': ['discrete mathematics', 'logic', 'graphs', 'sets'],
  'edition': '8th Edition',
  'total_copies': 5,
  'available_copies': 4,
  'shelf_location': 'J-02',
  'cover_image': '',
  'times_borrowed': 53,
  'rating': 4.7,
  'difficulty_level': 'Intermediate'},
 {'book_id': 'B037',
  'title': 'Concrete Mathematics',
  'author': 'Ronald L. Graham, Donald E. Knuth and Oren Patashnik',
  'main_category': 'Mathematics',
  'sub_category': 'Mathematics for CS',
  'isbn': '9780201558029',
  'publisher': 'Addison-Wesley',
  'year': 1994,
  'language': 'English',
  'description': 'Mathematical foundations useful for computer science and algorithm analysis.',
  'keywords': ['mathematics', 'algorithms', 'combinatorics'],
  'edition': '2nd Edition',
  'total_copies': 3,
  'available_copies': 1,
  'shelf_location': 'J-05',
  'cover_image': '',
  'times_borrowed': 22,
  'rating': 4.8,
  'difficulty_level': 'Advanced'},
 {'book_id': 'B038',
  'title': 'Compilers: Principles, Techniques, and Tools',
  'author': 'Alfred V. Aho and others',
  'main_category': 'Computer Science',
  'sub_category': 'Compiler Design',
  'isbn': '9780321486813',
  'publisher': 'Pearson',
  'year': 2006,
  'language': 'English',
  'description': 'A detailed textbook covering compiler construction and programming language processing.',
  'keywords': ['compiler', 'parsing', 'lexical analysis', 'languages'],
  'edition': '2nd Edition',
  'total_copies': 3,
  'available_copies': 2,
  'shelf_location': 'K-02',
  'cover_image': '',
  'times_borrowed': 26,
  'rating': 4.7,
  'difficulty_level': 'Advanced'},
 {'book_id': 'B039',
  'title': 'Computer Graphics with OpenGL',
  'author': 'Donald D. Hearn',
  'main_category': 'Computer Graphics',
  'sub_category': 'OpenGL',
  'isbn': '9780131496705',
  'publisher': 'Pearson',
  'year': 2003,
  'language': 'English',
  'description': 'Introduction to computer graphics algorithms and OpenGL programming.',
  'keywords': ['graphics', 'OpenGL', 'rendering', '3D'],
  'edition': '4th Edition',
  'total_copies': 3,
  'available_copies': 1,
  'shelf_location': 'K-05',
  'cover_image': '',
  'times_borrowed': 19,
  'rating': 4.4,
  'difficulty_level': 'Intermediate'},
 {'book_id': 'B040',
  'title': 'Agile Software Development',
  'author': 'Robert C. Martin',
  'main_category': 'Software Engineering',
  'sub_category': 'Agile',
  'isbn': '9780135974445',
  'publisher': 'Pearson',
  'year': 2002,
  'language': 'English',
  'description': 'Principles and practices of agile software development.',
  'keywords': ['Agile', 'software', 'Scrum', 'development'],
  'edition': '1st Edition',
  'total_copies': 3,
  'available_copies': 2,
  'shelf_location': 'G-08',
  'cover_image': '',
  'times_borrowed': 25,
  'rating': 4.5,
  'difficulty_level': 'Intermediate'},
 {'book_id': 'B041',
  'title': 'Refactoring',
  'author': 'Martin Fowler',
  'main_category': 'Software Engineering',
  'sub_category': 'Code Quality',
  'isbn': '9780134757599',
  'publisher': 'Addison-Wesley',
  'year': 2018,
  'language': 'English',
  'description': 'Techniques for improving the design of existing software without changing its behavior.',
  'keywords': ['refactoring', 'clean code', 'software design'],
  'edition': '2nd Edition',
  'total_copies': 4,
  'available_copies': 2,
  'shelf_location': 'G-10',
  'cover_image': '',
  'times_borrowed': 39,
  'rating': 4.8,
  'difficulty_level': 'Advanced'},
 {'book_id': 'B042',
  'title': 'The Pragmatic Programmer',
  'author': 'David Thomas and Andrew Hunt',
  'main_category': 'Programming',
  'sub_category': 'Software Development',
  'isbn': '9780135957059',
  'publisher': 'Addison-Wesley',
  'year': 2019,
  'language': 'English',
  'description': 'Practical advice and principles for becoming a better software developer.',
  'keywords': ['programming', 'software', 'best practices'],
  'edition': '2nd Edition',
  'total_copies': 5,
  'available_copies': 3,
  'shelf_location': 'G-12',
  'cover_image': '',
  'times_borrowed': 57,
  'rating': 4.9,
  'difficulty_level': 'Intermediate'},
 {'book_id': 'B043',
  'title': 'Code Complete',
  'author': 'Steve McConnell',
  'main_category': 'Programming',
  'sub_category': 'Software Construction',
  'isbn': '9780735619678',
  'publisher': 'Microsoft Press',
  'year': 2004,
  'language': 'English',
  'description': 'A practical guide to software construction and programming practices.',
  'keywords': ['programming', 'software construction', 'coding'],
  'edition': '2nd Edition',
  'total_copies': 4,
  'available_copies': 2,
  'shelf_location': 'G-15',
  'cover_image': '',
  'times_borrowed': 43,
  'rating': 4.8,
  'difficulty_level': 'Intermediate'},
 {'book_id': 'B044',
  'title': 'System Design Interview',
  'author': 'Alex Xu',
  'main_category': 'Software Engineering',
  'sub_category': 'System Design',
  'isbn': '9781736049171',
  'publisher': 'Independently Published',
  'year': 2020,
  'language': 'English',
  'description': 'Practical system design concepts and interview-oriented examples.',
  'keywords': ['system design', 'architecture', 'interviews'],
  'edition': '1st Edition',
  'total_copies': 4,
  'available_copies': 3,
  'shelf_location': 'L-02',
  'cover_image': '',
  'times_borrowed': 67,
  'rating': 4.8,
  'difficulty_level': 'Advanced'},
 {'book_id': 'B045',
  'title': 'Designing Data-Intensive Applications',
  'author': 'Martin Kleppmann',
  'main_category': 'Distributed Systems',
  'sub_category': 'Data Systems',
  'isbn': '9781449373320',
  'publisher': "O'Reilly Media",
  'year': 2017,
  'language': 'English',
  'description': 'A detailed guide to designing reliable, scalable and maintainable data systems.',
  'keywords': ['distributed systems', 'databases', 'scalability'],
  'edition': '1st Edition',
  'total_copies': 3,
  'available_copies': 1,
  'shelf_location': 'L-05',
  'cover_image': '',
  'times_borrowed': 36,
  'rating': 4.9,
  'difficulty_level': 'Advanced'},
 {'book_id': 'B046',
  'title': 'Distributed Systems',
  'author': 'Maarten van Steen and Andrew S. Tanenbaum',
  'main_category': 'Distributed Systems',
  'sub_category': 'Distributed Computing',
  'isbn': '9781543057386',
  'publisher': 'Maarten van Steen',
  'year': 2017,
  'language': 'English',
  'description': 'Introduction to principles and concepts of distributed systems.',
  'keywords': ['distributed systems', 'cloud', 'networks'],
  'edition': '3rd Edition',
  'total_copies': 3,
  'available_copies': 2,
  'shelf_location': 'L-08',
  'cover_image': '',
  'times_borrowed': 21,
  'rating': 4.6,
  'difficulty_level': 'Advanced'},
 {'book_id': 'B047',
  'title': 'Linux Command Line and Shell Scripting Bible',
  'author': 'Richard Blum and Christine Bresnahan',
  'main_category': 'Operating Systems',
  'sub_category': 'Linux',
  'isbn': '9781118983843',
  'publisher': 'Wiley',
  'year': 2015,
  'language': 'English',
  'description': 'Practical guide to Linux command-line tools and shell scripting.',
  'keywords': ['Linux', 'shell', 'bash', 'command line'],
  'edition': '3rd Edition',
  'total_copies': 4,
  'available_copies': 3,
  'shelf_location': 'E-25',
  'cover_image': '',
  'times_borrowed': 40,
  'rating': 4.6,
  'difficulty_level': 'Intermediate'},
 {'book_id': 'B048',
  'title': 'Automate the Boring Stuff with Python',
  'author': 'Al Sweigart',
  'main_category': 'Programming',
  'sub_category': 'Python',
  'isbn': '9781593279929',
  'publisher': 'No Starch Press',
  'year': 2019,
  'language': 'English',
  'description': 'Practical Python programming for automating everyday tasks.',
  'keywords': ['Python', 'automation', 'scripting'],
  'edition': '2nd Edition',
  'total_copies': 5,
  'available_copies': 5,
  'shelf_location': 'A-25',
  'cover_image': '',
  'times_borrowed': 70,
  'rating': 4.8,
  'difficulty_level': 'Beginner'},
 {'book_id': 'B049',
  'title': 'Fluent Python',
  'author': 'Luciano Ramalho',
  'main_category': 'Programming',
  'sub_category': 'Python',
  'isbn': '9781492056355',
  'publisher': "O'Reilly Media",
  'year': 2022,
  'language': 'English',
  'description': 'Advanced techniques and best practices for Python programming.',
  'keywords': ['Python', 'advanced Python', 'programming'],
  'edition': '2nd Edition',
  'total_copies': 4,
  'available_copies': 2,
  'shelf_location': 'A-28',
  'cover_image': '',
  'times_borrowed': 45,
  'rating': 4.8,
  'difficulty_level': 'Advanced'},
 {'book_id': 'B050',
  'title': 'Practical Statistics for Data Scientists',
  'author': 'Peter Bruce, Andrew Bruce and Peter Gedeck',
  'main_category': 'Data Science',
  'sub_category': 'Statistics',
  'isbn': '9781492072942',
  'publisher': "O'Reilly Media",
  'year': 2020,
  'language': 'English',
  'description': 'Practical statistics concepts and techniques for data science.',
  'keywords': ['statistics', 'data science', 'probability', 'Python'],
  'edition': '2nd Edition',
  'total_copies': 4,
  'available_copies': 3,
  'shelf_location': 'M-02',
  'cover_image': '',
  'times_borrowed': 38,
  'rating': 4.7,
  'difficulty_level': 'Intermediate'}]

# Create tables and seed the starter library after INITIAL_BOOKS is defined.
init_database()
# Add student management fields to existing databases

# ==========================================
# HELPER FUNCTIONS
# ==========================================

def normalize(text):
    return re.sub(r"\s+", " ", str(text).lower().strip())

def book_search_text(book):
    return normalize(" ".join([
        book.get("book_id", ""), book.get("title", ""), book.get("author", ""),
        book.get("main_category", ""), book.get("sub_category", ""), book.get("isbn", ""),
        book.get("publisher", ""), str(book.get("year", "")), book.get("language", ""),
        book.get("description", ""), " ".join(book.get("keywords", [])),
        book.get("edition", ""), book.get("shelf_location", ""), book.get("difficulty_level", "")
    ]))

def find_books(query):
    query = normalize(query)
    if not query:
        return []
    all_books = get_all_books()
    exact = [b for b in all_books if query == normalize(b["title"])]
    if exact:
        return exact
    stop = {"the","a","an","and","or","of","to","for","in","on","with","about","by","from","book","books","show","find","search","give","me","please","do","you","have","any","is","are","there","this","that","which","what","where","who","how","many","can","i","want","need","some","your","library","available","availability","tell","tell me","details","detail"}
    words = [w for w in re.findall(r"[a-zA-Z0-9+#.-]+", query) if w not in stop and len(w) > 1]
    scored=[]
    for b in all_books:
        text=book_search_text(b); score=0
        for w in words:
            if w in text:
                if w in normalize(b["title"]): score += 10
                elif w in normalize(b["author"]): score += 8
                elif w in normalize(b["main_category"]) or w in normalize(b["sub_category"]): score += 6
                elif any(w in normalize(k) for k in b["keywords"]): score += 5
                else: score += 1
        if score: scored.append((score,b))
    scored.sort(key=lambda x:x[0], reverse=True)
    return [b for _,b in scored]

def find_exact_book(query):
    query=normalize(query)
    m=re.search(r"\bB\d{3}\b", query, re.I)
    all_books=get_all_books()
    if m:
        bid=m.group(0).upper()
        for b in all_books:
            if b["book_id"].upper()==bid: return b
    for b in all_books:
        title=normalize(b["title"])
        if title == query or title in query:
            return b
    return None

def extract_shelf(message):
    m=re.search(r"\b([A-Z])\s*[- ]\s*(\d{1,2})\b", message.upper())
    return f"{m.group(1)}-{int(m.group(2)):02d}" if m else None

def extract_author(message):
    text=normalize(message)
    for pattern in [r"\bbooks?\s+by\s+(.+?)(?:\?|$)", r"\bwritten\s+by\s+(.+?)(?:\?|$)", r"\bauthor\s+(.+?)(?:\?|$)"]:
        m=re.search(pattern,text)
        if m:
            author=re.sub(r"\b(available|in the library|in library|please|books?)\b.*$","",m.group(1)).strip()
            if author: return author
    return None

def detect_topic(message):
    text=normalize(message)
    aliases={
        "artificial intelligence":["artificial intelligence","ai"],"machine learning":["machine learning","ml"],
        "deep learning":["deep learning","neural network","neural networks"],"python":["python"],"java":["java"],
        "c programming":["c programming","c language"],"c++":["c++","cpp"],"javascript":["javascript","js"],
        "web development":["web development","web design","frontend","front end"],"database":["database","databases","dbms"],
        "sql":["sql"],"networking":["networking","computer networks","network"],"operating systems":["operating system","operating systems","os"],
        "cybersecurity":["cybersecurity","cyber security","computer security"],"cryptography":["cryptography","encryption"],
        "software engineering":["software engineering","software development"],"algorithms":["algorithms","data structures","dsa"],
        "computer architecture":["computer architecture","computer organization","cpu"],"linux":["linux","shell scripting","bash"],
        "computer vision":["computer vision","image processing"],"nlp":["nlp","natural language processing"],
        "statistics":["statistics","data science"],"computer graphics":["computer graphics","opengl","graphics"],
        "distributed systems":["distributed systems","distributed computing"],"mathematics":["mathematics","discrete mathematics"]}
    for topic,vals in sorted(aliases.items(), key=lambda x:max(map(len,x[1])), reverse=True):
        if any(v in text for v in vals): return topic
    return None

def detect_difficulty(message):
    text=normalize(message)
    if any(x in text for x in ["beginner","beginners","basic","basics","easy","starting","start learning","new to"]): return "beginner"
    if any(x in text for x in ["intermediate","medium"]): return "intermediate"
    if any(x in text for x in ["advanced","expert","hard","difficult"]): return "advanced"
    return None

def is_casual_message(message):
    text=normalize(message)
    if text in {"hi","hello","hey","hii","hiii","good morning","good afternoon","good evening","good night"}:
        return "Hello! 👋 I’m your AI Library Assistant. How can I help you today?"
    if text in {"thanks","thank you","thank u","thx"}:
        return "You’re welcome! 😊 Let me know if you need help finding a book."
    if text in {"how are you","how r you","how r u"}:
        return "I’m doing great! 😊 What would you like to know about the library?"
    if text in {"who are you","what are you"}:
        return "I’m your AI Library Assistant. 📚 I can search, explain, compare, recommend, and help manage your books."
    if text in {"help","what can you do","what can you do?"}:
        return "I can search books, give details, check availability, find shelves, compare books, recommend books, and show your borrowed books."
    return None

def is_availability_question(message):
    text=normalize(message)
    return any(x in text for x in ["available","availability","can i borrow","borrow this","borrow","in library","have this book","do you have","does the library have","is there a book","are there books","which books are available"])

def is_location_question(message):
    text=normalize(message)
    return any(x in text for x in ["where","shelf","location","located","which shelf"])

def format_book_details(book):
    status="Available" if book["available_copies"]>0 else "Currently unavailable"
    return (f"📚 **{book['title']}** ({book['book_id']})\n"
            f"Author: {book['author']}\nCategory: {book['main_category']} → {book['sub_category']}\n"
            f"ISBN: {book['isbn']}\nPublisher: {book['publisher']}\nYear: {book['year']}\n"
            f"Language: {book['language']}\nEdition: {book['edition']}\n"
            f"Availability: {status}\nCopies: {book['available_copies']} / {book['total_copies']}\n"
            f"Shelf: {book['shelf_location']}\nRating: {book['rating']}/5\n"
            f"Difficulty: {book['difficulty_level']}\nTimes borrowed: {book['times_borrowed']}\n"
            f"Keywords: {', '.join(book['keywords'])}\nDescription: {book['description']}")

def format_book_list(found, heading):
    reply=heading+"\n\n"
    for b in found[:10]:
        status="Available" if b["available_copies"]>0 else "Unavailable"
        reply += f"• **{b['title']}** ({b['book_id']}) — {status}, {b['available_copies']} / {b['total_copies']} copies — Shelf {b['shelf_location']} — ⭐ {b['rating']}\n"
    if len(found)>10: reply += f"\nShowing 10 of {len(found)} matching books."
    return reply

def natural_language_search(message):
    text=normalize(message); all_books=get_all_books()
    shelf=extract_shelf(text)
    if shelf:
        result=[b for b in all_books if b["shelf_location"].upper()==shelf]
        return result,{"type":"shelf","shelf":shelf}
    author=extract_author(text)
    if author:
        words=[w for w in re.findall(r"[a-zA-Z]+",author) if len(w)>1]
        result=[b for b in all_books if all(w in normalize(b["author"]) for w in words)]
        if result: return result,{"type":"author","author":author}
    topic=detect_topic(text); difficulty=detect_difficulty(text)
    if topic or difficulty:
        result=[]
        for b in all_books:
            st=book_search_text(b)
            if topic=="artificial intelligence": tm="artificial intelligence" in st or "ai" in [normalize(k) for k in b["keywords"]]
            elif topic=="nlp": tm="nlp" in st or "natural language processing" in st
            elif topic=="deep learning": tm="deep learning" in st or "neural network" in st
            elif topic: tm=topic in st
            else: tm=True
            dm=normalize(b["difficulty_level"])==difficulty if difficulty else True
            if tm and dm: result.append(b)
        return result,{"type":"topic","topic":topic,"difficulty":difficulty}
    return find_books(text),{"type":"keyword"}

# ==========================================
# AUTHENTICATION
# ==========================================

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("login.html")

    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    if not email or not password:
        return render_template("login.html", error="Please enter email and password.")

    conn = get_db_connection()
    user = conn.execute(
        "SELECT * FROM users WHERE email = ?", (email,)
    ).fetchone()
    conn.close()

    if user is None or not check_password_hash(user["password"], password):
        return render_template("login.html", error="Invalid email or password.")

    session["user_id"] = user["id"]
    session["name"] = user["name"]
    session["role"] = user["role"]

    if user["role"] == "admin":
        return redirect(url_for("admin_dashboard"))

    return redirect(url_for("student_dashboard"))


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return render_template("register.html")

    name = request.form.get("name", "").strip()
    student_id = request.form.get("student_id", "").strip()
    department = request.form.get("department", "").strip()
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    if not all([name, student_id, department, email, password]):
        return render_template("register.html", error="Please fill in all fields.")

    if len(password) < 6:
        return render_template("register.html", error="Password must be at least 6 characters.")

    conn = get_db_connection()

    existing = conn.execute(
        "SELECT id FROM users WHERE email = ? OR student_id = ?",
        (email, student_id)
    ).fetchone()

    if existing:
        conn.close()
        return render_template(
            "register.html",
            error="Email or Student ID is already registered."
        )

    hashed_password = generate_password_hash(password)

    conn.execute("""
        INSERT INTO users (
            name, email, password, role, student_id, department,
            registration_date, account_status
        )
        VALUES (?, ?, ?, ?, ?, ?, datetime('now'), 'Active')
    """, (name, email, hashed_password, "student", student_id, department))

    conn.commit()
    conn.close()

    return redirect(url_for("login"))


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/me")
def me():
    if "user_id" not in session:
        return jsonify({"logged_in": False})

    return jsonify({
        "logged_in": True,
        "user_id": session["user_id"],
        "name": session["name"],
        "role": session["role"]
    })


# ==========================================
# DASHBOARDS
# ==========================================

@app.route("/")
def home():
    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("role") == "admin":
        return redirect(url_for("admin_dashboard"))

    return redirect(url_for("student_dashboard"))


@app.route("/student-dashboard")
def student_dashboard():
    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("role") != "student":
        return redirect(url_for("admin_dashboard"))

    return render_template("student_dashboard.html", user=current_user())


@app.route("/admin-dashboard")
def admin_dashboard():
    

    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("role") != "admin":
        return redirect(url_for("student_dashboard"))

    return render_template("admin_dashboard.html", user=current_user())
@app.route("/admin-students")
def admin_students_page():
    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("role") != "admin":
        return redirect(url_for("student_dashboard"))

    return render_template("admin_students.html")
@app.route("/api/admin/students")
def admin_students():
    if "user_id" not in session:
        return jsonify({"error": "Please login first."}), 401

    if session.get("role") != "admin":
        return jsonify({"error": "Admin access required."}), 403

    conn = get_db_connection()

    students = conn.execute("""
        SELECT
            u.id,
            u.name,
            u.email,
            u.student_id,
            u.department,
            u.registration_date,
            u.account_status,
            COUNT(b.id) AS books_borrowed,

            SUM(
                CASE
                    WHEN b.status = 'borrowed'
                    THEN 1
                    ELSE 0
                END
            ) AS active_books,

            SUM(
                CASE
                    WHEN b.status = 'returned'
                    THEN 1
                    ELSE 0
                END
            ) AS returned_books,

            SUM(
                CASE
                    WHEN b.status = 'borrowed'
                    AND b.due_date < datetime('now')
                    THEN 1
                    ELSE 0
                END
            ) AS overdue_books

        FROM users u

        LEFT JOIN borrowings b
            ON u.id = b.user_id

        WHERE u.role = 'student'

        GROUP BY
            u.id,
            u.name,
            u.email,
            u.student_id,
            u.department,
            u.registration_date,
            u.account_status

        ORDER BY u.name
    """).fetchall()

    conn.close()

    return jsonify([dict(student) for student in students])
@app.route("/api/admin/students/<int:student_id>/status", methods=["POST"])
def update_student_status(student_id):

    if "user_id" not in session:
        return jsonify({"error": "Please login first."}), 401

    if session.get("role") != "admin":
        return jsonify({"error": "Admin access required."}), 403

    data = request.get_json()
    status = data.get("status", "").strip()

    if status not in ["Active", "Suspended", "Inactive"]:
        return jsonify({"error": "Invalid account status."}), 400

    conn = get_db_connection()

    student = conn.execute(
        "SELECT id FROM users WHERE id = ? AND role = 'student'",
        (student_id,)
    ).fetchone()

    if not student:
        conn.close()
        return jsonify({"error": "Student not found."}), 404

    conn.execute(
        "UPDATE users SET account_status = ? WHERE id = ?",
        (status, student_id)
    )

    conn.commit()
    conn.close()

    return jsonify({
        "success": True,
        "message": "Student status updated.",
        "status": status
    })
@app.route("/api/admin/students/<int:student_id>/borrowings")
def admin_student_borrowings(student_id):
    if "user_id" not in session:
        return jsonify({"error": "Please login first."}), 401

    if session.get("role") != "admin":
        return jsonify({"error": "Admin access required."}), 403

    conn = get_db_connection()

    borrowings = conn.execute("""
        SELECT
            b.id,
            b.book_id,
            books.title,
            b.borrowed_at,
            b.due_date,
            b.returned_at,
            b.status
        FROM borrowings b
        LEFT JOIN books
            ON b.book_id = books.book_id
        WHERE b.user_id = ?
        ORDER BY b.borrowed_at DESC
    """, (student_id,)).fetchall()

    conn.close()

    return jsonify([dict(borrowing) for borrowing in borrowings])
# STUDENT PROFILE + BORROW / RETURN
# ==========================================

@app.route("/student-profile")
def student_profile():
    if "user_id" not in session:
        return redirect(url_for("login"))
    if session.get("role") != "student":
        return redirect(url_for("admin_dashboard"))
    return render_template("student-profile.html")


def student_only():
    if "user_id" not in session:
        return jsonify({"error": "Login required"}), 401
    if session.get("role") != "student":
        return jsonify({"error": "Student access required"}), 403
    return None


@app.route("/api/student/profile", methods=["GET", "PUT"])
def student_profile_api():
    denied = student_only()
    if denied:
        return denied

    conn = get_db_connection()
    if request.method == "GET":
        user = conn.execute(
            """
            SELECT id, name, email, student_id, department, role, account_status
            FROM users
            WHERE id = ?
            """,
            (session["user_id"],)
        ).fetchone()
        conn.close()
        if not user:
            return jsonify({"error": "Student not found."}), 404
        return jsonify(dict(user))

    data = request.get_json(silent=True) or {}
    name = str(data.get("name", "")).strip()
    department = str(data.get("department", "")).strip()
    if not name or not department:
        conn.close()
        return jsonify({"error": "Name and department are required."}), 400

    conn.execute(
        "UPDATE users SET name = ?, department = ? WHERE id = ?",
        (name, department, session["user_id"])
    )
    conn.commit()
    conn.close()
    session["name"] = name
    return jsonify({"message": "Profile updated successfully."})


@app.route("/api/student/borrowings")
def student_borrowings():
    denied = student_only()
    if denied:
        return denied

    conn = get_db_connection()
    rows = conn.execute("""
        SELECT br.id, br.book_id, b.title, b.author, b.shelf_location,
               br.borrowed_at, br.due_date, br.returned_at, br.status
        FROM borrowings br
        JOIN books b ON b.book_id = br.book_id
        WHERE br.user_id = ?
        ORDER BY br.id DESC
    """, (session["user_id"],)).fetchall()
    conn.close()
    return jsonify([dict(row) for row in rows])


@app.route("/api/student/borrow", methods=["POST"])
def borrow_book():
    denied = student_only()
    if denied:
        return denied

    data = request.get_json(silent=True) or {}
    book_id = str(data.get("book_id", "")).strip().upper()
    if not book_id:
        return jsonify({"error": "Book ID is required."}), 400

    conn = get_db_connection()
    student = conn.execute(
        "SELECT account_status FROM users WHERE id = ?",
        (session["user_id"],)
    ).fetchone()

    if student and student["account_status"] != "Active":
        conn.close()
        return jsonify({
            "error": f"Your library account is {student['account_status']}. You cannot borrow books."
        }), 403
    book = conn.execute(
        "SELECT * FROM books WHERE UPPER(book_id) = ?", (book_id,)
    ).fetchone()
    if not book:
        conn.close()
        return jsonify({"error": "Book not found."}), 404
    if book["available_copies"] <= 0:
        conn.close()
        return jsonify({"error": "This book is currently unavailable."}), 400

    active_count = conn.execute(
        "SELECT COUNT(*) AS count FROM borrowings WHERE user_id = ? AND status = 'borrowed'",
        (session["user_id"],)
    ).fetchone()["count"]
    max_books = int(conn.execute("SELECT value FROM library_settings WHERE key='max_books_per_student'").fetchone()["value"]) if conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='library_settings'").fetchone() else 3
    if active_count >= max_books:
        conn.close()
        return jsonify({"error": f"Borrowing limit reached. You can have up to {max_books} active books."}), 400

    already = conn.execute("""
        SELECT id FROM borrowings
        WHERE user_id = ? AND book_id = ? AND status = 'borrowed'
    """, (session["user_id"], book["book_id"])).fetchone()
    if already:
        conn.close()
        return jsonify({"error": "You already have this book borrowed."}), 400

    from datetime import datetime, timedelta
    now = datetime.now()
    borrowed_at = now.strftime("%Y-%m-%d %H:%M:%S")
    days = int(conn.execute("SELECT value FROM library_settings WHERE key='borrowing_period_days'").fetchone()["value"]) if conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='library_settings'").fetchone() else 14
    due_date = (now + timedelta(days=days)).strftime("%Y-%m-%d")

    conn.execute("""
        INSERT INTO borrowings (user_id, book_id, borrowed_at, due_date, status)
        VALUES (?, ?, ?, ?, 'borrowed')
    """, (session["user_id"], book["book_id"], borrowed_at, due_date))
    conn.execute("""
        UPDATE books
        SET available_copies = available_copies - 1,
            times_borrowed = times_borrowed + 1
        WHERE book_id = ? AND available_copies > 0
    """, (book["book_id"],))
    conn.commit()
    conn.close()
    return jsonify({"message": f"{book['title']} borrowed successfully.", "due_date": due_date})

@app.route("/api/student/return/<int:borrowing_id>", methods=["POST"])
def return_book(borrowing_id):
    denied = student_only()
    if denied:
        return denied

    conn = get_db_connection()
    borrowing = conn.execute("""
        SELECT br.*, b.title
        FROM borrowings br
        JOIN books b ON b.book_id = br.book_id
        WHERE br.id = ? AND br.user_id = ?
    """, (borrowing_id, session["user_id"])).fetchone()
    if not borrowing:
        conn.close()
        return jsonify({"error": "Borrowing record not found."}), 404
    if borrowing["status"] != "borrowed":
        conn.close()
        return jsonify({"error": "This book has already been returned."}), 400

    from datetime import datetime
    returned_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn.execute(
        "UPDATE borrowings SET status = 'returned', returned_at = ? WHERE id = ?",
        (returned_at, borrowing_id)
    )
    conn.execute("""
        UPDATE books
        SET available_copies = CASE
            WHEN available_copies < total_copies THEN available_copies + 1
            ELSE total_copies
        END
        WHERE book_id = ?
    """, (borrowing["book_id"],))
    conn.commit()
    conn.close()
    return jsonify({"message": f"{borrowing['title']} returned successfully."})


@app.route("/manage-books")
def manage_books():
    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("role") != "admin":
        return redirect(url_for("student_profile"))

    return render_template("manage_books.html", user=current_user())
@app.route("/api/admin/books")
def admin_books():
    if "user_id" not in session:
        return jsonify({"error": "Login required"}), 401

    if session.get("role") != "admin":
        return jsonify({"error": "Admin access required"}), 403

    return jsonify(get_all_books())
# ==========================================
# ADMIN BOOK MANAGEMENT APIs
# ==========================================

def admin_only():
    if "user_id" not in session:
        return jsonify({"error": "Login required"}), 401
    if session.get("role") != "admin":
        return jsonify({"error": "Admin access required"}), 403
    return None

def clean_book_payload(data, existing=None):
    existing = existing or {}
    def text(key):
        value = data.get(key, existing.get(key, ""))
        return str(value).strip()
    def integer(key, default=0):
        value = data.get(key, existing.get(key, default))
        if value in (None, ""):
            return default
        return int(value)
    def number(key, default=0.0):
        value = data.get(key, existing.get(key, default))
        if value in (None, ""):
            return default
        return float(value)
    keywords = data.get("keywords", existing.get("keywords", []))
    if isinstance(keywords, str):
        keywords = [x.strip() for x in keywords.split(",") if x.strip()]
    elif not isinstance(keywords, list):
        keywords = []
    return {
        "book_id": text("book_id"),
        "title": text("title"),
        "author": text("author"),
        "main_category": text("main_category"),
        "sub_category": text("sub_category"),
        "isbn": text("isbn"),
        "publisher": text("publisher"),
        "year": integer("year", 0),
        "language": text("language"),
        "description": text("description"),
        "keywords": keywords,
        "edition": text("edition"),
        "total_copies": integer("total_copies", 0),
        "available_copies": integer("available_copies", 0),
        "shelf_location": text("shelf_location"),
        "cover_image": text("cover_image"),
        "times_borrowed": integer("times_borrowed", 0),
        "rating": number("rating", 0.0),
        "difficulty_level": text("difficulty_level")
    }

@app.route("/api/admin/books/add", methods=["POST"])
def add_book():
    denied = admin_only()
    if denied:
        return denied

    data = request.get_json(silent=True) or {}
    try:
        new_book = clean_book_payload(data)
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid number value."}), 400

    if not new_book["book_id"] or not new_book["title"] or not new_book["author"]:
        return jsonify({"error": "Book ID, title and author are required."}), 400

    if get_book(new_book["book_id"]):
        return jsonify({"error": "Book ID already exists."}), 409

    if (
        new_book["total_copies"] < 1
        or new_book["available_copies"] < 0
        or new_book["available_copies"] > new_book["total_copies"]
    ):
        return jsonify({"error": "Invalid copy values."}), 400

    new_book["rating"] = max(0.0, min(5.0, new_book["rating"]))

    conn = get_db_connection()
    conn.execute("""
        INSERT INTO books (
            book_id, title, author, main_category, sub_category, isbn,
            publisher, year, language, description, keywords, edition,
            total_copies, available_copies, shelf_location, cover_image,
            times_borrowed, rating, difficulty_level
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        new_book["book_id"], new_book["title"], new_book["author"],
        new_book["main_category"], new_book["sub_category"], new_book["isbn"],
        new_book["publisher"], new_book["year"], new_book["language"],
        new_book["description"], json.dumps(new_book["keywords"]),
        new_book["edition"], new_book["total_copies"], new_book["available_copies"],
        new_book["shelf_location"], new_book["cover_image"],
        new_book["times_borrowed"], new_book["rating"], new_book["difficulty_level"]
    ))
    conn.commit()
    conn.close()

    return jsonify({
        "message": "Book added successfully.",
        "book": new_book
    }), 201


@app.route("/api/admin/books/update/<book_id>", methods=["PUT"])
def update_book(book_id):
    denied = admin_only()
    if denied:
        return denied

    existing = get_book(book_id)
    if not existing:
        return jsonify({"error": "Book not found."}), 404

    data = request.get_json(silent=True) or {}
    try:
        updated = clean_book_payload(data, existing)
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid number value."}), 400

    if (
        updated["total_copies"] < 1
        or updated["available_copies"] < 0
        or updated["available_copies"] > updated["total_copies"]
    ):
        return jsonify({"error": "Available copies cannot be greater than total copies."}), 400

    updated["book_id"] = existing["book_id"]
    updated["rating"] = max(0.0, min(5.0, updated["rating"]))

    conn = get_db_connection()
    conn.execute("""
        UPDATE books SET
            title = ?, author = ?, main_category = ?, sub_category = ?, isbn = ?,
            publisher = ?, year = ?, language = ?, description = ?, keywords = ?,
            edition = ?, total_copies = ?, available_copies = ?, shelf_location = ?,
            cover_image = ?, times_borrowed = ?, rating = ?, difficulty_level = ?
        WHERE UPPER(book_id) = UPPER(?)
    """, (
        updated["title"], updated["author"], updated["main_category"],
        updated["sub_category"], updated["isbn"], updated["publisher"],
        updated["year"], updated["language"], updated["description"],
        json.dumps(updated["keywords"]), updated["edition"],
        updated["total_copies"], updated["available_copies"],
        updated["shelf_location"], updated["cover_image"],
        updated["times_borrowed"], updated["rating"], updated["difficulty_level"],
        existing["book_id"]
    ))
    conn.commit()
    conn.close()

    return jsonify({
        "message": "Book updated successfully.",
        "book": get_book(existing["book_id"])
    })


@app.route("/api/admin/books/delete/<book_id>", methods=["DELETE"])
def delete_book(book_id):
    denied = admin_only()
    if denied:
        return denied

    existing = get_book(book_id)
    if not existing:
        return jsonify({"error": "Book not found."}), 404

    conn = get_db_connection()
    borrowing = conn.execute(
        "SELECT 1 FROM borrowings WHERE book_id = ? LIMIT 1",
        (existing["book_id"],)
    ).fetchone()
    if borrowing:
        conn.close()
        return jsonify({
            "error": "This book cannot be deleted because it has borrowing history."
        }), 409
    conn.execute("DELETE FROM books WHERE UPPER(book_id) = UPPER(?)", (book_id,))
    conn.commit()
    conn.close()

    return jsonify({
        "message": "Book deleted successfully.",
        "book": existing
    })


# ==========================================
# GET ALL BOOKS
# ==========================================

@app.route("/api/books")
def get_books():
    return jsonify(get_all_books())


# ==========================================
# SEARCH BOOKS
# ==========================================

@app.route("/api/search")
def search_books():

    query = request.args.get("q", "").strip()

    if not query:
        return jsonify([])

    results, _ = natural_language_search(query)

    return jsonify(results)


# ==========================================
# AI LIBRARY ASSISTANT
# ==========================================

@app.route("/ai-assistant")
def ai_assistant():
    if "user_id" not in session:
        return redirect(url_for("login"))
    if session.get("role") != "student":
        return redirect(url_for("admin_dashboard"))
    return render_template("ai_assistant.html", user=current_user())

@app.route("/api/chat", methods=["POST"])
def chat():
    denied = student_only()
    if denied:
        return denied

    try:
        data=request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify({"error": "Request body must be a JSON object."}), 400
        user_message=data.get("message", "")
        if not isinstance(user_message, str):
            return jsonify({"error": "Message must be text."}), 400
        user_message=user_message.strip()
        if not user_message:
            return jsonify({"reply":"Please enter a question."})

        conn = get_db_connection()
        ai_setting = conn.execute(
            "SELECT value FROM library_settings WHERE key = 'ai_enabled'"
        ).fetchone()
        conn.close()
        if ai_setting and ai_setting["value"] != "1":
            return jsonify({"reply": "The AI assistant is currently disabled by the library administrator."})

        log_ai_activity(user_message)
        casual=is_casual_message(user_message)
        if casual:
            return jsonify({"reply":casual})

        text=normalize(user_message)
        all_books=get_all_books()
        exact=find_exact_book(user_message)

        # My borrowed books / due dates
        if any(x in text for x in ["my books","books i borrowed","borrowed books","my borrowing","what did i borrow","due dates","when should i return"]):
            conn=get_db_connection()
            rows=conn.execute("""SELECT br.*, b.title, b.book_id FROM borrowings br JOIN books b ON b.book_id=br.book_id WHERE br.user_id=? AND br.status='borrowed' ORDER BY br.due_date""",(session["user_id"],)).fetchall()
            conn.close()
            if not rows: return jsonify({"reply":"You currently have no borrowed books. 📚"})
            reply="📚 **Your borrowed books:**\n\n"
            for r in rows: reply += f"• **{r['title']}** ({r['book_id']}) — Due: {r['due_date']}\n"
            return jsonify({"reply":reply})

        # Borrow a specific book through chat
        if any(x in text for x in ["borrow ","i want to borrow","let me borrow","can i borrow"]):
            book=exact
            if book:
                conn=get_db_connection()
                student = conn.execute(
                    "SELECT account_status FROM users WHERE id = ?",
                    (session["user_id"],)
                ).fetchone()
                if student and student["account_status"] != "Active":
                    conn.close()
                    return jsonify({
                        "reply": f"Your library account is {student['account_status']}. You cannot borrow books."
                    })
                active=conn.execute("SELECT COUNT(*) AS c FROM borrowings WHERE user_id=? AND status='borrowed'",(session["user_id"],)).fetchone()["c"]
                duplicate=conn.execute("SELECT COUNT(*) AS c FROM borrowings WHERE user_id=? AND book_id=? AND status='borrowed'",(session["user_id"],book["book_id"])).fetchone()["c"]
                if duplicate:
                    conn.close(); return jsonify({"reply":f"You already have **{book['title']}** borrowed."})
                settings_row=conn.execute("SELECT key,value FROM library_settings WHERE key IN ('max_books_per_student','borrowing_period_days')").fetchall()
                settings={r["key"]:r["value"] for r in settings_row}
                max_books=int(settings.get("max_books_per_student",3))
                if active>=max_books:
                    conn.close(); return jsonify({"reply":f"You already have {max_books} active borrowed books. Return one before borrowing another."})
                if book["available_copies"]<=0:
                    conn.close(); return jsonify({"reply":f"**{book['title']}** is currently unavailable."})
                from datetime import datetime, timedelta
                borrowed_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                days=int(settings.get("borrowing_period_days",14))
                due=(datetime.now()+timedelta(days=days)).strftime("%Y-%m-%d")
                conn.execute("INSERT INTO borrowings (user_id,book_id,borrowed_at,due_date,status) VALUES (?,?,?,?, 'borrowed')",(session["user_id"],book["book_id"],borrowed_at,due))
                conn.execute("UPDATE books SET available_copies=available_copies-1, times_borrowed=times_borrowed+1 WHERE book_id=?",(book["book_id"],))
                conn.commit(); conn.close()
                return jsonify({"reply":f"✅ **{book['title']}** has been borrowed successfully.\nDue date: **{due}**\nShelf: {book['shelf_location']}"})

        # Return a specific book through chat
        if any(x in text for x in ["return ","return my book","give back"]):
            book=exact
            if book:
                conn=get_db_connection()
                row=conn.execute("SELECT id FROM borrowings WHERE user_id=? AND book_id=? AND status='borrowed' ORDER BY id DESC LIMIT 1",(session["user_id"],book["book_id"])).fetchone()
                if not row:
                    conn.close(); return jsonify({"reply":f"You do not currently have **{book['title']}** borrowed."})
                from datetime import datetime
                conn.execute("UPDATE borrowings SET returned_at=?, status='returned' WHERE id=?",(datetime.now().strftime("%Y-%m-%d %H:%M:%S"),row["id"]))
                conn.execute("UPDATE books SET available_copies=MIN(total_copies, available_copies+1) WHERE book_id=?",(book["book_id"],))
                conn.commit(); conn.close()
                return jsonify({"reply":f"✅ **{book['title']}** has been returned successfully."})

        # Compare two books
        if any(x in text for x in ["compare","difference between","vs ","versus"]):
            mentioned=[b for b in all_books if normalize(b["title"]) in text or b["book_id"].lower() in text]
            if len(mentioned)>=2:
                a,b=mentioned[0],mentioned[1]
                return jsonify({"reply":f"📊 **Comparison**\n\n**{a['title']}** — {a['difficulty_level']}, ⭐ {a['rating']}, {a['available_copies']}/{a['total_copies']} available, {a['year']}\n**{b['title']}** — {b['difficulty_level']}, ⭐ {b['rating']}, {b['available_copies']}/{b['total_copies']} available, {b['year']}"})

        # Ranking / aggregate questions
        if any(x in text for x in ["highest rated","best rated","top rated","highest rating","most popular","most borrowed","popular books"]):
            if "borrow" in text or "popular" in text: ranked=sorted(all_books,key=lambda b:b["times_borrowed"],reverse=True)
            else: ranked=sorted(all_books,key=lambda b:b["rating"],reverse=True)
            return jsonify({"reply":format_book_list(ranked,"Here are the top books in the library:")})
        if any(x in text for x in ["newest","latest books","recent books"]):
            return jsonify({"reply":format_book_list(sorted(all_books,key=lambda b:b["year"] or 0,reverse=True),"Here are the newest books:")})
        if any(x in text for x in ["oldest books","oldest book"]):
            return jsonify({"reply":format_book_list(sorted(all_books,key=lambda b:b["year"] or 9999),"Here are the oldest books:")})

        # Exact book questions
        if exact:
            if is_location_question(user_message):
                return jsonify({"reply":f"📍 **{exact['title']}** is on shelf **{exact['shelf_location']}**.\nAvailable: {exact['available_copies']} / {exact['total_copies']} copies."})
            if is_availability_question(user_message):
                status="available" if exact["available_copies"]>0 else "currently unavailable"
                return jsonify({"reply":f"**{exact['title']}** is {status}.\nAvailable: {exact['available_copies']} / {exact['total_copies']} copies.\nShelf: {exact['shelf_location']}"})
            return jsonify({"reply":format_book_details(exact)})

        matching,info=natural_language_search(user_message)
        if matching:
            # availability-only filtering
            if is_availability_question(user_message) and not any(x in text for x in ["borrow","can i borrow"]):
                matching=[b for b in matching if b["available_copies"]>0]
            if not matching:
                return jsonify({"reply":"I found matching books, but none are currently available."})
            if len(matching)==1:
                return jsonify({"reply":format_book_details(matching[0])})
            return jsonify({"reply":format_book_list(matching,"Yes. I found these matching books in the library:")})

        # Flexible filters for language/publisher/year/copies/rating
        year_match=re.search(r"(?:after|since|from)\s+(\d{4})|(?:before|until)\s+(\d{4})|\b(19\d{2}|20\d{2})\b",text)
        language=None
        for lang in sorted({normalize(b["language"]) for b in all_books}, key=len, reverse=True):
            if lang and lang in text: language=lang; break
        publisher=None
        for pub in sorted({normalize(b["publisher"]) for b in all_books}, key=len, reverse=True):
            if pub and pub in text: publisher=pub; break
        filtered=all_books
        if language: filtered=[b for b in filtered if normalize(b["language"])==language]
        if publisher: filtered=[b for b in filtered if normalize(b["publisher"])==publisher]
        if year_match:
            year=int(next(g for g in year_match.groups() if g))
            if "after" in text or "since" in text or "from" in text: filtered=[b for b in filtered if (b["year"] or 0)>=year]
            elif "before" in text or "until" in text: filtered=[b for b in filtered if (b["year"] or 0)<=year]
            else: filtered=[b for b in filtered if b["year"]==year]
        if filtered != all_books and filtered:
            return jsonify({"reply":format_book_list(filtered,"Here are the matching books:")})

        # Gemini fallback, grounded in current DB
        if client is not None:
            library_data="\n".join([f"{b['book_id']} | {b['title']} | {b['author']} | {b['main_category']} | {b['sub_category']} | {b['isbn']} | {b['publisher']} | {b['year']} | {b['language']} | {b['edition']} | {b['available_copies']}/{b['total_copies']} | {b['shelf_location']} | {b['rating']} | {b['difficulty_level']} | {b['description']}" for b in all_books])
            prompt=f"""You are an AI Library Assistant. Answer the student using ONLY the library records below. Never invent books, ISBNs, authors, availability, shelves, ratings or other library facts. You may explain, summarize, recommend or compare books, but recommendations must come from the records. If the answer is not supported by the records, say so.\n\nLIBRARY RECORDS:\n{library_data}\n\nQUESTION:\n{user_message}"""
            try:
                response=client.models.generate_content(model="gemini-2.5-flash",contents=prompt)
                return jsonify({"reply":response.text})
            except Exception as e:
                print("Gemini Error:",repr(e),flush=True)

        return jsonify({"reply":"I couldn't find a matching book in the library. Try asking by title, author, topic, category, ISBN, publisher, year, shelf, rating, difficulty, or availability."})
    except Exception as e:
        print("Server Error:",repr(e),flush=True)
        return jsonify({"reply":"Something went wrong while processing your question."}),500

# ==========================================
# ADMIN PORTAL: BORROW / RETURN / ANALYTICS / AI / SETTINGS
# ==========================================

def init_admin_features():
    conn = get_db_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS library_settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    """)
    defaults = {
        "max_books_per_student": "3",
        "borrowing_period_days": "14",
        "overdue_grace_days": "0",
        "library_name": "AI Library Assistant",
        "ai_enabled": "1"
    }
    for key, value in defaults.items():
        conn.execute("INSERT OR IGNORE INTO library_settings (key,value) VALUES (?,?)", (key, value))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS ai_activity (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            message TEXT NOT NULL,
            intent TEXT NOT NULL DEFAULT 'general',
            created_at TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    """)
    conn.commit()
    conn.close()


def log_ai_activity(message):
    text = normalize(message)
    if any(x in text for x in ["borrow ", "i want to borrow", "let me borrow", "can i borrow"]):
        intent = "borrow"
    elif any(x in text for x in ["return ", "return my book", "give back"]):
        intent = "return"
    elif any(x in text for x in ["recommend", "suggest", "what should i read"]):
        intent = "recommendation"
    elif any(x in text for x in ["compare", "difference between", " versus ", " vs "]):
        intent = "comparison"
    elif any(x in text for x in ["my books", "borrowed books", "due dates", "when should i return"]):
        intent = "my_books"
    else:
        intent = "search"
    try:
        conn = get_db_connection()
        conn.execute("INSERT INTO ai_activity (user_id,message,intent,created_at) VALUES (?,?,?,datetime('now'))",
                     (session.get("user_id"), message[:500], intent))
        conn.commit()
        conn.close()
    except Exception as e:
        print("AI analytics log error:", repr(e), flush=True)


def admin_query_rows(status="all", search=""):
    conn = get_db_connection()
    where = []
    params = []
    if status == "active":
        where.append("br.status='borrowed'")
    elif status == "returned":
        where.append("br.status='returned'")
    elif status == "overdue":
        where.append("br.status='borrowed' AND date(br.due_date) < date('now', '-' || COALESCE((SELECT value FROM library_settings WHERE key='overdue_grace_days'),'0') || ' days')")
    if search:
        where.append("(u.name LIKE ? OR u.student_id LIKE ? OR b.book_id LIKE ? OR b.title LIKE ?)")
        q = f"%{search}%"
        params += [q, q, q, q]
    clause = (" WHERE " + " AND ".join(where)) if where else ""
    rows = conn.execute(f"""
        SELECT br.id, br.user_id, u.name AS student_name, u.student_id, u.email,
               br.book_id, b.title, b.author, b.shelf_location,
               br.borrowed_at, br.due_date, br.returned_at, br.status,
               CASE WHEN br.status='borrowed' AND date(br.due_date) < date('now', '-' || COALESCE((SELECT value FROM library_settings WHERE key='overdue_grace_days'),'0') || ' days')
                    THEN 1 ELSE 0 END AS overdue,
               CASE WHEN br.status='borrowed'
                    THEN CAST(julianday(br.due_date)-julianday(date('now')) AS INTEGER)
                    ELSE NULL END AS days_remaining
        FROM borrowings br
        JOIN users u ON u.id=br.user_id
        JOIN books b ON b.book_id=br.book_id
        {clause}
        ORDER BY br.id DESC
    """, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.route("/api/admin/borrowings")
def admin_borrowings_api():
    denied = admin_only()
    if denied:
        return denied
    status = request.args.get("status", "all").lower()
    if status not in {"all", "active", "returned", "overdue"}:
        status = "all"
    return jsonify(admin_query_rows(status, request.args.get("search", "").strip()))


@app.route("/api/admin/return/<int:borrowing_id>", methods=["POST"])
def admin_return_book(borrowing_id):
    denied = admin_only()
    if denied:
        return denied
    conn = get_db_connection()
    row = conn.execute("""SELECT br.*, b.title FROM borrowings br
                          JOIN books b ON b.book_id=br.book_id
                          WHERE br.id=?""", (borrowing_id,)).fetchone()
    if not row:
        conn.close()
        return jsonify({"error":"Borrowing record not found."}), 404
    if row["status"] != "borrowed":
        conn.close()
        return jsonify({"error":"This book has already been returned."}), 400
    from datetime import datetime
    returned_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn.execute("UPDATE borrowings SET status='returned', returned_at=? WHERE id=?", (returned_at, borrowing_id))
    conn.execute("UPDATE books SET available_copies=MIN(total_copies, available_copies+1) WHERE book_id=?", (row["book_id"],))
    conn.commit()
    conn.close()
    return jsonify({"success":True, "message":f"{row['title']} returned successfully."})


@app.route("/api/admin/analytics")
def admin_analytics_api():
    denied = admin_only()
    if denied:
        return denied
    conn = get_db_connection()
    counts = conn.execute("""
        SELECT
          (SELECT COUNT(*) FROM books) AS total_books,
          (SELECT COALESCE(SUM(total_copies),0) FROM books) AS total_copies,
          (SELECT COALESCE(SUM(available_copies),0) FROM books) AS available_copies,
          (SELECT COUNT(*) FROM borrowings WHERE status='borrowed') AS currently_borrowed,
          (SELECT COUNT(*) FROM borrowings WHERE status='returned') AS total_returns,
          (SELECT COUNT(*) FROM borrowings WHERE status='borrowed' AND date(due_date)<date('now', '-' || COALESCE((SELECT value FROM library_settings WHERE key='overdue_grace_days'),'0') || ' days')) AS overdue,
          (SELECT COUNT(*) FROM users WHERE role='student') AS students
    """).fetchone()
    popular_books = conn.execute("SELECT book_id,title,times_borrowed,rating FROM books ORDER BY times_borrowed DESC, rating DESC LIMIT 10").fetchall()
    active_students = conn.execute("""
        SELECT u.name,u.student_id,COUNT(br.id) total_borrowed,
               COALESCE(SUM(CASE WHEN br.status='borrowed' THEN 1 ELSE 0 END), 0) active_books
        FROM users u LEFT JOIN borrowings br ON br.user_id=u.id
        WHERE u.role='student' GROUP BY u.id ORDER BY total_borrowed DESC, u.name LIMIT 10
    """).fetchall()
    categories = conn.execute("SELECT COALESCE(main_category,'Uncategorized') category, COUNT(*) book_count, COALESCE(SUM(times_borrowed),0) borrow_count FROM books GROUP BY main_category ORDER BY borrow_count DESC LIMIT 10").fetchall()
    trends = conn.execute("""
        SELECT substr(borrowed_at,1,7) month, COUNT(*) borrow_count
        FROM borrowings GROUP BY substr(borrowed_at,1,7) ORDER BY month DESC LIMIT 12
    """).fetchall()
    ai_counts = conn.execute("SELECT COUNT(*) total_queries, SUM(CASE WHEN intent='borrow' THEN 1 ELSE 0 END) ai_borrows, SUM(CASE WHEN intent='return' THEN 1 ELSE 0 END) ai_returns, SUM(CASE WHEN intent='recommendation' THEN 1 ELSE 0 END) recommendations FROM ai_activity").fetchone()
    ai_intents = conn.execute("SELECT intent,COUNT(*) count FROM ai_activity GROUP BY intent ORDER BY count DESC").fetchall()
    ai_recent = conn.execute("""SELECT a.created_at,a.intent,a.message,u.name student_name,u.student_id
                              FROM ai_activity a LEFT JOIN users u ON u.id=a.user_id
                              ORDER BY a.id DESC LIMIT 15""").fetchall()
    conn.close()
    return jsonify({
        "counts": dict(counts),
        "popular_books": [dict(r) for r in popular_books],
        "active_students": [dict(r) for r in active_students],
        "categories": [dict(r) for r in categories],
        "trends": [dict(r) for r in reversed(trends)],
        "ai": dict(ai_counts),
        "ai_intents": [dict(r) for r in ai_intents],
        "ai_recent": [dict(r) for r in ai_recent]
    })


@app.route("/api/admin/settings", methods=["GET", "PUT"])
def admin_settings_api():
    denied = admin_only()
    if denied:
        return denied
    init_admin_features()
    conn = get_db_connection()
    if request.method == "GET":
        rows = conn.execute("SELECT key,value FROM library_settings ORDER BY key").fetchall()
        conn.close()
        data = {r["key"]: r["value"] for r in rows}
        data["ai_enabled"] = data.get("ai_enabled", "1") == "1"
        return jsonify(data)
    data = request.get_json(silent=True) or {}
    allowed = {"max_books_per_student","borrowing_period_days","overdue_grace_days","library_name","ai_enabled"}
    for key in allowed:
        if key in data:
            value = data[key]
            if key == "ai_enabled":
                value = "1" if bool(value) else "0"
            elif key in {"max_books_per_student","borrowing_period_days","overdue_grace_days"}:
                try:
                    value = str(max(0, int(value)))
                except (ValueError,TypeError):
                    conn.close()
                    return jsonify({"error":f"Invalid value for {key}."}),400
            else:
                value = str(value).strip()[:200]
            conn.execute("INSERT INTO library_settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key,value))
    conn.commit()
    rows = conn.execute("SELECT key,value FROM library_settings ORDER BY key").fetchall()
    conn.close()
    result = {r["key"]: r["value"] for r in rows}
    result["ai_enabled"] = result.get("ai_enabled", "1") == "1"
    return jsonify({"success":True,"settings":result})


init_admin_features()

# ==========================================
# RUN FLASK APPLICATION
# ==========================================

if __name__ == "__main__":

    app.run(
        debug=False,
        host="127.0.0.1",
        port=5000
    )