"""
Database models and operations for InciteRewrite.
SQLite-based storage with privacy-first design.
"""
import sqlite3
import uuid
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import logging

logger = logging.getLogger(__name__)

class Database:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.init_tables()
    
    def get_connection(self):
        """Get database connection with row factory."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def init_tables(self):
        """Initialize database tables."""
        with self.get_connection() as conn:
            # Sessions table - tracks analysis sessions
            conn.execute('''
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    expires_at DATETIME NOT NULL,
                    document_hash TEXT NOT NULL,
                    status TEXT DEFAULT 'active',
                    UNIQUE(document_hash, session_id)
                )
            ''')
            
            # Results table - stores analysis results
            conn.execute('''
                CREATE TABLE IF NOT EXISTS results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    document_hash TEXT NOT NULL,
                    citations_found INTEGER DEFAULT 0,
                    citations_verified INTEGER DEFAULT 0,
                    confidence_score REAL DEFAULT 0.0,
                    analysis_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    verification_details TEXT,
                    FOREIGN KEY (session_id) REFERENCES sessions (session_id)
                )
            ''')
            
            # Create indexes separately
            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_session_results ON results (session_id)
            ''')
            
            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_document_hash ON results (document_hash)
            ''')
            
            # Citation details table - stores individual citation results
            conn.execute('''
                CREATE TABLE IF NOT EXISTS citation_details (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    result_id INTEGER NOT NULL,
                    citation_text TEXT NOT NULL,
                    citation_type TEXT,
                    verified BOOLEAN DEFAULT FALSE,
                    confidence_score REAL DEFAULT 0.0,
                    courtlistener_match TEXT,
                    error_message TEXT,
                    FOREIGN KEY (result_id) REFERENCES results (id)
                )
            ''')
            
            conn.commit()

# Database instance
db_instance = None

def init_db(db_path: str):
    """Initialize database singleton."""
    global db_instance
    db_instance = Database(db_path)
    logger.info(f"Database initialized at {db_path}")

class SessionManager:
    """Manage analysis sessions with automatic cleanup."""
    
    @staticmethod
    def create_session(document_hash: str) -> str:
        """Create a new analysis session."""
        session_id = str(uuid.uuid4())
        expires_at = datetime.utcnow() + timedelta(hours=1)
        
        with db_instance.get_connection() as conn:
            conn.execute('''
                INSERT INTO sessions (session_id, document_hash, expires_at)
                VALUES (?, ?, ?)
            ''', (session_id, document_hash, expires_at))
            conn.commit()
        
        logger.info(f"Created session {session_id} for document hash {document_hash[:16]}...")
        return session_id
    
    @staticmethod
    def get_session(session_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve session information."""
        with db_instance.get_connection() as conn:
            cursor = conn.execute('''
                SELECT * FROM sessions WHERE session_id = ?
            ''', (session_id,))
            row = cursor.fetchone()
            
            if row:
                session_data = dict(row)
                
                # Check if session was manually expired
                if session_data['status'] == 'expired':
                    return None
                
                # Check if session has expired by time
                expires_at = datetime.fromisoformat(session_data['expires_at'])
                if datetime.utcnow() > expires_at:
                    SessionManager.expire_session(session_id)
                    return None
                return session_data
            return None
    
    @staticmethod
    def expire_session(session_id: str):
        """Mark session as expired."""
        with db_instance.get_connection() as conn:
            conn.execute('''
                UPDATE sessions SET status = 'expired' WHERE session_id = ?
            ''', (session_id,))
            conn.commit()
        logger.info(f"Session {session_id} marked as expired")
    
    @staticmethod
    def cleanup_expired_sessions():
        """Remove expired sessions and associated data."""
        with db_instance.get_connection() as conn:
            # Find expired sessions
            cursor = conn.execute('''
                SELECT session_id FROM sessions 
                WHERE expires_at < ? OR status = 'expired'
            ''', (datetime.utcnow(),))
            
            expired_sessions = [row[0] for row in cursor.fetchall()]
            
            if expired_sessions:
                # Delete associated results and citation details
                placeholders = ','.join('?' * len(expired_sessions))
                conn.execute(f'''
                    DELETE FROM citation_details 
                    WHERE result_id IN (
                        SELECT id FROM results WHERE session_id IN ({placeholders})
                    )
                ''', expired_sessions)
                
                conn.execute(f'''
                    DELETE FROM results WHERE session_id IN ({placeholders})
                ''', expired_sessions)
                
                conn.execute(f'''
                    DELETE FROM sessions WHERE session_id IN ({placeholders})
                ''', expired_sessions)
                
                conn.commit()
                logger.info(f"Cleaned up {len(expired_sessions)} expired sessions")

class ResultsManager:
    """Manage analysis results storage and retrieval."""
    
    @staticmethod
    def store_result(session_id: str, document_hash: str, 
                    citations_found: int, citations_verified: int,
                    confidence_score: float, verification_details: str = None) -> int:
        """Store analysis results."""
        with db_instance.get_connection() as conn:
            cursor = conn.execute('''
                INSERT INTO results 
                (session_id, document_hash, citations_found, citations_verified, 
                 confidence_score, verification_details)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (session_id, document_hash, citations_found, citations_verified,
                  confidence_score, verification_details))
            
            result_id = cursor.lastrowid
            conn.commit()
            
        logger.info(f"Stored results for session {session_id}, result ID {result_id}")
        return result_id
    
    @staticmethod
    def get_results(session_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve results for a session."""
        with db_instance.get_connection() as conn:
            cursor = conn.execute('''
                SELECT * FROM results WHERE session_id = ?
                ORDER BY analysis_timestamp DESC LIMIT 1
            ''', (session_id,))
            
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None
    
    @staticmethod
    def store_citation_detail(result_id: int, citation_text: str, 
                             citation_type: str, verified: bool,
                             confidence_score: float, courtlistener_match: str = None,
                             error_message: str = None):
        """Store individual citation verification details."""
        with db_instance.get_connection() as conn:
            conn.execute('''
                INSERT INTO citation_details 
                (result_id, citation_text, citation_type, verified, 
                 confidence_score, courtlistener_match, error_message)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (result_id, citation_text, citation_type, verified,
                  confidence_score, courtlistener_match, error_message))
            conn.commit()
    
    @staticmethod
    def get_citation_details(result_id: int) -> List[Dict[str, Any]]:
        """Get detailed citation verification results."""
        with db_instance.get_connection() as conn:
            cursor = conn.execute('''
                SELECT * FROM citation_details WHERE result_id = ?
                ORDER BY id
            ''', (result_id,))
            
            return [dict(row) for row in cursor.fetchall()]