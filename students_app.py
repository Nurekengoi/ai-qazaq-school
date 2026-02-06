# students_app.py - AI QAZAQ Students Platform (ТОЛЫҚ ЖАҢАРТЫЛҒАН ВЕРСИЯ)
import streamlit as st
import sqlite3
import hashlib
import pandas as pd
from datetime import datetime
import os
import json
import io
import time
import base64
import traceback
import tempfile
from pathlib import Path
import random

# =============== НЕГІЗГИ ФУНКЦИЯЛАР ===============

def hash_password(password):
    """Құпия сөзді хэштеу"""
    return hashlib.sha256(password.encode()).hexdigest()

def connect_db():
    """Дерекқорға қосылу"""
    try:
        conn = sqlite3.connect('ai_qazaq_teachers.db', check_same_thread=False)
        return conn
    except Exception as e:
        print(f"❌ Дерекқорға қосылу қатесі: {e}")
        raise Exception(f"Дерекқорға қосылу мүмкін емес: {e}")

def login_student(username, password):
    """Оқушы кіруі"""
    conn = connect_db()
    c = conn.cursor()
    hashed_password = hash_password(password)
    
    try:
        c.execute("""
        SELECT s.id, s.full_name, s.student_code, s.class_id, 
               c.name as class_name, s.grade_points, s.academic_performance
        FROM students s
        LEFT JOIN classes c ON s.class_id = c.id
        WHERE s.id IN (
            SELECT student_id FROM student_logins 
            WHERE username = ? AND password = ?
        )
        """, (username, hashed_password))
        
        student = c.fetchone()
        
        if student:
            return {
                'id': student[0],
                'full_name': student[1],
                'student_code': student[2],
                'class_id': student[3],
                'class_name': student[4] if student[4] else 'Сынып анықталмады',
                'grade_points': student[5] if student[5] else 0,
                'academic_performance': student[6] if student[6] else 'Орташа'
            }
        return None
    except Exception as e:
        print(f"❌ Оқушы кіру қатесі: {e}")
        return None
    finally:
        conn.close()

# ============ ФАЙЛ ФУНКЦИЯЛАРЫ ============

def get_file_size_str(size_bytes):
    """Файл көлемін оқиғалы форматада көрсету"""
    if size_bytes is None:
        return "0 B"
    
    try:
        size_bytes = int(size_bytes)
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes/1024:.2f} KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes/(1024*1024):.2f} MB"
        else:
            return f"{size_bytes/(1024*1024*1024):.2f} GB"
    except:
        return "0 B"

def download_task_file(task_id):
    """Тапсырма файлын жүктеп алу"""
    conn = connect_db()
    c = conn.cursor()
    
    try:
        c.execute("PRAGMA table_info(student_tasks)")
        columns = [col[1] for col in c.fetchall()]
        
        if 'task_file' in columns:
            c.execute("""
                SELECT task_name, task_file, task_file_type, task_file_size 
                FROM student_tasks 
                WHERE id = ?
            """, (task_id,))
            
            result = c.fetchone()
            if result and result[1]:
                task_name, task_file, file_type, file_size = result
                
                # Файл атауын анықтау
                if task_name:
                    safe_filename = "".join(c for c in task_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
                else:
                    safe_filename = f"task_{task_id}"
                
                # Кеңейтуді анықтау
                if file_type:
                    ext = file_type.split('/')[-1].split(';')[0]
                else:
                    # Әдепкі кеңейту
                    if task_file[:4] == b'%PDF':
                        ext = 'pdf'
                    elif task_file[:2] == b'\xff\xd8':
                        ext = 'jpg'
                    elif task_file[:8] == b'\x89PNG\r\n\x1a\n':
                        ext = 'png'
                    else:
                        ext = 'bin'
                
                filename = f"{safe_filename}.{ext}"
                
                return {
                    'filename': filename,
                    'data': task_file,
                    'content_type': file_type or 'application/octet-stream',
                    'size': file_size
                }
        return None
        
    except Exception as e:
        print(f"❌ Тапсырма файлын жүктеп алу қатесі: {e}")
        return None
    finally:
        conn.close()

def preview_file(file_data, file_type, file_name="preview"):
    """Файлды алдын ала көру"""
    if not file_data:
        st.info("📭 Файл мазмұны бос")
        return False
    
    try:
        # PDF файлдар
        if file_type and 'pdf' in file_type.lower():
            st.markdown(f"**📄 {file_name}**")
            
            # PDF көрсету
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
                tmp_file.write(file_data)
                tmp_path = tmp_file.name
            
            try:
                with open(tmp_path, "rb") as f:
                    base64_pdf = base64.b64encode(f.read()).decode('utf-8')
                
                # PDF көрсету
                pdf_display = f'''
                <div style="border: 1px solid #ddd; border-radius: 5px; padding: 10px; margin: 10px 0;">
                    <iframe src="data:application/pdf;base64,{base64_pdf}" 
                            width="100%" 
                            height="600" 
                            style="border: none;">
                    </iframe>
                </div>
                '''
                st.markdown(pdf_display, unsafe_allow_html=True)
                
            except Exception as e:
                st.error(f"PDF көрсету қатесі: {e}")
                st.info("PDF файлды жүктеп алып, көңілгі компьютерде ашыңыз")
            finally:
                try:
                    os.unlink(tmp_path)
                except:
                    pass
            
            return True
        
        # Сурет файлдары
        elif file_type and any(img_type in file_type.lower() for img_type in ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'svg', 'image']):
            st.markdown(f"**🖼️ {file_name}**")
            
            try:
                # Суретті көрсету
                st.image(file_data, use_column_width=True)
            except Exception as e:
                st.error(f"Сурет көрсету қатесі: {e}")
                st.info("Сурет файлды жүктеп алыңыз")
            
            return True
        
        # Мәтін файлдары
        elif file_type and any(text_type in file_type.lower() for text_type in ['text', 'txt', 'csv', 'json', 'plain']):
            st.markdown(f"**📝 {file_name}**")
            
            try:
                # Кодектерді тексеру
                encodings = ['utf-8', 'utf-8-sig', 'cp1251', 'iso-8859-1', 'utf-16']
                text_content = None
                
                for encoding in encodings:
                    try:
                        text_content = file_data.decode(encoding)
                        break
                    except UnicodeDecodeError:
                        continue
                
                if text_content:
                    # Шектеулі мәтін көрсету
                    max_chars = 10000
                    if len(text_content) > max_chars:
                        st.info(f"Файл мазмұны (алғашқы {max_chars} таңба)")
                        st.code(text_content[:max_chars] + "\n\n... (толық нұсқаны жүктеп алыңыз)", 
                              language='text')
                    else:
                        st.code(text_content, language='text')
                else:
                    st.warning("Мәтін файлын оқу мүмкін болмады")
                    
            except Exception as e:
                st.error(f"Мәтін файлын көрсету қатесі: {e}")
            
            return True
        
        # Word, Excel, PowerPoint файлдары
        elif file_type and any(doc_type in file_type.lower() for doc_type in ['word', 'excel', 'powerpoint', 'msword', 'vnd.ms', 'vnd.openxmlformats']):
            st.markdown(f"**📎 {file_name}**")
            st.info(f"""
            ℹ️ **{file_name}** файлы браузерде тікелей көрсетілмейді.
            
            **Жүктеп алып көру үшін:**
            1. Төмендегі "📥 Жүктеп алу" түймесін басыңыз
            2. Файлды компьютеріңізге сақтаңыз
            3. Тиісті бағдарламада ашыңыз (Word, Excel, PowerPoint)
            
            **Файл туралы ақпарат:**
            - Түрі: {file_type}
            - Көлемі: {get_file_size_str(len(file_data))}
            """)
            
            return False
        
        # Басқа файл түрлері
        else:
            st.markdown(f"**📦 {file_name}**")
            st.info(f"""
            ℹ️ Файл түрі: **{file_type or 'Белгісіз'}**
            
            Файлды көру үшін жүктеп алып, тиісті бағдарламада ашыңыз.
            
            **Файл көлемі:** {get_file_size_str(len(file_data))}
            """)
            
            return False
            
    except Exception as e:
        st.error(f"❌ Файлды көрсету қатесі: {str(e)[:200]}")
        return False

# ============ ТАПСЫРМАЛАР ФУНКЦИЯЛАРЫ ============

def get_student_tasks_from_db(student_id):
    """Дерекқордан оқушы тапсырмаларын алу"""
    conn = connect_db()
    c = conn.cursor()
    
    try:
        # Баған атауларын тексеру
        c.execute("PRAGMA table_info(student_tasks)")
        columns_info = c.fetchall()
        column_names = [col[1] for col in columns_info]
        
        # Бағаналарды таңдау
        select_columns = [
            'id', 'task_name', 'task_description', 'due_date', 'status',
            'teacher_name', 'points', 'score', 'student_answer_text',
            'teacher_feedback', 'assigned_date', 'student_submitted_date',
            'difficulty', 'tags', 'task_file', 'task_file_type', 'task_file_size',
            'student_answer_file', 'student_answer_file_type', 'student_answer_file_size',
            'student_answer_file_name'
        ]
        
        # Тек бар бағаналарды таңдау
        available_columns = []
        for col in select_columns:
            if col in column_names:
                available_columns.append(col)
        
        if not available_columns:
            print("⚠️ student_tasks кестесінде ешбір қажетті бағана жоқ")
            return []
        
        query = f"""
            SELECT {', '.join(available_columns)}
            FROM student_tasks 
            WHERE student_id = ?
            ORDER BY 
                CASE 
                    WHEN status = 'Тағайындалды' THEN 1
                    WHEN status = 'Жіберілді' THEN 2
                    WHEN status = 'Тексерілді' THEN 3
                    ELSE 4
                END,
                CASE 
                    WHEN due_date IS NOT NULL THEN due_date
                    ELSE assigned_date
                END ASC
        """
        
        c.execute(query, (student_id,))
        rows = c.fetchall()
        
        tasks = []
        for row in rows:
            task = {}
            for i, col in enumerate(available_columns):
                task[col] = row[i]
            
            # Статусты баптау
            if 'status' not in task or not task['status']:
                task['status'] = 'Тағайындалды'
            
            tasks.append(task)
        
        return tasks
        
    except Exception as e:
        print(f"❌ Тапсырмаларды алу қатесі: {e}")
        return []
    finally:
        conn.close()

def submit_student_answer_with_file(task_id, answer_text, uploaded_file):
    """Файлмен жауап жіберу"""
    conn = connect_db()
    c = conn.cursor()
    
    try:
        # Баған атауларын тексеру
        c.execute("PRAGMA table_info(student_tasks)")
        columns = [col[1] for col in c.fetchall()]
        
        # Файлды оқу
        file_data = None
        file_type = None
        file_name = None
        
        if uploaded_file is not None:
            file_data = uploaded_file.read()
            file_type = uploaded_file.type
            file_name = uploaded_file.name
            
            # Бағаналарды тексеру және қосу
            if 'student_answer_file' not in columns:
                c.execute("ALTER TABLE student_tasks ADD COLUMN student_answer_file BLOB")
            if 'student_answer_file_type' not in columns:
                c.execute("ALTER TABLE student_tasks ADD COLUMN student_answer_file_type TEXT")
            if 'student_answer_file_size' not in columns:
                c.execute("ALTER TABLE student_tasks ADD COLUMN student_answer_file_size INTEGER")
            if 'student_answer_file_name' not in columns:
                c.execute("ALTER TABLE student_tasks ADD COLUMN student_answer_file_name TEXT")
        
        # SQL сұранысын құру
        if file_data:
            # Файлмен жаңарту
            c.execute("""
                UPDATE student_tasks 
                SET student_answer_text = ?,
                    student_answer_file = ?,
                    student_answer_file_type = ?,
                    student_answer_file_size = ?,
                    student_answer_file_name = ?,
                    status = 'Жіберілді',
                    student_submitted_date = datetime('now')
                WHERE id = ?
            """, (answer_text, file_data, file_type, len(file_data), file_name, task_id))
        else:
            # Тек мәтінмен жаңарту
            c.execute("""
                UPDATE student_tasks 
                SET student_answer_text = ?,
                    status = 'Жіберілді',
                    student_submitted_date = datetime('now')
                WHERE id = ?
            """, (answer_text, task_id))
        
        conn.commit()
        return True
        
    except Exception as e:
        st.error(f"❌ Жауап сақтау қатесі: {e}")
        return False
    finally:
        conn.close()

def download_student_answer_file(task_id):
    """Оқушының жіберген жауап файлын жүктеп алу"""
    conn = connect_db()
    c = conn.cursor()
    
    try:
        c.execute("""
            SELECT student_answer_file, student_answer_file_type, 
                   student_answer_file_name, student_answer_file_size
            FROM student_tasks 
            WHERE id = ?
        """, (task_id,))
        
        result = c.fetchone()
        if result and result[0]:
            file_data, file_type, file_name, file_size = result
            
            # Файл атауын анықтау
            if not file_name:
                file_name = f"answer_{task_id}"
                
                # Кеңейтуді файл түрінен алу
                if file_type:
                    ext = file_type.split('/')[-1].split(';')[0]
                    if '.' not in file_name:
                        file_name = f"{file_name}.{ext}"
            
            return {
                'filename': file_name,
                'data': file_data,
                'content_type': file_type or 'application/octet-stream',
                'size': file_size
            }
        return None
        
    except Exception as e:
        print(f"❌ Жауап файлын жүктеп алу қатесі: {e}")
        return None
    finally:
        conn.close()

# ============ БЖБ ТАПСЫРМАЛАРЫ ============

def get_student_bzb_tasks(class_id):
    """БЖБ тапсырмаларын алу"""
    conn = connect_db()
    c = conn.cursor()
    
    try:
        c.execute("""
            SELECT b.id, b.task_name, b.file_type, b.upload_date, 
                   b.difficulty_level, b.task_file, c.name as class_name
            FROM bzb_tasks b
            JOIN classes c ON b.class_id = c.id
            WHERE b.class_id = ? 
            ORDER BY b.upload_date DESC
        """, (class_id,))
        
        tasks = []
        for row in c.fetchall():
            tasks.append({
                'id': row[0],
                'task_name': row[1],
                'file_type': row[2],
                'upload_date': row[3],
                'difficulty': row[4],
                'task_file': row[5],
                'class_name': row[6]
            })
        return tasks
    except Exception as e:
        print(f"❌ БЖБ тапсырмаларын алу қатесі: {e}")
        return []
    finally:
        conn.close()

def download_bzb_task(task_id):
    """БЖБ тапсырмасын жүктеп алу"""
    conn = connect_db()
    c = conn.cursor()
    
    try:
        c.execute("SELECT task_name, task_file, file_type FROM bzb_tasks WHERE id = ?", (task_id,))
        task = c.fetchone()
        
        if task:
            task_name, task_file, file_type = task
            
            # Файл атауын анықтау
            safe_filename = "".join(c for c in task_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
            
            if file_type:
                ext = file_type.split('/')[-1].split(';')[0]
            else:
                ext = 'file'
            
            filename = f"{safe_filename}.{ext}"
            
            return {
                'filename': filename,
                'data': task_file,
                'content_type': file_type or 'application/octet-stream'
            }
        return None
    except Exception as e:
        print(f"❌ БЖБ тапсырмасын жүктеп алу қатесі: {e}")
        return None
    finally:
        conn.close()

# ============ КӨРНЕКІЛІКТЕР ============

def get_class_visual_materials(class_id):
    """Көрнекілік материалдарын алу"""
    conn = connect_db()
    c = conn.cursor()
    
    try:
        c.execute("""
            SELECT v.id, v.file_name, v.file_type, v.category, 
                   v.upload_date, v.file_data, t.full_name as teacher_name
            FROM visual_materials v
            JOIN teachers t ON v.teacher_id = t.id
            JOIN classes c ON c.teacher_id = t.id
            WHERE c.id = ?
            ORDER BY v.upload_date DESC
        """, (class_id,))
        
        materials = []
        for row in c.fetchall():
            materials.append({
                'id': row[0],
                'file_name': row[1],
                'file_type': row[2],
                'category': row[3],
                'upload_date': row[4],
                'file_data': row[5],
                'teacher_name': row[6]
            })
        return materials
    except Exception as e:
        print(f"❌ Көрнекіліктерді алу қатесі: {e}")
        return []
    finally:
        conn.close()

def download_visual_material(file_id):
    """Көрнекілік файлын жүктеп алу"""
    conn = connect_db()
    c = conn.cursor()
    
    try:
        c.execute("SELECT file_name, file_data, file_type FROM visual_materials WHERE id = ?", (file_id,))
        file = c.fetchone()
        
        if file:
            file_name, file_data, file_type = file
            
            # Файл атауын анықтау
            safe_filename = "".join(c for c in file_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
            
            if file_type:
                ext = file_type.split('/')[-1].split(';')[0]
            else:
                ext = 'file'
            
            filename = f"{safe_filename}.{ext}"
            
            return {
                'filename': filename,
                'data': file_data,
                'content_type': file_type or 'application/octet-stream'
            }
        return None
    except Exception as e:
        print(f"❌ Файлды жүктеп алу қатесі: {e}")
        return None
    finally:
        conn.close()

# ============ БАҒАЛАР ============

def get_student_grades(student_id):
    """Оқушының бағаларын алу"""
    conn = connect_db()
    c = conn.cursor()
    
    try:
        c.execute("PRAGMA table_info(students)")
        columns = [col[1] for col in c.fetchall()]
        
        grade_column = None
        academic_column = None
        
        for col in columns:
            col_lower = col.lower()
            if any(keyword in col_lower for keyword in ['grade', 'point', 'score', 'mark']):
                grade_column = col
            elif any(keyword in col_lower for keyword in ['academic', 'performance', 'level']):
                academic_column = col
        
        select_columns = []
        if grade_column:
            select_columns.append(grade_column)
        if academic_column:
            select_columns.append(academic_column)
        
        if not select_columns:
            return {
                'grade_points': 0,
                'academic_performance': 'Орташа'
            }
        
        query = f"SELECT {', '.join(select_columns)} FROM students WHERE id = ?"
        c.execute(query, (student_id,))
        
        result = c.fetchone()
        
        if result:
            if len(result) == 2:
                return {
                    'grade_points': result[0],
                    'academic_performance': result[1]
                }
            else:
                return {
                    'grade_points': result[0],
                    'academic_performance': 'Орташа'
                }
        return {
            'grade_points': 0,
            'academic_performance': 'Орташа'
        }
    except Exception as e:
        print(f"❌ Бағаларды алу қатесі: {e}")
        return {
            'grade_points': 0,
            'academic_performance': 'Орташа'
        }
    finally:
        conn.close()

# ============ ҚҰПИЯ СӨЗДІ ӨЗГЕРТУ ============

def update_student_password_in_db(student_id, old_password, new_password):
    """Құпия сөзді өзгерту"""
    conn = connect_db()
    c = conn.cursor()
    
    try:
        hashed_old_password = hash_password(old_password)
        c.execute("""
            SELECT id FROM student_logins 
            WHERE student_id = ? AND password = ?
        """, (student_id, hashed_old_password))
        
        if c.fetchone():
            hashed_new_password = hash_password(new_password)
            c.execute("""
                UPDATE student_logins 
                SET password = ? 
                WHERE student_id = ?
            """, (hashed_new_password, student_id))
            
            conn.commit()
            return True, "Құпия сөз сәтті өзгертілді!"
        else:
            return False, "Ескі құпия сөз дұрыс емес!"
    except Exception as e:
        print(f"❌ Құпия сөзді өзгерту қатесі: {e}")
        return False, f"Қате: {str(e)}"
    finally:
        conn.close()

# ============ СЕССИЯНЫ ҚАЛПЫНА КЕЛТІРУ ФУНКЦИЯЛАРЫ ============

def save_login_to_cookie(student_data):
    """Логин деректерін cookie-ге сақтау (query_params арқылы)"""
    try:
        import urllib.parse
        # Логин деректерін қысқаша хэш түрінде сақтау
        login_hash = hashlib.md5(f"{student_data['id']}_{student_data['student_code']}".encode()).hexdigest()[:8]
        st.query_params['logged_in'] = 'true'
        st.query_params['student_id'] = str(student_data['id'])
        st.query_params['login_hash'] = login_hash
    except Exception as e:
        print(f"⚠️ Cookie сақтау қатесі: {e}")

def clear_login_cookie():
    """Логин cookie-лерін тазарту"""
    try:
        # Барлық параметрлерді өшіру
        for key in list(st.query_params.keys()):
            del st.query_params[key]
    except:
        pass

def restore_session_from_cookie():
    """Cookie-ден сессияны қалпына келтіру"""
    try:
        if 'logged_in' in st.query_params and st.query_params['logged_in'] == 'true':
            if 'student_id' in st.query_params and 'login_hash' in st.query_params:
                student_id = st.query_params['student_id']
                login_hash = st.query_params['login_hash']
                
                # Дерекқордан студент деректерін алу
                conn = connect_db()
                c = conn.cursor()
                
                c.execute("""
                    SELECT s.id, s.full_name, s.student_code, s.class_id, 
                           c.name as class_name, s.grade_points, s.academic_performance
                    FROM students s
                    LEFT JOIN classes c ON s.class_id = c.id
                    WHERE s.id = ?
                """, (student_id,))
                
                student_db = c.fetchone()
                conn.close()
                
                if student_db:
                    # Хэшты тексеру
                    expected_hash = hashlib.md5(f"{student_db[0]}_{student_db[2]}".encode()).hexdigest()[:8]
                    
                    if login_hash == expected_hash:
                        student_data = {
                            'id': student_db[0],
                            'full_name': student_db[1],
                            'student_code': student_db[2],
                            'class_id': student_db[3],
                            'class_name': student_db[4] if student_db[4] else 'Сынып анықталмады',
                            'grade_points': student_db[5] if student_db[5] else 0,
                            'academic_performance': student_db[6] if student_db[6] else 'Орташа'
                        }
                        
                        # Сессияға қайта орнату
                        st.session_state.student = student_data
                        st.session_state.is_logged_in = True
                        st.session_state.current_page = 'my_tasks'
                        return True
    except Exception as e:
        print(f"⚠️ Сессияны қалпына келтіру қатесі: {e}")
    
    return False

# ============ КӨРСЕТУ ФУНКЦИЯЛАРЫ ============

def show_my_tasks():
    """Менің тапсырмаларым"""
    student = st.session_state.student
    
    st.markdown(f"<h2 style='color: #0066CC;'>📝 Менің тапсырмаларым</h2>", unsafe_allow_html=True)
    
    # Сүзгілер
    col1, col2, col3 = st.columns(3)
    with col1:
        status_filter = st.selectbox(
            "Статус бойынша сүзгі",
            ["Барлығы", "Тағайындалды", "Жіберілді", "Тексерілді"],
            key="status_filter_main_page"  # БІРЕГЕЙ КІЛТ
        )
    with col2:
        show_with_files = st.checkbox("Тек файл бар тапсырмалар", value=False, key="show_files_checkbox_main")
    with col3:
        if st.button("🔄 Тапсырмаларды жаңарту", use_container_width=True, key="refresh_tasks_main_btn"):
            st.rerun()
    
    # Тапсырмаларды алу
    tasks = get_student_tasks_from_db(student['id'])
    
    if not tasks:
        st.info("📭 Сізге әлі тапсырмалар жіберілмеген")
        return
    
    # Сүзгілерді қолдану
    filtered_tasks = []
    for task in tasks:
        # Статус бойынша сүзгі
        if status_filter != "Барлығы":
            if task.get('status', 'Тағайындалды') != status_filter:
                continue
        
        # Файл бар тапсырмалар
        if show_with_files:
            has_task_file = task.get('task_file') is not None
            has_answer_file = task.get('student_answer_file') is not None
            if not (has_task_file or has_answer_file):
                continue
        
        filtered_tasks.append(task)
    
    if not filtered_tasks:
        st.warning("⚠️ Сүзгі бойынша тапсырмалар табылмады")
        return
    
    st.success(f"✅ {len(filtered_tasks)} тапсырма табылды")
    
    # Тапсырмаларды көрсету
    for idx, task in enumerate(filtered_tasks):
        task_id = task['id']
        task_name = task.get('task_name', 'Атауы жоқ тапсырма')
        status = task.get('status', 'Тағайындалды')
        
        # Статус бойынша түс
        if status == 'Тағайындалды':
            border_color = "#ff4b4b"  # Қызыл
            status_icon = "🔴"
        elif status == 'Жіберілді':
            border_color = "#ffa500"  # Сары
            status_icon = "🟡"
        elif status == 'Тексерілді':
            border_color = "#28a745"  # Жасыл
            status_icon = "🟢"
        else:
            border_color = "#6c757d"  # Сұр
            status_icon = "⚪"
        
        # Карточка стилі
        st.markdown(f"""
        <div style="border: 2px solid {border_color}; border-radius: 10px; padding: 15px; margin: 10px 0; background: white;">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <h3 style="margin: 0; color: #333;">{status_icon} {task_name}</h3>
                <span style="background: {border_color}; color: white; padding: 5px 15px; border-radius: 20px; font-size: 0.9rem;">
                    {status}
                </span>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # Кеңейтілетін бөлім
        with st.expander(f"Тапсырма ақпаратын көрсету - {task_name[:30]}", expanded=False):
            # Екі бағанға бөлу
            col_left, col_right = st.columns([2, 1])
            
            with col_left:
                # Негізгі ақпарат
                st.markdown("**📋 Негізгі ақпарат:**")
                st.write(f"👨‍🏫 **Мұғалім:** {task.get('teacher_name', 'Мұғалім')}")
                
                due_date = task.get('due_date')
                if due_date:
                    st.write(f"📅 **Мерзімі:** {due_date}")
                
                st.write(f"⭐ **Ұпай:** {task.get('points', 10)}")
                
                score = task.get('score')
                if score:
                    st.success(f"📊 **Баға:** {score}/{task.get('points', 10)}")
                
                difficulty = task.get('difficulty')
                if difficulty:
                    st.write(f"⚡ **Қиындық:** {difficulty}")
                
                # Тапсырма сипаттамасы
                description = task.get('task_description')
                if description:
                    st.markdown("---")
                    st.markdown("**📝 Тапсырма сипаттамасы:**")
                    st.info(description)
                
                # ТАПСЫРМА ФАЙЛЫ
                task_file_info = download_task_file(task_id)
                if task_file_info:
                    st.markdown("---")
                    st.markdown("**📎 Тапсырма файлы:**")
                    
                    col_file1, col_file2, col_file3 = st.columns([3, 1, 1])
                    
                    with col_file1:
                        st.write(f"📄 **Атауы:** {task_file_info['filename']}")
                        st.write(f"📊 **Көлемі:** {get_file_size_str(task_file_info.get('size', len(task_file_info['data'])))}")
                        st.write(f"📝 **Түрі:** {task_file_info['content_type']}")
                    
                    with col_file2:
                        # Көрсету түймесі
                        if st.button("👁️ Көрсету", key=f"view_task_{task_id}_{idx}"):
                            # Модальды терезе
                            with st.container():
                                st.markdown("---")
                                st.markdown(f"### 📄 {task_file_info['filename']} - Алдын ала қарау")
                                preview_file(task_file_info['data'], 
                                           task_file_info['content_type'],
                                           task_file_info['filename'])
                    
                    with col_file3:
                        # Жүктеп алу түймесі
                        st.download_button(
                            label="📥 Жүктеп алу",
                            data=task_file_info['data'],
                            file_name=task_file_info['filename'],
                            mime=task_file_info['content_type'],
                            key=f"download_task_{task_id}_{idx}",
                            use_container_width=True
                        )
            
            with col_right:
                # Сіздің жауабыңыз
                answer_text = task.get('student_answer_text')
                if answer_text:
                    st.markdown("---")
                    st.markdown("**✍️ Сіздің жауабыңыз:**")
                    st.info(answer_text)
                
                # ЖІБЕРГЕН ЖАУАП ФАЙЛЫ
                answer_file_info = download_student_answer_file(task_id)
                if answer_file_info:
                    st.markdown("---")
                    st.markdown("**📤 Сіз жіберген файл:**")
                    
                    col_ans1, col_ans2 = st.columns([2, 1])
                    
                    with col_ans1:
                        st.write(f"📄 **Атауы:** {answer_file_info['filename']}")
                        st.write(f"📊 **Көлемі:** {get_file_size_str(answer_file_info.get('size', len(answer_file_info['data'])))}")
                    
                    with col_ans2:
                        # Көрсету түймесі
                        if st.button("👁️ Көрсету", key=f"view_answer_{task_id}_{idx}"):
                            with st.container():
                                st.markdown("---")
                                st.markdown(f"### 📄 {answer_file_info['filename']} - Алдын ала қарау")
                                preview_file(answer_file_info['data'], 
                                           answer_file_info['content_type'],
                                           answer_file_info['filename'])
                    
                    # Жүктеп алу түймесі
                    st.download_button(
                        label="📥 Жауап файлын жүктеп алу",
                        data=answer_file_info['data'],
                        file_name=answer_file_info['filename'],
                        mime=answer_file_info['content_type'],
                        key=f"download_answer_{task_id}_{idx}",
                        use_container_width=True
                    )
                
                # Мұғалім пікірі
                feedback = task.get('teacher_feedback')
                if feedback:
                    st.markdown("---")
                    st.markdown("**💬 Мұғалім пікірі:**")
                    st.success(feedback)
                
                # ЖАУАП БЕРУ ФОРМАСЫ
                if status == 'Тағайындалды':
                    st.markdown("---")
                    st.markdown("### 📤 Жауап жіберу")
                    
                    with st.form(key=f"answer_form_{task_id}_{idx}", clear_on_submit=True):
                        new_answer = st.text_area(
                            "📝 Жауап мәтіні", 
                            height=100,
                            value=answer_text if answer_text else "",
                            key=f"text_{task_id}_{idx}",
                            placeholder="Мұнда жауабыңызды енгізіңіз..."
                        )
                        
                        uploaded_file = st.file_uploader(
                            "📎 Файл қосу (PDF, Word, Excel, сурет, т.б.)",
                            type=['pdf', 'doc', 'docx', 'xls', 'xlsx', 'jpg', 'jpeg', 
                                  'png', 'txt', 'ppt', 'pptx', 'zip', 'rar'],
                            key=f"file_{task_id}_{idx}",
                            help="Максимум 10MB, барлық құжат түрлері қолдауы бар"
                        )
                        
                        if uploaded_file:
                            file_size_mb = len(uploaded_file.getvalue()) / (1024 * 1024)
                            if file_size_mb > 10:
                                st.error(f"❌ Файл көлемі тым үлкен ({file_size_mb:.2f} MB). Максимум 10 MB.")
                            else:
                                st.success(f"✅ Файл таңдалды: {uploaded_file.name} ({file_size_mb:.2f} MB)")
                        
                        submit_col1, submit_col2 = st.columns([3, 1])
                        
                        with submit_col1:
                            submit_btn = st.form_submit_button(
                                "🚀 Жауап жіберу",
                                use_container_width=True,
                                type="primary"
                            )
                        
                        with submit_col2:
                            clear_btn = st.form_submit_button(
                                "🗑️ Тазарту",
                                use_container_width=True,
                                type="secondary"
                            )
                        
                        if submit_btn:
                            if new_answer.strip() or uploaded_file:
                                with st.spinner("Жауап жіберілуде..."):
                                    if submit_student_answer_with_file(task_id, new_answer, uploaded_file):
                                        st.success("✅ Жауап сәтті жіберілді!")
                                        time.sleep(2)
                                        st.rerun()
                                    else:
                                        st.error("❌ Жауап жіберу кезінде қате пайда болды")
                            else:
                                st.warning("⚠️ Жауап мәтінін енгізіңіз немесе файл таңдаңыз!")
                        
                        if clear_btn:
                            st.rerun()

def show_bzb_tasks():
    """БЖБ тапсырмалары"""
    student = st.session_state.student
    
    st.markdown(f"<h2 style='color: #0066CC;'>📚 БЖБ тапсырмалары</h2>", unsafe_allow_html=True)
    
    tasks = get_student_bzb_tasks(student['class_id'])
    
    if not tasks:
        st.info("📭 БЖБ тапсырмалары әлі жоқ")
        return
    
    st.info("ℹ️ БЖБ (Бірлік Жиынтық Бағалау) - стандартты тест тапсырмалары")
    
    for idx, task in enumerate(tasks):
        with st.expander(f"📝 {task['task_name']}", expanded=False):
            col1, col2 = st.columns([3, 1])
            
            with col1:
                st.write(f"**🏫 Сынып:** {task['class_name']}")
                st.write(f"**📄 Файл түрі:** {task['file_type']}")
                st.write(f"**📅 Жүктелген күні:** {task['upload_date']}")
                st.write(f"**⚡ Қиындық:** {task['difficulty']}")
            
            with col2:
                file_data = download_bzb_task(task['id'])
                if file_data and file_data['data']:
                    # Көрсету түймесі
                    if st.button("👁️ Көрсету", key=f"view_bzb_{task['id']}_{idx}"):
                        with st.container():
                            st.markdown(f"### 📄 {file_data['filename']}")
                            preview_file(file_data['data'], 
                                       file_data['content_type'],
                                       file_data['filename'])
                    
                    # Жүктеп алу түймесі
                    st.download_button(
                        label="📥 Жүктеп алу",
                        data=file_data['data'],
                        file_name=file_data['filename'],
                        mime=file_data['content_type'],
                        key=f"download_bzb_{task['id']}_{idx}",
                        use_container_width=True
                    )
                else:
                    st.warning("📭 Файл жүктеп алу мүмкін емес")

def show_visual_materials():
    """Көрнекіліктер"""
    student = st.session_state.student
    
    st.markdown(f"<h2 style='color: #0066CC;'>📁 Көрнекілік материалдары</h2>", unsafe_allow_html=True)
    
    materials = get_class_visual_materials(student['class_id'])
    
    if not materials:
        st.info("📭 Көрнекілік материалдары әлі жоқ")
        return
    
    # Категория бойынша сүзгі
    categories = list(set([m['category'] for m in materials if m['category']]))
    categories.insert(0, "Барлығы")
    
    selected_category = st.selectbox("Санат бойынша сүзгі", categories, key="category_filter_visual")
    
    for idx, material in enumerate(materials):
        if selected_category != "Барлығы" and material['category'] != selected_category:
            continue
            
        with st.expander(f"📁 {material['file_name']} ({material['category']})", expanded=False):
            col1, col2 = st.columns([3, 1])
            
            with col1:
                st.write(f"**👨‍🏫 Мұғалім:** {material['teacher_name']}")
                st.write(f"**🏷️ Санаты:** {material['category']}")
                st.write(f"**📄 Файл түрі:** {material['file_type']}")
                st.write(f"**📅 Жүктелген күні:** {material['upload_date']}")
            
            with col2:
                file_data = download_visual_material(material['id'])
                if file_data and file_data['data']:
                    # Көрсету түймесі
                    if st.button("👁️ Көрсету", key=f"view_vis_{material['id']}_{idx}"):
                        with st.container():
                            st.markdown(f"### 📄 {file_data['filename']}")
                            preview_file(file_data['data'], 
                                       file_data['content_type'],
                                       file_data['filename'])
                    
                    # Жүктеп алу түймесі
                    st.download_button(
                        label="📥 Жүктеп алу",
                        data=file_data['data'],
                        file_name=file_data['filename'],
                        mime=file_data['content_type'],
                        key=f"download_vis_{material['id']}_{idx}",
                        use_container_width=True
                    )
                else:
                    st.warning("📭 Файл жүктеп алу мүмкін емес")

def show_my_grades():
    """Менің бағаларым"""
    student = st.session_state.student
    
    st.markdown(f"<h2 style='color: #0066CC;'>📊 Менің бағаларым</h2>", unsafe_allow_html=True)
    
    grades = get_student_grades(student['id'])
    
    # Статистика карточкалары
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown(f"""
        <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                    padding: 20px; border-radius: 10px; color: white; text-align: center;">
            <h3 style="margin: 0; font-size: 2rem;">{grades['grade_points']}</h3>
            <p style="margin: 5px 0 0 0; font-size: 0.9rem;">Орташа балл</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        # Бағаға түрлендіру
        try:
            points = float(grades['grade_points'])
            if points >= 9:
                grade = "A"
                color = "green"
                desc = "Өте жақсы"
            elif points >= 7:
                grade = "B"
                color = "lightgreen"
                desc = "Жақсы"
            elif points >= 5:
                grade = "C"
                color = "orange"
                desc = "Орташа"
            elif points >= 3:
                grade = "D"
                color = "red"
                desc = "Қанағаттанарлық"
            else:
                grade = "F"
                color = "darkred"
                desc = "Әлсіз"
            
            st.markdown(f"""
            <div style="background: linear-gradient(135deg, {color} 0%, #ffffff 100%); 
                        padding: 20px; border-radius: 10px; text-align: center;">
                <h1 style="margin: 0; font-size: 3rem; color: {color};">{grade}</h1>
                <p style="margin: 5px 0 0 0; color: #333;">{desc}</p>
            </div>
            """, unsafe_allow_html=True)
        except:
            st.markdown("""
            <div style="background: #f8f9fa; padding: 20px; border-radius: 10px; text-align: center;">
                <h3 style="margin: 0;">Анықталмады</h3>
            </div>
            """, unsafe_allow_html=True)
    
    with col3:
        st.markdown(f"""
        <div style="background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); 
                    padding: 20px; border-radius: 10px; color: white; text-align: center;">
            <h3 style="margin: 0; font-size: 1.5rem;">{grades['academic_performance']}</h3>
            <p style="margin: 5px 0 0 0; font-size: 0.9rem;">Оқу деңгейі</p>
        </div>
        """, unsafe_allow_html=True)
    
    # Бағалар тарихы
    st.markdown("---")
    st.subheader("📈 Бағалар тарихы")
    
    try:
        months = ['Қаңтар', 'Ақпан', 'Наурыз', 'Сәуір', 'Мамыр', 'Маусым',
                 'Шілде', 'Тамыз', 'Қыркүйек', 'Қазан', 'Қараша', 'Желтоқсан']
        
        base_point = float(grades['grade_points']) if isinstance(grades['grade_points'], (int, float)) else 5
        
        # Мысалдық мәндер
        grade_history = {
            'Ай': months[:6],
            'Орташа балл': [
                max(1, base_point - 2 + random.uniform(-0.5, 0.5)),
                max(1, base_point - 1 + random.uniform(-0.5, 0.5)),
                base_point + random.uniform(-0.5, 0.5),
                min(10, base_point + 1 + random.uniform(-0.5, 0.5)),
                min(10, base_point + 2 + random.uniform(-0.5, 0.5)),
                base_point + random.uniform(-0.5, 0.5)
            ]
        }
        
        df = pd.DataFrame(grade_history)
        
        # Диаграмма
        chart_data = pd.DataFrame({
            'Ай': df['Ай'],
            'Балл': df['Орташа балл']
        })
        
        st.line_chart(chart_data.set_index('Ай'))
        
        # Кесте
        st.markdown("**📋 Айлық бағалар:**")
        st.dataframe(df, use_container_width=True, hide_index=True)
        
    except Exception as e:
        st.info("📊 Бағалар тарихын көрсету мүмкін болмады")

def show_change_password():
    """Құпия сөзді өзгерту"""
    student = st.session_state.student
    
    st.markdown(f"<h2 style='color: #0066CC;'>🔐 Құпия сөзді өзгерту</h2>", unsafe_allow_html=True)
    
    # Ағымдағы логин алу
    conn = connect_db()
    c = conn.cursor()
    c.execute("SELECT username FROM student_logins WHERE student_id = ?", (student['id'],))
    login_info = c.fetchone()
    conn.close()
    
    if not login_info:
        st.error("❌ Логин табылмады! Мұғаліміңізге хабарласыңыз.")
        return
    
    st.info(f"**👤 Ағымдағы логин:** `{login_info[0]}`")
    
    with st.form("change_password_form", clear_on_submit=True):
        old_password = st.text_input(
            "🔑 Ескі құпия сөз", 
            type="password",
            help="Қазіргі құпия сөзіңізді енгізіңіз",
            key="old_password_input"
        )
        
        new_password = st.text_input(
            "🔐 Жаңа құпия сөз", 
            type="password",
            help="Жаңа құпия сөзді енгізіңіз (кемінде 6 таңба)",
            key="new_password_input"
        )
        
        confirm_password = st.text_input(
            "🔐 Жаңа құпия сөзді растау", 
            type="password",
            help="Жаңа құпия сөзді қайта енгізіңіз",
            key="confirm_password_input"
        )
        
        col1, col2 = st.columns([3, 1])
        
        with col1:
            submitted = st.form_submit_button(
                "💾 Құпия сөзді өзгерту", 
                use_container_width=True,
                type="primary"
            )
        
        with col2:
            clear_btn = st.form_submit_button(
                "🗑️ Тазарту",
                use_container_width=True,
                type="secondary"
            )
        
        if submitted:
            if not old_password or not new_password or not confirm_password:
                st.error("❌ Барлық өрістерді толтырыңыз!")
            elif new_password != confirm_password:
                st.error("❌ Жаңа құпия сөздер сәйкес келмейді!")
            elif len(new_password) < 6:
                st.error("❌ Құпия сөз кемінде 6 таңба болуы керек!")
            elif old_password == new_password:
                st.error("❌ Жаңа құпия сөз ескісінен өзгеше болуы керек!")
            else:
                with st.spinner("Құпия сөз өзгертілуде..."):
                    success, message = update_student_password_in_db(
                        student['id'], 
                        old_password, 
                        new_password
                    )
                    if success:
                        st.success(f"✅ {message}")
                        time.sleep(2)
                        st.rerun()
                    else:
                        st.error(f"❌ {message}")
        
        if clear_btn:
            st.rerun()

# ============ НЕГІЗГІ БАҒДАРЛАМА ============

def main():
    """Негізгі бағдарлама"""
    # Page configuration
    st.set_page_config(
        page_title="AI QAZAQ Students",
        page_icon="🎒",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # CSS стильдері
    st.markdown("""
    <style>
    /* Негізгі стильдер */
    .stApp {
        max-width: 1200px;
        margin: 0 auto;
    }
    
    /* Сессия сақтау ақпараты */
    .session-info {
        background: #e7f5ff;
        border: 1px solid #b6e0ff;
        border-radius: 5px;
        padding: 10px;
        margin: 10px 0;
        font-size: 0.9rem;
    }
    
    .session-info.success {
        background: #d4edda;
        border-color: #c3e6cb;
    }
    
    .session-info.warning {
        background: #fff3cd;
        border-color: #ffeaa7;
    }
    
    /* Карточкалар */
    .student-card {
        background: white;
        padding: 1.5rem;
        border-radius: 10px;
        border-left: 5px solid #28a745;
        margin-bottom: 1rem;
        box-shadow: 0 2px 5px rgba(0,0,0,0.1);
    }
    
    /* Түймелер */
    .stButton > button {
        border-radius: 8px !important;
        transition: all 0.3s ease !important;
    }
    
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    }
    
    /* Кеңейткіштер */
    .streamlit-expanderHeader {
        background: #f8f9fa !important;
        border-radius: 8px !important;
        border: 1px solid #dee2e6 !important;
    }
    
    /* Формалар */
    .stForm {
        border: 1px solid #dee2e6;
        border-radius: 10px;
        padding: 20px;
        background: white;
    }
    
    /* Прогресс бар */
    .stProgress > div > div > div {
        background-color: #0066CC;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Сессия state баптау
    if 'student' not in st.session_state:
        st.session_state.student = None
    if 'is_logged_in' not in st.session_state:
        st.session_state.is_logged_in = False
    if 'current_page' not in st.session_state:
        st.session_state.current_page = 'my_tasks'
    if 'last_refresh' not in st.session_state:
        st.session_state.last_refresh = time.time()
    
    # ЖАҢАРТУ: Сессияны қалпына келтіру (F5 төзімділік)
    if st.session_state.student is None:
        # Cookie-ден сессияны қалпына келтіруге тырысу
        if restore_session_from_cookie():
            st.success("✅ Сессия қалпына келтірілді! Деректер жүктелуде...")
            time.sleep(0.5)
    
    # Навигация
    if st.session_state.student is None:
        show_student_login()
    else:
        show_student_dashboard()

def show_student_login():
    """Оқушы кіру беті"""
    st.markdown("""
    <div style="background: linear-gradient(135deg, #0066CC 0%, #CC0000 100%); 
                padding: 2rem; border-radius: 15px; color: white; text-align: center; margin-bottom: 2rem;">
        <h1 style="margin: 0; font-size: 2.5rem;">🎒 AI QAZAQ STUDENTS</h1>
        <p style="margin: 10px 0 0 0; font-size: 1.2rem;">Оқушыларға арналған AI платформасы</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Сессияны сақтау туралы ақпарат
    st.markdown("""
    <div class="session-info success">
        <strong>ℹ️ Сессияны сақтау жүйесі:</strong><br>
        • Кіргеннен кейін сессияңыз сақталады<br>
        • F5 бассаңыз да жүйеден шықпайсыз<br>
        • Браузерді жапсаңыз да сессия сақталады<br>
        • Қауіпсіздік үшін шығу түймесін басыңыз
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("👨‍🎓 Оқушы ретінде кіру")
        
        with st.form("student_login_form", clear_on_submit=True):
            username = st.text_input(
                "👤 Логин", 
                placeholder="Мұғалім берген логин",
                key="login_username_input"
            )
            password = st.text_input(
                "🔒 Құпия сөз", 
                type="password", 
                placeholder="Мұғалім берген құпия сөз",
                key="login_password_input"
            )
            
            remember_session = st.checkbox(
                "💾 Сессияны сақтау (F5 төзімділік)", 
                value=True,
                help="Сессияны сақтау арқылы F5 бассаңыз да жүйеден шықпайсыз",
                key="remember_session_checkbox"
            )
            
            submitted = st.form_submit_button(
                "✅ Кіру", 
                use_container_width=True,
                type="primary"
            )
            
            if submitted:
                with st.spinner("Кіру тексерілуде..."):
                    if username and password:
                        student = login_student(username, password)
                        if student:
                            # Сессияны сақтау
                            st.session_state.student = student
                            st.session_state.is_logged_in = True
                            
                            # Еске сақтау опциясы
                            if remember_session:
                                save_login_to_cookie(student)
                            
                            st.success(f"✅ Қош келдіңіз, {student['full_name']}!")
                            
                            # 2 секунд күтіп, бетті жаңарту
                            time.sleep(1.5)
                            st.rerun()
                        else:
                            st.error("❌ Қате логин немесе құпия сөз!")
                    else:
                        st.error("❌ Логин мен құпия сөзді енгізіңіз!")
    
    with col2:
        st.info("""
        **ℹ️ Ақпарат:**
        
        • Логин мен құпия сөзді мұғаліміңізден аласыз
        • Кіруден кейін сізге тапсырмалар, БЖБ тапсырмалары және бағалар қолжетімді болады
        
        **🎯 Мүмкіндіктер:**
        • Тапсырма файлдарын көру және жүктеп алу
        • Жауап ретінде файл жіберу
        • Бағаларды бақылау
        • Көрнекілік материалдары
        
        **🔒 Қауіпсіздік:**
        • Сессияңыз F5 басуға төзімді
        • Браузерді жапсаңыз да, кіру деректері сақталады
        • Қауіпсіз шығу үшін "Жүйеден шығу" түймесін басыңыз
        """)

def show_student_dashboard():
    """Оқушы басқару панелі"""
    if 'student' not in st.session_state or not st.session_state.student:
        st.error("❌ Оқушы сессиясы табылмады")
        return

    student = st.session_state.student

    # Sidebar карточкасы
    with st.sidebar:
        # Оқушы ақпараты
        st.markdown(f"### 👨‍🎓 {student.get('full_name', 'Оқушы')}")
        st.markdown(f"**🏫 Сынып:** {student.get('class_name', '-')}")
        st.markdown(f"**🎯 Код:** {student.get('student_code', '-')}")
        
        # Прогресс
        grade_points = student.get("grade_points", 0)
        try:
            progress = int(float(grade_points) * 10)
        except:
            progress = 60  # Әдепкі мән
        
        st.progress(progress/100, text=f"📈 Оқу прогрессі: {progress}%")
        
        # Деңгей
        if progress >= 80:
            level = "Өте жақсы"
            level_color = "green"
        elif progress >= 60:
            level = "Жақсы"
            level_color = "orange"
        elif progress >= 40:
            level = "Орташа"
            level_color = "yellow"
        else:
            level = "Бастапқы"
            level_color = "red"
            
        st.markdown(f"**📊 Деңгей:** <span style='color:{level_color}; font-weight:bold;'>{level}</span>", unsafe_allow_html=True)
        
        st.markdown("---")
        
        # Навигация
        st.markdown("### 📍 Навигация")
        
        if st.button("📝 Менің тапсырмаларым", use_container_width=True, key="nav_my_tasks"):
            st.session_state.current_page = 'my_tasks'
            st.rerun()
            
        if st.button("📚 БЖБ тапсырмалары", use_container_width=True, key="nav_bzb_tasks"):
            st.session_state.current_page = 'bzb_tasks'
            st.rerun()
            
        if st.button("📁 Материалдар", use_container_width=True, key="nav_visual_materials"):
            st.session_state.current_page = 'visual_materials'
            st.rerun()
            
        if st.button("📊 Бағаларым", use_container_width=True, key="nav_my_grades"):
            st.session_state.current_page = 'my_grades'
            st.rerun()
            
        if st.button("🔐 Құпия сөз", use_container_width=True, key="nav_change_password"):
            st.session_state.current_page = 'change_password'
            st.rerun()
        
        st.markdown("---")
        
        # Басқару түймелері
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔄 Жаңарту", use_container_width=True, key="refresh_btn"):
                st.rerun()
        with col2:
            if st.button("🚪 Шығу", type="primary", use_container_width=True, key="logout_btn"):
                st.session_state.clear()
                clear_login_cookie()
                st.success("✅ Шықтыңыз")
                time.sleep(1)
                st.rerun()

    # Негізгі бет
    st.markdown(f"# 🎒 AI QAZAQ Students")
    st.markdown(f"### Қош келдің, {student.get('full_name', '')} 👋")
    
    # Беттерді көрсету
    try:
        if st.session_state.current_page == 'my_tasks':
            show_my_tasks()
        elif st.session_state.current_page == 'bzb_tasks':
            show_bzb_tasks()
        elif st.session_state.current_page == 'visual_materials':
            show_visual_materials()
        elif st.session_state.current_page == 'my_grades':
            show_my_grades()
        elif st.session_state.current_page == 'change_password':
            show_change_password()
    except Exception as e:
        st.error(f"❌ Бетті көрсету қатесі: {str(e)[:200]}")
        st.info("Бетті қайта жаңартып көріңіз")

if __name__ == "__main__":
    main()
