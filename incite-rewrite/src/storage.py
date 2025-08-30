import json
import sqlite3
import secrets
from datetime import datetime, timedelta

class ResultStore:
    def __init__(self, db_path='results.db'):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute('''
            CREATE TABLE IF NOT EXISTS results (
                hash_id TEXT PRIMARY KEY,
                data TEXT NOT NULL,
                created_at TIMESTAMP NOT NULL,
                last_accessed TIMESTAMP
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS sessions (
                token TEXT PRIMARY KEY,
                hash_id TEXT NOT NULL,
                expires_at TIMESTAMP NOT NULL,
                FOREIGN KEY (hash_id) REFERENCES results(hash_id)
            )
        ''')
        conn.commit()
        conn.close()
    
    def store(self, hash_id: str, data: dict):
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            'INSERT OR REPLACE INTO results (hash_id, data, created_at) VALUES (?, ?, ?)',
            (hash_id, json.dumps(data), datetime.utcnow())
        )
        conn.commit()
        conn.close()
    
    def create_session(self, hash_id: str, ttl_hours: int = 1) -> str:
        token = secrets.token_urlsafe(32)
        expires_at = datetime.utcnow() + timedelta(hours=ttl_hours)
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            'INSERT INTO sessions (token, hash_id, expires_at) VALUES (?, ?, ?)',
            (token, hash_id, expires_at)
        )
        conn.commit()
        conn.close()
        return token
    
    def get_hash_from_token(self, token: str) -> str:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute(
            'SELECT hash_id FROM sessions WHERE token = ? AND expires_at > ?',
            (token, datetime.utcnow())
        )
        row = cursor.fetchone()
        conn.close()
        return row[0] if row else None
    
    def retrieve(self, hash_id: str) -> dict:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute(
            'SELECT data FROM results WHERE hash_id = ?',
            (hash_id,)
        )
        conn.execute('UPDATE results SET last_accessed = ? WHERE hash_id = ?', 
                    (datetime.utcnow(), hash_id))
        conn.commit()
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return json.loads(row[0])
        return None
    
    def check_hash_exists(self, hash_id: str) -> dict:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute(
            'SELECT created_at FROM results WHERE hash_id = ?',
            (hash_id,)
        )
        row = cursor.fetchone()
        conn.close()
        return {'exists': bool(row), 'created_at': row[0] if row else None}
    
    def cleanup_expired_sessions(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute('DELETE FROM sessions WHERE expires_at <= ?', (datetime.utcnow(),))
        conn.commit()
        conn.close()