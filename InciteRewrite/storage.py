import json
import sqlite3
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
                expires_at TIMESTAMP NOT NULL
            )
        ''')
        conn.commit()
        conn.close()
    
    def store(self, hash_id: str, data: dict, ttl: int = 604800):
        conn = sqlite3.connect(self.db_path)
        expires_at = datetime.utcnow() + timedelta(seconds=ttl)
        conn.execute(
            'INSERT OR REPLACE INTO results (hash_id, data, expires_at) VALUES (?, ?, ?)',
            (hash_id, json.dumps(data), expires_at)
        )
        conn.commit()
        conn.close()
    
    def retrieve(self, hash_id: str) -> dict:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute(
            'SELECT data FROM results WHERE hash_id = ? AND expires_at > ?',
            (hash_id, datetime.utcnow())
        )
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return json.loads(row[0])
        return None
    
    def cleanup_expired(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute('DELETE FROM results WHERE expires_at <= ?', (datetime.utcnow(),))
        conn.commit()
        conn.close()