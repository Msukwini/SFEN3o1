import sqlite3
from datetime import datetime
import hashlib

def init_db():
    conn = sqlite3.connect('attendance.db')
    c = conn.cursor()
    
    c.execute('''CREATE TABLE IF NOT EXISTS students
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  name TEXT NOT NULL,
                  surname TEXT NOT NULL,
                  email TEXT UNIQUE NOT NULL,
                  course TEXT NOT NULL,
                  Faculty TEXT NOT NULL,
                  password TEXT NOT NULL,
                  face_image TEXT,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS lecturers
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  name TEXT NOT NULL,
                  surname TEXT NOT NULL,
                  email TEXT UNIQUE NOT NULL,
                  Faculty TEXT NOT NULL,
                  password TEXT NOT NULL,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS modules
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  name TEXT NOT NULL,
                  code TEXT UNIQUE NOT NULL,
                  Faculty TEXT NOT NULL,
                  lecturer_id INTEGER NOT NULL,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  FOREIGN KEY (lecturer_id) REFERENCES lecturers (id))''')
    
    # Student_modules table (many-to-many relationship)
    c.execute('''CREATE TABLE IF NOT EXISTS student_modules
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  student_id INTEGER NOT NULL,
                  module_id INTEGER NOT NULL,
                  final_mark REAL DEFAULT 0,
                  enrolled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  FOREIGN KEY (student_id) REFERENCES students (id),
                  FOREIGN KEY (module_id) REFERENCES modules (id))''')

    c.execute('''CREATE TABLE IF NOT EXISTS sessions
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  module_id INTEGER NOT NULL,
                  session_date TEXT NOT NULL,
                  start_time TEXT NOT NULL,
                  end_time TEXT NOT NULL,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  FOREIGN KEY (module_id) REFERENCES modules (id))''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS attendance
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  student_id INTEGER NOT NULL,
                  module_id INTEGER NOT NULL,
                  session_id INTEGER NOT NULL,
                  status TEXT DEFAULT 'Absent',
                  attendance_time TIMESTAMP,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  FOREIGN KEY (student_id) REFERENCES students (id),
                  FOREIGN KEY (module_id) REFERENCES modules (id),
                  FOREIGN KEY (session_id) REFERENCES sessions (id))''')
    
    conn.commit()
    conn.close()

def update_db():
    """Update existing database to add the face_image column to students table and final_mark to student_modules"""
    conn = sqlite3.connect('attendance.db')
    c = conn.cursor()
    
    try:
        # Check if face_image column exists in students
        c.execute("PRAGMA table_info(students)")
        columns = [column[1] for column in c.fetchall()]
        
        if 'face_image' not in columns:
            c.execute("ALTER TABLE students ADD COLUMN face_image TEXT")
            print("Added face_image column to students table")
        
        # Check if final_mark column exists in student_modules
        c.execute("PRAGMA table_info(student_modules)")
        columns = [column[1] for column in c.fetchall()]
        
        if 'final_mark' not in columns:
            c.execute("ALTER TABLE student_modules ADD COLUMN final_mark REAL DEFAULT 0")
            print("Added final_mark column to student_modules table")
        
        conn.commit()
    except Exception as e:
        print(f"Error updating database: {e}")
    finally:
        conn.close()

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

if __name__ == '__main__':
    init_db()
    update_db()
    print("Database initialized and updated successfully!")