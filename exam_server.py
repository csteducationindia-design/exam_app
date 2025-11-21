import sqlite3
import os
import json
import uuid
from flask import Flask, request, jsonify, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta

# Determine the directory of the script to make file paths reliable
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Create a 'data' folder if it doesn't exist
DATA_DIR = os.path.join(SCRIPT_DIR, 'data')
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

# Save the database INSIDE the data folder
DATABASE_PATH = os.path.join(DATA_DIR, 'exam_data.db')
STATIC_DIR = os.path.join(SCRIPT_DIR, 'static')

app = Flask(__name__, static_url_path='/static', static_folder=STATIC_DIR)

def get_db_connection():
    """Establishes a connection to the database."""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initializes the database with all necessary tables."""
    conn = get_db_connection()
    c = conn.cursor()

    # Create teachers table
    c.execute('''
        CREATE TABLE IF NOT EXISTS teachers (
            teacher_id TEXT PRIMARY KEY,
            password_hash TEXT NOT NULL
        )
    ''')

    # Create students table
    c.execute('''
        CREATE TABLE IF NOT EXISTS students (
            student_id TEXT PRIMARY KEY,
            teacher_id TEXT NOT NULL,
            student_name TEXT NOT NULL,
            FOREIGN KEY (teacher_id) REFERENCES teachers(teacher_id)
        )
    ''')
    
    # Create questions table
    c.execute('''
        CREATE TABLE IF NOT EXISTS questions (
            exam_id TEXT NOT NULL,
            teacher_id TEXT NOT NULL,
            question_text TEXT NOT NULL,
            correct_option TEXT NOT NULL,
            options TEXT NOT NULL,
            exam_title TEXT NOT NULL,
            school_name TEXT,
            duration INTEGER,
            allowed_attempts INTEGER,
            passing_percentage REAL,
            image_url TEXT,
            enable_analysis_report INTEGER,
            PRIMARY KEY (exam_id, question_text),
            FOREIGN KEY (teacher_id) REFERENCES teachers(teacher_id)
        )
    ''')

    # Create results table
    c.execute('''
        CREATE TABLE IF NOT EXISTS results (
            result_id TEXT PRIMARY KEY,
            exam_id TEXT NOT NULL,
            student_id TEXT NOT NULL,
            teacher_id TEXT NOT NULL,
            student_name TEXT NOT NULL,
            score INTEGER NOT NULL,
            answers TEXT NOT NULL,
            submission_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Create in-progress exams table
    c.execute('''
        CREATE TABLE IF NOT EXISTS in_progress_exams (
            student_id TEXT NOT NULL,
            exam_id TEXT NOT NULL,
            teacher_id TEXT NOT NULL,
            answers TEXT NOT NULL,
            question_status TEXT NOT NULL,
            time_left INTEGER NOT NULL,
            PRIMARY KEY (student_id, exam_id)
        )
    ''')

    conn.commit()
    conn.close()

# API Endpoints

@app.route('/')
def serve_admin_portal():
    """Serves the main Admin/Teacher portal page."""
    return send_from_directory(STATIC_DIR, 'admin_teacher_portal.html')

@app.route('/static/student_exam_client.html')
def serve_student_client():
    """Serves the student exam client page."""
    return send_from_directory(STATIC_DIR, 'student_exam_client.html')

@app.route('/api/register/teacher', methods=['POST'])
def register_teacher():
    """Registers a new teacher."""
    data = request.json
    teacher_id = data.get('teacher_id')
    password = data.get('password')

    if not teacher_id or not password:
        return jsonify({'message': 'Teacher ID and password are required'}), 400

    conn = get_db_connection()
    try:
        c = conn.cursor()
        c.execute('SELECT 1 FROM teachers WHERE teacher_id = ?', (teacher_id,))
        if c.fetchone():
            return jsonify({'message': 'Teacher ID already exists'}), 409
        
        password_hash = generate_password_hash(password)
        c.execute('INSERT INTO teachers (teacher_id, password_hash) VALUES (?, ?)', (teacher_id, password_hash))
        conn.commit()
        return jsonify({'message': 'Teacher registered successfully'}), 201
    except sqlite3.IntegrityError:
        return jsonify({'message': 'Teacher ID already exists'}), 409
    finally:
        conn.close()

@app.route('/api/login/teacher', methods=['POST'])
def login_teacher():
    """Authenticates a teacher."""
    data = request.json
    teacher_id = data.get('teacher_id')
    password = data.get('password')

    if not teacher_id or not password:
        return jsonify({'message': 'Teacher ID and password are required'}), 400

    conn = get_db_connection()
    try:
        c = conn.cursor()
        c.execute('SELECT password_hash FROM teachers WHERE teacher_id = ?', (teacher_id,))
        teacher = c.fetchone()
        
        if teacher and check_password_hash(teacher['password_hash'], password):
            return jsonify({'message': 'Login successful'}), 200
        else:
            return jsonify({'message': 'Invalid Teacher ID or password'}), 401
    finally:
        conn.close()
    
@app.route('/api/students/bulk-upload-csv', methods=['POST'])
def bulk_upload_students():
    """Uploads a list of students from a CSV file."""
    data = request.json
    teacher_id = data.get('teacher_id')
    students_list = data.get('students')
    
    if not teacher_id or not students_list:
        return jsonify({'message': 'Invalid data'}), 400

    conn = get_db_connection()
    c = conn.cursor()
    
    try:
        for student in students_list:
            c.execute('INSERT OR IGNORE INTO students (student_id, teacher_id, student_name) VALUES (?, ?, ?)',
                      (student['student_id'], teacher_id, student['student_name']))
        conn.commit()
        return jsonify({'message': f'Successfully uploaded {len(students_list)} students.'}), 200
    except Exception as e:
        return jsonify({'message': f'An error occurred: {str(e)}'}), 500
    finally:
        conn.close()

@app.route('/api/student/create', methods=['POST'])
def create_single_student():
    """Creates a single student entry."""
    data = request.json
    teacher_id = data.get('teacher_id')
    student_id = data.get('student_id')
    student_name = data.get('student_name')
    
    if not teacher_id or not student_id or not student_name:
        return jsonify({'message': 'Invalid data. Teacher ID, Student ID, and Student Name are required.'}), 400

    conn = get_db_connection()
    c = conn.cursor()

    try:
        c.execute('INSERT OR IGNORE INTO students (student_id, teacher_id, student_name) VALUES (?, ?, ?)', (student_id, teacher_id, student_name))
        conn.commit()
        if c.rowcount == 0:
            return jsonify({'message': 'Student ID already exists.'}), 409
        return jsonify({'message': 'Student created successfully.'}), 201
    except Exception as e:
        return jsonify({'message': f'An error occurred: {str(e)}'}), 500
    finally:
        conn.close()

@app.route('/api/student/delete', methods=['DELETE'])
def delete_student():
    """Deletes a student entry."""
    data = request.json
    teacher_id = data.get('teacher_id')
    student_id = data.get('student_id')

    conn = get_db_connection()
    c = conn.cursor()
    try:
        c.execute('DELETE FROM students WHERE student_id = ? AND teacher_id = ?', (student_id, teacher_id))
        conn.commit()
        if c.rowcount == 0:
            return jsonify({'message': 'Student not found or not authorized to delete.'}), 404
        return jsonify({'message': 'Student deleted successfully.'}), 200
    except Exception as e:
        return jsonify({'message': f'An error occurred: {str(e)}'}), 500
    finally:
        conn.close()

@app.route('/api/student/update', methods=['PUT'])
def update_student():
    """Updates a student's ID and name."""
    data = request.json
    teacher_id = data.get('teacher_id')
    old_student_id = data.get('old_student_id')
    new_student_id = data.get('new_student_id')
    student_name = data.get('student_name')

    if not all([teacher_id, old_student_id, new_student_id, student_name]):
        return jsonify({'message': 'Invalid data'}), 400

    conn = get_db_connection()
    c = conn.cursor()
    try:
        c.execute('UPDATE students SET student_id = ?, student_name = ? WHERE student_id = ? AND teacher_id = ?',
                  (new_student_id, student_name, old_student_id, teacher_id))
        conn.commit()
        if c.rowcount == 0:
            return jsonify({'message': 'Student not found or not authorized to update.'}), 404
        return jsonify({'message': 'Student updated successfully.'}), 200
    except Exception as e:
        return jsonify({'message': f'An error occurred: {str(e)}'}), 500
    finally:
        conn.close()

@app.route('/api/students/<teacher_id>', methods=['GET'])
def get_students_by_teacher(teacher_id):
    """Retrieves all students for a specific teacher."""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('SELECT student_id, student_name FROM students WHERE teacher_id = ?', (teacher_id,))
    students = c.fetchall()
    conn.close()
    return jsonify([dict(row) for row in students]), 200

@app.route('/api/students/by-id', methods=['POST'])
def get_student_by_id():
    """Retrieves a student's name by their ID."""
    data = request.json
    student_id = data.get('student_id')
    if not student_id:
        return jsonify({'message': 'Student ID is required'}), 400

    conn = get_db_connection()
    try:
        c = conn.cursor()
        c.execute('SELECT student_name, teacher_id FROM students WHERE student_id = ?', (student_id,))
        student = c.fetchone()
        if student:
            return jsonify({'student_name': student['student_name'], 'teacher_id': student['teacher_id']}), 200
        else:
            return jsonify({'message': 'Student ID not found'}), 404
    finally:
        conn.close()

@app.route('/api/questions/bulk-upload-csv', methods=['POST'])
def bulk_upload_questions():
    """Bulk uploads questions from a CSV format."""
    data = request.json
    teacher_id = data.get('teacher_id')
    exam_id = data.get('exam_id')
    questions = data.get('questions')
    
    if not teacher_id or not exam_id or not questions:
        return jsonify({'message': 'Invalid data provided.'}), 400

    conn = get_db_connection()
    c = conn.cursor()

    try:
        c.execute('SELECT exam_title, school_name, duration, allowed_attempts, passing_percentage, enable_analysis_report FROM questions WHERE exam_id = ? AND teacher_id = ? AND question_text = "placeholder" LIMIT 1', (exam_id, teacher_id))
        exam_settings = c.fetchone()
        if not exam_settings:
            return jsonify({'message': 'Exam settings not found. Please save exam settings first.'}), 404
        
        exam_title = exam_settings['exam_title']
        school_name = exam_settings['school_name']
        duration = exam_settings['duration']
        attempts = exam_settings['allowed_attempts']
        passing_percentage = exam_settings['passing_percentage']
        enable_analysis_report = exam_settings['enable_analysis_report']

        for q in questions:
            q_options_json = json.dumps(q['options'])
            c.execute('''
                INSERT OR REPLACE INTO questions (exam_id, teacher_id, question_text, correct_option, options, exam_title, school_name, duration, allowed_attempts, passing_percentage, image_url, enable_analysis_report)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (exam_id, teacher_id, q['question_text'], q['correct_option'], q_options_json, exam_title, school_name, duration, attempts, passing_percentage, q.get('image_url'), enable_analysis_report))

        conn.commit()
        return jsonify({'message': f'Successfully uploaded {len(questions)} questions.'}), 200
    except Exception as e:
        return jsonify({'message': f'An error occurred: {str(e)}'}), 500
    finally:
        conn.close()

@app.route('/api/questions/single-upload', methods=['POST'])
def single_upload_question():
    """Saves or updates a single question."""
    data = request.json
    teacher_id = data.get('teacher_id')
    exam_id = data.get('exam_id')
    question_text = data.get('question_text')
    original_question_text = data.get('original_question_text')
    correct_option = data.get('correct_option')
    options = data.get('options')
    image_url = data.get('image_url')
    
    if not all([teacher_id, exam_id, question_text, correct_option, options]):
        return jsonify({'message': 'All required fields are missing.'}), 400
        
    conn = get_db_connection()
    c = conn.cursor()
    
    try:
        c.execute('SELECT exam_title, school_name, duration, allowed_attempts, passing_percentage, enable_analysis_report FROM questions WHERE exam_id = ? AND teacher_id = ? AND question_text = "placeholder" LIMIT 1', (exam_id, teacher_id))
        exam_settings = c.fetchone()
        if not exam_settings:
            return jsonify({'message': 'Exam settings not found. Please save exam settings first.'}), 404

        # If it's an update and the question text has changed, delete the old one first
        if original_question_text and original_question_text != question_text:
            c.execute('DELETE FROM questions WHERE teacher_id = ? AND exam_id = ? AND question_text = ?', (teacher_id, exam_id, original_question_text))
            
        c.execute('''
            INSERT OR REPLACE INTO questions (exam_id, teacher_id, question_text, correct_option, options, exam_title, school_name, duration, allowed_attempts, passing_percentage, image_url, enable_analysis_report)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (exam_id, teacher_id, question_text, correct_option, json.dumps(options), exam_settings['exam_title'], exam_settings['school_name'], exam_settings['duration'], exam_settings['allowed_attempts'], exam_settings['passing_percentage'], image_url, exam_settings['enable_analysis_report']))
        conn.commit()
        return jsonify({'message': 'Question saved/updated successfully.'}), 200
    except Exception as e:
        return jsonify({'message': f'An error occurred: {str(e)}'}), 500
    finally:
        conn.close()


@app.route('/api/exams/settings', methods=['POST'])
def save_exam_settings():
    """Saves exam metadata."""
    data = request.json
    teacher_id = data.get('teacher_id')
    exam_id = data.get('exam_id')
    exam_title = data.get('exam_title')
    school_name = data.get('school_name')
    duration = data.get('duration')
    attempts = data.get('attempts')
    passing_percentage = data.get('passing_percentage')
    enable_analysis_report = data.get('enable_analysis_report', False)
    
    if not all([teacher_id, exam_id, exam_title, school_name, duration, attempts, passing_percentage is not None]):
        return jsonify({'message': 'All fields are required.'}), 400

    conn = get_db_connection()
    c = conn.cursor()
    
    try:
        c.execute('SELECT 1 FROM questions WHERE exam_id = ? AND teacher_id = ? AND question_text = "placeholder"', (exam_id, teacher_id))
        if c.fetchone():
            c.execute('''
                UPDATE questions SET exam_title = ?, school_name = ?, duration = ?, allowed_attempts = ?, passing_percentage = ?, enable_analysis_report = ?
                WHERE exam_id = ? AND teacher_id = ? AND question_text = "placeholder"
            ''', (exam_title, school_name, duration, attempts, passing_percentage, 1 if enable_analysis_report else 0, exam_id, teacher_id))
        else:
            c.execute('''
                INSERT INTO questions (exam_id, teacher_id, exam_title, school_name, duration, allowed_attempts, passing_percentage, enable_analysis_report, question_text, correct_option, options)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'placeholder', 'A', '{}')
            ''', (exam_id, teacher_id, exam_title, school_name, duration, attempts, passing_percentage, 1 if enable_analysis_report else 0))
            
        conn.commit()
        return jsonify({'message': 'Exam settings saved successfully.'}), 200
    except Exception as e:
        return jsonify({'message': f'An error occurred: {str(e)}'}), 500
    finally:
        conn.close()


@app.route('/api/exam/start', methods=['POST'])
def check_exam_eligibility():
    """Checks if a student is eligible to take an exam."""
    data = request.json
    student_id = data.get('student_id')
    exam_id = data.get('exam_id')

    conn = get_db_connection()
    try:
        c = conn.cursor()
        
        c.execute('SELECT teacher_id FROM questions WHERE exam_id = ? LIMIT 1', (exam_id,))
        exam_teacher = c.fetchone()
        if not exam_teacher:
            return jsonify({'message': 'Exam not found.'}), 404
        
        c.execute('SELECT 1 FROM students WHERE student_id = ? AND teacher_id = ?', (student_id, exam_teacher['teacher_id']))
        if not c.fetchone():
            return jsonify({'message': 'Student ID not found or not associated with this exam.'}), 404

        c.execute('''
            SELECT exam_title, school_name, duration, allowed_attempts, passing_percentage, enable_analysis_report
            FROM questions WHERE exam_id = ? LIMIT 1
        ''', (exam_id,))
        exam_settings = c.fetchone()

        if not exam_settings:
            return jsonify({'message': 'Could not retrieve exam settings.'}), 404

        allowed_attempts = exam_settings['allowed_attempts']
        
        c.execute('SELECT COUNT(*) as num_attempts FROM results WHERE student_id = ? AND exam_id = ?', (student_id, exam_id))
        attempts_taken = c.fetchone()['num_attempts']
        
        if attempts_taken >= allowed_attempts:
            return jsonify({'message': f'You have already taken this exam {attempts_taken} times. No more attempts remaining.'}), 403

        c.execute('SELECT student_name, teacher_id FROM students WHERE student_id = ?', (student_id,))
        student_data = c.fetchone()
        
        c.execute('SELECT question_text, options, image_url FROM questions WHERE exam_id = ? AND question_text != "placeholder"', (exam_id,))
        exam_data_rows = c.fetchall()

        if not exam_data_rows:
            return jsonify({'message': 'This exam has no questions. Please contact your teacher.'}), 404
        
        questions_list = []
        for q in exam_data_rows:
            questions_list.append({
                'question_text': q['question_text'],
                'options': json.loads(q['options']),
                'image_url': q['image_url']
            })

        import random
        random.shuffle(questions_list)
        
        c.execute('SELECT answers, time_left, question_status FROM in_progress_exams WHERE student_id = ? AND exam_id = ?', (student_id, exam_id))
        in_progress_data = c.fetchone()

        exam_data = {
            'exam_title': exam_settings['exam_title'],
            'school_name': exam_settings['school_name'],
            'duration': exam_settings['duration'],
            'allowed_attempts': exam_settings['allowed_attempts'],
            'passing_percentage': exam_settings['passing_percentage'],
            'enable_analysis_report': bool(exam_settings['enable_analysis_report']),
            'questions': questions_list,
            'answers': json.loads(in_progress_data['answers']) if in_progress_data else {},
            'question_status': json.loads(in_progress_data['question_status']) if in_progress_data else {},
            'time_left': in_progress_data['time_left'] if in_progress_data else exam_settings['duration'] * 60,
            'attempt_number': attempts_taken + 1
        }
        
        return jsonify({
            'message': 'Eligibility check passed.',
            'student_name': student_data['student_name'],
            'teacher_id': student_data['teacher_id'],
            'exam_data': exam_data
        }), 200
        
    finally:
        conn.close()

@app.route('/api/save-progress', methods=['POST'])
def save_progress():
    """Saves a student's in-progress exam data."""
    data = request.json
    student_id = data.get('student_id')
    exam_id = data.get('exam_id')
    teacher_id = data.get('teacher_id')
    answers = data.get('answers')
    time_left = data.get('time_left')
    question_status = data.get('question_status')

    if not all([student_id, exam_id, teacher_id, answers, time_left is not None, question_status]):
        return jsonify({'message': 'Invalid data'}), 400

    conn = get_db_connection()
    c = conn.cursor()
    try:
        c.execute('''
            INSERT OR REPLACE INTO in_progress_exams (student_id, exam_id, teacher_id, answers, time_left, question_status)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (student_id, exam_id, teacher_id, json.dumps(answers), time_left, json.dumps(question_status)))
        conn.commit()
        return jsonify({'message': 'Progress saved successfully.'}), 200
    except Exception as e:
        return jsonify({'message': f'An error occurred: {str(e)}'}), 500
    finally:
        conn.close()

@app.route('/api/questions/by-exam/<exam_id>', methods=['GET'])
def get_questions_by_exam(exam_id):
    """Retrieves all questions for a specific exam."""
    conn = get_db_connection()
    c = conn.cursor()
    
    c.execute('SELECT question_text, correct_option, options, image_url FROM questions WHERE exam_id = ? AND question_text != "placeholder"', (exam_id,))
    questions = c.fetchall()
    
    conn.close()
    
    questions_list = []
    for q in questions:
        questions_list.append({
            'question_text': q['question_text'],
            'correct_option': q['correct_option'],
            'options': json.loads(q['options']),
            'image_url': q['image_url']
        })
    
    return jsonify(questions_list), 200

@app.route('/api/exams/by-teacher/<teacher_id>', methods=['GET'])
def get_exams_by_teacher(teacher_id):
    """Retrieves exams managed by a specific teacher."""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('SELECT DISTINCT exam_id, exam_title FROM questions WHERE teacher_id = ?', (teacher_id,))
    exams = c.fetchall()
    conn.close()
    return jsonify([dict(row) for row in exams]), 200

@app.route('/api/submit/exam', methods=['POST'])
def submit_exam():
    """Submits a student's exam answers, calculates score, and generates an analysis report."""
    data = request.json
    exam_id = data.get('exam_id')
    student_id = data.get('student_id')
    student_name = data.get('student_name')
    answers = data.get('answers')
    teacher_id = data.get('teacher_id')
    
    conn = get_db_connection()
    c = conn.cursor()
    
    try:
        all_questions = c.execute('SELECT question_text, correct_option, options FROM questions WHERE exam_id = ? AND question_text != "placeholder"', (exam_id,)).fetchall()
        
        if not all_questions:
            return jsonify({'message': 'Could not find questions for this exam to calculate score.'}), 500

        correct_answers_map = {row['question_text']: row['correct_option'] for row in all_questions}
        
        score = 0
        analysis_report = []

        for question in all_questions:
            q_text = question['question_text']
            student_answer_key = answers.get(q_text)
            correct_answer_key = correct_answers_map.get(q_text)
            is_correct = (student_answer_key == correct_answer_key)
            if is_correct: score += 1
            
            analysis_report.append({
                'question_text': q_text, 'options': json.loads(question['options']),
                'student_answer': student_answer_key, 'correct_answer': correct_answer_key,
                'is_correct': is_correct
            })
            
        result_id = str(uuid.uuid4())
        c.execute('INSERT INTO results (result_id, exam_id, student_id, student_name, teacher_id, score, answers) VALUES (?, ?, ?, ?, ?, ?, ?)',
                  (result_id, exam_id, student_id, student_name, teacher_id, score, json.dumps(answers)))
        
        c.execute('DELETE FROM in_progress_exams WHERE student_id = ? AND exam_id = ?', (student_id, exam_id))
        
        conn.commit()
        
        return jsonify({
            'message': 'Exam submitted successfully.', 
            'score': score,
            'analysis_report': analysis_report
        }), 200
    except Exception as e:
        return jsonify({'message': f'An error occurred during submission: {str(e)}'}), 500
    finally:
        conn.close()

@app.route('/api/results', methods=['GET'])
def get_all_results():
    """Retrieves all exam results."""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('SELECT * FROM results')
    results = c.fetchall()
    conn.close()
    return jsonify([dict(row) for row in results]), 200

@app.route('/api/all-questions', methods=['GET'])
def get_all_questions():
    """Retrieves all questions from the database."""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('SELECT * FROM questions')
    questions = c.fetchall()
    conn.close()
    return jsonify([dict(row) for row in questions]), 200

@app.route('/api/question/delete', methods=['DELETE'])
def delete_question():
    data = request.json
    teacher_id = data.get('teacher_id')
    exam_id = data.get('exam_id')
    question_text = data.get('question_text')
    if not all([teacher_id, exam_id, question_text]):
        return jsonify({'message': 'Invalid data provided.'}), 400
    conn = get_db_connection()
    c = conn.cursor()
    try:
        c.execute('DELETE FROM questions WHERE teacher_id = ? AND exam_id = ? AND question_text = ?',
                  (teacher_id, exam_id, question_text))
        conn.commit()
        if c.rowcount > 0:
            return jsonify({'message': 'Question deleted successfully.'}), 200
        else:
            return jsonify({'message': 'Question not found or you are not authorized to delete.'}), 404
    finally:
        conn.close()

if __name__ == '__main__':
    if not os.path.exists(DATABASE_PATH):
        print("Database not found. Initializing a new database...")
        init_db()
        print("Database initialized successfully.")
    else:
        init_db()
        print("Database found. Running server.")
    
    if not os.path.exists(STATIC_DIR):
        os.makedirs(STATIC_DIR)
        
    print(f"Server running at http://0.0.0.0:5000")
    app.run(debug=True, host='0.0.0.0', port=5000)
