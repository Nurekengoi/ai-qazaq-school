# app.py - AI QAZAQ Teachers Platform (ТОЛЫҚ ФАЙЛ ЖҮЙЕСІ БЕН ТҮЗЕТІЛГЕН)
import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import hashlib
import random
import json
import os
import io
import base64
import string
import time
import matplotlib.pyplot as plt
import numpy as np
import traceback
import tempfile
from pathlib import Path

try:
    import plotly.graph_objects as go
    import plotly.express as px
    PLOTLY_AVAILABLE = True
except:
    PLOTLY_AVAILABLE = False

from flask import Flask

app = Flask(__name__)

@app.route("/")
def home():
    return """
    <h2>Білім беру платформасы</h2>
    <a href='/student'>Оқушы</a><br><br>
    <a href='/teacher'>Мұғалім</a>
    """

@app.route("/student")
def student():
    return "<h3>Оқушы беті</h3>"

@app.route("/teacher")
def teacher():
    return "<h3>Мұғалім беті</h3>"

if __name__ == "__main__":
    app.run(debug=True)
    
# ============ ДЕРЕКҚОР БАЗАСЫ ============
def init_db():
    """Дерекқорды бастапқы жасау"""
    conn = sqlite3.connect('ai_qazaq_teachers.db', check_same_thread=False)
    c = conn.cursor()
    
    # Мұғалімдер кестесі
    c.execute('''
        CREATE TABLE IF NOT EXISTS teachers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            email TEXT,
            full_name TEXT,
            school TEXT,
            city TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Сыныптар кестесі
    c.execute('''
        CREATE TABLE IF NOT EXISTS classes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            teacher_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            subject TEXT,
            grade_level TEXT,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (teacher_id) REFERENCES teachers (id)
        )
    ''')
    
    # Оқушылар кестесі
    c.execute('''
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            class_id INTEGER NOT NULL,
            full_name TEXT NOT NULL,
            student_code TEXT UNIQUE,
            grade_points INTEGER DEFAULT 0,
            academic_performance TEXT DEFAULT 'Орташа',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (class_id) REFERENCES classes (id)
        )
    ''')
    
    # Оқушы логиндері
    c.execute('''
        CREATE TABLE IF NOT EXISTS student_logins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (student_id) REFERENCES students (id)
        )
    ''')
    
    # БЖБ тапсырмалары
    c.execute('''
        CREATE TABLE IF NOT EXISTS bzb_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            teacher_id INTEGER NOT NULL,
            class_id INTEGER NOT NULL,
            task_name TEXT NOT NULL,
            task_file BLOB,
            file_type TEXT,
            upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completion_rate INTEGER DEFAULT 0,
            difficulty_level TEXT,
            ai_solution TEXT,
            FOREIGN KEY (teacher_id) REFERENCES teachers (id),
            FOREIGN KEY (class_id) REFERENCES classes (id)
        )
    ''')
    
    # Көрнекіліктер
    c.execute('''
        CREATE TABLE IF NOT EXISTS visual_materials (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            teacher_id INTEGER NOT NULL,
            file_name TEXT NOT NULL,
            file_data BLOB,
            file_type TEXT,
            file_size INTEGER,
            category TEXT,
            upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (teacher_id) REFERENCES teachers (id)
        )
    ''')
    
    # Сабақ жоспарлары
    c.execute('''
        CREATE TABLE IF NOT EXISTS lesson_plans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            teacher_id INTEGER NOT NULL,
            class_id INTEGER NOT NULL,
            lesson_name TEXT NOT NULL,
            subject TEXT,
            grade_level TEXT,
            lesson_type TEXT,
            duration_minutes INTEGER DEFAULT 40,
            goals TEXT,
            methods TEXT,
            equipment TEXT,
            stages TEXT,
            reflection TEXT,
            ai_suggestions TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (teacher_id) REFERENCES teachers (id),
            FOREIGN KEY (class_id) REFERENCES classes (id)
        )
    ''')
    
    # Оқушыларға тапсырмалар - БІРІКТІРІЛГЕН ЖАҢА КЕСТЕ
    c.execute('''
        CREATE TABLE IF NOT EXISTS student_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            teacher_id INTEGER NOT NULL,
            student_id INTEGER NOT NULL,
            class_id INTEGER NOT NULL,
            
            -- Тапсырма ақпараты
            task_name TEXT NOT NULL,
            task_description TEXT,
            
            -- Тапсырма файлы
            task_file BLOB,
            task_file_type TEXT,
            task_file_name TEXT,
            task_file_size INTEGER,
            
            -- Мұғалім ақпараты
            teacher_name TEXT,
            
            -- Оқушы ақпараты  
            student_name TEXT,
            class_name TEXT,
            
            -- Мерзімдер
            assigned_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            due_date DATE,
            
            -- Статус
            status TEXT DEFAULT 'Тағайындалды',
            
            -- Оқушының жауабы
            student_answer_text TEXT,
            student_answer_file BLOB,
            student_answer_file_type TEXT,
            student_answer_file_name TEXT,
            student_answer_file_size INTEGER,
            student_submitted_date TIMESTAMP,
            
            -- Бағалау
            points INTEGER DEFAULT 10,
            score INTEGER,
            teacher_feedback TEXT,
            checked_date TIMESTAMP,
            
            -- Түйіндеулер
            tags TEXT,
            difficulty TEXT DEFAULT 'Орташа',
            
            FOREIGN KEY (teacher_id) REFERENCES teachers (id),
            FOREIGN KEY (student_id) REFERENCES students (id),
            FOREIGN KEY (class_id) REFERENCES classes (id)
        )
    ''')
    
    # Индекстер қосу
    c.execute('CREATE INDEX IF NOT EXISTS idx_student_tasks_student_id ON student_tasks(student_id)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_student_tasks_teacher_id ON student_tasks(teacher_id)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_student_tasks_status ON student_tasks(status)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_student_tasks_due_date ON student_tasks(due_date)')
    
    conn.commit()
    conn.close()
    print("✅ Дерекқор сәтті бастапқыланды!")

# ============ СЕССИЯ БАСҚАРУ ============
USER_SESSION_FILE = "user_session.json"
STUDENT_SESSION_FILE = "student_session.json"

def save_user_session(user):
    try:
        with open(USER_SESSION_FILE, "w", encoding="utf-8") as f:
            json.dump({
                "id": user[0],
                "username": user[1],
                "full_name": user[2],
                "school": user[3],
                "city": user[4]
            }, f, ensure_ascii=False)
    except Exception as e:
        print(f"❌ Сессияны сақтау қатесі: {e}")

def load_user_session():
    if os.path.exists(USER_SESSION_FILE):
        try:
            with open(USER_SESSION_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            return (data["id"], data["username"], data["full_name"], data["school"], data["city"])
        except:
            return None
    return None

def save_student_session(student):
    try:
        with open(STUDENT_SESSION_FILE, "w", encoding="utf-8") as f:
            json.dump({
                "id": student[0],
                "full_name": student[1],
                "student_code": student[2],
                "class_id": student[3],
                "class_name": student[4],
                "subject": student[5],
                "grade_points": student[6],
                "academic_performance": student[7] if len(student) > 7 else "Орташа"
            }, f, ensure_ascii=False)
    except Exception as e:
        print(f"❌ Студент сессиясын сақтау қатесі: {e}")

def load_student_session():
    if os.path.exists(STUDENT_SESSION_FILE):
        try:
            with open(STUDENT_SESSION_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            return (data["id"], data["full_name"], data["student_code"], 
                    data["class_id"], data["class_name"], data["subject"],
                    data["grade_points"], data["academic_performance"])
        except:
            return None
    return None

def clear_user_session():
    if os.path.exists(USER_SESSION_FILE):
        try:
            os.remove(USER_SESSION_FILE)
        except:
            pass

def clear_student_session():
    if os.path.exists(STUDENT_SESSION_FILE):
        try:
            os.remove(STUDENT_SESSION_FILE)
        except:
            pass

# ============ ОРТАҚ ФУНКЦИЯЛАР ============
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def generate_random_password(length=8):
    characters = string.ascii_letters + string.digits
    return ''.join(random.choice(characters) for _ in range(length))

def get_file_extension(file_type):
    if '/' in file_type:
        return file_type.split('/')[-1]
    return 'file'

def get_file_size_str(size_bytes):
    """Файл көлемін оқуға ыңғайлы форматтау"""
    if size_bytes < 1024:
        return f"{size_bytes} Б"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} КБ"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} МБ"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.1f} ГБ"

def points_to_grade(points):
    try:
        if isinstance(points, str):
            points = points.strip()
            if points == '':
                return "F"
            try:
                points_int = int(float(points))
            except:
                return "F"
        elif isinstance(points, (int, float)):
            points_int = int(points)
        else:
            return "F"
        
        if points_int >= 9: return "A"
        elif points_int >= 7: return "B"
        elif points_int >= 5: return "C"
        elif points_int >= 3: return "D"
        else: return "F"
    except:
        return "F"

def get_grade_class(grade):
    grade_classes = {
        "A": "grade-a", "B": "grade-b", "C": "grade-c",
        "D": "grade-d", "F": "grade-f"
    }
    return grade_classes.get(grade, "grade-f")

def export_to_csv(dataframe):
    output = io.BytesIO()
    csv_data = dataframe.to_csv(index=False, encoding='utf-8-sig')
    output.write(csv_data.encode('utf-8-sig'))
    output.seek(0)
    return output

def preview_file(file_data, file_type, file_name):
    """Файлды алдын ала көру - ЖАҢА ТҮЗЕТІЛГЕН"""
    st.markdown(f"### 📄 {file_name}")
    
    try:
        # Уақытша файл жасау
        with tempfile.NamedTemporaryFile(delete=False, suffix=f".{get_file_extension(file_type)}") as tmp_file:
            tmp_file.write(file_data)
            tmp_file_path = tmp_file.name
        
        # Файл түріне байланысты көрсету
        if file_type.startswith('image/'):
            st.image(file_data, caption=file_name, use_container_width=True)
        
        elif file_type == 'application/pdf':
            # PDF файлды көрсету
            base64_pdf = base64.b64encode(file_data).decode('utf-8')
            pdf_display = f'''
            <div style="height: 600px; overflow: auto; border: 1px solid #ddd; border-radius: 5px; padding: 10px;">
                <iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="580px"></iframe>
            </div>
            '''
            st.markdown(pdf_display, unsafe_allow_html=True)
            
            # Жүктеп алу түймесі
            st.download_button(
                label="📥 PDF файлды жүктеп алу",
                data=file_data,
                file_name=file_name,
                mime=file_type
            )
        
        elif file_type == 'text/plain' or file_name.endswith('.txt'):
            try:
                text_content = file_data.decode('utf-8')
                st.text_area("📝 Файл мазмұны", text_content, height=300)
            except:
                # Басқа кодировкаларды көру
                try:
                    text_content = file_data.decode('latin-1')
                    st.text_area("📝 Файл мазмұны", text_content, height=300)
                except:
                    st.warning("⚠️ Мәтінді декодтау мүмкін болмады")
        
        elif file_type in ['application/vnd.openxmlformats-officedocument.wordprocessingml.document', 
                          'application/msword']:
            # Word файлдары үшін
            st.info(f"📄 Word файлы: {file_name}")
            st.download_button(
                label="📥 Word файлды жүктеп алу",
                data=file_data,
                file_name=file_name,
                mime=file_type
            )
        
        elif file_type in ['application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                          'application/vnd.ms-excel']:
            # Excel файлдары үшін
            st.info(f"📊 Excel файлы: {file_name}")
            st.download_button(
                label="📥 Excel файлды жүктеп алу",
                data=file_data,
                file_name=file_name,
                mime=file_type
            )
        
        elif file_type.startswith('video/'):
            st.video(file_data)
        
        elif file_type.startswith('audio/'):
            st.audio(file_data)
        
        elif file_type in ['application/vnd.ms-powerpoint', 
                          'application/vnd.openxmlformats-officedocument.presentationml.presentation']:
            # PowerPoint файлдары
            st.info(f"📊 PowerPoint файлы: {file_name}")
            st.download_button(
                label="📥 PowerPoint жүктеп алу",
                data=file_data,
                file_name=file_name,
                mime=file_type
            )
        
        else:
            st.info(f"📁 Файл түрі: {file_type}")
            st.info(f"📁 Файл атауы: {file_name}")
            
            # Әр түрлі файл үшін жүктеп алу
            st.download_button(
                label="📥 Файлды жүктеп алу",
                data=file_data,
                file_name=file_name,
                mime=file_type
            )
        
        # Уақытша файлды тазалау
        try:
            os.unlink(tmp_file_path)
        except:
            pass
            
    except Exception as e:
        st.error(f"❌ Файлды көрсету кезінде қате: {e}")

def display_file_preview(file_data, file_type, file_name):
    """Файлды көрсетуді жеңілдетілген нұсқасы"""
    if file_data:
        # Файл түріне байланысты әртүрлі көрсету
        if file_type.startswith('image/'):
            st.image(file_data, caption=file_name, use_container_width=True)
        
        elif file_type == 'application/pdf':
            st.info(f"📄 PDF файл: {file_name}")
            base64_pdf = base64.b64encode(file_data).decode('utf-8')
            pdf_display = f'''
            <div style="height: 500px; overflow: auto;">
                <iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="480px"></iframe>
            </div>
            '''
            st.markdown(pdf_display, unsafe_allow_html=True)
        
        elif file_type.endswith('.txt') or file_type == 'text/plain':
            try:
                text = file_data.decode('utf-8')
                st.text_area("📝 Мәтін мазмұны", text, height=200)
            except:
                st.info(f"📝 Текст файлы: {file_name}")
        
        else:
            st.info(f"📁 Файл: {file_name} ({file_type})")
    
    # Әрдайым жүктеп алу түймесі
    if file_data:
        st.download_button(
            label="📥 Файлды жүктеп алу",
            data=file_data,
            file_name=file_name,
            mime=file_type,
            use_container_width=True
        )

# ============ ДЕРЕКҚОР ТҮЗЕТУ ФУНКЦИЯЛАРЫ ============
def fix_database_structure():
    """Дерекқор құрылымын түзету"""
    conn = sqlite3.connect('ai_qazaq_teachers.db', check_same_thread=False)
    c = conn.cursor()
    
    try:
        # Кестелердің бар-жоғын тексеру
        c.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [table[0] for table in c.fetchall()]
        print(f"📊 Қолжетімді кестелер: {tables}")
        
        # student_tasks кестесінің дұрыстығын тексеру
        if 'student_tasks' in tables:
            c.execute("PRAGMA table_info(student_tasks)")
            student_task_columns = [col[1] for col in c.fetchall()]
            print(f"📋 student_tasks кестесінің бағаналары: {student_task_columns}")
            
            # student_tasks кестесінде дерек бар ма?
            c.execute("SELECT COUNT(*) FROM student_tasks")
            task_count = c.fetchone()[0]
            print(f"📊 student_tasks кестесінде: {task_count} тапсырма")
        
        conn.commit()
        print("✅ Дерекқор құрылымы түзетілді!")
        return True
    except Exception as e:
        print(f"❌ Дерекқорды түзету қатесі: {e}")
        return False
    finally:
        conn.close()

def fix_student_tasks_columns():
    """student_tasks кестесіндегі барлық қажетті бағаналарды тексеру және қосу"""
    conn = sqlite3.connect('ai_qazaq_teachers.db', check_same_thread=False)
    c = conn.cursor()
    
    try:
        # Кесте бағаналарын алу
        c.execute("PRAGMA table_info(student_tasks)")
        columns = c.fetchall()
        column_names = [col[1] for col in columns]
        
        print("📋 student_tasks кестесінің бағаналары:")
        for col in columns:
            print(f"  - {col[1]} ({col[2]})")
        
        # Барлық қажетті бағаналарды қосу
        required_columns = [
            ('task_file_size', 'INTEGER'),
            ('student_answer_file_name', 'TEXT'),
            ('student_answer_file_size', 'INTEGER'),
            ('points', 'INTEGER DEFAULT 10'),
            ('due_date', 'DATE'),
            ('task_file_type', 'TEXT'),
            ('task_file_name', 'TEXT'),
            ('teacher_name', 'TEXT'),
            ('student_name', 'TEXT'),
            ('class_name', 'TEXT'),
            ('tags', 'TEXT'),
            ('difficulty', 'TEXT DEFAULT "Орташа"'),
            ('checked_date', 'TIMESTAMP'),
            ('student_answer_file_type', 'TEXT'),
            ('status', 'TEXT DEFAULT "Тағайындалды"'),
            ('teacher_feedback', 'TEXT'),
            ('score', 'INTEGER'),
            ('student_answer_text', 'TEXT'),
            ('student_answer_file', 'BLOB'),
            ('student_submitted_date', 'TIMESTAMP'),
            ('assigned_date', 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP')
        ]
        
        for col_name, col_type in required_columns:
            if col_name not in column_names:
                print(f"➕ {col_name} бағанасын қосу...")
                try:
                    c.execute(f"ALTER TABLE student_tasks ADD COLUMN {col_name} {col_type}")
                    print(f"✅ {col_name} бағанасы қосылды")
                except Exception as e:
                    print(f"⚠️ {col_name} қосу қатесі: {e}")
        
        conn.commit()
        print("✅ student_tasks кестесі түзетілді!")
        return True
    except Exception as e:
        print(f"❌ Кестені түзету қатесі: {e}")
        traceback.print_exc()
        return False
    finally:
        conn.close()

# ============ МҰҒАЛІМ ФУНКЦИЯЛАРЫ ============
def register_user(username, password, email, full_name, school, city):
    conn = sqlite3.connect('ai_qazaq_teachers.db', check_same_thread=False)
    c = conn.cursor()
    try:
        hashed_password = hash_password(password)
        c.execute(
            """INSERT INTO teachers (username, password, email, full_name, school, city) 
            VALUES (?, ?, ?, ?, ?, ?)""",
            (username, hashed_password, email, full_name, school, city)
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def login_user(username, password):
    conn = sqlite3.connect('ai_qazaq_teachers.db', check_same_thread=False)
    c = conn.cursor()
    hashed_password = hash_password(password)
    c.execute(
        """SELECT id, username, full_name, school, city FROM teachers 
        WHERE username=? AND password=?""",
        (username, hashed_password)
    )
    user = c.fetchone()
    conn.close()
    return user

def get_classes(teacher_id):
    conn = sqlite3.connect('ai_qazaq_teachers.db', check_same_thread=False)
    c = conn.cursor()
    c.execute("SELECT id, name, subject, grade_level FROM classes WHERE teacher_id = ? ORDER BY name", (teacher_id,))
    classes = c.fetchall()
    conn.close()
    return classes

def add_class(teacher_id, name, subject, grade_level, description):
    conn = sqlite3.connect('ai_qazaq_teachers.db', check_same_thread=False)
    c = conn.cursor()
    try:
        c.execute(
            """INSERT INTO classes (teacher_id, name, subject, grade_level, description) 
            VALUES (?, ?, ?, ?, ?)""",
            (teacher_id, name, subject, grade_level, description)
        )
        conn.commit()
        return True
    except Exception as e:
        print(f"❌ Сынып қосу қатесі: {e}")
        return False
    finally:
        conn.close()

def delete_class(class_id):
    conn = sqlite3.connect('ai_qazaq_teachers.db', check_same_thread=False)
    c = conn.cursor()
    try:
        c.execute("DELETE FROM student_logins WHERE student_id IN (SELECT id FROM students WHERE class_id = ?)", (class_id,))
        c.execute("DELETE FROM students WHERE class_id = ?", (class_id,))
        c.execute("DELETE FROM bzb_tasks WHERE class_id = ?", (class_id,))
        c.execute("DELETE FROM classes WHERE id = ?", (class_id,))
        conn.commit()
        return True
    except Exception as e:
        print(f"❌ Сыныпты жою қатесі: {e}")
        return False
    finally:
        conn.close()

def get_students_by_class(class_id):
    conn = sqlite3.connect('ai_qazaq_teachers.db', check_same_thread=False)
    c = conn.cursor()
    try:
        c.execute("SELECT * FROM students WHERE class_id = ? ORDER BY full_name", (class_id,))
        students = c.fetchall()
        return students
    except Exception as e:
        print(f"❌ Оқушыларды алу қатесі: {e}")
        return []
    finally:
        conn.close()

def add_student(class_id, full_name, student_code, grade_points, academic_performance):
    conn = sqlite3.connect('ai_qazaq_teachers.db', check_same_thread=False)
    c = conn.cursor()
    try:
        # grade_points мәнін санға түрлендіру
        try:
            if isinstance(grade_points, str):
                grade_points_int = int(float(grade_points.strip()))
            else:
                grade_points_int = int(grade_points)
        except (ValueError, TypeError):
            grade_points_int = 5
        
        # Шектеулер
        if grade_points_int < 1:
            grade_points_int = 1
        elif grade_points_int > 10:
            grade_points_int = 10
        
        if not academic_performance:
            academic_performance = "Орташа"
        
        # Оқушыны қосу
        c.execute(
            """INSERT INTO students (class_id, full_name, student_code, grade_points, academic_performance) 
            VALUES (?, ?, ?, ?, ?)""",
            (class_id, full_name, student_code, grade_points_int, academic_performance)
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError as e:
        print(f"❌ Оқушы қосу қатесі (интеграция): {e}")
        return False
    except Exception as e:
        print(f"❌ Оқушы қосу қатесі: {e}")
        return False
    finally:
        conn.close()

def delete_student(student_id):
    conn = sqlite3.connect('ai_qazaq_teachers.db', check_same_thread=False)
    c = conn.cursor()
    try:
        c.execute("DELETE FROM student_logins WHERE student_id = ?", (student_id,))
        c.execute("DELETE FROM students WHERE id = ?", (student_id,))
        conn.commit()
        return True
    except Exception as e:
        print(f"❌ Оқушыны жою қатесі: {e}")
        return False
    finally:
        conn.close()

def register_student_login(student_id, username, password):
    conn = sqlite3.connect('ai_qazaq_teachers.db', check_same_thread=False)
    c = conn.cursor()
    try:
        c.execute("SELECT id FROM students WHERE id = ?", (student_id,))
        if not c.fetchone():
            conn.close()
            return False, "Оқушы табылмады"
        
        c.execute("SELECT id FROM student_logins WHERE username = ?", (username,))
        if c.fetchone():
            conn.close()
            return False, "Бұл логин бос емес"
        
        c.execute("SELECT id FROM student_logins WHERE student_id = ?", (student_id,))
        if c.fetchone():
            conn.close()
            return False, "Оқушыда логин бар"
        
        hashed_password = hash_password(password)
        c.execute(
            """INSERT INTO student_logins (student_id, username, password) 
            VALUES (?, ?, ?)""",
            (student_id, username, hashed_password)
        )
        conn.commit()
        return True, "Сәтті тіркелді"
    except sqlite3.IntegrityError as e:
        return False, f"Дерекқор қатесі: {str(e)}"
    except Exception as e:
        return False, f"Қате: {str(e)}"
    finally:
        conn.close()

def get_student_logins(student_id):
    conn = sqlite3.connect('ai_qazaq_teachers.db', check_same_thread=False)
    c = conn.cursor()
    c.execute("SELECT id, username FROM student_logins WHERE student_id = ?", (student_id,))
    logins = c.fetchall()
    conn.close()
    return logins

def update_student_password(login_id, new_password):
    conn = sqlite3.connect('ai_qazaq_teachers.db', check_same_thread=False)
    c = conn.cursor()
    try:
        hashed_password = hash_password(new_password)
        c.execute(
            "UPDATE student_logins SET password = ? WHERE id = ?",
            (hashed_password, login_id)
        )
        conn.commit()
        return True
    except Exception as e:
        print(f"❌ Құпия сөзді өзгерту қатесі: {e}")
        return False
    finally:
        conn.close()

def delete_student_login(login_id):
    conn = sqlite3.connect('ai_qazaq_teachers.db', check_same_thread=False)
    c = conn.cursor()
    try:
        c.execute("DELETE FROM student_logins WHERE id = ?", (login_id,))
        conn.commit()
        return True
    except Exception as e:
        print(f"❌ Логинды жою қатесі: {e}")
        return False
    finally:
        conn.close()

def save_file_to_db(teacher_id, file_name, file_data, category):
    conn = sqlite3.connect('ai_qazaq_teachers.db', check_same_thread=False)
    c = conn.cursor()
    try:
        file_bytes = file_data.read()
        file_type = file_data.type
        c.execute(
            """INSERT INTO visual_materials 
            (teacher_id, file_name, file_data, file_type, file_size, category) 
            VALUES (?, ?, ?, ?, ?, ?)""",
            (teacher_id, file_name, file_bytes, file_type, len(file_bytes), category)
        )
        conn.commit()
        return True
    except Exception as e:
        print(f"❌ Файлды сақтау қатесі: {e}")
        return False
    finally:
        conn.close()

def get_saved_files(teacher_id):
    conn = sqlite3.connect('ai_qazaq_teachers.db', check_same_thread=False)
    c = conn.cursor()
    try:
        c.execute(
            """SELECT id, file_name, file_type, file_size, 
                      category, upload_date, file_data
               FROM visual_materials 
               WHERE teacher_id = ? 
               ORDER BY upload_date DESC""",
            (teacher_id,)
        )
        
        files = []
        for row in c.fetchall():
            files.append({
                'id': row[0],
                'name': row[1],
                'type': row[2],
                'size': f"{row[3]} байт",
                'category': row[4],
                'uploaded': row[5],
                'data': row[6]
            })
        return files
    except Exception as e:
        print(f"❌ Файлдарды алу қатесі: {e}")
        return []
    finally:
        conn.close()

def delete_file(file_id):
    conn = sqlite3.connect('ai_qazaq_teachers.db', check_same_thread=False)
    c = conn.cursor()
    try:
        c.execute("DELETE FROM visual_materials WHERE id = ?", (file_id,))
        conn.commit()
        return True
    except Exception as e:
        print(f"❌ Файлды жою қатесі: {e}")
        return False
    finally:
        conn.close()

def get_visual_material(file_id):
    conn = sqlite3.connect('ai_qazaq_teachers.db', check_same_thread=False)
    c = conn.cursor()
    try:
        c.execute(
            """SELECT file_name, file_data, file_type 
               FROM visual_materials 
               WHERE id = ?""",
            (file_id,)
        )
        file = c.fetchone()
        if file:
            return {
                'name': file[0],
                'data': file[1],
                'type': file[2]
            }
        return None
    except Exception as e:
        print(f"❌ Файлды алу қатесі: {e}")
        return None
    finally:
        conn.close()

def save_bzb_task(teacher_id, class_id, task_name, task_file, file_type, completion_rate, difficulty_level):
    conn = sqlite3.connect('ai_qazaq_teachers.db', check_same_thread=False)
    c = conn.cursor()
    try:
        file_bytes = task_file.read()
        ai_solution = generate_ai_solution(completion_rate, difficulty_level)
        c.execute(
            """INSERT INTO bzb_tasks 
            (teacher_id, class_id, task_name, task_file, file_type, completion_rate, difficulty_level, ai_solution) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (teacher_id, class_id, task_name, file_bytes, file_type, completion_rate, difficulty_level, ai_solution)
        )
        conn.commit()
        return True
    except Exception as e:
        print(f"❌ БЖБ тапсырмасын сақтау қатесі: {e}")
        return False
    finally:
        conn.close()

def generate_ai_solution(completion_rate, difficulty_level):
    solutions = {
        "Оңай": {
            "low": "• Қарапайым түсініктемелер\n• Қадамдық нұсқаулар\n• Мысалдар келтіру",
            "medium": "• Толық түсіндірме\n• Формулаларды түсіндіру\n• Практикалық мысалдар",
            "high": "• Талдау және шешім\n• Баламалы тәсілдер\n• Түбіне дейін зерттеу"
        },
        "Орташа": {
            "low": "• Негізгі түсініктемелер\n• Қадам-қалам нұсқау\n• Жеңілдетілген тәсіл",
            "medium": "• Толық талдау\n• Формулалар мен ережелер\n• Мысалдармен түсіндіру",
            "high": "• Кешенді түсініктеме\n• Ғылыми тәсілдер\n• Қосымша ресурстар"
        },
        "Қиын": {
            "low": "• Негізгі тұжырымдар\n• Бастапқы тәсілдер\n• Мысалдармен түсіндіру",
            "medium": "• Терең талдау\n• Күрделі формулалар\n• Көп деңгейлі шешімдер",
            "high": "• Зерттеу және талдау\n• Инновациялық тәсілдер\n• Ғылыми негіздеу"
        }
    }
    
    if completion_rate < 30:
        level = "low"
    elif completion_rate < 70:
        level = "medium"
    else:
        level = "high"
    
    return solutions.get(difficulty_level, {}).get(level, "Шешім табылмады")

def get_bzb_tasks(teacher_id):
    conn = sqlite3.connect('ai_qazaq_teachers.db', check_same_thread=False)
    c = conn.cursor()
    try:
        c.execute("""
        SELECT b.id, b.task_name, b.file_type, b.upload_date, 
               b.completion_rate, b.difficulty_level, b.ai_solution,
               c.name as class_name
        FROM bzb_tasks b
        JOIN classes c ON b.class_id = c.id
        WHERE b.teacher_id = ?
        ORDER BY b.upload_date DESC
        """, (teacher_id,))
        
        tasks = []
        for row in c.fetchall():
            tasks.append({
                'id': row[0],
                'name': row[1],
                'type': row[2],
                'uploaded': row[3],
                'rate': row[4],
                'difficulty': row[5],
                'ai_solution': row[6],
                'class_name': row[7]
            })
        return tasks
    except Exception as e:
        print(f"❌ БЖБ тапсырмаларын алу қатесі: {e}")
        return []
    finally:
        conn.close()

def get_bzb_task(task_id):
    conn = sqlite3.connect('ai_qazaq_teachers.db', check_same_thread=False)
    c = conn.cursor()
    try:
        c.execute(
            """SELECT task_name, task_file, file_type, ai_solution
               FROM bzb_tasks 
               WHERE id = ?""",
            (task_id,)
        )
        task = c.fetchone()
        if task:
            return {
                'name': task[0],
                'data': task[1],
                'type': task[2],
                'ai_solution': task[3]
            }
        return None
    except Exception as e:
        print(f"❌ БЖБ тапсырмасын алу қатесі: {e}")
        return None
    finally:
        conn.close()

def delete_bzb_task(task_id):
    conn = sqlite3.connect('ai_qazaq_teachers.db', check_same_thread=False)
    c = conn.cursor()
    try:
        c.execute("DELETE FROM bzb_tasks WHERE id = ?", (task_id,))
        conn.commit()
        return True
    except Exception as e:
        print(f"❌ БЖБ тапсырмасын жою қатесі: {e}")
        return False
    finally:
        conn.close()

def get_class_count(teacher_id):
    conn = sqlite3.connect('ai_qazaq_teachers.db', check_same_thread=False)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM classes WHERE teacher_id=?", (teacher_id,))
    count = c.fetchone()[0]
    conn.close()
    return count

def get_student_count(teacher_id):
    conn = sqlite3.connect('ai_qazaq_teachers.db', check_same_thread=False)
    c = conn.cursor()
    c.execute("""SELECT COUNT(*) FROM students s 
                 JOIN classes c ON s.class_id = c.id 
                 WHERE c.teacher_id=?""", (teacher_id,))
    count = c.fetchone()[0]
    conn.close()
    return count

# ============ БІРІКТІРІЛГЕН ТАПСЫРМА ФУНКЦИЯЛАРЫ (ТҮЗЕТІЛГЕН) ============

def save_unified_student_task(teacher_id, student_id, class_id, task_data):
    """Жаңа тапсырманы сақтау - ФАЙЛДАР МЕН БІРГЕ"""
    conn = sqlite3.connect('ai_qazaq_teachers.db', check_same_thread=False)
    c = conn.cursor()
    
    try:
        # Бағаналарды бір рет тексеру және қосу
        fix_student_tasks_columns()
        
        # Мұғалім, оқушы және сынып ақпаратын алу
        c.execute("SELECT full_name FROM teachers WHERE id = ?", (teacher_id,))
        teacher = c.fetchone()
        teacher_name = teacher[0] if teacher else "Мұғалім"
        
        c.execute("SELECT s.full_name, c.name FROM students s JOIN classes c ON s.class_id = c.id WHERE s.id = ?", (student_id,))
        student = c.fetchone()
        student_name = student[0] if student else "Оқушы"
        class_name = student[1] if student else "Сынып"
        
        # Файлды өңдеу
        task_file = task_data.get('task_file')
        file_bytes = None
        file_type = None
        file_name = None
        file_size = 0
        
        if task_file and hasattr(task_file, 'read'):
            file_bytes = task_file.read()
            file_type = task_file.type
            file_name = task_file.name
            file_size = len(file_bytes)
        
        # Тапсырманы сақтау
        c.execute('''
            INSERT INTO student_tasks 
            (teacher_id, student_id, class_id, task_name, task_description, 
             task_file, task_file_type, task_file_name, task_file_size,
             teacher_name, student_name, class_name, due_date, points, 
             status, tags, difficulty)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            teacher_id,
            student_id,
            class_id,
            task_data.get('task_name'),
            task_data.get('task_description'),
            file_bytes,
            file_type,
            file_name,
            file_size,
            teacher_name,
            student_name,
            class_name,
            task_data.get('due_date'),
            task_data.get('points', 10),
            'Тағайындалды',
            task_data.get('tags'),
            task_data.get('difficulty', 'Орташа')
        ))
        
        conn.commit()
        return True, "✅ Тапсырма сәтті сақталды!"
        
    except Exception as e:
        print(f"❌ Тапсырма сақтау қатесі: {e}")
        traceback.print_exc()
        return False, f"Қате: {str(e)}"
    finally:
        conn.close()

def get_unified_student_tasks_by_teacher(teacher_id):
    """Мұғалім берген барлық тапсырмалар - ФАЙЛ АҚПАРАТЫМЕН"""
    conn = sqlite3.connect('ai_qazaq_teachers.db', check_same_thread=False)
    c = conn.cursor()
    
    try:
        c.execute('''
            SELECT 
                st.id, st.task_name, st.task_description, st.due_date,
                st.points, st.status, st.assigned_date, st.teacher_feedback,
                st.student_answer_text, st.student_submitted_date, st.score,
                st.student_name, st.class_name, st.teacher_name,
                st.task_file_type, st.task_file_name, st.task_file_size,
                st.student_answer_file_type, st.student_answer_file_name, st.student_answer_file_size,
                st.tags, st.difficulty,
                CASE 
                    WHEN st.due_date < date('now') AND st.status = 'Тағайындалды' THEN 'Кешікті'
                    ELSE st.status
                END as display_status
            FROM student_tasks st
            WHERE st.teacher_id = ?
            ORDER BY 
                CASE display_status
                    WHEN 'Кешікті' THEN 1
                    WHEN 'Тағайындалды' THEN 2
                    WHEN 'Жіберілді' THEN 3
                    WHEN 'Тексерілді' THEN 4
                    ELSE 5
                END,
                st.due_date ASC,
                st.assigned_date DESC
        ''', (teacher_id,))
        
        tasks = []
        columns = [desc[0] for desc in c.description]
        
        for row in c.fetchall():
            task = dict(zip(columns, row))
            
            # Даталарды форматтау
            for date_field in ['due_date', 'assigned_date', 'student_submitted_date']:
                if task.get(date_field):
                    try:
                        if isinstance(task[date_field], str):
                            if 'T' in task[date_field]:
                                dt = datetime.fromisoformat(task[date_field].replace('Z', '+00:00'))
                                task[f'{date_field}_formatted'] = dt.strftime('%d.%m.%Y %H:%M')
                            else:
                                task[f'{date_field}_formatted'] = task[date_field]
                    except:
                        task[f'{date_field}_formatted'] = str(task[date_field])
            
            # Мерзім өткенін тексеру
            if task.get('due_date'):
                try:
                    due_date_str = task['due_date']
                    if isinstance(due_date_str, str):
                        due_date = datetime.strptime(due_date_str, '%Y-%m-%d').date()
                        today = datetime.now().date()
                        task['is_overdue'] = due_date < today and task['display_status'] == 'Тағайындалды'
                        task['days_left'] = (due_date - today).days if due_date >= today else (today - due_date).days
                except:
                    task['is_overdue'] = False
            
            # Файл көлемін форматтау
            if task.get('task_file_size'):
                task['task_file_size_str'] = get_file_size_str(task['task_file_size'])
            
            if task.get('student_answer_file_size'):
                task['student_answer_file_size_str'] = get_file_size_str(task['student_answer_file_size'])
            
            tasks.append(task)
        
        return tasks
        
    except Exception as e:
        print(f"❌ Тапсырмаларды алу қатесі: {e}")
        traceback.print_exc()
        return []
    finally:
        conn.close()

def get_unified_student_tasks_by_student(student_id):
    """Оқушыға берілген барлық тапсырмалар - ФАЙЛДАРМЕН"""
    conn = sqlite3.connect('ai_qazaq_teachers.db', check_same_thread=False)
    c = conn.cursor()
    
    try:
        c.execute('''
            SELECT 
                st.id, st.task_name, st.task_description, st.due_date,
                st.points, st.status, st.assigned_date, st.teacher_feedback,
                st.student_answer_text, st.student_submitted_date, st.score,
                st.student_name, st.class_name, st.teacher_name,
                st.task_file_type, st.task_file_name, st.task_file_size,
                st.student_answer_file_type, st.student_answer_file_name, st.student_answer_file_size,
                st.tags, st.difficulty,
                CASE 
                    WHEN st.due_date < date('now') AND st.status = 'Тағайындалды' THEN 'Кешікті'
                    ELSE st.status
                END as display_status
            FROM student_tasks st
            WHERE st.student_id = ?
            ORDER BY 
                CASE display_status
                    WHEN 'Кешікті' THEN 1
                    WHEN 'Тағайындалды' THEN 2
                    WHEN 'Жіберілді' THEN 3
                    WHEN 'Тексерілді' THEN 4
                    ELSE 5
                END,
                st.due_date ASC
        ''', (student_id,))
        
        tasks = []
        columns = [desc[0] for desc in c.description]
        
        for row in c.fetchall():
            task = dict(zip(columns, row))
            
            # Даталарды форматтау
            for date_field in ['due_date', 'assigned_date', 'student_submitted_date']:
                if task.get(date_field):
                    try:
                        if isinstance(task[date_field], str):
                            if 'T' in task[date_field]:
                                dt = datetime.fromisoformat(task[date_field].replace('Z', '+00:00'))
                                task[f'{date_field}_formatted'] = dt.strftime('%d.%m.%Y %H:%M')
                            else:
                                task[f'{date_field}_formatted'] = task[date_field]
                    except:
                        task[f'{date_field}_formatted'] = str(task[date_field])
            
            # Мерзім өткенін тексеру
            if task.get('due_date'):
                try:
                    due_date_str = task['due_date']
                    if isinstance(due_date_str, str):
                        due_date = datetime.strptime(due_date_str, '%Y-%m-%d').date()
                        today = datetime.now().date()
                        task['is_overdue'] = due_date < today and task['display_status'] == 'Тағайындалды'
                        task['days_left'] = (due_date - today).days if due_date >= today else (today - due_date).days
                except:
                    task['is_overdue'] = False
            
            # Файл көлемін форматтау
            if task.get('task_file_size'):
                task['task_file_size_str'] = get_file_size_str(task['task_file_size'])
            
            if task.get('student_answer_file_size'):
                task['student_answer_file_size_str'] = get_file_size_str(task['student_answer_file_size'])
            
            tasks.append(task)
        
        return tasks
        
    except Exception as e:
        print(f"❌ Оқушы тапсырмаларын алу қатесі: {e}")
        traceback.print_exc()
        return []
    finally:
        conn.close()

def update_unified_task_status(task_id, new_status, feedback=None, score=None):
    """Тапсырма статусын жаңарту"""
    conn = sqlite3.connect('ai_qazaq_teachers.db', check_same_thread=False)
    c = conn.cursor()
    
    try:
        if new_status == 'Тексерілді' and score is not None:
            c.execute('''
                UPDATE student_tasks 
                SET status = ?, 
                    teacher_feedback = ?,
                    score = ?,
                    checked_date = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (new_status, feedback, score, task_id))
        else:
            c.execute('''
                UPDATE student_tasks 
                SET status = ?, 
                    teacher_feedback = ?
                WHERE id = ?
            ''', (new_status, feedback, task_id))
        
        conn.commit()
        return True, "✅ Тапсырма күйі жаңартылды!"
        
    except Exception as e:
        print(f"❌ Статус жаңарту қатесі: {e}")
        traceback.print_exc()
        return False, f"Қате: {str(e)}"
    finally:
        conn.close()

def submit_unified_student_answer(task_id, answer_text, answer_file=None):
    """Оқушының жауабын сақтау - ФАЙЛДАРМЕН"""
    conn = sqlite3.connect('ai_qazaq_teachers.db', check_same_thread=False)
    c = conn.cursor()
    
    try:
        file_bytes = None
        file_type = None
        file_name = None
        file_size = 0
        
        if answer_file and hasattr(answer_file, 'read'):
            file_bytes = answer_file.read()
            file_type = answer_file.type
            file_name = answer_file.name
            file_size = len(file_bytes)
        
        c.execute('''
            UPDATE student_tasks 
            SET student_answer_text = ?,
                student_answer_file = ?,
                student_answer_file_type = ?,
                student_answer_file_name = ?,
                student_answer_file_size = ?,
                status = 'Жіберілді',
                student_submitted_date = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (answer_text, file_bytes, file_type, file_name, file_size, task_id))
        
        conn.commit()
        return True, "✅ Жауап сәтті жіберілді!"
        
    except Exception as e:
        print(f"❌ Жауап сақтау қатесі: {e}")
        traceback.print_exc()
        return False, f"Қате: {str(e)}"
    finally:
        conn.close()

def get_unified_task_file(task_id, file_type='task'):
    """Тапсырма немесе жауап файлын алу"""
    conn = sqlite3.connect('ai_qazaq_teachers.db', check_same_thread=False)
    c = conn.cursor()
    
    try:
        if file_type == 'task':
            c.execute('''
                SELECT task_file, task_file_type, task_file_name, task_name 
                FROM student_tasks 
                WHERE id = ? AND task_file IS NOT NULL
            ''', (task_id,))
        else:  # answer
            c.execute('''
                SELECT student_answer_file, student_answer_file_type, student_answer_file_name, task_name 
                FROM student_tasks 
                WHERE id = ? AND student_answer_file IS NOT NULL
            ''', (task_id,))
        
        file_data = c.fetchone()
        
        if file_data:
            if file_type == 'task':
                file_bytes, file_type_db, file_name, task_name = file_data
                if not file_name:
                    ext = get_file_extension(file_type_db)
                    file_name = f"Тапсырма_{task_name}.{ext}"
            else:
                file_bytes, file_type_db, file_name, task_name = file_data
                if not file_name:
                    ext = get_file_extension(file_type_db) if file_type_db else 'file'
                    file_name = f"Жауап_{task_name}.{ext}"
            
            return {
                'data': file_bytes,
                'type': file_type_db,
                'filename': file_name
            }
        
        return None
        
    except Exception as e:
        print(f"❌ Файл алу қатесі: {e}")
        traceback.print_exc()
        return None
    finally:
        conn.close()

def delete_unified_task(task_id):
    """Тапсырманы жою"""
    conn = sqlite3.connect('ai_qazaq_teachers.db', check_same_thread=False)
    c = conn.cursor()
    
    try:
        c.execute("DELETE FROM student_tasks WHERE id = ?", (task_id,))
        conn.commit()
        return True, "✅ Тапсырма жойылды!"
    except Exception as e:
        print(f"❌ Тапсырманы жою қатесі: {e}")
        return False, f"Қате: {str(e)}"
    finally:
        conn.close()

def get_task_statistics_unified(teacher_id):
    """Тапсырмалар статистикасы"""
    conn = sqlite3.connect('ai_qazaq_teachers.db', check_same_thread=False)
    c = conn.cursor()
    
    try:
        c.execute('''
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN status = 'Тағайындалды' THEN 1 ELSE 0 END) as assigned,
                SUM(CASE WHEN status = 'Жіберілді' THEN 1 ELSE 0 END) as submitted,
                SUM(CASE WHEN status = 'Тексерілді' THEN 1 ELSE 0 END) as checked,
                SUM(CASE WHEN due_date < date('now') AND status = 'Тағайындалды' THEN 1 ELSE 0 END) as overdue
            FROM student_tasks
            WHERE teacher_id = ?
        ''', (teacher_id,))
        
        stats = c.fetchone()
        
        return {
            'total': stats[0] or 0,
            'assigned': stats[1] or 0,
            'submitted': stats[2] or 0,
            'checked': stats[3] or 0,
            'overdue': stats[4] or 0
        }
        
    except Exception as e:
        print(f"❌ Статистика алу қатесі: {e}")
        return {}
    finally:
        conn.close()

# ============ ОҚУШЫ ПОРТАЛЫ ФУНКЦИЯЛАРЫ ============
def student_login(username, password):
    """Оқушы кіруі"""
    conn = sqlite3.connect('ai_qazaq_teachers.db', check_same_thread=False)
    c = conn.cursor()
    hashed_password = hash_password(password)
    
    try:
        c.execute("""
        SELECT s.id, s.full_name, s.student_code, s.class_id, c.name as class_name,
               c.subject, s.grade_points, s.academic_performance
        FROM students s
        JOIN student_logins sl ON s.id = sl.student_id
        JOIN classes c ON s.class_id = c.id
        WHERE sl.username = ? AND sl.password = ?
        """, (username, hashed_password))
        
        student = c.fetchone()
        
        # Егер academic_performance жоқ болса, әдепкі мән қосу
        if student and len(student) == 7:  # academic_performance жоқ
            student = student + ("Орташа",)
        
        return student
    except Exception as e:
        print(f"❌ Оқушы кіру қатесі: {e}")
        return None
    finally:
        conn.close()

# ============ МӘТІНДЕР ============
texts = {
    "kk": {
        "title": "AI QAZAQ Teachers",
        "subtitle": "Қазақстандық мұғалімдерге арналған AI платформасы",
        "login": "✅ Кіру",
        "register": "📝 Тіркелу",
        "username": "👤 Пайдаланушы аты",
        "password": "🔒 Құпия сөз",
        "fullname": "📛 Толық аты-жөні",
        "email": "📧 Электронды пошта",
        "school": "🏫 Мектеп атауы",
        "confirm_pass": "🔐 Құпия сөзді растау",
        "welcome": "🎉 Қош келдіңіз",
        "dashboard": "📊 Басқару панелі",
        "classes": "🏫 Сыныптар",
        "students": "👨‍🎓 Оқушылар",
        "student_performance": "📊 Оқушылардың үлгерімі",
        "bzb_tasks": "📝 БЖБ тапсырмалары",
        "student_tasks": "🎯 Оқушыларға тапсырмалар",
        "visual_materials": "📁 Көрнекіліктер",
        "ai_tools": "🤖 AI құралдары",
        "logout": "🚪 Шығу",
        "add_class": "➕ Жаңа сынып",
        "class_name": "Сынып атауы",
        "subject": "Пән",
        "description": "Сипаттама",
        "add": "Қосу",
        "import_students": "📥 Оқушыларды импорттау",
        "select_class": "Сыныпты таңдаңыз",
        "no_classes": "Сізде әлі сыныптар жоқ",
        "student_added": "✅ Оқушы сәтті қосылды!",
        "class_deleted": "✅ Сынып сәтті жойылды!",
        "delete_warning": "⚠️ Сыныпты жоюға сенімдісіз бе? Бұл әрекетті кері қайтару мүмкін емес!",
        "add_student": "➕ Оқушы қосу",
        "student_name": "Оқушының аты-жөні",
        "student_id": "Оқушының коды",
        "import_excel": "Excel файлын жүктеу",
        "no_students": "📚 Бұл сыныпта оқушылар әлі жоқ",
        "points": "Ұпай",
        "academic_performance": "📚 Оқу үлгерімі",
        "delete_student": "🗑️ Оқушыны жою",
        "student_portal": "🎒 Оқушы порталы",
        "ai_lesson_plan": "AI сабақ жоспары",
        "student_analysis": "Оқушы талдауы",
        "task_generator": "Тапсырма генераторы",
        "assessment_rubric": "Бағалау критерийлері",
        "predictive_analysis": "Прогноздық талдау",
        "teaching_advice": "Педагогикалық кеңестер",
        "ai_assistant": "AI көмекші",
        "back": "Артқа",
        "generate": "Жасау",
        "analyze": "Талдау",
        "create": "Құру",
        "view_analysis": "Талдауды қарау",
        "class": "Сынып",
        "average_grade": "Орташа баға",
        "performance_level": "Оқу деңгейі",
        "grade_distribution": "Бағалардың таралуы",
        "export_to_excel": "📥 Excel-ге экспорттау",
        "filter_by_class": "Сынып бойынша сүзгі",
        "filter_by_subject": "Пән бойынша сүзгі",
        "view_details": "Толығырақ қарау",
        "total_students": "Барлық оқушылар",
        "excellent": "Өте жақсы",
        "good": "Жақсы",
        "average": "Орташа",
        "satisfactory": "Қанағаттанарлық",
        "weak": "Әлсіз",
        "assign_task": "➕ Тапсырма беру",
        "task_name": "Тапсырма атауы",
        "task_description": "Тапсырма сипаттамасы",
        "due_date": "Мерзімі",
        "upload_file": "Файл жүктеу",
        "status": "Статус",
        "assigned": "Тағайындалды",
        "not_completed": "Орындалмады",
        "completed": "Орындалды",
        "late": "Кешікті",
        "view_tasks": "Тапсырмаларды қарау",
        "feedback": "Кері байланыс",
        "give_feedback": "Кері байланыс беру",
        "mark_completed": "Орындалды деп белгілеу",
        "download_task": "Тапсырманы жүктеп алу",
        "in_progress": "Орындалуда",
        "all_tasks": "Барлық тапсырмалар",
        "submit_answer": "Жауап жіберу",
        "answer_text": "Жауап мәтіні",
        "answer_file": "Жауап файлы",
        "submit": "Жіберу"
    }
}

# ============ КӨРСЕТУ ФУНКЦИЯЛАРЫ (ТҮЗЕТІЛГЕН) ============
def show_logo_header():
    t = texts[st.session_state.language]
    
    st.markdown(f"""
    <div style='background: linear-gradient(135deg, #0066CC, #CC0000); 
                padding: 1.5rem; border-radius: 10px; color: white; margin-bottom: 20px;'>
        <h1 style='margin: 0; text-align: center;'>🇰🇿 AI QAZAQ TEACHERS</h1>
        <p style='margin: 0; text-align: center; font-size: 1.2rem;'>{t['subtitle']}</p>
    </div>
    """, unsafe_allow_html=True)

def show_classes_management():
    """Сыныптарды басқару"""
    t = texts[st.session_state.language]
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        st.markdown(f"<h2>🏫 {t['classes']}</h2>", unsafe_allow_html=True)
    
    with col2:
        if st.button(f"➕ {t['add_class']}", use_container_width=True):
            st.session_state.show_add_class = True
    
    if st.session_state.get('show_add_class', False):
        with st.form("add_class_form"):
            st.subheader(f"➕ {t['add_class']}")
            
            name = st.text_input(f"🏫 {t['class_name']}")
            subject = st.text_input(f"📚 {t['subject']}")
            grade_level = st.selectbox("🎯 Сынып деңгейі", ["1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11"])
            description = st.text_area(f"📄 {t['description']}")
            
            col_submit, col_cancel = st.columns(2)
            
            with col_submit:
                if st.form_submit_button(f"✅ {t['add']}", use_container_width=True):
                    if name and subject:
                        if add_class(st.session_state.user[0], name, subject, grade_level, description):
                            st.success(f"✅ '{name}' сыныбы сәтті қосылды!")
                            st.session_state.show_add_class = False
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error("❌ Сыныпты қосу кезінде қате пайда болды")
                    else:
                        st.error("❌ Сынып атауы мен пәнді толтырыңыз!")
            
            with col_cancel:
                if st.form_submit_button(f"❌ Болдырмау", use_container_width=True):
                    st.session_state.show_add_class = False
                    st.rerun()
    
    # Сыныптар тізімі
    classes = get_classes(st.session_state.user[0])
    
    if not classes:
        st.info(f"📭 {t['no_classes']}")
        return
    
    for class_item in classes:
        with st.expander(f"🏫 {class_item[1]} - {class_item[2]} (Сынып {class_item[3]})", expanded=False):
            col_info, col_actions = st.columns([3, 1])
            
            with col_info:
                st.markdown(f"**Пән:** {class_item[2]}")
                st.markdown(f"**Сынып деңгейі:** {class_item[3]}")
                if st.button(f"👨‍🎓 Оқушыларды басқару", key=f"manage_{class_item[0]}"):
                    st.session_state.current_class_id = class_item[0]
                    st.session_state.current_page = 'students'
                    st.rerun()
            
            with col_actions:
                if st.button("🗑️ Сыныпты жою", key=f"delete_{class_item[0]}"):
                    st.session_state.class_to_delete = class_item[0]
                    st.session_state.confirm_delete = True
    
    # Сыныпты жою растау
    if st.session_state.get('confirm_delete', False) and st.session_state.get('class_to_delete'):
        st.warning(f"⚠️ {t['delete_warning']}")
        col_confirm, col_cancel = st.columns(2)
        
        with col_confirm:
            if st.button("✅ Иә, жою", use_container_width=True):
                if delete_class(st.session_state.class_to_delete):
                    st.success(f"✅ {t['class_deleted']}")
                    st.session_state.class_to_delete = None
                    st.session_state.confirm_delete = False
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("❌ Сыныпты жою кезінде қате пайда болды")
        
        with col_cancel:
            if st.button("❌ Жоқ, болдырмау", use_container_width=True):
                st.session_state.class_to_delete = None
                st.session_state.confirm_delete = False
                st.rerun()

def show_students_management():
    """Оқушыларды басқару"""
    t = texts[st.session_state.language]
    
    st.markdown(f"<h2>👨‍🎓 {t['students']}</h2>", unsafe_allow_html=True)
    
    # Session state инициализациясы
    if 'current_class_id' not in st.session_state:
        st.session_state.current_class_id = None
    
    # Сыныпты таңдау
    classes = get_classes(st.session_state.user[0])
    
    if not classes:
        st.info(f"📭 {t['no_classes']}")
        return
    
    # Сынып опцияларын құру
    class_options = {}
    for c in classes:
        class_id, name, subject, grade_level = c
        class_name = f"{name} - {subject} (Сынып {grade_level})"
        class_options[class_name] = class_id
    
    # Тандалған сыныпты анықтау
    if st.session_state.current_class_id is None:
        st.session_state.current_class_id = classes[0][0]
        selected_class_name = list(class_options.keys())[0]
    else:
        # Тандалған сыныптың атауын табу
        selected_class_name = ""
        for c in classes:
            if c[0] == st.session_state.current_class_id:
                selected_class_name = f"{c[1]} - {c[2]} (Сынып {c[3]})"
                break
        
        if not selected_class_name:
            selected_class_name = list(class_options.keys())[0]
            st.session_state.current_class_id = class_options[selected_class_name]
    
    # Сыныпты таңдау
    selected_class_name = st.selectbox(
        f"🎯 {t['select_class']}",
        list(class_options.keys()),
        index=list(class_options.keys()).index(selected_class_name) if selected_class_name in class_options else 0
    )
    
    # Тандалған сыныпты сақтау
    st.session_state.current_class_id = class_options[selected_class_name]
    current_class_id = st.session_state.current_class_id
    
    # Тандалған сынып ақпараты
    for class_item in classes:
        if class_item[0] == current_class_id:
            st.info(f"**Тандалған сынып:** {class_item[1]} - {class_item[2]} (Сынып {class_item[3]})")
            break
    
    # Оқушыларды қосу формасы
    st.markdown("---")
    st.markdown(f"### ➕ {t['add_student']}")
    
    with st.form("add_student_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            full_name = st.text_input(f"👤 {t['student_name']}", placeholder="Мысалы: Әлімхан Сағатов")
            student_code = st.text_input(f"🎯 {t['student_id']}", placeholder="Мысалы: S001")
        
        with col2:
            grade_points = st.number_input(f"⭐ {t['points']}", min_value=0, max_value=10, value=5)
            academic_performance = st.selectbox(
                f"📊 {t['academic_performance']}",
                ["Өте жақсы", "Жақсы", "Орташа", "Қанағаттанарлық", "Әлсіз"]
            )
        
        submit_button = st.form_submit_button(f"➕ {t['add_student']}", use_container_width=True)
        
        if submit_button:
            if full_name and student_code:
                if add_student(current_class_id, full_name, student_code, grade_points, academic_performance):
                    st.success(f"✅ {t['student_added']}")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("❌ Оқушыны қосу кезінде қате пайда болды")
            else:
                st.error("❌ Оқушының аты мен кодын толтырыңыз!")
    
    # Оқушылар тізімі
    st.markdown("---")
    st.markdown("### 👨‍🎓 Оқушылар тізімі")
    
    students = get_students_by_class(current_class_id)
    
    if not students:
        st.info(f"📭 {t['no_students']}")
        return
    
    st.success(f"✅ Барлығы: {len(students)} оқушы")
    
    # Әр оқушы үшін карточка
    for student in students:
        student_id = student[0]
        student_name = student[2] if len(student) > 2 else "Аты жоқ"
        student_code_val = student[3] if len(student) > 3 else "Коды жоқ"
        grade_points_val = student[4] if len(student) > 4 else 0
        academic_performance_val = student[5] if len(student) > 5 else "Орташа"
        
        with st.expander(f"**{student_name}** ({student_code_val}) - {grade_points_val} балл", expanded=False):
            col_info, col_login, col_delete = st.columns([3, 2, 1])
            
            with col_info:
                st.markdown(f"**Оқушы коды:** {student_code_val}")
                st.markdown(f"**Балл:** {grade_points_val}")
                st.markdown(f"**Оқу деңгейі:** {academic_performance_val}")
                st.markdown(f"**ID:** {student_id}")
            
            with col_login:
                st.markdown("**🔐 Логин басқару**")
                logins = get_student_logins(student_id)
                
                if not logins:
                    if st.button("Логин құру", key=f"create_{student_id}", use_container_width=True):
                        # Логин құру
                        username = f"student_{student_code_val}"
                        password = generate_random_password()
                        
                        success, message = register_student_login(student_id, username, password)
                        if success:
                            st.success(f"✅ Логин құрылды!")
                            st.code(f"Логин: {username}\nҚұпия сөз: {password}", language="text")
                            time.sleep(2)
                            st.rerun()
                        else:
                            st.error(f"❌ {message}")
                else:
                    for login in logins:
                        login_id, username = login
                        
                        st.markdown(f"**Логин:** `{username}`")
                        
                        col_btn1, col_btn2 = st.columns(2)
                        
                        with col_btn1:
                            if st.button("🔄", key=f"change_{login_id}", help="Құпия сөзді өзгерту"):
                                new_password = generate_random_password()
                                if update_student_password(login_id, new_password):
                                    st.success(f"✅ Жаңа құпия сөз: {new_password}")
                                    time.sleep(2)
                                    st.rerun()
                        
                        with col_btn2:
                            if st.button("🗑️", key=f"del_login_{login_id}", help="Логинды жою"):
                                if delete_student_login(login_id):
                                    st.success("✅ Логин жойылды")
                                    time.sleep(1)
                                    st.rerun()
            
            with col_delete:
                st.markdown("**⚠️ Оқушыны жою**")
                if st.button("🗑️ Жою", key=f"delete_{student_id}", use_container_width=True):
                    if delete_student(student_id):
                        st.success("✅ Оқушы жойылды!")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("❌ Оқушыны жою кезінде қате пайда болды")
    
    # Excel импорттау опциясы
    st.markdown("---")
    with st.expander(f"📁 {t['import_excel']}"):
        uploaded_file = st.file_uploader("Excel файлын жүктеңіз (.xlsx)", type=["xlsx"])
        
        if uploaded_file is not None:
            try:
                df = pd.read_excel(uploaded_file)
                st.write("Файл құрамы:", df.head())
                
                if st.button("📥 Оқушыларды импорттау"):
                    success_count = 0
                    for _, row in df.iterrows():
                        if 'full_name' in df.columns and 'student_code' in df.columns:
                            full_name = row['full_name']
                            student_code = row['student_code']
                            grade_points = row.get('grade_points', 5)
                            academic_performance = row.get('academic_performance', 'Орташа')
                            
                            if add_student(current_class_id, full_name, student_code, grade_points, academic_performance):
                                success_count += 1
                    
                    st.success(f"✅ {success_count} оқушы сәтті импортталды!")
                    time.sleep(1)
                    st.rerun()
            except Exception as e:
                st.error(f"❌ Файлды өңдеу кезінде қате: {e}")

def show_student_performance():
    """Оқушылардың үлгерімін көрсету"""
    t = texts[st.session_state.language]
    st.markdown(f"<h2>📊 {t['student_performance']}</h2>", unsafe_allow_html=True)
    
    classes = get_classes(st.session_state.user[0])
    if not classes:
        st.info("📭 Сізде әлі сыныптар жоқ")
        return
    
    all_students = []
    for class_item in classes:
        students = get_students_by_class(class_item[0])
        for student in students:
            try:
                grade_points = student[4] if len(student) > 4 else 0
                points_value = int(grade_points) if grade_points is not None else 0
            except (ValueError, TypeError):
                points_value = 0
            
            academic_performance = student[5] if len(student) > 5 else "Орташа"
            
            all_students.append({
                'class': class_item[1],
                'name': student[2] if len(student) > 2 else "Аты жоқ",
                'code': student[3] if len(student) > 3 else "Коды жоқ",
                'points': points_value,
                'performance': academic_performance,
                'grade': points_to_grade(points_value)
            })
    
    if not all_students:
        st.info("📭 Оқушылар жоқ")
        return
    
    df = pd.DataFrame(all_students)
    
    if df['points'].dtype == 'object':
        df['points'] = pd.to_numeric(df['points'], errors='coerce').fillna(0)
    
    # Статистика
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Барлық оқушылар", len(df))
    with col2:
        avg_points = df['points'].mean()
        st.metric("Орташа балл", f"{avg_points:.1f}")
    with col3:
        excellent = len(df[df['grade'] == 'A'])
        st.metric("Өте жақсы (A)", excellent)
    with col4:
        weak = len(df[df['grade'] == 'F'])
        st.metric("Әлсіз (F)", weak)
    
    # Кесте
    display_df = df.copy()
    display_df['points'] = display_df['points'].astype(str) + ' балл'
    st.dataframe(display_df, use_container_width=True)
    
    # График
    if len(df) > 0:
        fig, ax = plt.subplots(1, 2, figsize=(12, 5))
        
        grade_counts = df['grade'].value_counts().sort_index()
        colors = ['#28a745', '#ffc107', '#fd7e14', '#dc3545', '#6c757d']
        ax[0].bar(grade_counts.index, grade_counts.values, color=colors[:len(grade_counts)])
        ax[0].set_title('Бағалардың таралуы')
        ax[0].set_xlabel('Баға')
        ax[0].set_ylabel('Оқушылар саны')
        
        class_avg = df.groupby('class')['points'].mean()
        ax[1].bar(class_avg.index, class_avg.values)
        ax[1].set_title('Сыныптар бойынша орташа балл')
        ax[1].set_xlabel('Сынып')
        ax[1].set_ylabel('Орташа балл')
        ax[1].tick_params(axis='x', rotation=45)
        
        st.pyplot(fig)

def show_bzb_tasks():
    """БЖБ тапсырмаларын көрсету (өшіру функциясы қосылды)"""
    t = texts[st.session_state.language]
    st.markdown(f"<h2>📝 {t['bzb_tasks']}</h2>", unsafe_allow_html=True)
    
    # Тапсырма қосу формасы
    with st.form("add_bzb_task"):
        st.subheader("📤 Жаңа БЖБ тапсырмасын қосу")
        
        classes = get_classes(st.session_state.user[0])
        if not classes:
            st.info("Алдымен сынып қосыңыз.")
            return
        
        class_options = {f"{c[1]} (Сынып {c[3]})": c[0] for c in classes}
        selected_class = st.selectbox("🎯 Сыныпты таңдаңыз", list(class_options.keys()))
        class_id = class_options[selected_class]
        
        task_name = st.text_input("📝 Тапсырма атауы")
        task_file = st.file_uploader("📁 Файл жүктеу", type=['pdf', 'doc', 'docx', 'txt', 'xlsx', 'jpg', 'png', 'pptx'])
        completion_rate = st.slider("✅ Орындалу деңгейі (%)", 0, 100, 50)
        difficulty_level = st.selectbox("⚡ Қиындық деңгейі", ["Оңай", "Орташа", "Қиын"])
        
        if st.form_submit_button("📤 Тапсырманы жүктеу", use_container_width=True):
            if task_name and task_file:
                if save_bzb_task(st.session_state.user[0], class_id, task_name, task_file, 
                               task_file.type, completion_rate, difficulty_level):
                    st.success("✅ БЖБ тапсырмасы сәтті жүктелді!")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("❌ Тапсырманы жүктеу кезінде қате пайда болды")
            else:
                st.error("❌ Тапсырма атауы мен файлын толтырыңыз!")
    
    # Тапсырмалар тізімі
    st.markdown("---")
    st.subheader("📋 БЖБ тапсырмалары тізімі")
    
    tasks = get_bzb_tasks(st.session_state.user[0])
    
    if not tasks:
        st.info("📭 БЖБ тапсырмалары жоқ")
        return
    
    for task in tasks:
        with st.expander(f"📝 {task['name']} - {task['class_name']}", expanded=False):
            col1, col2, col3 = st.columns([3, 1, 1])
            
            with col1:
                st.markdown(f"**Сынып:** {task['class_name']}")
                st.markdown(f"**Жүктелген күні:** {task['uploaded']}")
                st.markdown(f"**Орындалу деңгейі:** {task['rate']}%")
                st.markdown(f"**Қиындық деңгейі:** {task['difficulty']}")
                
                if task['ai_solution']:
                    with st.expander("🤖 AI шешімі", expanded=False):
                        st.info(task['ai_solution'])
            
            with col2:
                if st.button("👁️ Алдын ала қарау", key=f"preview_{task['id']}"):
                    st.session_state.preview_file = {'id': task['id'], 'type': 'bzb', 'name': task['name']}
                    st.rerun()
                
                task_data = get_bzb_task(task['id'])
                if task_data:
                    file_extension = get_file_extension(task_data['type'])
                    st.download_button(
                        label="📥 Жүктеп алу",
                        data=task_data['data'],
                        file_name=f"{task_data['name']}.{file_extension}",
                        mime=task_data['type'],
                        key=f"download_{task['id']}"
                    )
            
            with col3:
                if st.button("🗑️ Өшіру", key=f"delete_{task['id']}", use_container_width=True):
                    if delete_bzb_task(task['id']):
                        st.success("✅ БЖБ тапсырмасы өшірілді!")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("❌ Тапсырманы өшіру кезінде қате пайда болды")

def show_student_tasks():
    """Оқушыларға тапсырмалар бөлімі - ТҮЗЕТІЛГЕН ФАЙЛДАРМЕН"""
    t = texts[st.session_state.language]
    
    st.markdown(f"<h2>🎯 {t['student_tasks']}</h2>", unsafe_allow_html=True)
    
    # Бөлімдер
    tab1, tab2, tab3 = st.tabs(["📤 Тапсырма беру", "📋 Тапсырмалар тізімі", "📊 Статистика"])
    
    with tab1:
        show_unified_assign_task_form()
    
    with tab2:
        show_unified_assigned_tasks()
    
    with tab3:
        show_task_statistics_unified_section()

def show_unified_assign_task_form():
    """Жаңа тапсырма беру формасы - ФАЙЛДАРМЕН"""
    t = texts[st.session_state.language]
    
    st.subheader("📤 Жаңа тапсырма беру")
    
    with st.form("new_task_form"):
        # Сыныпты таңдау
        classes = get_classes(st.session_state.user[0])
        if not classes:
            st.info("Алдымен сынып қосыңыз.")
            return
        
        class_options = {f"{c[1]} - {c[2]}": c[0] for c in classes}
        selected_class_name = st.selectbox("🎯 Сыныпты таңдаңыз", list(class_options.keys()))
        selected_class_id = class_options[selected_class_name]
        
        # Оқушыны таңдау
        students = get_students_by_class(selected_class_id)
        if not students:
            st.info("Бұл сыныпта оқушылар жоқ.")
            return
        
        student_options = {}
        for s in students:
            student_name = s[2] if len(s) > 2 else "Аты жоқ"
            student_code = s[3] if len(s) > 3 else "Коды жоқ"
            student_options[f"{student_name} ({student_code})"] = s[0]
        
        selected_students = st.multiselect(
            "👨‍🎓 Оқушыларды таңдаңыз (бір немесе бірнеше)",
            list(student_options.keys())
        )
        
        # Тапсырма ақпараты
        col1, col2 = st.columns(2)
        with col1:
            task_name = st.text_input(f"📝 {t['task_name']}", placeholder="Тапсырма атауы")
            due_date = st.date_input(f"📅 {t['due_date']}", value=datetime.now().date() + timedelta(days=7))
            points = st.number_input(f"⭐ {t['points']}", min_value=0, max_value=100, value=10)
        
        with col2:
            difficulty = st.selectbox("⚡ Қиындық", ["Оңай", "Орташа", "Қиын"])
            tags = st.multiselect("🏷️ Тегтер", ["Математика", "Қазақ тілі", "Физика", "Тест", "Үй тапсырмасы", "Практика"])
            task_file = st.file_uploader(
                f"📁 {t['upload_file']} (міндетті емес)",
                type=['pdf', 'doc', 'docx', 'txt', 'jpg', 'png', 'ppt', 'pptx', 'xlsx', 'zip']
            )
        
        task_description = st.text_area(
            f"📄 {t['task_description']}",
            placeholder="Тапсырманың толық сипаттамасы...",
            height=150
        )
        
        if st.form_submit_button(f"🚀 {t['assign_task']}", use_container_width=True):
            if task_name and selected_students:
                success_count = 0
                error_messages = []
                
                for student_display in selected_students:
                    student_id = student_options[student_display]
                    
                    task_data = {
                        'task_name': task_name,
                        'task_description': task_description,
                        'due_date': due_date.strftime('%Y-%m-%d'),
                        'points': points,
                        'difficulty': difficulty,
                        'tags': ','.join(tags) if tags else None,
                        'task_file': task_file
                    }
                    
                    success, message = save_unified_student_task(
                        st.session_state.user[0],
                        student_id,
                        selected_class_id,
                        task_data
                    )
                    
                    if success:
                        success_count += 1
                    else:
                        error_messages.append(f"{student_display}: {message}")
                
                if success_count > 0:
                    success_msg = f"✅ {success_count} оқушыға тапсырма сәтті жіберілді!"
                    if error_messages:
                        success_msg += f"\n\n⚠️ Қателіктер:\n" + "\n".join(error_messages)
                    st.success(success_msg)
                    time.sleep(2)
                    st.rerun()
                else:
                    error_msg = "❌ Тапсырмалар жіберілмеді!\n" + "\n".join(error_messages)
                    st.error(error_msg)
            else:
                st.error("❌ Тапсырма атауы мен оқушыларды таңдаңыз!")

def show_unified_assigned_tasks():
    """Жіберілген тапсырмалар тізімі - ФАЙЛДАРМЕН КӨРСЕТУ"""
    t = texts[st.session_state.language]
    
    st.subheader("📋 Жіберілген тапсырмалар")
    
    # Тапсырмаларды алу
    tasks = get_unified_student_tasks_by_teacher(st.session_state.user[0])
    
    if not tasks:
        st.info("📭 Тапсырмалар жоқ")
        return
    
    # Статистика
    total_tasks = len(tasks)
    assigned = len([t for t in tasks if t['status'] == 'Тағайындалды'])
    submitted = len([t for t in tasks if t['status'] == 'Жіберілді'])
    checked = len([t for t in tasks if t['status'] == 'Тексерілді'])
    overdue = len([t for t in tasks if t.get('is_overdue', False)])
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Барлығы", total_tasks)
    with col2:
        st.metric("Тағайындалды", assigned)
    with col3:
        st.metric("Жіберілді", submitted)
    with col4:
        st.metric("Кешікті", overdue)
    
    # Сүзгілер
    st.markdown("---")
    col_filter1, col_filter2, col_filter3 = st.columns(3)
    with col_filter1:
        status_filter = st.selectbox(
            "Статус бойынша",
            ["Барлығы", "Тағайындалды", "Кешікті", "Жіберілді", "Тексерілді"]
        )
    with col_filter2:
        search_query = st.text_input("Іздеу...")
    with col_filter3:
        sort_by = st.selectbox("Сұрыптау", ["Мерзім", "Оқушы", "Статус"])
    
    # Тапсырмаларды сүзу
    filtered_tasks = tasks
    if status_filter != "Барлығы":
        filtered_tasks = [t for t in filtered_tasks if t['display_status'] == status_filter]
    
    if search_query:
        filtered_tasks = [t for t in filtered_tasks if 
                         search_query.lower() in t['task_name'].lower() or 
                         search_query.lower() in t['student_name'].lower()]
    
    # Сұрыптау
    if sort_by == "Мерзім":
        filtered_tasks.sort(key=lambda x: x.get('due_date', ''))
    elif sort_by == "Оқушы":
        filtered_tasks.sort(key=lambda x: x.get('student_name', ''))
    else:
        filtered_tasks.sort(key=lambda x: x.get('status', ''))
    
    # Көрсету
    st.info(f"📊 Көрсетілуде: {len(filtered_tasks)} тапсырма")
    
    for task in filtered_tasks:
        status_icons = {
            'Тағайындалды': '🔴',
            'Кешікті': '⏰',
            'Жіберілді': '🟡',
            'Тексерілді': '🟢'
        }
        
        status_icon = status_icons.get(task['display_status'], '⚪')
        
        with st.expander(f"{status_icon} {task['task_name']} - {task['student_name']}", expanded=False):
            col_info, col_actions, col_delete = st.columns([3, 2, 1])
            
            with col_info:
                st.write(f"**👨‍🎓 Оқушы:** {task['student_name']}")
                st.write(f"**🏫 Сынып:** {task['class_name']}")
                st.write(f"**📅 Мерзімі:** {task.get('due_date_formatted', task['due_date'])}")
                
                if task.get('is_overdue'):
                    st.error(f"⏰ Мерзімі өткен! ({task.get('days_left', 0)} күн бұрын)")
                
                st.write(f"**⭐ Ұпай:** {task['points']}")
                st.write(f"**📊 Статус:** {task['display_status']}")
                
                if task.get('tags'):
                    st.write(f"**🏷️ Тегтер:** {task['tags']}")
                
                if task.get('difficulty'):
                    st.write(f"**⚡ Қиындық:** {task['difficulty']}")
                
                # ТАПСЫРМА ФАЙЛЫ ТУРАЛЫ АҚПАРАТ
                if task.get('task_file_name'):
                    st.write(f"**📎 Тапсырма файлы:** {task['task_file_name']}")
                    if task.get('task_file_size_str'):
                        st.write(f"**📦 Көлемі:** {task['task_file_size_str']}")
                
                if task.get('student_submitted_date_formatted'):
                    st.write(f"**📤 Жіберілді:** {task['student_submitted_date_formatted']}")
                
                # ЖАУАП ФАЙЛЫ ТУРАЛЫ АҚПАРАТ
                if task.get('student_answer_file_name'):
                    st.write(f"**📎 Жауап файлы:** {task['student_answer_file_name']}")
                    if task.get('student_answer_file_size_str'):
                        st.write(f"**📦 Көлемі:** {task['student_answer_file_size_str']}")
                
                if task.get('score'):
                    st.success(f"**📊 Баға:** {task['score']}/{task['points']}")
                
                if task['task_description']:
                    with st.expander("📝 Сипаттама", expanded=False):
                        st.write(task['task_description'])
                
                if task.get('student_answer_text'):
                    with st.expander("✍️ Оқушының жауабы", expanded=False):
                        st.write(task['student_answer_text'])
                
                if task.get('teacher_feedback'):
                    with st.expander("💬 Кері байланыс", expanded=False):
                        st.write(task['teacher_feedback'])
            
            with col_actions:
                # ТАПСЫРМА ФАЙЛЫН КӨРСЕТУ ЖӘНЕ ЖҮКТЕП АЛУ
                task_file = get_unified_task_file(task['id'], 'task')
                if task_file:
                    st.markdown("**📥 Тапсырма файлы:**")
                    
                    # Файлды көрсету түймесі
                    if st.button("👁️ Көрсету", key=f"show_task_{task['id']}", use_container_width=True):
                        st.session_state.preview_file = {
                            'id': task['id'],
                            'type': 'task',
                            'name': task_file['filename']
                        }
                        st.rerun()
                    
                    # Файлды жүктеп алу түймесі
                    st.download_button(
                        label="📥 Жүктеп алу",
                        data=task_file['data'],
                        file_name=task_file['filename'],
                        mime=task_file['type'],
                        key=f"task_dl_{task['id']}"
                    )
                
                # ЖАУАП ФАЙЛЫН КӨРСЕТУ ЖӘНЕ ЖҮКТЕП АЛУ
                answer_file = get_unified_task_file(task['id'], 'answer')
                if answer_file:
                    st.markdown("---")
                    st.markdown("**📥 Жауап файлы:**")
                    
                    # Файлды көрсету түймесі
                    if st.button("👁️ Көрсету", key=f"show_answer_{task['id']}", use_container_width=True):
                        st.session_state.preview_file = {
                            'id': task['id'],
                            'type': 'answer',
                            'name': answer_file['filename']
                        }
                        st.rerun()
                    
                    # Файлды жүктеп алу түймесі
                    st.download_button(
                        label="📥 Жүктеп алу",
                        data=answer_file['data'],
                        file_name=answer_file['filename'],
                        mime=answer_file['type'],
                        key=f"answer_dl_{task['id']}"
                    )
                
                # Бағалау формасы
                st.markdown("---")
                with st.form(key=f"grade_form_{task['id']}"):
                    st.write("**📊 Бағалау**")
                    
                    score = st.number_input(
                        "Балл",
                        min_value=0,
                        max_value=task['points'],
                        value=task.get('score', 0),
                        key=f"score_{task['id']}"
                    )
                    
                    feedback = st.text_area(
                        "Кері байланыс",
                        value=task.get('teacher_feedback', ''),
                        height=100,
                        key=f"feedback_{task['id']}"
                    )
                    
                    col_btn1, col_btn2 = st.columns(2)
                    
                    with col_btn1:
                        if st.form_submit_button("💾 Сақтау", use_container_width=True):
                            success, message = update_unified_task_status(
                                task['id'], 
                                'Тексерілді',
                                feedback,
                                score
                            )
                            if success:
                                st.success("✅ Баға сақталды!")
                                time.sleep(1)
                                st.rerun()
            
            with col_delete:
                st.markdown("---")
                if st.button("🗑️ Жою", key=f"delete_task_{task['id']}", use_container_width=True):
                    success, message = delete_unified_task(task['id'])
                    if success:
                        st.success("✅ Тапсырма жойылды!")
                        time.sleep(1)
                        st.rerun()

def show_task_statistics_unified_section():
    """Тапсырма статистикасы"""
    st.subheader("📊 Тапсырмалар статистикасы")
    
    stats = get_task_statistics_unified(st.session_state.user[0])
    
    if not stats:
        st.info("Статистика жоқ")
        return
    
    # Статистиканы көрсету
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        st.metric("Барлығы", stats['total'])
    
    with col2:
        st.metric("Тағайындалды", stats['assigned'])
    
    with col3:
        st.metric("Жіберілді", stats['submitted'])
    
    with col4:
        st.metric("Тексерілді", stats['checked'])
    
    with col5:
        st.metric("Кешікті", stats['overdue'])
    
    # График
    st.markdown("---")
    st.subheader("📈 Статистика графигі")
    
    categories = ['Тағайындалды', 'Жіберілді', 'Тексерілді', 'Кешікті']
    values = [stats['assigned'], stats['submitted'], stats['checked'], stats['overdue']]
    
    fig, ax = plt.subplots(figsize=(10, 6))
    bars = ax.bar(categories, values, color=['#ffc107', '#28a745', '#007bff', '#dc3545'])
    
    # Мәндерді бағандардың үстіне жазу
    for bar, value in zip(bars, values):
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height + 0.1,
                f'{value}', ha='center', va='bottom')
    
    ax.set_title('Тапсырмалардың статусы бойынша таралуы')
    ax.set_ylabel('Тапсырмалар саны')
    
    st.pyplot(fig)

def show_visual_materials():
    """Көрнекіліктерді көрсету"""
    t = texts[st.session_state.language]
    
    st.markdown(f"<h2>📁 {t['visual_materials']}</h2>", unsafe_allow_html=True)
    
    # Файл жүктеу бөлімі
    with st.form("upload_file_form"):
        st.subheader("📤 Жаңа файл жүктеу")
        
        col1, col2 = st.columns(2)
        
        with col1:
            file_name = st.text_input("📝 Файл атауы")
            uploaded_file = st.file_uploader(
                "📁 Файлды таңдаңыз",
                type=['pdf', 'doc', 'docx', 'txt', 'xlsx', 'pptx', 'jpg', 'png', 'mp4', 'mp3', 'zip']
            )
        
        with col2:
            category = st.selectbox(
                "📂 Категория",
                ["Сабақ материалы", "Көрнекілік", "Тапсырма", "Бақылау", "БЖБ", "Басқа"]
            )
        
        if st.form_submit_button("📤 Файлды жүктеу", use_container_width=True):
            if file_name and uploaded_file:
                if save_file_to_db(st.session_state.user[0], file_name, uploaded_file, category):
                    st.success("✅ Файл сәтті жүктелді!")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("❌ Файлды жүктеу кезінде қате пайда болды")
            else:
                st.error("❌ Файл атауы мен файлды толтырыңыз!")
    
    # Файлдар тізімі
    st.markdown("---")
    st.subheader("📋 Файлдар тізімі")
    
    files = get_saved_files(st.session_state.user[0])
    
    if not files:
        st.info("📭 Файлдар жоқ")
        return
    
    # Категория бойынша сүзгі
    categories = ["Барлығы"] + sorted(list(set([f['category'] for f in files])))
    selected_category = st.selectbox("Категория бойынша сүзгі", categories)
    
    # Көрсетілетін файлдар
    display_files = files
    if selected_category != "Барлығы":
        display_files = [f for f in files if f['category'] == selected_category]
    
    for file in display_files:
        with st.expander(f"📁 {file['name']} ({file['category']})", expanded=False):
            col_info, col_preview, col_actions = st.columns([2, 2, 1])
            
            with col_info:
                st.markdown(f"**Түрі:** {file['type']}")
                st.markdown(f"**Көлемі:** {file['size']}")
                st.markdown(f"**Жүктелген:** {file['uploaded']}")
                st.markdown(f"**Категория:** {file['category']}")
            
            with col_preview:
                if st.button("👁️ Көрсету", key=f"preview_{file['id']}"):
                    st.session_state.preview_file = {'id': file['id'], 'type': 'visual'}
                    st.rerun()
                
                # Файлды жүктеп алу
                st.download_button(
                    label="📥 Жүктеп алу",
                    data=file['data'],
                    file_name=file['name'],
                    mime=file['type'],
                    key=f"download_{file['id']}"
                )
            
            with col_actions:
                if st.button("🗑️", key=f"delete_{file['id']}"):
                    if delete_file(file['id']):
                        st.success("✅ Файл жойылды!")
                        time.sleep(1)
                        st.rerun()

def show_ai_tools():
    """AI құралдарын көрсету"""
    t = texts[st.session_state.language]
    
    st.markdown(f"<h2>🤖 {t['ai_tools']}</h2>", unsafe_allow_html=True)
    
    # AI құралдары карточкалары
    col1, col2 = st.columns(2)
    
    with col1:
        with st.container():
            st.markdown("""
            <div style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                        padding: 20px; border-radius: 10px; color: white; margin-bottom: 20px;'>
                <h3>📝 AI Сабақ жоспары</h3>
                <p>Пән, сынып деңгейі және тақырып негізінде сабақ жоспарын жасау</p>
            </div>
            """, unsafe_allow_html=True)
            
            if st.button("📝 Жасау", use_container_width=True):
                st.session_state.current_ai_tool = "lesson_plan"
                st.rerun()
    
    with col2:
        with st.container():
            st.markdown("""
            <div style='background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); 
                        padding: 20px; border-radius: 10px; color: white; margin-bottom: 20px;'>
                <h3>📊 Оқушы талдауы</h3>
                <p>Оқушылардың үлгерімі бойынша толық талдау жасау</p>
            </div>
            """, unsafe_allow_html=True)
            
            if st.button("📊 Талдау", use_container_width=True):
                st.session_state.current_ai_tool = "student_analysis"
                st.rerun()
    
    col3, col4 = st.columns(2)
    
    with col3:
        with st.container():
            st.markdown("""
            <div style='background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%); 
                        padding: 20px; border-radius: 10px; color: white; margin-bottom: 20px;'>
                <h3>🎯 Тапсырма генераторы</h3>
                <p>Тақырып пен деңгей бойынша тапсырмалар жасау</p>
            </div>
            """, unsafe_allow_html=True)
            
            if st.button("🎯 Құру", use_container_width=True):
                st.session_state.current_ai_tool = "task_generator"
                st.rerun()
    
    with col4:
        with st.container():
            st.markdown("""
            <div style='background: linear-gradient(135deg, #43e97b 0%, #38f9d7 100%); 
                        padding: 20px; border-radius: 10px; color: white; margin-bottom: 20px;'>
                <h3>📋 Бағалау критерийлері</h3>
                <p>Тапсырмалар үшін бағалау критерийлерін жасау</p>
            </div>
            """, unsafe_allow_html=True)
            
            if st.button("📋 Жасау", use_container_width=True):
                st.session_state.current_ai_tool = "assessment_rubric"
                st.rerun()
    
    # AI құралын көрсету
    if st.session_state.get('current_ai_tool'):
        show_ai_tool_content(st.session_state.current_ai_tool)

def show_ai_tool_content(tool_name):
    """AI құралының мазмұнын көрсету"""
    t = texts[st.session_state.language]
    
    st.markdown("---")
    
    if st.button(f"← {t['back']}"):
        st.session_state.current_ai_tool = None
        st.rerun()
    
    if tool_name == "lesson_plan":
        show_ai_lesson_plan()
    elif tool_name == "student_analysis":
        show_student_analysis()
    elif tool_name == "task_generator":
        show_task_generator()
    elif tool_name == "assessment_rubric":
        show_assessment_rubric()

def show_ai_lesson_plan():
    """AI сабақ жоспары"""
    st.subheader("📝 AI Сабақ жоспары")
    
    with st.form("lesson_plan_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            subject = st.text_input("Пән", value="Математика")
            grade_level = st.selectbox("Сынып", ["1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11"])
            lesson_type = st.selectbox("Сабақ түрі", ["Жаңа білім", "Бекіту", "Қорытынды", "Практикалық", "Бақылау"])
        
        with col2:
            topic = st.text_input("Тақырып", value="Бөлшектерді қосу")
            duration = st.number_input("Сабақ ұзақтығы (минут)", min_value=20, max_value=120, value=40)
            teaching_method = st.selectbox("Оқыту әдісі", ["Дәстүрлі", "Интерактивті", "Топтық", "Жобалық", "Проблемалық"])
        
        goals = st.text_area("Сабақтың мақсаттары", 
                           value="1. Бөлшектерді қосу ережесін меңгерту\n2. Есептер шығару дағдысын дамыту")
        equipment = st.text_input("Қажетті құрал-жабдықтар", 
                                value="Оқулық, дәптер, бор, слайдтар, интерактивті тақта")
        
        if st.form_submit_button("🤖 Сабақ жоспарын жасау"):
            with st.spinner("AI сабақ жоспарын жасауда..."):
                time.sleep(2)
                
                st.success("✅ Сабақ жоспары сәтті жасалды!")
                
                # AI жасаған сабақ жоспары
                st.markdown("### 🤖 AI жасаған сабақ жоспары")
                
                lesson_plan = f"""
## 📚 Сабақ жоспары: {subject} - {topic}

### 🎯 Сабақтың мақсаттары:
{goals}

### 📝 Негізгі құзыреттіліктер:
1. Білімділік: {topic} тақырыбын түсіну және қолдану
2. Іскерлік: Есептер шығару дағдысын дамыту
3. Тәрбиелік: Өздігінен жұмыс істеу дағдысын қалыптастыру

### ⏰ Сабақ кезеңдері:
#### 1. Ұйымдастыру кезеңі (5 минут)
- Сыныптың дайындығын тексеру
- Сабақтың мақсатын түсіндіру
- Мотивациялық сәт

#### 2. Жаңа білімді меңгеру (15 минут)
- Жаңа тақырыпты түсіндіру
- Мысалдар келтіру
- Оқушылармен бірлесіп жұмыс

#### 3. Бекіту кезеңі (15 минут)
- Практикалық тапсырмалар
- Топтық жұмыс
- Жеке жұмыс

#### 4. Қорытынды (5 минут)
- Өтілген тақырыпты қорытындылау
- Бағалау
- Үйге тапсырма беру

### 📊 Бағалау критерийлері:
- Өздігінен жұмыс істеу - 25%
- Дұрыс шешім - 50%
- Түсіндіру қабілеті - 25%

### 🏠 Үй тапсырмасы:
Оқулықтан №1-20 есептер

### 🔍 Рефлексия:
Сабақ соңында оқушылардан кері байланыс алу, қиындықтарды анықтау және шешу жолдарын ұсыну.
"""
                
                st.markdown(lesson_plan)
                
                # Жүктеп алу опциясы
                st.download_button(
                    label="📥 Сабақ жоспарын жүктеп алу",
                    data=lesson_plan,
                    file_name=f"Сабақ_жоспары_{subject}_{topic}.txt",
                    mime="text/plain"
                )

def show_student_analysis():
    """Оқушылардың үлгерімін талдау"""
    st.subheader("📊 Оқушы талдауы")
    
    classes = get_classes(st.session_state.user[0])
    if not classes:
        st.info("Алдымен сынып қосыңыз.")
        return
    
    class_options = {f"{c[1]} (Сынып {c[3]})": c[0] for c in classes}
    selected_class_name = st.selectbox("Сыныпты таңдаңыз", list(class_options.keys()))
    selected_class_id = class_options[selected_class_name]
    
    students = get_students_by_class(selected_class_id)
    
    if not students:
        st.info("Бұл сыныпта оқушылар жоқ.")
        return
    
    # Оқушыларды талдау
    if st.button("🤖 Оқушыларды талдау", use_container_width=True):
        with st.spinner("AI оқушыларды талдауда..."):
            time.sleep(2)
            
            # Статистиканы есептеу
            total_students = len(students)
            grade_points_list = []
            performance_levels = {"Өте жақсы": 0, "Жақсы": 0, "Орташа": 0, "Қанағаттанарлық": 0, "Әлсіз": 0}
            
            for student in students:
                points = student[4] if len(student) > 4 else 0
                if isinstance(points, str):
                    try:
                        points = float(points)
                    except:
                        points = 0
                grade_points_list.append(points)
                
                performance = student[5] if len(student) > 5 else "Орташа"
                performance_levels[performance] = performance_levels.get(performance, 0) + 1
            
            avg_points = sum(grade_points_list) / total_students if total_students > 0 else 0
            max_points = max(grade_points_list) if grade_points_list else 0
            min_points = min(grade_points_list) if grade_points_list else 0
            
            # AI талдауы
            analysis = f"""
## 📊 Оқушы талдауы: {selected_class_name}

### 📈 Статистика:
- **Барлық оқушылар:** {total_students} адам
- **Орташа балл:** {avg_points:.1f}/10
- **Ең жоғары балл:** {max_points}/10
- **Ең төмен балл:** {min_points}/10

### 📊 Оқу деңгейлері:
- Өте жақсы: {performance_levels['Өте жақсы']} адам ({performance_levels['Өте жақсы']/total_students*100:.1f}%)
- Жақсы: {performance_levels['Жақсы']} адам ({performance_levels['Жақсы']/total_students*100:.1f}%)
- Орташа: {performance_levels['Орташа']} адам ({performance_levels['Орташа']/total_students*100:.1f}%)
- Қанағаттанарлық: {performance_levels['Қанағаттанарлық']} адам ({performance_levels['Қанағаттанарлық']/total_students*100:.1f}%)
- Әлсіз: {performance_levels['Әлсіз']} адам ({performance_levels['Әлсіз']/total_students*100:.1f}%)

### 🎯 AI Ұсынымдары:

#### 1. Өте жақсы оқушыларға ({performance_levels['Өте жақсы']} адам):
- Күрделі тапсырмалар беру
- Зерттеу жобаларын ұсыну
- Басқа оқушыларға көмектесуге ынталандыру

#### 2. Жақсы оқушыларға ({performance_levels['Жақсы']} адам):
- Қосымша практикалық тапсырмалар
- Білімдерін тереңдету
- Өздігінен жұмыс істеу дағдысын дамыту

#### 3. Орташа оқушыларға ({performance_levels['Орташа']} адам):
- Негізгі білімді нығайту
- Қадамдық түсіндіру
- Көп практика

#### 4. Қанағаттанарлық оқушыларға ({performance_levels['Қанағаттанарлық']} адам):
- Жеңілдетілген тапсырмалар
- Жеке көмек
- Мотивацияны арттыру

#### 5. Әлсіз оқушыларға ({performance_levels['Әлсіз']} адам):
- Индивидуалды көмек
- Негізгі білімді қайталау
- Қарапайым тапсырмалар
- Жетістіктерін марапаттау

### 📝 Жалпы ұсынымдар:
1. **Дифференциалды оқыту:** Әр оқушының деңгейіне қарай тапсырмалар беру
2. **Топтық жұмыс:** Өте жақсы оқушыларды әлсіз оқушылармен топтастыру
3. **Қайталау:** Көп қайталау арқылы білімді бекіту
4. **Мотивация:** Жетістіктерін марапаттап, ынталандыру
5. **Үй тапсырмасы:** Әр оқушының деңгейіне сай үй тапсырмасы беру
"""
            
            st.markdown(analysis)
            
            # Графиктер
            fig, ax = plt.subplots(1, 2, figsize=(14, 6))
            
            # Бағалардың таралуы
            grade_categories = ['Өте жақсы', 'Жақсы', 'Орташа', 'Қанағаттанарлық', 'Әлсіз']
            grade_values = [performance_levels[cat] for cat in grade_categories]
            colors = ['#28a745', '#20c997', '#ffc107', '#fd7e14', '#dc3545']
            
            ax[0].bar(grade_categories, grade_values, color=colors)
            ax[0].set_title('Оқу деңгейлерінің таралуы')
            ax[0].set_xlabel('Деңгей')
            ax[0].set_ylabel('Оқушылар саны')
            ax[0].tick_params(axis='x', rotation=45)
            
            # Баллдардың таралуы
            ax[1].hist(grade_points_list, bins=10, edgecolor='black', alpha=0.7)
            ax[1].set_title('Баллдардың таралуы')
            ax[1].set_xlabel('Балл (0-10)')
            ax[1].set_ylabel('Оқушылар саны')
            ax[1].axvline(avg_points, color='red', linestyle='--', label=f'Орташа: {avg_points:.1f}')
            ax[1].legend()
            
            st.pyplot(fig)
            
            # Жүктеп алу опциясы
            st.download_button(
                label="📥 Талдауды жүктеп алу",
                data=analysis,
                file_name=f"Оқушы_талдауы_{selected_class_name}.txt",
                mime="text/plain"
            )

def show_task_generator():
    """Тапсырма генераторы"""
    st.subheader("🎯 AI Тапсырма генераторы")
    
    with st.form("task_generator_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            subject = st.text_input("Пән", value="Математика")
            topic = st.text_input("Тақырып", value="Бөлшектер")
            difficulty = st.selectbox("Қиындық деңгейі", ["Оңай", "Орташа", "Қиын"])
        
        with col2:
            grade_level = st.selectbox("Сынып", ["1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11"])
            task_type = st.selectbox("Тапсырма түрі", ["Теориялық", "Практикалық", "Есептер", "Сынақ", "Жоба"])
            task_count = st.slider("Тапсырмалар саны", 1, 20, 5)
        
        additional_info = st.text_area("Қосымша ақпарат", 
                                     placeholder="Тапсырмаға қажетті қосымша ақпарат...")
        
        if st.form_submit_button("🤖 Тапсырмаларды жасау", use_container_width=True):
            with st.spinner("AI тапсырмаларды жасауда..."):
                time.sleep(2)
                
                st.success("✅ Тапсырмалар сәтті жасалды!")
                
                # AI жасаған тапсырмалар
                tasks = f"""
## 📚 {subject} - {topic}
## 🎯 Қиындық: {difficulty}
## 👨‍🎓 Сынып: {grade_level}

### 📝 Тапсырмалар:

"""
                
                # Әр түрлі тапсырмалар
                task_templates = {
                    "Оңай": [
                        "Түсіндіріп беріңіз:",
                        "Анықтамасын жазыңыз:",
                        "Мысал келтіріңіз:",
                        "Салыстырыңыз:",
                        "Тізім жасаңыз:"
                    ],
                    "Орташа": [
                        "Талдап жазсаңыз:",
                        "Сипаттап беріңіз:",
                        "Себеп-салдарын түсіндіріңіз:",
                        "Есеп шығарыңіз:",
                        "Дәлелдеңіз:"
                    ],
                    "Қиын": [
                        "Зерттеп, қорытынды жасаңіз:",
                        "Талдау жүргізіңіз:",
                        "Өз пікіріңізді негіздеңіз:",
                        "Кешенді есеп шығарыңыз:",
                        "Жоба әзірлеңіз:"
                    ]
                }
                
                selected_templates = task_templates.get(difficulty, task_templates["Орташа"])
                
                for i in range(task_count):
                    task_template = selected_templates[i % len(selected_templates)]
                    tasks += f"""
#### Тапсырма {i+1}: {task_template} {topic} тақырыбы бойынша.

**Баға:** {random.randint(5, 10)} балл
**Күрделілік:** {difficulty}
**Уақыт:** {random.randint(5, 15)} минут
**Ұсыныс:** Оқулықтан {random.randint(1, 50)}-есепті қараңыз

---
"""
                
                st.markdown(tasks)
                
                # Жүктеп алу опциясы
                st.download_button(
                    label="📥 Тапсырмаларды жүктеп алу",
                    data=tasks,
                    file_name=f"Тапсырмалар_{subject}_{topic}.txt",
                    mime="text/plain"
                )

def show_assessment_rubric():
    """Бағалау критерийлері"""
    st.subheader("📋 AI Бағалау критерийлері")
    
    with st.form("rubric_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            subject = st.text_input("Пән", value="Математика")
            task_type = st.selectbox("Тапсырма түрі", 
                                   ["Теориялық сұрақ", "Есеп шығару", "Жоба", "Презентация", "Сынақ"])
            max_score = st.number_input("Максималды балл", min_value=1, max_value=100, value=10)
        
        with col2:
            grade_level = st.selectbox("Сынып", ["1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11"])
            criteria_count = st.slider("Критерийлер саны", 1, 10, 4)
        
        task_description = st.text_area("Тапсырма сипаттамасы", 
                                      placeholder="Тапсырманың толық сипаттамасы...")
        
        if st.form_submit_button("🤖 Критерийлерді жасау", use_container_width=True):
            with st.spinner("AI критерийлерді жасауда..."):
                time.sleep(2)
                
                st.success("✅ Бағалау критерийлері сәтті жасалды!")
                
                # Бағалау критерийлері
                rubric = f"""
## 📋 Бағалау критерийлері
## 📚 Пән: {subject}
## 🎯 Тапсырма түрі: {task_type}
## 👨‍🎓 Сынып: {grade_level}
## ⭐ Максималды балл: {max_score}

### 📝 Тапсырма сипаттамасы:
{task_description if task_description else "Жоқ"}

### 📊 Бағалау критерийлері:
"""
                
                # Әр түрлі критерийлер
                criteria_options = [
                    ("Білімділік", "Тақырыпты түсіну деңгейі", 25),
                    ("Іскерлік", "Есеп шығару дағдысы", 25),
                    ("Талдау", "Талдау және салыстыру қабілеті", 20),
                    ("Шығармашылық", "Шығармашылық және инновация", 15),
                    ("Ұйымдастыру", "Жұмысты ұйымдастыру", 10),
                    ("Уақыт", "Уақытты тиімді пайдалану", 5),
                    ("Өздігінен жұмыс", "Өздігінен жұмыс істеу", 10),
                    ("Түсіндіру", "Нәтижелерді түсіндіру", 15),
                    ("Дәлдік", "Есептеулердің дәлдігі", 20),
                    ("Толықтық", "Жауаптың толықтығы", 15)
                ]
                
                # Критерийлерді таңдау
                selected_criteria = random.sample(criteria_options, min(criteria_count, len(criteria_options)))
                
                # Баллды бөлу
                total_percentage = sum(c[2] for c in selected_criteria)
                for i, (name, description, percentage) in enumerate(selected_criteria):
                    adjusted_percentage = (percentage / total_percentage) * 100
                    score = (adjusted_percentage / 100) * max_score
                    
                    rubric += f"""
#### Критерий {i+1}: {name}
**Сипаттама:** {description}
**Балл:** {score:.1f} / {max_score * (adjusted_percentage/100):.1f}
**Бағалау дескрипторлары:**

- **5 (Өте жақсы):** Толық сәйкестік, барлық талаптар орындалған
- **4 (Жақсы):** Жетілдіруге болатын аздаған қателіктер
- **3 (Қанағаттанарлық):** Негізгі талаптар орындалған
- **2 (Қанағаттанарлықсыз):** Маңызды қателіктер бар
- **1 (Әлсіз):** Тапсырма орындалмаған

---
"""
                
                st.markdown(rubric)
                
                # Жүктеп алу опциясы
                st.download_button(
                    label="📥 Критерийлерді жүктеп алу",
                    data=rubric,
                    file_name=f"Бағалау_критерийлері_{subject}_{task_type}.txt",
                    mime="text/plain"
                )

def show_student_portal():
    """Оқушы порталы - ФАЙЛДАРМЕН КӨРСЕТУ"""
    t = texts[st.session_state.language]
    
    st.markdown(f"""
    <div style='background: linear-gradient(135deg, #00b09b, #96c93d); 
                padding: 1.5rem; border-radius: 10px; color: white; margin-bottom: 20px;'>
        <h2 style='margin: 0; text-align: center;'>🎒 ОҚУШЫ ПОРТАЛЫ</h2>
        <p style='margin: 0; text-align: center; font-size: 1.2rem;'>{st.session_state.student[1]} - {st.session_state.student[4]}</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Статистика
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Балл", f"{st.session_state.student[6]}/10")
    
    with col2:
        grade = points_to_grade(st.session_state.student[6])
        grade_class = get_grade_class(grade)
        st.markdown(f"""
        <div style='text-align: center;'>
            <div style='font-size: 2rem; font-weight: bold; color: {grade_class};'>{grade}</div>
            <div>Баға</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.metric("Оқу деңгейі", st.session_state.student[7])
    
    with col4:
        tasks = get_unified_student_tasks_by_student(st.session_state.student[0])
        completed_tasks = len([t for t in tasks if t['status'] == 'Тексерілді'])
        total_tasks = len(tasks)
        if total_tasks > 0:
            completion_rate = int((completed_tasks / total_tasks) * 100)
            st.metric("Тапсырмалар", f"{completion_rate}%")
        else:
            st.metric("Тапсырмалар", "0%")
    
    # Оқушыға берілген тапсырмалар
    st.markdown("---")
    st.subheader("📋 Менің тапсырмаларым")
    
    tasks = get_unified_student_tasks_by_student(st.session_state.student[0])
    
    if not tasks:
        st.info("📭 Сізге тапсырмалар әлі жіберілмеген")
    else:
        # Сүзгілер
        col1, col2 = st.columns(2)
        with col1:
            status_filter = st.selectbox(
                "Статус бойынша сүзгі",
                ["Барлығы", "Тағайындалды", "Кешікті", "Жіберілді", "Тексерілді"],
                key="student_task_filter"
            )
        
        # Тапсырмаларды көрсету
        display_tasks = tasks
        if status_filter != "Барлығы":
            display_tasks = [t for t in tasks if t['display_status'] == status_filter]
        
        for task in display_tasks:
            status_colors = {
                "Тағайындалды": "🔴",
                "Кешікті": "⏰",
                "Жіберілді": "🟡",
                "Тексерілді": "🟢"
            }
            status_icon = status_colors.get(task['display_status'], "⚪")
            
            with st.expander(f"{status_icon} {task['task_name']} - {task['teacher_name']}", expanded=False):
                col_info, col_submit = st.columns([3, 2])
                
                with col_info:
                    st.markdown(f"**👨‍🏫 Мұғалім:** {task['teacher_name']}")
                    st.markdown(f"**🏫 Сынып:** {task['class_name']}")
                    st.markdown(f"**📅 Мерзімі:** {task.get('due_date_formatted', task['due_date'])}")
                    
                    if task.get('is_overdue'):
                        st.error(f"⏰ Мерзімі өткен! ({task.get('days_left', 0)} күн бұрын)")
                    
                    st.markdown(f"**⭐ Ұпай:** {task['points']}")
                    st.markdown(f"**📊 Статус:** {task['display_status']}")
                    
                    # ТАПСЫРМА ФАЙЛЫ ТУРАЛЫ АҚПАРАТ
                    if task.get('task_file_name'):
                        st.markdown(f"**📎 Тапсырма файлы:** {task['task_file_name']}")
                        if task.get('task_file_size_str'):
                            st.markdown(f"**📦 Көлемі:** {task['task_file_size_str']}")
                    
                    if task.get('student_submitted_date_formatted'):
                        st.markdown(f"**📤 Сіз жібердіңіз:** {task['student_submitted_date_formatted']}")
                    
                    if task.get('score'):
                        st.success(f"**📊 Бағаңыз:** {task['score']}/{task['points']}")
                    
                    if task['task_description']:
                        with st.expander("📝 Тапсырма сипаттамасы", expanded=False):
                            st.write(task['task_description'])
                    
                    if task.get('teacher_feedback'):
                        with st.expander("💬 Мұғалімнің кері байланысы", expanded=False):
                            st.write(task['teacher_feedback'])
                
                with col_submit:
                    # ТАПСЫРМА ФАЙЛЫН КӨРСЕТУ ЖӘНЕ ЖҮКТЕП АЛУ
                    task_file = get_unified_task_file(task['id'], 'task')
                    if task_file:
                        st.markdown("**📥 Тапсырма файлы:**")
                        
                        # Файлды көрсету түймесі
                        if st.button("👁️ Көрсету", key=f"student_show_task_{task['id']}", use_container_width=True):
                            st.session_state.preview_file = {
                                'id': task['id'],
                                'type': 'task',
                                'name': task_file['filename']
                            }
                            st.rerun()
                        
                        # Файлды жүктеп алу түймесі
                        st.download_button(
                            label="📥 Жүктеп алу",
                            data=task_file['data'],
                            file_name=task_file['filename'],
                            mime=task_file['type'],
                            key=f"student_download_{task['id']}"
                        )
                    
                    # ЖАУАП ЖІБЕРУ (ЕГЕР ӘЛІ ЖІБЕРМЕГЕН БОЛСА)
                    if task['display_status'] in ['Тағайындалды', 'Кешікті']:
                        st.markdown("---")
                        st.write("**✍️ Жауап беру:**")
                        
                        with st.form(key=f"student_submit_{task['id']}"):
                            answer_text = st.text_area(
                                "Жауап мәтіні",
                                value=task.get('student_answer_text', ''),
                                height=150,
                                key=f"student_answer_{task['id']}"
                            )
                            
                            answer_file = st.file_uploader(
                                "📁 Файл жүктеу (міндетті емес)",
                                type=['pdf', 'doc', 'docx', 'txt', 'jpg', 'png', 'xlsx', 'pptx'],
                                key=f"student_file_{task['id']}"
                            )
                            
                            if st.form_submit_button("📤 Жауап жіберу", use_container_width=True):
                                if answer_text or answer_file:
                                    success, message = submit_unified_student_answer(
                                        task['id'],
                                        answer_text,
                                        answer_file
                                    )
                                    
                                    if success:
                                        st.success("✅ Жауап сәтті жіберілді!")
                                        time.sleep(2)
                                        st.rerun()
                                    else:
                                        st.error(f"❌ {message}")
                                else:
                                    st.warning("⚠️ Жауап мәтінін енгізіңіз немесе файл жүктеңіз")
                    
                    # ӨЗ ЖАУАБЫҢЫЗДЫ КӨРУ
                    elif task.get('student_answer_text'):
                        st.markdown("---")
                        st.info(f"**✍️ Сіздің жауабыңыз:**\n{task['student_answer_text']}")
                        
                        # ЖАУАП ФАЙЛЫН КӨРСЕТУ
                        answer_file = get_unified_task_file(task['id'], 'answer')
                        if answer_file:
                            st.markdown("**📎 Сіздің файлыңыз:**")
                            
                            # Файлды көрсету түймесі
                            if st.button("👁️ Көрсету", key=f"student_show_answer_{task['id']}", use_container_width=True):
                                st.session_state.preview_file = {
                                    'id': task['id'],
                                    'type': 'answer',
                                    'name': answer_file['filename']
                                }
                                st.rerun()
                            
                            # Файлды жүктеп алу түймесі
                            st.download_button(
                                label="📥 Жүктеп алу",
                                data=answer_file['data'],
                                file_name=answer_file['filename'],
                                mime=answer_file['type'],
                                key=f"student_answer_dl_{task['id']}"
                            )

def show_file_preview():
    """Файлды алдын ала көру - ЖАҢА ТҮЗЕТІЛГЕН"""
    if st.session_state.get('preview_file'):
        file_info = st.session_state.preview_file
        
        st.markdown("---")
        st.subheader("📄 Файлды көрсету")
        
        if file_info['type'] == 'bzb':
            file_data = get_bzb_task(file_info['id'])
            if file_data:
                preview_file(file_data['data'], file_data['type'], file_data['name'])
        
        elif file_info['type'] == 'visual':
            file_data = get_visual_material(file_info['id'])
            if file_data:
                preview_file(file_data['data'], file_data['type'], file_data['name'])
        
        elif file_info['type'] == 'task':
            file_data = get_unified_task_file(file_info['id'], 'task')
            if file_data:
                display_file_preview(file_data['data'], file_data['type'], file_data['filename'])
        
        elif file_info['type'] == 'answer':
            file_data = get_unified_task_file(file_info['id'], 'answer')
            if file_data:
                display_file_preview(file_data['data'], file_data['type'], file_data['filename'])
        
        if st.button("← Артқа"):
            st.session_state.preview_file = None
            st.rerun()

def show_dashboard():
    """Басқару панелі"""
    t = texts[st.session_state.language]
    
    # Ақпарат панелі
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("🏫 Сыныптар", get_class_count(st.session_state.user[0]))
    
    with col2:
        st.metric("👨‍🎓 Оқушылар", get_student_count(st.session_state.user[0]))
    
    with col3:
        classes = get_classes(st.session_state.user[0])
        if classes:
            st.metric("📚 Пәндер", len(set([c[2] for c in classes])))
        else:
            st.metric("📚 Пәндер", 0)
    
    with col4:
        # Тапсырма статистикасы
        stats = get_task_statistics_unified(st.session_state.user[0])
        total_tasks = stats.get('total', 0) if stats else 0
        st.metric("📋 Тапсырмалар", total_tasks)
    
    # Жылдам қолжетімділік карточкалары
    st.markdown("---")
    st.subheader("⚡ Жылдам қолжетімділік")
    
    cols = st.columns(4)
    tools = [
        ("🏫 Сыныптар", "classes", "blue"),
        ("👨‍🎓 Оқушылар", "students", "green"),
        ("🎯 Тапсырмалар", "student_tasks", "orange"),
        ("🤖 AI құралдары", "ai_tools", "purple")
    ]
    
    for i, (title, page, color) in enumerate(tools):
        with cols[i]:
            if st.button(title, use_container_width=True, 
                        key=f"quick_{page}"):
                st.session_state.current_page = page
                st.rerun()
    
    # Соңғы тапсырмалар
    st.markdown("---")
    st.subheader("📝 Соңғы тапсырмалар")
    
    tasks = get_unified_student_tasks_by_teacher(st.session_state.user[0])[:5]
    if tasks:
        for task in tasks:
            col1, col2 = st.columns([3, 1])
            with col1:
                st.markdown(f"**{task['task_name']}** - {task['student_name']}")
            with col2:
                status_badge = {
                    'Тағайындалды': '🔴',
                    'Жіберілді': '🟡',
                    'Тексерілді': '🟢',
                    'Кешікті': '⏰'
                }.get(task['display_status'], '⚪')
                st.markdown(f"`{status_badge} {task['display_status']}`")
            st.markdown("---")
    else:
        st.info("📭 Әрекеттер жоқ")

# ============ НЕГІЗГІ БАҒДАРЛАМА ============
def main():
    # Streamlit session state инициализациясы
    if 'current_class_id' not in st.session_state:
        st.session_state.current_class_id = None
    
    if 'show_add_class' not in st.session_state:
        st.session_state.show_add_class = False
    
    if 'current_page' not in st.session_state:
        st.session_state.current_page = 'dashboard'
    
    if 'language' not in st.session_state:
        st.session_state.language = 'kk'
    
    if 'class_to_delete' not in st.session_state:
        st.session_state.class_to_delete = None
    
    if 'confirm_delete' not in st.session_state:
        st.session_state.confirm_delete = False
    
    if 'preview_file' not in st.session_state:
        st.session_state.preview_file = None
    
    if 'current_ai_tool' not in st.session_state:
        st.session_state.current_ai_tool = None
    
    if 'show_student_login' not in st.session_state:
        st.session_state.show_student_login = False
    
    # Дерекқорды баптау
    if not os.path.exists('ai_qazaq_teachers.db'):
        init_db()
        print("✅ Жаңа дерекқор құрылды!")
    else:
        print("✅ Дерекқор бар, тексеру жүргізілуде...")
    
    # Дерекқор құрылымын тексеру
    fix_database_structure()
    
    # student_tasks кестесінің бағаналарын түзету
    fix_student_tasks_columns()
    
    # Басты бағдарлама
    st.set_page_config(
        page_title="AI QAZAQ Teachers",
        page_icon="🇰🇿",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # CSS стильдері
    st.markdown("""
    <style>
    .stButton > button {
        width: 100%;
    }
    .grade-a { color: #28a745; }
    .grade-b { color: #20c997; }
    .grade-c { color: #ffc107; }
    .grade-d { color: #fd7e14; }
    .grade-f { color: #dc3545; }
    </style>
    """, unsafe_allow_html=True)
    
    # Сессияны тексеру
    user_session = load_user_session()
    student_session = load_student_session()
    
    # Сессияны баптау
    if user_session:
        st.session_state.user = user_session
        st.session_state.is_authenticated = True
        st.session_state.is_student = False
    elif student_session:
        st.session_state.student = student_session
        st.session_state.is_authenticated = True
        st.session_state.is_student = True
    else:
        st.session_state.is_authenticated = False
    
    # Навигация
    if not st.session_state.is_authenticated:
        show_login_page()
    else:
        if st.session_state.is_student:
            show_student_portal()
        else:
            show_teacher_dashboard()

def show_login_page():
    """Кіру бетін көрсету"""
    t = texts[st.session_state.language]
    
    show_logo_header()
    
    # Кіру және тіркелу табы
    tab1, tab2 = st.tabs(["✅ Кіру", "📝 Тіркелу"])
    
    with tab1:
        st.subheader("👤 Мұғалім кіруі")
        
        with st.form("teacher_login_form"):
            username = st.text_input(f"{t['username']}", key="login_username")
            password = st.text_input(f"{t['password']}", type="password", key="login_password")
            
            col_login, col_student = st.columns(2)
            
            with col_login:
                if st.form_submit_button(f"🚀 {t['login']}", use_container_width=True):
                    user = login_user(username, password)
                    if user:
                        st.session_state.user = user
                        st.session_state.is_authenticated = True
                        st.session_state.is_student = False
                        save_user_session(user)
                        st.success(f"🎉 {t['welcome']}, {user[2]}!")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("❌ Қате логин немесе құпия сөз!")
            
            with col_student:
                if st.button("🎒 Оқушы ретінде кіру", use_container_width=True):
                    st.session_state.show_student_login = True
                    st.rerun()
        
        # Оқушы кіруі
        if st.session_state.get('show_student_login', False):
            st.markdown("---")
            st.subheader("🎒 Оқушы кіруі")
            
            with st.form("student_login_form"):
                student_username = st.text_input("👤 Оқушы логині", key="student_username")
                student_password = st.text_input("🔒 Құпия сөз", type="password", key="student_password")
                
                if st.form_submit_button("🚀 Оқушы ретінде кіру", use_container_width=True):
                    student = student_login(student_username, student_password)
                    if student:
                        st.session_state.student = student
                        st.session_state.is_authenticated = True
                        st.session_state.is_student = True
                        save_student_session(student)
                        st.success(f"🎉 Қош келдің, {student[1]}!")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("❌ Қате логин немесе құпия сөз!")
            
            if st.button("← Мұғалім кіруіне оралу"):
                st.session_state.show_student_login = False
                st.rerun()
    
    with tab2:
        st.subheader("📝 Жаңа тіркелу")
        
        with st.form("register_form"):
            col1, col2 = st.columns(2)
            
            with col1:
                full_name = st.text_input(f"{t['fullname']}")
                username = st.text_input(f"{t['username']}")
                password = st.text_input(f"{t['password']}", type="password")
            
            with col2:
                email = st.text_input(f"{t['email']}")
                school = st.text_input(f"{t['school']}")
                confirm_password = st.text_input(f"{t['confirm_pass']}", type="password")
                city = st.text_input("🏙️ Қала")
            
            if st.form_submit_button(f"📝 {t['register']}", use_container_width=True):
                if password != confirm_password:
                    st.error("❌ Құпия сөздер сәйкес емес!")
                elif not all([username, password, full_name, school, city]):
                    st.error("❌ Барлық өрістерді толтырыңыз!")
                else:
                    if register_user(username, password, email, full_name, school, city):
                        st.success("✅ Тіркелу сәтті аяқталды! Енді кіре аласыз.")
                        time.sleep(2)
                        st.rerun()
                    else:
                        st.error("❌ Бұл пайдаланучы аты бос емес!")

def show_teacher_dashboard():
    """Мұғалім басқару панелі"""
    t = texts[st.session_state.language]
    
    # Бүйірлік мәзір
    with st.sidebar:
        st.markdown(f"""
        <div style='text-align: center; margin-bottom: 20px;'>
            <h3>👤 {st.session_state.user[2]}</h3>
            <p>{st.session_state.user[3]}, {st.session_state.user[4]}</p>
        </div>
        """, unsafe_allow_html=True)
        
        # Навигация
        pages = [
            ("📊 Басқару панелі", "dashboard"),
            ("🏫 Сыныптар", "classes"),
            ("👨‍🎓 Оқушылар", "students"),
            ("📊 Оқушы үлгерімі", "performance"),
            ("📝 БЖБ тапсырмалары", "bzb_tasks"),
            ("🎯 Оқушыларға тапсырмалар", "student_tasks"),
            ("📁 Көрнекіліктер", "visual_materials"),
            ("🤖 AI құралдары", "ai_tools")
        ]
        
        for page_name, page_key in pages:
            if st.button(page_name, use_container_width=True, 
                        key=f"nav_{page_key}"):
                st.session_state.current_page = page_key
        
        st.markdown("---")
        
        # Тіл таңдау
        lang = st.selectbox("🌐 Тіл", ["Қазақша", "Русский"], 
                           index=0, key="language_select")
        st.session_state.language = 'kk' if lang == "Қазақша" else 'ru'
        
        # Шығу
        if st.button(f"🚪 {t['logout']}", use_container_width=True):
            clear_user_session()
            st.session_state.clear()
            st.success("✅ Сіз жүйеден шықтыңыз!")
            time.sleep(1)
            st.rerun()
    
    # Қолжетімділік түймелері
    col1, col2 = st.columns([6, 1])
    
    with col1:
        show_logo_header()
    
    with col2:
        if st.button("🔄", help="Жаңарту"):
            st.rerun()
    
    # Файл алдын ала көру
    if st.session_state.get('preview_file'):
        show_file_preview()
        return
    
    # Ағымдағы бетті көрсету
    current_page = st.session_state.current_page
    
    if current_page == 'dashboard':
        show_dashboard()
    elif current_page == 'classes':
        show_classes_management()
    elif current_page == 'students':
        show_students_management()
    elif current_page == 'performance':
        show_student_performance()
    elif current_page == 'bzb_tasks':
        show_bzb_tasks()
    elif current_page == 'student_tasks':
        show_student_tasks()
    elif current_page == 'visual_materials':
        show_visual_materials()
    elif current_page == 'ai_tools':
        show_ai_tools()

if __name__ == "__main__":

    main()
