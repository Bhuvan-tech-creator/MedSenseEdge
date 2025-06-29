"""User-related database operations"""

import sqlite3
from datetime import datetime, timedelta
from models.database import get_db_connection


def save_user_profile(user_id, age, gender, platform):
    """Save or update user profile"""
    try:
        conn = sqlite3.connect('medsense_history.db')
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO user_profiles (user_id, age, gender, timestamp, platform)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, age, gender, datetime.now(), platform))
        conn.commit()
        conn.close()
        print(f"Saved profile for user {user_id}: age {age}, gender {gender}")
        return True
    except Exception as e:
        print(f"Error saving user profile: {e}")
        return False


def get_user_profile(user_id):
    """Get user profile information"""
    try:
        conn = sqlite3.connect('medsense_history.db')
        cursor = conn.cursor()
        cursor.execute('''
            SELECT age, gender FROM user_profiles WHERE user_id = ?
        ''', (user_id,))
        result = cursor.fetchone()
        conn.close()
        if result:
            return {"age": result[0], "gender": result[1]}
        return None
    except Exception as e:
        print(f"Error retrieving user profile: {e}")
        return None


def is_new_user(user_id):
    """Check if user is new (no profile and no history)"""
    profile = get_user_profile(user_id)
    history = get_user_history(user_id)
    return profile is None and len(history) == 0


def save_user_location(user_id, latitude, longitude, address, platform):
    """Save user location data"""
    try:
        conn = sqlite3.connect('medsense_history.db')
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO user_locations (user_id, latitude, longitude, address, timestamp, platform)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (user_id, latitude, longitude, address, datetime.now(), platform))
        conn.commit()
        conn.close()
        print(f"Saved location for user {user_id}: {latitude}, {longitude}")
        return True
    except Exception as e:
        print(f"Error saving user location: {e}")
        return False


def get_user_recent_location(user_id, hours_back=24):
    """Get user's most recent location within specified timeframe"""
    try:
        conn = sqlite3.connect('medsense_history.db')
        cursor = conn.cursor()
        cutoff_time = datetime.now() - timedelta(hours=hours_back)
        cursor.execute('''
            SELECT latitude, longitude, address FROM user_locations 
            WHERE user_id = ? AND timestamp >= ?
            ORDER BY timestamp DESC LIMIT 1
        ''', (user_id, cutoff_time))
        result = cursor.fetchone()
        conn.close()
        if result:
            return {"lat": result[0], "lon": result[1], "address": result[2]}
        return None
    except Exception as e:
        print(f"Error retrieving user location: {e}")
        return None


def save_user_country(user_id, country, platform):
    """Save user's country for disease outbreak notifications"""
    try:
        conn = sqlite3.connect('medsense_history.db')
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO user_countries (user_id, country, timestamp, platform)
            VALUES (?, ?, ?, ?)
        ''', (user_id, country, datetime.now(), platform))
        conn.commit()
        conn.close()
        print(f"Saved country {country} for user {user_id}")
        return True
    except Exception as e:
        print(f"Error saving user country: {e}")
        return False


def get_user_country(user_id):
    """Get user's country for disease outbreak checking"""
    try:
        conn = sqlite3.connect('medsense_history.db')
        cursor = conn.cursor()
        cursor.execute('SELECT country FROM user_countries WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else None
    except Exception as e:
        print(f"Error retrieving user country: {e}")
        return None


def save_diagnosis_to_history(user_id, platform, symptoms, diagnosis, body_part=None, severity=None, location_data=None):
    """Save diagnosis to user's medical history"""
    try:
        conn = sqlite3.connect('medsense_history.db')
        cursor = conn.cursor()
        
        lat, lon, address = None, None, None
        if location_data:
            lat = location_data.get('lat')
            lon = location_data.get('lon')
            address = location_data.get('address')
        
        cursor.execute('''
            INSERT INTO symptom_history (user_id, platform, symptoms, diagnosis, timestamp, body_part, severity, location_lat, location_lon, location_address)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, platform, symptoms, diagnosis, datetime.now(), body_part, severity, lat, lon, address))
        history_id = cursor.lastrowid
        
        # Schedule 24-hour follow-up reminder
        followup_time = datetime.now() + timedelta(hours=24)
        cursor.execute('''
            INSERT INTO follow_up_reminders (user_id, platform, symptoms, diagnosis_id, scheduled_time, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (user_id, platform, symptoms, history_id, followup_time, datetime.now()))
        
        conn.commit()
        conn.close()
        print(f"Saved diagnosis to history for user {user_id} with 24h follow-up scheduled")
        return history_id
    except Exception as e:
        print(f"Error saving to database: {e}")
        return None


def get_user_history(user_id, days_back=365):
    """Get user's medical history"""
    try:
        conn = sqlite3.connect('medsense_history.db')
        cursor = conn.cursor()
        cutoff_date = datetime.now() - timedelta(days=days_back)
        cursor.execute('''
            SELECT symptoms, diagnosis, timestamp, body_part, severity 
            FROM symptom_history 
            WHERE user_id = ? AND timestamp >= ?
            ORDER BY timestamp DESC
        ''', (user_id, cutoff_date))
        history = cursor.fetchall()
        conn.close()
        return history
    except Exception as e:
        print(f"Error retrieving history: {e}")
        return []


def get_history_id(user_id, timestamp):
    """Get history ID for a specific timestamp"""
    try:
        conn = sqlite3.connect('medsense_history.db')
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id FROM symptom_history 
            WHERE user_id = ? AND timestamp = ?
        ''', (user_id, timestamp))
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else None
    except Exception as e:
        print(f"Error retrieving history_id: {e}")
        return None


def save_feedback(user_id, history_id, feedback):
    """Save user feedback for a diagnosis"""
    try:
        conn = sqlite3.connect('medsense_history.db')
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO diagnosis_feedback (user_id, history_id, feedback, timestamp)
            VALUES (?, ?, ?, ?)
        ''', (user_id, history_id, feedback, datetime.now()))
        conn.commit()
        conn.close()
        print(f"Saved feedback for user {user_id}, history_id {history_id}")
    except Exception as e:
        print(f"Error saving feedback: {e}")


def get_pending_followups():
    """Get all pending follow-up reminders that are due"""
    try:
        conn = sqlite3.connect('medsense_history.db')
        cursor = conn.cursor()
        current_time = datetime.now()
        cursor.execute('''
            SELECT id, user_id, platform, symptoms, diagnosis_id, scheduled_time
            FROM follow_up_reminders 
            WHERE sent = FALSE AND scheduled_time <= ?
            ORDER BY scheduled_time ASC
        ''', (current_time,))
        followups = cursor.fetchall()
        conn.close()
        return followups
    except Exception as e:
        print(f"Error retrieving pending follow-ups: {e}")
        return []


def mark_followup_sent(followup_id):
    """Mark a follow-up reminder as sent"""
    try:
        conn = sqlite3.connect('medsense_history.db')
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE follow_up_reminders 
            SET sent = TRUE 
            WHERE id = ?
        ''', (followup_id,))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error marking follow-up as sent: {e}")
        return False


def save_followup_response(user_id, response_text):
    """Save user's response to a follow-up check-in"""
    try:
        conn = sqlite3.connect('medsense_history.db')
        cursor = conn.cursor()
        # Find the most recent sent follow-up for this user that hasn't received a response
        cursor.execute('''
            UPDATE follow_up_reminders 
            SET response_received = TRUE, user_response = ?
            WHERE user_id = ? AND sent = TRUE AND response_received = FALSE
            ORDER BY scheduled_time DESC
            LIMIT 1
        ''', (response_text, user_id))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error saving follow-up response: {e}")
        return False


def is_followup_response_expected(user_id):
    """Check if a follow-up response is expected from this user"""
    try:
        conn = sqlite3.connect('medsense_history.db')
        cursor = conn.cursor()
        cursor.execute('''
            SELECT COUNT(*) FROM follow_up_reminders 
            WHERE user_id = ? AND sent = TRUE AND response_received = FALSE
        ''', (user_id,))
        count = cursor.fetchone()[0]
        conn.close()
        return count > 0
    except Exception as e:
        print(f"Error checking follow-up response status: {e}")
        return False 