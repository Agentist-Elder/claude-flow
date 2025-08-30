"""
Database connection and operations layer.
Real database testing without mocks for London School TDD.
"""

import sqlite3
import json
import time
import threading
from typing import Dict, List, Any, Optional, Tuple
from contextlib import contextmanager
from dataclasses import dataclass
import logging


logger = logging.getLogger(__name__)


@dataclass
class DatabaseStats:
    """Database statistics for monitoring."""
    total_connections: int
    active_connections: int
    total_queries: int
    avg_query_time: float
    error_count: int
    last_error: Optional[str] = None


class DatabaseManager:
    """
    Database connection manager with real operations and monitoring.
    Tests validate actual database behavior and performance.
    """
    
    def __init__(self, db_path: str = ":memory:", pool_size: int = 10):
        self.db_path = db_path
        self.pool_size = pool_size
        self._connection_pool = []
        self._pool_lock = threading.Lock()
        self._stats = DatabaseStats(0, 0, 0, 0.0, 0)
        self._query_times = []
        self._initialize_pool()
        self._create_monitoring_tables()
    
    def _initialize_pool(self) -> None:
        """Initialize connection pool."""
        with self._pool_lock:
            for _ in range(self.pool_size):
                conn = sqlite3.connect(self.db_path, check_same_thread=False)
                conn.row_factory = sqlite3.Row  # Enable dict-like access
                self._connection_pool.append(conn)
            
            self._stats.total_connections = self.pool_size
    
    def _create_monitoring_tables(self) -> None:
        """Create tables for monitoring database performance."""
        with self.get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS query_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    query_hash TEXT,
                    query_type TEXT,
                    execution_time REAL,
                    timestamp REAL,
                    success BOOLEAN,
                    error_message TEXT
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS connection_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL,
                    active_connections INTEGER,
                    pool_utilization REAL,
                    total_queries INTEGER
                )
            """)
            
            conn.commit()
    
    @contextmanager
    def get_connection(self):
        """Get database connection from pool with automatic cleanup."""
        connection = None
        start_time = time.time()
        
        try:
            with self._pool_lock:
                if self._connection_pool:
                    connection = self._connection_pool.pop()
                    self._stats.active_connections += 1
                else:
                    # Create new connection if pool is empty
                    connection = sqlite3.connect(self.db_path, check_same_thread=False)
                    connection.row_factory = sqlite3.Row
                    self._stats.total_connections += 1
            
            yield connection
            
        except Exception as e:
            self._stats.error_count += 1
            self._stats.last_error = str(e)
            logger.error(f"Database error: {str(e)}")
            raise
            
        finally:
            if connection:
                # Record query time
                query_time = time.time() - start_time
                self._query_times.append(query_time)
                self._stats.total_queries += 1
                
                # Keep only last 1000 query times for rolling average
                if len(self._query_times) > 1000:
                    self._query_times = self._query_times[-1000:]
                
                self._stats.avg_query_time = sum(self._query_times) / len(self._query_times)
                
                with self._pool_lock:
                    self._connection_pool.append(connection)
                    self._stats.active_connections = max(0, self._stats.active_connections - 1)
    
    def execute_query(self, query: str, params: Tuple = ()) -> List[Dict[str, Any]]:
        """Execute SELECT query and return results."""
        start_time = time.time()
        query_hash = str(hash(query))
        
        try:
            with self.get_connection() as conn:
                cursor = conn.execute(query, params)
                results = [dict(row) for row in cursor.fetchall()]
                
                # Log successful query
                self._log_query(query_hash, "SELECT", time.time() - start_time, True)
                return results
                
        except Exception as e:
            # Log failed query
            self._log_query(query_hash, "SELECT", time.time() - start_time, False, str(e))
            raise
    
    def execute_update(self, query: str, params: Tuple = ()) -> int:
        """Execute UPDATE/INSERT/DELETE query and return affected rows."""
        start_time = time.time()
        query_hash = str(hash(query))
        query_type = query.strip().split()[0].upper()
        
        try:
            with self.get_connection() as conn:
                cursor = conn.execute(query, params)
                conn.commit()
                affected_rows = cursor.rowcount
                
                # Log successful query
                self._log_query(query_hash, query_type, time.time() - start_time, True)
                return affected_rows
                
        except Exception as e:
            # Log failed query
            self._log_query(query_hash, query_type, time.time() - start_time, False, str(e))
            raise
    
    def execute_batch(self, queries: List[Tuple[str, Tuple]]) -> List[int]:
        """Execute multiple queries in a transaction."""
        start_time = time.time()
        results = []
        
        try:
            with self.get_connection() as conn:
                for query, params in queries:
                    cursor = conn.execute(query, params)
                    results.append(cursor.rowcount)
                
                conn.commit()
                
                # Log batch operation
                self._log_query("BATCH", "BATCH", time.time() - start_time, True)
                return results
                
        except Exception as e:
            # Log failed batch
            self._log_query("BATCH", "BATCH", time.time() - start_time, False, str(e))
            raise
    
    def _log_query(self, query_hash: str, query_type: str, execution_time: float, 
                   success: bool, error_message: str = None) -> None:
        """Log query execution for monitoring."""
        try:
            with self.get_connection() as conn:
                conn.execute("""
                    INSERT INTO query_log 
                    (query_hash, query_type, execution_time, timestamp, success, error_message)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (query_hash, query_type, execution_time, time.time(), success, error_message))
                conn.commit()
        except Exception as e:
            # Don't fail the original operation due to logging issues
            logger.warning(f"Failed to log query: {str(e)}")
    
    def get_stats(self) -> DatabaseStats:
        """Get current database statistics."""
        # Update connection stats
        try:
            with self.get_connection() as conn:
                conn.execute("""
                    INSERT INTO connection_stats 
                    (timestamp, active_connections, pool_utilization, total_queries)
                    VALUES (?, ?, ?, ?)
                """, (time.time(), self._stats.active_connections, 
                     self._stats.active_connections / self._stats.total_connections,
                     self._stats.total_queries))
                conn.commit()
        except Exception as e:
            logger.warning(f"Failed to update connection stats: {str(e)}")
        
        return self._stats
    
    def get_performance_metrics(self, hours: int = 24) -> Dict[str, Any]:
        """Get performance metrics for the specified time period."""
        since_time = time.time() - (hours * 3600)
        
        try:
            with self.get_connection() as conn:
                # Query performance metrics
                cursor = conn.execute("""
                    SELECT 
                        query_type,
                        COUNT(*) as query_count,
                        AVG(execution_time) as avg_time,
                        MAX(execution_time) as max_time,
                        MIN(execution_time) as min_time,
                        SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) as error_count
                    FROM query_log 
                    WHERE timestamp > ?
                    GROUP BY query_type
                """, (since_time,))
                
                query_metrics = {}
                for row in cursor.fetchall():
                    query_metrics[row['query_type']] = {
                        'count': row['query_count'],
                        'avg_time': round(row['avg_time'], 4),
                        'max_time': round(row['max_time'], 4),
                        'min_time': round(row['min_time'], 4),
                        'error_count': row['error_count'],
                        'success_rate': round((row['query_count'] - row['error_count']) / row['query_count'] * 100, 2)
                    }
                
                # Connection utilization metrics
                cursor = conn.execute("""
                    SELECT 
                        AVG(pool_utilization) as avg_utilization,
                        MAX(pool_utilization) as max_utilization,
                        COUNT(*) as samples
                    FROM connection_stats
                    WHERE timestamp > ?
                """, (since_time,))
                
                utilization_row = cursor.fetchone()
                
                return {
                    'timeframe_hours': hours,
                    'query_metrics': query_metrics,
                    'connection_metrics': {
                        'avg_utilization': round(utilization_row['avg_utilization'] or 0, 2),
                        'max_utilization': round(utilization_row['max_utilization'] or 0, 2),
                        'total_connections': self._stats.total_connections,
                        'samples': utilization_row['samples']
                    },
                    'overall_stats': {
                        'total_queries': self._stats.total_queries,
                        'avg_query_time': round(self._stats.avg_query_time, 4),
                        'error_rate': round(self._stats.error_count / max(self._stats.total_queries, 1) * 100, 2),
                        'last_error': self._stats.last_error
                    }
                }
                
        except Exception as e:
            logger.error(f"Failed to get performance metrics: {str(e)}")
            return {'error': str(e)}
    
    def health_check(self) -> Dict[str, Any]:
        """Perform database health check."""
        try:
            start_time = time.time()
            
            with self.get_connection() as conn:
                # Test basic operations
                conn.execute("SELECT 1").fetchone()
                
                # Check table integrity
                tables = conn.execute("""
                    SELECT name FROM sqlite_master WHERE type='table'
                """).fetchall()
                
                query_time = time.time() - start_time
                
                return {
                    'status': 'healthy',
                    'response_time': round(query_time, 4),
                    'tables_count': len(tables),
                    'connection_pool': {
                        'total': self._stats.total_connections,
                        'active': self._stats.active_connections,
                        'available': len(self._connection_pool)
                    },
                    'performance': {
                        'total_queries': self._stats.total_queries,
                        'avg_query_time': round(self._stats.avg_query_time, 4),
                        'error_rate': round(self._stats.error_count / max(self._stats.total_queries, 1) * 100, 2)
                    }
                }
                
        except Exception as e:
            return {
                'status': 'unhealthy',
                'error': str(e),
                'timestamp': time.time()
            }
    
    def cleanup_old_logs(self, days: int = 30) -> int:
        """Clean up old query logs and stats."""
        cutoff_time = time.time() - (days * 24 * 3600)
        
        try:
            with self.get_connection() as conn:
                # Clean up query logs
                cursor = conn.execute("""
                    DELETE FROM query_log WHERE timestamp < ?
                """, (cutoff_time,))
                query_log_deleted = cursor.rowcount
                
                # Clean up connection stats
                cursor = conn.execute("""
                    DELETE FROM connection_stats WHERE timestamp < ?
                """, (cutoff_time,))
                stats_deleted = cursor.rowcount
                
                conn.commit()
                
                return query_log_deleted + stats_deleted
                
        except Exception as e:
            logger.error(f"Failed to cleanup old logs: {str(e)}")
            return 0
    
    def close_all_connections(self) -> None:
        """Close all connections in the pool."""
        with self._pool_lock:
            for conn in self._connection_pool:
                try:
                    conn.close()
                except Exception as e:
                    logger.warning(f"Error closing connection: {str(e)}")
            
            self._connection_pool.clear()
            self._stats.total_connections = 0
            self._stats.active_connections = 0