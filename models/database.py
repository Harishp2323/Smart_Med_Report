import sqlite3
from datetime import datetime
import json

class CBCDatabase:
    def __init__(self, db_path='cbc_reports.db'):
        self.db_path = db_path
        self.init_db()
    
    def init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Reports table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS reports (
                report_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                report_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                age INTEGER,
                sex TEXT,
                raw_text TEXT,
                parameters TEXT,
                assessment TEXT,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        ''')
        
        # Chat history table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS chat_history (
                chat_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                report_id INTEGER,
                message TEXT,
                response TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id),
                FOREIGN KEY (report_id) REFERENCES reports (report_id)
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def create_user(self, username):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute('INSERT INTO users (username) VALUES (?)', (username,))
            conn.commit()
            user_id = cursor.lastrowid
        except sqlite3.IntegrityError:
            cursor.execute('SELECT user_id FROM users WHERE username = ?', (username,))
            user_id = cursor.fetchone()[0]
        conn.close()
        return user_id
    
    def save_report(self, user_id, age, sex, raw_text, parameters, assessment):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO reports (user_id, age, sex, raw_text, parameters, assessment)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (user_id, age, sex, raw_text, json.dumps(parameters), json.dumps(assessment)))
        conn.commit()
        report_id = cursor.lastrowid
        conn.close()
        return report_id
    
    def get_user_reports(self, user_id, limit=10):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT report_id, report_date, age, sex, parameters, assessment
            FROM reports
            WHERE user_id = ?
            ORDER BY report_date DESC
            LIMIT ?
        ''', (user_id, limit))
        reports = cursor.fetchall()
        conn.close()
        
        result = []
        for report in reports:
            result.append({
                'report_id': report[0],
                'date': report[1],
                'age': report[2],
                'sex': report[3],
                'parameters': json.loads(report[4]),
                'assessment': json.loads(report[5])
            })
        return result
    
    def save_chat(self, user_id, report_id, message, response):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO chat_history (user_id, report_id, message, response)
            VALUES (?, ?, ?, ?)
        ''', (user_id, report_id, message, response))
        conn.commit()
        conn.close()
    
    def get_chat_history(self, user_id, report_id=None, limit=50):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if report_id:
            cursor.execute('''
                SELECT message, response, timestamp
                FROM chat_history
                WHERE user_id = ? AND report_id = ?
                ORDER BY timestamp ASC
                LIMIT ?
            ''', (user_id, report_id, limit))
        else:
            cursor.execute('''
                SELECT message, response, timestamp
                FROM chat_history
                WHERE user_id = ?
                ORDER BY timestamp DESC
                LIMIT ?
            ''', (user_id, limit))
        
        history = cursor.fetchall()
        conn.close()
        
        return [{'message': h[0], 'response': h[1], 'timestamp': h[2]} for h in history]