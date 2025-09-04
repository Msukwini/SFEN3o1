from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
import sqlite3
from datetime import datetime, time
import re
import cv2
import numpy as np
from deepface import DeepFace
import os
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'

UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def get_db_connection():
    conn = sqlite3.connect('attendance.db')
    conn.row_factory = sqlite3.Row
    return conn

def validate_student_email(email):
    """Validate student email format: 8 digits followed by @dut4life.ac.za"""
    pattern = r'^\d{8}@dut4life\.ac\.za$'
    return bool(re.match(pattern, email))

def validate_lecturer_email(email):
    """Validate lecturer email format: must end with @dut.ac.za"""
    pattern = r'^[a-zA-Z0-9._%+-]+@dut\.ac\.za$'
    return bool(re.match(pattern, email))

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def hash_password(password):
    import hashlib
    return hashlib.sha256(password.encode()).hexdigest()

def verify_face(image_path, student_id):
    """Compare uploaded face with registered face in database"""
    try:
        # Get the registered face path from database
        conn = get_db_connection()
        student = conn.execute('SELECT face_image FROM students WHERE id = ?', (student_id,)).fetchone()
        conn.close()
        
        if not student or not student['face_image']:
            return False, "No registered face found"
        
        # Check if registered face image exists
        if not os.path.exists(student['face_image']):
            return False, "Registered face image not found"
        
        # Check if uploaded image exists
        if not os.path.exists(image_path):
            return False, "Uploaded image not found"
        
        try:
            result = DeepFace.verify(
                img1_path=student['face_image'], 
                img2_path=image_path,
                model_name='VGG-Face',
                detector_backend='opencv' 
            )
            return result['verified'], f"Distance: {result['distance']:.4f}"
        except Exception as e:
            return False, f"Face comparison error: {str(e)}"
            
    except Exception as e:
        return False, f"Verification error: {str(e)}"

def has_face_image(student_id):
    """Check if student has a face image registered"""
    conn = get_db_connection()
    student = conn.execute('SELECT face_image FROM students WHERE id = ?', (student_id,)).fetchone()
    conn.close()
    
    if student and student['face_image']:
        # Check if the file actually exists
        return os.path.exists(student['face_image'])
    return False

@app.route('/')
def index():
    return render_template('index.html')

# Login page
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user_type = request.form['user_type']
        
        conn = get_db_connection()
        
        if user_type == 'student':
            if not validate_student_email(email):
                flash('Invalid student email format. Must be 8 digits followed by @dut4life.ac.za (e.g., 12345678@dut4life.ac.za)', 'error')
                return render_template('login.html')
            
            user = conn.execute('SELECT * FROM students WHERE email = ?', (email,)).fetchone()
            dashboard_route = 'student_dashboard'
        
        else:  
            if not validate_lecturer_email(email):
                flash('Invalid lecturer email format. Must end with @dut.ac.za (e.g., john.doe@dut.ac.za)', 'error')
                return render_template('login.html')
            
            user = conn.execute('SELECT * FROM lecturers WHERE email = ?', (email,)).fetchone()
            dashboard_route = 'lecturer_dashboard'
        
        conn.close()
        
        if user and user['password'] == hash_password(password):
            session['user_id'] = user['id']
            session['user_type'] = user_type
            session['name'] = user['name']
            session['email'] = user['email']
            
            flash('Login successful!', 'success')
            return redirect(url_for(dashboard_route))
        else:
            flash('Invalid email or password', 'error')
    
    return render_template('login.html')

# Registration page
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        user_type = request.form['user_type']
        name = request.form['name']
        surname = request.form['surname']
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        
        if password != confirm_password:
            flash('Passwords do not match', 'error')
            return render_template('register.html')
        
        conn = get_db_connection()
        
        if user_type == 'student':
            course = request.form['course']
            Faculty = request.form['Faculty']

            if not validate_student_email(email):
                flash('Invalid student email format. Must be 8 digits followed by @dut4life.ac.za (e.g., 12345678@dut4life.ac.za)', 'error')
                return render_template('register.html')
            
            # Handle face image upload
            face_image_path = None
            if 'face_image' in request.files:
                file = request.files['face_image']
                if file and allowed_file(file.filename):
                    filename = secure_filename(f"student_{email}_{file.filename}")
                    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                    file.save(filepath)
                    face_image_path = filepath
            
            try:
                conn.execute('INSERT INTO students (name, surname, email, course, Faculty, password, face_image) VALUES (?, ?, ?, ?, ?, ?, ?)',
                             (name, surname, email, course, Faculty, hash_password(password), face_image_path))
                conn.commit()
                flash('Student registration successful! Please login.', 'success')
            except sqlite3.IntegrityError:
                flash('Email already exists!', 'error')
        
        else:  # lecturer
            Faculty = request.form['Faculty']
            
            if not validate_lecturer_email(email):
                flash('Invalid lecturer email format. Must end with @dut.ac.za (e.g., john.doe@dut.ac.za)', 'error')
                return render_template('register.html')
            
            try:
                conn.execute('INSERT INTO lecturers (name, surname, email, Faculty, password) VALUES (?, ?, ?, ?, ?)',
                             (name, surname, email, Faculty, hash_password(password)))
                conn.commit()
                flash('Lecturer registration successful! Please login.', 'success')
            except sqlite3.IntegrityError:
                flash('Email already exists!', 'error')
        
        conn.close()
        return redirect(url_for('login'))
    
    return render_template('register.html')

# Upload face image for student
@app.route('/upload_face', methods=['GET', 'POST'])
def upload_face():
    if 'user_id' not in session or session['user_type'] != 'student':
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        if 'face_image' not in request.files:
            flash('No image uploaded', 'error')
            return redirect(url_for('upload_face'))
        
        file = request.files['face_image']
        if file.filename == '':
            flash('No image selected', 'error')
            return redirect(url_for('upload_face'))
        
        if file and allowed_file(file.filename):
            filename = secure_filename(f"student_{session['email']}_{file.filename}")
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            
            # Update student record with face image path
            conn = get_db_connection()
            conn.execute('UPDATE students SET face_image = ? WHERE id = ?', 
                         (filepath, session['user_id']))
            conn.commit()
            conn.close()
            
            flash('Face image uploaded successfully!', 'success')
            return redirect(url_for('student_dashboard'))
    
    return render_template('upload_face.html')


@app.route('/lecturer/dashboard')
def lecturer_dashboard():
    if 'user_id' not in session or session['user_type'] != 'lecturer':
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    modules = conn.execute('SELECT * FROM modules WHERE lecturer_id = ?', (session['user_id'],)).fetchall()
    conn.close()
    
    return render_template('lecturer_dashboard.html', modules=modules)

@app.route('/student/dashboard')
def student_dashboard():
    if 'user_id' not in session or session['user_type'] != 'student':
        return redirect(url_for('login'))
    
    
    if not has_face_image(session['user_id']):
        flash('Please register your face image for attendance marking.', 'warning')
        return redirect(url_for('upload_face'))
    
    conn = get_db_connection()

    modules = conn.execute('''
        SELECT m.*, 
               (SELECT COUNT(*) FROM sessions WHERE module_id = m.id) as total_sessions,
               COUNT(a.id) as attended_sessions
        FROM modules m
        JOIN student_modules sm ON m.id = sm.module_id
        LEFT JOIN attendance a ON m.id = a.module_id AND a.student_id = ? AND a.status = 'Present'
        WHERE sm.student_id = ?
        GROUP BY m.id
    ''', (session['user_id'], session['user_id'])).fetchall()
    
    conn.close()
    
    return render_template('student_dashboard.html', modules=modules)

# Add Module (Lecturer)
@app.route('/add_module', methods=['GET', 'POST'])
def add_module():
    if 'user_id' not in session or session['user_type'] != 'lecturer':
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        name = request.form['name']
        code = request.form['code']
        Faculty = request.form['Faculty']
        
        conn = get_db_connection()
        try:
            conn.execute('INSERT INTO modules (name, code, Faculty, lecturer_id) VALUES (?, ?, ?, ?)',
                         (name, code, Faculty, session['user_id']))
            conn.commit()
            flash('Module added successfully!', 'success')
        except sqlite3.IntegrityError:
            flash('Module code already exists!', 'error')
        conn.close()
        
        return redirect(url_for('lecturer_dashboard'))
    
    return render_template('add_module.html')

# Module Detail (Lecturer)
@app.route('/module/<int:module_id>')
def module_detail(module_id):
    if 'user_id' not in session or session['user_type'] != 'lecturer':
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    
    # Get module details
    module = conn.execute('SELECT * FROM modules WHERE id = ?', (module_id,)).fetchone()

    students = conn.execute('''
        SELECT s.*, sm.final_mark,
               (SELECT COUNT(*) FROM sessions WHERE module_id = ?) as total_sessions,
               COUNT(a.id) as attended_sessions
        FROM students s
        JOIN student_modules sm ON s.id = sm.student_id
        LEFT JOIN attendance a ON s.id = a.student_id AND a.module_id = ? AND a.status = 'Present'
        WHERE sm.module_id = ?
        GROUP BY s.id
    ''', (module_id, module_id, module_id)).fetchall()

    sessions = conn.execute('SELECT * FROM sessions WHERE module_id = ? ORDER BY session_date DESC, start_time DESC', (module_id,)).fetchall()
    
    conn.close()
    
    return render_template('module_detail.html', module=module, students=students, sessions=sessions)

# Update final mark for a student
@app.route('/module/<int:module_id>/update_mark/<int:student_id>', methods=['POST'])
def update_final_mark(module_id, student_id):
    if 'user_id' not in session or session['user_type'] != 'lecturer':
        return redirect(url_for('login'))
    
    try:
        final_mark = float(request.form['final_mark'])

        if not 0 <= final_mark <= 100:
            flash('Final mark must be between 0 and 100', 'error')
            return redirect(url_for('module_detail', module_id=module_id))
        
        conn = get_db_connection()
        conn.execute('UPDATE student_modules SET final_mark = ? WHERE student_id = ? AND module_id = ?',
                     (final_mark, student_id, module_id))
        conn.commit()
        conn.close()
        
        flash('Final mark updated successfully!', 'success')
    except ValueError:
        flash('Please enter a valid number for the final mark', 'error')
    
    return redirect(url_for('module_detail', module_id=module_id))

# Add Student to Module (Lecturer)
@app.route('/module/<int:module_id>/add_student', methods=['POST'])
def add_student_to_module(module_id):
    if 'user_id' not in session or session['user_type'] != 'lecturer':
        return redirect(url_for('login'))
    
    student_email = request.form['student_email']

    if not validate_student_email(student_email):
        flash('Invalid student email format. Must be 8 digits followed by @dut4life.ac.za', 'error')
        return redirect(url_for('module_detail', module_id=module_id))
    
    conn = get_db_connection()
    
    # Check if student exists
    student = conn.execute('SELECT * FROM students WHERE email = ?', (student_email,)).fetchone()
    
    if not student:
        flash('Student with this email does not exist!', 'error')
    else:
        # Check if student is already enrolled
        existing = conn.execute('SELECT * FROM student_modules WHERE student_id = ? AND module_id = ?', 
                               (student['id'], module_id)).fetchone()
        
        if existing:
            flash('Student is already enrolled in this module!', 'error')
        else:
            # Enroll student
            conn.execute('INSERT INTO student_modules (student_id, module_id) VALUES (?, ?)',
                         (student['id'], module_id))
            conn.commit()
            flash('Student added to module successfully!', 'success')
    
    conn.close()
    return redirect(url_for('module_detail', module_id=module_id))

# Create Session (Lecturer)
@app.route('/module/<int:module_id>/create_session', methods=['GET', 'POST'])
def create_session(module_id):
    if 'user_id' not in session or session['user_type'] != 'lecturer':
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        session_date = request.form['session_date']
        start_time = request.form['start_time']
        end_time = request.form['end_time']
        
        conn = get_db_connection()
        conn.execute('INSERT INTO sessions (module_id, session_date, start_time, end_time) VALUES (?, ?, ?, ?)',
                     (module_id, session_date, start_time, end_time))
        conn.commit()
        conn.close()
        
        flash('Session created successfully!', 'success')
        return redirect(url_for('module_detail', module_id=module_id))
    
    return render_template('create_session.html', module_id=module_id)

@app.route('/student/module/<int:module_id>')
def student_module(module_id):
    if 'user_id' not in session or session['user_type'] != 'student':
        return redirect(url_for('login'))

    if not has_face_image(session['user_id']):
        flash('Please register your face image for attendance marking.', 'warning')
        return redirect(url_for('upload_face'))
    
    conn = get_db_connection()
    
    enrollment = conn.execute('SELECT * FROM student_modules WHERE student_id = ? AND module_id = ?', 
                             (session['user_id'], module_id)).fetchone()
    
    if not enrollment:
        flash('You are not enrolled in this module!', 'error')
        return redirect(url_for('student_dashboard'))

    module = conn.execute('SELECT * FROM modules WHERE id = ?', (module_id,)).fetchone()
    
    attendance = conn.execute('''
        SELECT s.id, s.session_date, s.start_time, s.end_time, a.status, a.attendance_time
        FROM sessions s
        LEFT JOIN attendance a ON s.id = a.session_id AND a.student_id = ?
        WHERE s.module_id = ?
        ORDER BY s.session_date DESC, s.start_time DESC
    ''', (session['user_id'], module_id)).fetchall()

    attendance_stats = conn.execute('''
        SELECT 
            (SELECT COUNT(*) FROM sessions WHERE module_id = ?) as total_sessions,
            COUNT(a.id) as attended_sessions
        FROM attendance a
        JOIN sessions s ON a.session_id = s.id
        WHERE a.student_id = ? AND s.module_id = ? AND a.status = 'Present'
    ''', (module_id, session['user_id'], module_id)).fetchone()
    
    conn.close()
    
    return render_template('student_module.html', module=module, attendance=attendance, attendance_stats=attendance_stats)

@app.route('/mark_attendance/<int:module_id>/<int:session_id>')
def mark_attendance_page(module_id, session_id):
    if 'user_id' not in session or session['user_type'] != 'student':
        return redirect(url_for('login'))

    if not has_face_image(session['user_id']):
        flash('Please register your face image for attendance marking.', 'warning')
        return redirect(url_for('upload_face'))
    
    conn = get_db_connection()
    
    existing = conn.execute('SELECT * FROM attendance WHERE student_id = ? AND session_id = ?', 
                           (session['user_id'], session_id)).fetchone()
    
    if existing:
        flash('Attendance already marked for this session!', 'info')
        conn.close()
        return redirect(url_for('student_module', module_id=module_id))
    
    session_details = conn.execute('SELECT * FROM sessions WHERE id = ?', (session_id,)).fetchone()
    conn.close()
    
    if not session_details:
        flash('Session not found!', 'error')
        return redirect(url_for('student_module', module_id=module_id))
    
    current_datetime = datetime.now()
    session_date = datetime.strptime(session_details['session_date'], '%Y-%m-%d').date()
    session_start = datetime.strptime(session_details['start_time'], '%H:%M').time()
    session_end = datetime.strptime(session_details['end_time'], '%H:%M').time()
    
    if current_datetime.date() != session_date:
        flash('Attendance can only be marked on the session date!', 'error')
        return redirect(url_for('student_module', module_id=module_id))
    
    current_time = current_datetime.time()
    if not (session_start <= current_time <= session_end):
        flash('Attendance can only be marked during the session time!', 'error')
        return redirect(url_for('student_module', module_id=module_id))
    
    return render_template('mark_attendance.html', module_id=module_id, session_id=session_id)

@app.route('/process_attendance/<int:module_id>/<int:session_id>', methods=['POST'])
def process_attendance(module_id, session_id):
    if 'user_id' not in session or session['user_type'] != 'student':
        return jsonify({'success': False, 'message': 'Not authorized'})
    
    if 'face_image' not in request.files:
        return jsonify({'success': False, 'message': 'No image uploaded'})
    
    file = request.files['face_image']
    if file.filename == '':
        return jsonify({'success': False, 'message': 'No image selected'})
    
    if file and allowed_file(file.filename):
        filename = secure_filename(f"attendance_{session['user_id']}_{session_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg")
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        is_verified, result = verify_face(filepath, session['user_id'])
        
        if is_verified:
            
            conn = get_db_connection()
            conn.execute('INSERT INTO attendance (student_id, module_id, session_id, status, attendance_time) VALUES (?, ?, ?, ?, ?)',
                         (session['user_id'], module_id, session_id, 'Present', datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
            conn.commit()
            conn.close()
            
            os.remove(filepath)
            
            return jsonify({'success': True, 'message': 'Attendance marked successfully!'})
        else:
           
            os.remove(filepath)
            return jsonify({'success': False, 'message': f'Face verification failed. Please try again. (Error: {result})'})
    
    return jsonify({'success': False, 'message': 'Invalid file format'})


@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out successfully.', 'info')
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)