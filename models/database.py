"""Database initialization and connection management"""

import sqlite3


def get_db_connection(db_path='medsense_history.db'):
    """Get database connection"""
    try:
        conn = sqlite3.connect(db_path)
        return conn
    except Exception as e:
        print(f"Database connection error: {e}")
        return None


def init_database():
    """Initialize database with all required tables"""
    try:
        conn = sqlite3.connect('medsense_history.db')
        cursor = conn.cursor()
        
        # Symptom history table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS symptom_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                platform TEXT NOT NULL,
                symptoms TEXT NOT NULL,
                diagnosis TEXT NOT NULL,
                timestamp DATETIME NOT NULL,
                body_part TEXT,
                severity TEXT,
                location_lat REAL,
                location_lon REAL,
                location_address TEXT
            )
        ''')
        
        # Diagnosis feedback table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS diagnosis_feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                history_id INTEGER NOT NULL,
                feedback TEXT NOT NULL,
                timestamp DATETIME NOT NULL,
                FOREIGN KEY (history_id) REFERENCES symptom_history(id)
            )
        ''')
        
        # User profiles table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT UNIQUE NOT NULL,
                age INTEGER,
                gender TEXT,
                timestamp DATETIME NOT NULL,
                platform TEXT NOT NULL
            )
        ''')
        
        # User locations table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_locations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                latitude REAL NOT NULL,
                longitude REAL NOT NULL,
                address TEXT,
                timestamp DATETIME NOT NULL,
                platform TEXT NOT NULL
            )
        ''')
        
        # User countries table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_countries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT UNIQUE NOT NULL,
                country TEXT NOT NULL,
                timestamp DATETIME NOT NULL,
                platform TEXT NOT NULL
            )
        ''')
        
        # Disease notifications table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS disease_notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                disease_name TEXT NOT NULL,
                country TEXT NOT NULL,
                who_event_id TEXT NOT NULL,
                notification_sent BOOLEAN DEFAULT FALSE,
                timestamp DATETIME NOT NULL
            )
        ''')
        
        # Follow-up reminders table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS follow_up_reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                platform TEXT NOT NULL,
                symptoms TEXT NOT NULL,
                diagnosis_id INTEGER NOT NULL,
                scheduled_time DATETIME NOT NULL,
                sent BOOLEAN DEFAULT FALSE,
                response_received BOOLEAN DEFAULT FALSE,
                user_response TEXT,
                timestamp DATETIME NOT NULL,
                FOREIGN KEY (diagnosis_id) REFERENCES symptom_history(id)
            )
        ''')
        
        conn.commit()
        conn.close()
        print("✅ Database initialized successfully")
        
    except Exception as e:
        print(f"❌ Database initialization error: {e}")
        raise e 