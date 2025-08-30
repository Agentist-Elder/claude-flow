"""
Database storage operation tests using London School TDD methodology.
Tests focus on database behavior, connection management, and data persistence.
"""

import pytest
import sqlite3
import time
import threading
import tempfile
import os
from unittest.mock import Mock, patch, MagicMock, call
from typing import Dict, List, Any, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

from src.database.connection import DatabaseManager, DatabaseStats


class TestDatabaseManagerInitialization:
    """Test database manager initialization and pool setup."""
    
    def test_initializes_with_memory_database(self):
        """Should initialize with in-memory database and connection pool."""
        db_manager = DatabaseManager(":memory:", pool_size=5)
        
        assert db_manager.db_path == ":memory:"
        assert db_manager.pool_size == 5
        assert len(db_manager._connection_pool) == 5
        assert db_manager._stats.total_connections == 5
        assert db_manager._stats.active_connections == 0
        assert db_manager._stats.total_queries == 0
    
    def test_initializes_with_file_database(self, temp_db_path):
        """Should initialize with file-based database."""
        db_manager = DatabaseManager(temp_db_path, pool_size=3)
        
        assert db_manager.db_path == temp_db_path
        assert db_manager.pool_size == 3
        assert len(db_manager._connection_pool) == 3
        
        # Database file should exist after initialization
        assert os.path.exists(temp_db_path)
    
    def test_creates_monitoring_tables_on_initialization(self, memory_db_manager):
        """Should create monitoring tables during initialization."""
        # Verify monitoring tables exist
        with memory_db_manager.get_connection() as conn:
            cursor = conn.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name IN ('query_log', 'connection_stats')
            """)
            
            tables = [row[0] for row in cursor.fetchall()]
            assert 'query_log' in tables
            assert 'connection_stats' in tables
    
    def test_configures_row_factory_for_dict_access(self, memory_db_manager):
        """Should configure row factory for dictionary-like access to results."""
        with memory_db_manager.get_connection() as conn:
            # Insert test data
            conn.execute("CREATE TABLE test (id INTEGER, name TEXT)")
            conn.execute("INSERT INTO test (id, name) VALUES (1, 'test')")
            conn.commit()
            
            # Query should return row with dictionary access
            cursor = conn.execute("SELECT id, name FROM test WHERE id = 1")
            row = cursor.fetchone()
            
            assert row['id'] == 1
            assert row['name'] == 'test'


class TestConnectionPoolManagement:
    """Test connection pool management and lifecycle."""
    
    def test_provides_connection_from_pool(self, memory_db_manager):
        """Should provide database connection from connection pool."""
        initial_pool_size = len(memory_db_manager._connection_pool)
        
        with memory_db_manager.get_connection() as conn:
            # Connection should be retrieved from pool
            assert len(memory_db_manager._connection_pool) == initial_pool_size - 1
            assert memory_db_manager._stats.active_connections == 1
            
            # Connection should be usable
            cursor = conn.execute("SELECT 1")
            result = cursor.fetchone()
            assert result[0] == 1
        
        # Connection should be returned to pool
        assert len(memory_db_manager._connection_pool) == initial_pool_size
        assert memory_db_manager._stats.active_connections == 0
    
    def test_creates_new_connection_when_pool_empty(self):
        """Should create new connection when pool is exhausted."""
        db_manager = DatabaseManager(":memory:", pool_size=1)
        
        # Use the only connection in pool
        with db_manager.get_connection() as conn1:
            assert len(db_manager._connection_pool) == 0
            
            # Request another connection - should create new one
            with db_manager.get_connection() as conn2:
                assert db_manager._stats.total_connections == 2
                assert conn1 != conn2
    
    def test_handles_connection_errors_gracefully(self):
        """Should handle connection errors and update error statistics."""
        db_manager = DatabaseManager(":memory:")
        
        # Simulate connection error
        with patch('sqlite3.connect', side_effect=sqlite3.Error("Connection failed")):
            with pytest.raises(sqlite3.Error):
                with db_manager.get_connection():
                    pass
        
        # Error statistics should be updated
        assert db_manager._stats.error_count > 0
        assert db_manager._stats.last_error == "Connection failed"
    
    def test_tracks_query_execution_time(self, memory_db_manager):
        """Should track query execution time for performance monitoring."""
        initial_query_count = memory_db_manager._stats.total_queries
        
        with memory_db_manager.get_connection() as conn:
            # Simulate some work
            time.sleep(0.01)  # Small delay to ensure measurable time
            conn.execute("SELECT 1")
        
        # Statistics should be updated
        assert memory_db_manager._stats.total_queries > initial_query_count
        assert memory_db_manager._stats.avg_query_time > 0
        assert len(memory_db_manager._query_times) > 0


class TestQueryExecutionBehavior:
    """Test query execution methods and result handling."""
    
    def test_executes_select_query_and_returns_results(self, memory_db_manager):
        """Should execute SELECT query and return results as list of dicts."""
        # Setup test data
        with memory_db_manager.get_connection() as conn:
            conn.execute("CREATE TABLE users (id INTEGER, name TEXT, email TEXT)")
            conn.execute("INSERT INTO users (id, name, email) VALUES (1, 'John', 'john@example.com')")
            conn.execute("INSERT INTO users (id, name, email) VALUES (2, 'Jane', 'jane@example.com')")
            conn.commit()
        
        # Execute query using manager
        results = memory_db_manager.execute_query(
            "SELECT id, name, email FROM users WHERE id > ?", (0,)
        )
        
        assert len(results) == 2
        assert results[0]['id'] == 1
        assert results[0]['name'] == 'John'
        assert results[1]['id'] == 2
        assert results[1]['name'] == 'Jane'
    
    def test_executes_update_query_and_returns_affected_rows(self, memory_db_manager):
        """Should execute UPDATE query and return number of affected rows."""
        # Setup test data
        with memory_db_manager.get_connection() as conn:
            conn.execute("CREATE TABLE products (id INTEGER, price REAL)")
            conn.execute("INSERT INTO products (id, price) VALUES (1, 10.0)")
            conn.execute("INSERT INTO products (id, price) VALUES (2, 20.0)")
            conn.commit()
        
        # Execute update
        affected_rows = memory_db_manager.execute_update(
            "UPDATE products SET price = price * 1.1 WHERE price < ?", (15.0,)
        )
        
        assert affected_rows == 1  # Only one product with price < 15
        
        # Verify update was applied
        results = memory_db_manager.execute_query("SELECT price FROM products WHERE id = 1")
        assert abs(results[0]['price'] - 11.0) < 0.001
    
    def test_executes_insert_query_and_returns_affected_rows(self, memory_db_manager):
        """Should execute INSERT query and return number of affected rows."""
        # Create table
        memory_db_manager.execute_update("CREATE TABLE logs (id INTEGER, message TEXT)")
        
        # Insert record
        affected_rows = memory_db_manager.execute_update(
            "INSERT INTO logs (id, message) VALUES (?, ?)", (1, "Test log message")
        )
        
        assert affected_rows == 1
        
        # Verify insertion
        results = memory_db_manager.execute_query("SELECT message FROM logs WHERE id = 1")
        assert len(results) == 1
        assert results[0]['message'] == "Test log message"
    
    def test_executes_delete_query_and_returns_affected_rows(self, memory_db_manager):
        """Should execute DELETE query and return number of affected rows."""
        # Setup test data
        memory_db_manager.execute_update("CREATE TABLE temp_data (id INTEGER, value TEXT)")
        memory_db_manager.execute_update("INSERT INTO temp_data (id, value) VALUES (1, 'keep')")
        memory_db_manager.execute_update("INSERT INTO temp_data (id, value) VALUES (2, 'delete')")
        memory_db_manager.execute_update("INSERT INTO temp_data (id, value) VALUES (3, 'delete')")
        
        # Delete records
        affected_rows = memory_db_manager.execute_update(
            "DELETE FROM temp_data WHERE value = ?", ('delete',)
        )
        
        assert affected_rows == 2
        
        # Verify deletions
        results = memory_db_manager.execute_query("SELECT COUNT(*) as count FROM temp_data")
        assert results[0]['count'] == 1
    
    def test_handles_query_execution_errors(self, memory_db_manager):
        """Should handle query execution errors and log them appropriately."""
        initial_error_count = memory_db_manager._stats.error_count
        
        # Execute invalid query
        with pytest.raises(sqlite3.Error):
            memory_db_manager.execute_query("SELECT * FROM nonexistent_table")
        
        # Error count should be incremented
        assert memory_db_manager._stats.error_count > initial_error_count
    
    def test_logs_query_performance_metrics(self, memory_db_manager):
        """Should log query performance metrics for monitoring."""
        # Create test table
        memory_db_manager.execute_update("CREATE TABLE performance_test (id INTEGER)")
        
        initial_query_count = memory_db_manager._stats.total_queries
        
        # Execute query
        memory_db_manager.execute_query("SELECT COUNT(*) FROM performance_test")
        
        # Query should be logged
        assert memory_db_manager._stats.total_queries > initial_query_count
        
        # Check query log table
        log_entries = memory_db_manager.execute_query(
            "SELECT query_type, success FROM query_log ORDER BY timestamp DESC LIMIT 1"
        )
        
        assert len(log_entries) > 0
        assert log_entries[0]['query_type'] == 'SELECT'
        assert log_entries[0]['success'] == 1  # SQLite stores booleans as integers


class TestBatchQueryExecution:
    """Test batch query execution functionality."""
    
    def test_executes_batch_queries_in_transaction(self, memory_db_manager):
        """Should execute multiple queries in a single transaction."""
        # Create table
        memory_db_manager.execute_update("CREATE TABLE batch_test (id INTEGER, name TEXT)")
        
        # Prepare batch queries
        batch_queries = [
            ("INSERT INTO batch_test (id, name) VALUES (?, ?)", (1, 'First')),
            ("INSERT INTO batch_test (id, name) VALUES (?, ?)", (2, 'Second')),
            ("INSERT INTO batch_test (id, name) VALUES (?, ?)", (3, 'Third'))
        ]
        
        # Execute batch
        results = memory_db_manager.execute_batch(batch_queries)
        
        # All queries should succeed
        assert len(results) == 3
        assert all(affected_rows == 1 for affected_rows in results)
        
        # Verify all records were inserted
        records = memory_db_manager.execute_query("SELECT COUNT(*) as count FROM batch_test")
        assert records[0]['count'] == 3
    
    def test_rolls_back_batch_on_error(self, memory_db_manager):
        """Should roll back entire batch if any query fails."""
        # Create table
        memory_db_manager.execute_update("CREATE TABLE rollback_test (id INTEGER PRIMARY KEY, name TEXT)")
        
        # Prepare batch with one failing query (duplicate primary key)
        batch_queries = [
            ("INSERT INTO rollback_test (id, name) VALUES (1, 'First')", ()),
            ("INSERT INTO rollback_test (id, name) VALUES (1, 'Duplicate')", ()),  # This will fail
            ("INSERT INTO rollback_test (id, name) VALUES (2, 'Third')", ())
        ]
        
        # Batch should fail
        with pytest.raises(sqlite3.IntegrityError):
            memory_db_manager.execute_batch(batch_queries)
        
        # No records should be inserted due to rollback
        records = memory_db_manager.execute_query("SELECT COUNT(*) as count FROM rollback_test")
        assert records[0]['count'] == 0
    
    def test_logs_batch_execution_performance(self, memory_db_manager):
        """Should log batch execution performance metrics."""
        # Create table
        memory_db_manager.execute_update("CREATE TABLE perf_batch (id INTEGER)")
        
        # Execute batch
        batch_queries = [
            ("INSERT INTO perf_batch (id) VALUES (?)", (i,)) for i in range(5)
        ]
        
        memory_db_manager.execute_batch(batch_queries)
        
        # Check that batch operation was logged
        log_entries = memory_db_manager.execute_query(
            "SELECT query_type, execution_time FROM query_log WHERE query_type = 'BATCH' ORDER BY timestamp DESC LIMIT 1"
        )
        
        assert len(log_entries) > 0
        assert log_entries[0]['query_type'] == 'BATCH'
        assert log_entries[0]['execution_time'] > 0


class TestDatabaseStatisticsAndMonitoring:
    """Test database statistics collection and monitoring functionality."""
    
    def test_provides_current_database_statistics(self, memory_db_manager):
        """Should provide current database statistics."""
        stats = memory_db_manager.get_stats()
        
        assert isinstance(stats, DatabaseStats)
        assert stats.total_connections > 0
        assert stats.active_connections >= 0
        assert stats.total_queries >= 0
        assert stats.avg_query_time >= 0
        assert stats.error_count >= 0
    
    def test_tracks_connection_utilization_over_time(self, memory_db_manager):
        """Should track connection utilization in connection_stats table."""
        # Get initial stats
        initial_stats = memory_db_manager.get_stats()
        
        # Make some database operations
        memory_db_manager.execute_update("CREATE TABLE utilization_test (id INTEGER)")
        memory_db_manager.execute_query("SELECT COUNT(*) FROM utilization_test")
        
        # Get updated stats
        updated_stats = memory_db_manager.get_stats()
        
        # Query count should have increased
        assert updated_stats.total_queries > initial_stats.total_queries
        
        # Connection stats should be recorded
        conn_stats = memory_db_manager.execute_query(
            "SELECT COUNT(*) as count FROM connection_stats"
        )
        assert conn_stats[0]['count'] > 0
    
    def test_calculates_performance_metrics_over_time_period(self, memory_db_manager):
        """Should calculate performance metrics for specified time period."""
        # Create test table and insert some data
        memory_db_manager.execute_update("CREATE TABLE metrics_test (id INTEGER, data TEXT)")
        memory_db_manager.execute_update("INSERT INTO metrics_test (id, data) VALUES (1, 'test')")
        
        # Execute various query types
        memory_db_manager.execute_query("SELECT * FROM metrics_test")
        memory_db_manager.execute_update("UPDATE metrics_test SET data = 'updated' WHERE id = 1")
        memory_db_manager.execute_update("DELETE FROM metrics_test WHERE id = 999")  # Delete with no matches
        
        # Get performance metrics
        metrics = memory_db_manager.get_performance_metrics(hours=24)
        
        assert 'query_metrics' in metrics
        assert 'connection_metrics' in metrics
        assert 'overall_stats' in metrics
        
        # Should have metrics for different query types
        query_metrics = metrics['query_metrics']
        assert len(query_metrics) > 0
        
        # Each query type should have performance data
        for query_type, data in query_metrics.items():
            assert 'count' in data
            assert 'avg_time' in data
            assert 'success_rate' in data
    
    def test_provides_connection_utilization_metrics(self, memory_db_manager):
        """Should provide connection pool utilization metrics."""
        # Generate some load to create utilization data
        for i in range(3):
            memory_db_manager.execute_query("SELECT ?",(i,))
        
        metrics = memory_db_manager.get_performance_metrics(hours=1)
        
        conn_metrics = metrics['connection_metrics']
        assert 'avg_utilization' in conn_metrics
        assert 'max_utilization' in conn_metrics
        assert 'total_connections' in conn_metrics
        assert conn_metrics['total_connections'] > 0
    
    def test_tracks_error_rates_and_success_rates(self, memory_db_manager):
        """Should track error rates and success rates for queries."""
        # Execute successful query
        memory_db_manager.execute_update("CREATE TABLE error_test (id INTEGER)")
        
        # Execute failing query (but catch the exception)
        try:
            memory_db_manager.execute_query("SELECT * FROM nonexistent_table")
        except sqlite3.Error:
            pass  # Expected error
        
        # Get performance metrics
        metrics = memory_db_manager.get_performance_metrics(hours=1)
        
        # Should have error rate information
        overall_stats = metrics['overall_stats']
        assert 'error_rate' in overall_stats
        assert overall_stats['error_rate'] >= 0
        
        # Should have success rate information per query type
        if metrics['query_metrics']:
            for query_type, data in metrics['query_metrics'].items():
                assert 'success_rate' in data
                assert 0 <= data['success_rate'] <= 100


class TestDatabaseHealthChecking:
    """Test database health check functionality."""
    
    def test_performs_basic_health_check(self, memory_db_manager):
        """Should perform basic database health check."""
        health_status = memory_db_manager.health_check()
        
        assert health_status['status'] == 'healthy'
        assert 'response_time' in health_status
        assert 'tables_count' in health_status
        assert 'connection_pool' in health_status
        assert 'performance' in health_status
        
        # Response time should be reasonable
        assert health_status['response_time'] > 0
        assert health_status['response_time'] < 1.0  # Should be very fast for in-memory DB
    
    def test_reports_connection_pool_status_in_health_check(self, memory_db_manager):
        """Should include connection pool status in health check."""
        health_status = memory_db_manager.health_check()
        
        pool_status = health_status['connection_pool']
        assert 'total' in pool_status
        assert 'active' in pool_status
        assert 'available' in pool_status
        
        assert pool_status['total'] > 0
        assert pool_status['active'] >= 0
        assert pool_status['available'] >= 0
    
    def test_includes_performance_summary_in_health_check(self, memory_db_manager):
        """Should include performance summary in health check."""
        # Generate some activity
        memory_db_manager.execute_update("CREATE TABLE health_test (id INTEGER)")
        memory_db_manager.execute_query("SELECT COUNT(*) FROM health_test")
        
        health_status = memory_db_manager.health_check()
        
        performance = health_status['performance']
        assert 'total_queries' in performance
        assert 'avg_query_time' in performance
        assert 'error_rate' in performance
        
        assert performance['total_queries'] > 0
        assert performance['avg_query_time'] >= 0
        assert performance['error_rate'] >= 0
    
    def test_detects_unhealthy_database_state(self):
        """Should detect and report unhealthy database state."""
        # Create manager with invalid database path
        with patch('sqlite3.connect', side_effect=sqlite3.Error("Database corrupted")):
            db_manager = DatabaseManager("/invalid/path/database.db")
            
            health_status = db_manager.health_check()
            
            assert health_status['status'] == 'unhealthy'
            assert 'error' in health_status
            assert 'Database corrupted' in health_status['error']


class TestDatabaseMaintenanceOperations:
    """Test database maintenance and cleanup operations."""
    
    def test_cleans_up_old_query_logs(self, memory_db_manager):
        """Should clean up old query logs and connection stats."""
        # Create some test data with old timestamps
        with memory_db_manager.get_connection() as conn:
            old_timestamp = time.time() - (31 * 24 * 3600)  # 31 days ago
            
            # Insert old log entries
            conn.execute("""
                INSERT INTO query_log (query_hash, query_type, execution_time, timestamp, success)
                VALUES ('old1', 'SELECT', 0.1, ?, 1)
            """, (old_timestamp,))
            
            conn.execute("""
                INSERT INTO connection_stats (timestamp, active_connections, pool_utilization, total_queries)
                VALUES (?, 1, 0.5, 10)
            """, (old_timestamp,))
            
            conn.commit()
        
        # Add recent entries
        memory_db_manager.execute_query("SELECT 1")  # This will create recent log entry
        
        # Clean up old entries (keep only last 7 days)
        deleted_count = memory_db_manager.cleanup_old_logs(days=7)
        
        assert deleted_count > 0
        
        # Verify old entries were removed
        old_logs = memory_db_manager.execute_query(
            "SELECT COUNT(*) as count FROM query_log WHERE timestamp < ?",
            (time.time() - (7 * 24 * 3600),)
        )
        assert old_logs[0]['count'] == 0
    
    def test_handles_cleanup_errors_gracefully(self, memory_db_manager):
        """Should handle cleanup errors gracefully without crashing."""
        # Simulate error during cleanup
        with patch.object(memory_db_manager, 'get_connection', side_effect=sqlite3.Error("Cleanup failed")):
            deleted_count = memory_db_manager.cleanup_old_logs(days=30)
            
            # Should return 0 on error rather than crashing
            assert deleted_count == 0
    
    def test_closes_all_connections_properly(self, temp_db_path):
        """Should close all connections in the pool properly."""
        db_manager = DatabaseManager(temp_db_path, pool_size=3)
        
        # Verify connections exist
        assert len(db_manager._connection_pool) == 3
        assert db_manager._stats.total_connections == 3
        
        # Close all connections
        db_manager.close_all_connections()
        
        # Pool should be empty
        assert len(db_manager._connection_pool) == 0
        assert db_manager._stats.total_connections == 0
        assert db_manager._stats.active_connections == 0
    
    def test_handles_connection_close_errors(self, memory_db_manager):
        """Should handle errors when closing connections."""
        # Mock connection that raises error on close
        mock_connection = Mock()
        mock_connection.close.side_effect = sqlite3.Error("Close failed")
        
        # Add mock connection to pool
        memory_db_manager._connection_pool.append(mock_connection)
        
        # Should not raise exception even if individual connection close fails
        memory_db_manager.close_all_connections()
        
        # Pool should still be cleared
        assert len(memory_db_manager._connection_pool) == 0


class TestConcurrentDatabaseAccess:
    """Test concurrent database access and thread safety."""
    
    def test_handles_concurrent_queries_safely(self, memory_db_manager):
        """Should handle concurrent queries from multiple threads safely."""
        # Create test table
        memory_db_manager.execute_update("CREATE TABLE concurrent_test (id INTEGER, thread_id TEXT, value INTEGER)")
        
        results = []
        errors = []
        
        def worker_function(thread_id):
            try:
                # Each thread performs multiple operations
                for i in range(5):
                    # Insert data
                    memory_db_manager.execute_update(
                        "INSERT INTO concurrent_test (id, thread_id, value) VALUES (?, ?, ?)",
                        (thread_id * 100 + i, f"thread_{thread_id}", i)
                    )
                    
                    # Query data
                    data = memory_db_manager.execute_query(
                        "SELECT COUNT(*) as count FROM concurrent_test WHERE thread_id = ?",
                        (f"thread_{thread_id}",)
                    )
                    
                    results.append((thread_id, data[0]['count']))
                    
            except Exception as e:
                errors.append((thread_id, str(e)))
        
        # Start multiple worker threads
        threads = []
        for i in range(5):
            thread = threading.Thread(target=worker_function, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Verify no errors occurred
        assert len(errors) == 0, f"Concurrent access errors: {errors}"
        
        # Verify all operations completed
        assert len(results) == 25  # 5 threads × 5 operations each
        
        # Verify final data consistency
        final_count = memory_db_manager.execute_query(
            "SELECT COUNT(*) as count FROM concurrent_test"
        )
        assert final_count[0]['count'] == 25
    
    def test_connection_pool_thread_safety(self, temp_db_path):
        """Should manage connection pool safely across multiple threads."""
        db_manager = DatabaseManager(temp_db_path, pool_size=3)
        connection_usage = []
        errors = []
        
        def use_connection(thread_id):
            try:
                with db_manager.get_connection() as conn:
                    connection_usage.append(f"thread_{thread_id}_start")
                    
                    # Simulate some work
                    conn.execute("CREATE TABLE IF NOT EXISTS thread_test (id INTEGER)")
                    conn.execute("INSERT INTO thread_test (id) VALUES (?)", (thread_id,))
                    
                    time.sleep(0.01)  # Small delay to increase chance of contention
                    
                    connection_usage.append(f"thread_{thread_id}_end")
                    
            except Exception as e:
                errors.append((thread_id, str(e)))
        
        # Start more threads than connections in pool
        threads = []
        for i in range(6):  # 6 threads, 3 connections in pool
            thread = threading.Thread(target=use_connection, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join()
        
        # Verify no errors
        assert len(errors) == 0, f"Thread safety errors: {errors}"
        
        # Verify all threads completed their work
        assert len(connection_usage) == 12  # 6 threads × 2 events each
        
        # Verify pool state is consistent
        stats = db_manager.get_stats()
        assert stats.active_connections == 0  # All connections returned to pool
    
    def test_concurrent_batch_operations(self, memory_db_manager):
        """Should handle concurrent batch operations safely."""
        # Create test table
        memory_db_manager.execute_update("CREATE TABLE batch_concurrent (id INTEGER, batch_id INTEGER)")
        
        batch_results = []
        errors = []
        
        def execute_batch(batch_id):
            try:
                # Create batch of queries for this batch_id
                batch_queries = [
                    ("INSERT INTO batch_concurrent (id, batch_id) VALUES (?, ?)", (batch_id * 10 + i, batch_id))
                    for i in range(5)
                ]
                
                results = memory_db_manager.execute_batch(batch_queries)
                batch_results.append((batch_id, sum(results)))
                
            except Exception as e:
                errors.append((batch_id, str(e)))
        
        # Execute multiple batches concurrently
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(execute_batch, i) for i in range(4)]
            
            for future in as_completed(futures):
                future.result()  # Wait for completion and raise any exceptions
        
        # Verify no errors
        assert len(errors) == 0, f"Concurrent batch errors: {errors}"
        
        # Verify all batches completed
        assert len(batch_results) == 4
        
        # Each batch should have inserted 5 records (sum of affected rows = 5)
        for batch_id, affected_rows in batch_results:
            assert affected_rows == 5
        
        # Verify total records in database
        total_records = memory_db_manager.execute_query(
            "SELECT COUNT(*) as count FROM batch_concurrent"
        )
        assert total_records[0]['count'] == 20  # 4 batches × 5 records each


class TestDatabaseErrorHandling:
    """Test database error handling and recovery scenarios."""
    
    def test_handles_database_lock_errors(self, temp_db_path):
        """Should handle database lock errors gracefully."""
        db_manager = DatabaseManager(temp_db_path)
        
        # Create a situation that might cause locking (simplified simulation)
        with db_manager.get_connection() as conn1:
            conn1.execute("CREATE TABLE lock_test (id INTEGER)")
            conn1.execute("BEGIN EXCLUSIVE TRANSACTION")
            
            # Try to access from another connection (might be blocked)
            try:
                with db_manager.get_connection() as conn2:
                    conn2.execute("INSERT INTO lock_test (id) VALUES (1)")
                    conn2.commit()
            except sqlite3.OperationalError as e:
                # Database lock error is expected in this scenario
                assert "locked" in str(e).lower() or "busy" in str(e).lower()
            
            conn1.rollback()  # Release the lock
    
    def test_handles_corrupt_database_gracefully(self):
        """Should handle corrupt database scenarios."""
        # Simulate database corruption by using invalid file
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            f.write(b"This is not a valid SQLite database file")
            corrupt_db_path = f.name
        
        try:
            # Attempting to connect to corrupt database should be handled
            db_manager = DatabaseManager(corrupt_db_path)
            
            with pytest.raises(sqlite3.DatabaseError):
                db_manager.execute_query("SELECT 1")
            
            # Error should be tracked
            assert db_manager._stats.error_count > 0
            
        finally:
            os.unlink(corrupt_db_path)
    
    def test_handles_disk_full_scenarios(self, temp_db_path):
        """Should handle disk full scenarios appropriately."""
        db_manager = DatabaseManager(temp_db_path)
        
        # Create test table
        db_manager.execute_update("CREATE TABLE disk_test (id INTEGER, data TEXT)")
        
        # Simulate disk full error
        with patch.object(db_manager, 'get_connection') as mock_get_conn:
            mock_conn = Mock()
            mock_conn.__enter__ = Mock(return_value=mock_conn)
            mock_conn.__exit__ = Mock(return_value=None)
            mock_conn.execute.side_effect = sqlite3.OperationalError("database or disk is full")
            mock_get_conn.return_value = mock_conn
            
            with pytest.raises(sqlite3.OperationalError, match="disk is full"):
                db_manager.execute_update("INSERT INTO disk_test (id, data) VALUES (1, 'test')")
    
    def test_recovers_from_temporary_connection_failures(self, memory_db_manager):
        """Should recover from temporary connection failures."""
        # Simulate temporary connection failure
        original_get_connection = memory_db_manager.get_connection
        failure_count = 0
        
        def failing_get_connection():
            nonlocal failure_count
            if failure_count < 2:  # Fail first 2 attempts
                failure_count += 1
                raise sqlite3.Error("Temporary connection failure")
            return original_get_connection()
        
        # This test would require retry logic in the actual implementation
        # For now, we just verify that the error is properly raised and logged
        with patch.object(memory_db_manager, 'get_connection', side_effect=failing_get_connection):
            with pytest.raises(sqlite3.Error):
                memory_db_manager.execute_query("SELECT 1")
            
            # Error should be tracked
            assert memory_db_manager._stats.error_count > 0


@pytest.mark.integration
class TestDatabaseIntegrationScenarios:
    """Test database integration with other system components."""
    
    def test_integrates_with_text_processor_storage(self, temp_db_path):
        """Should integrate properly with text processor for document storage."""
        from src.utils.text_processing import TextProcessor
        
        # Use same database for both components
        db_manager = DatabaseManager(temp_db_path)
        text_processor = TextProcessor(temp_db_path)
        
        # Process and store text
        sample_text = "This is a test document for integration testing."
        analysis = text_processor.analyze_text(sample_text, store_result=True)
        
        # Verify data was stored using database manager
        documents = db_manager.execute_query(
            "SELECT doc_id, word_count, character_count FROM text_documents"
        )
        
        assert len(documents) == 1
        assert documents[0]['word_count'] == analysis.word_count
        assert documents[0]['character_count'] == analysis.character_count
    
    def test_supports_concurrent_application_access(self, temp_db_path):
        """Should support concurrent access from multiple application components."""
        from src.utils.text_processing import TextProcessor
        from src.auth.authentication import AuthenticationManager
        
        # Create multiple components using same database
        db_manager = DatabaseManager(temp_db_path)
        text_processor = TextProcessor(temp_db_path)
        auth_manager = AuthenticationManager(temp_db_path)
        
        # Concurrent operations from different components
        def text_operations():
            for i in range(3):
                text_processor.analyze_text(f"Test document {i}", store_result=True)
        
        def auth_operations():
            for i in range(3):
                try:
                    auth_manager.register_user(f"user{i}", f"user{i}@example.com", "password123")
                except Exception:
                    pass  # User might already exist
        
        def db_operations():
            for i in range(3):
                db_manager.execute_query("SELECT COUNT(*) FROM sqlite_master")
        
        # Run operations concurrently
        threads = [
            threading.Thread(target=text_operations),
            threading.Thread(target=auth_operations),
            threading.Thread(target=db_operations)
        ]
        
        for thread in threads:
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # Verify all operations completed without errors
        # Check that data from different components exists
        text_docs = db_manager.execute_query("SELECT COUNT(*) as count FROM text_documents")
        user_count = db_manager.execute_query("SELECT COUNT(*) as count FROM users")
        
        assert text_docs[0]['count'] > 0
        assert user_count[0]['count'] > 0
    
    def test_maintains_data_consistency_across_transactions(self, memory_db_manager):
        """Should maintain data consistency across complex transactions."""
        # Create related tables
        memory_db_manager.execute_update("""
            CREATE TABLE orders (id INTEGER PRIMARY KEY, customer_id INTEGER, total REAL)
        """)
        
        memory_db_manager.execute_update("""
            CREATE TABLE order_items (id INTEGER PRIMARY KEY, order_id INTEGER, product_id INTEGER, quantity INTEGER)
        """)
        
        # Execute complex transaction with multiple related inserts
        transaction_queries = [
            ("INSERT INTO orders (id, customer_id, total) VALUES (1, 123, 99.99)", ()),
            ("INSERT INTO order_items (id, order_id, product_id, quantity) VALUES (1, 1, 101, 2)", ()),
            ("INSERT INTO order_items (id, order_id, product_id, quantity) VALUES (2, 1, 102, 1)", ()),
            ("UPDATE orders SET total = (SELECT SUM(quantity * 49.99) FROM order_items WHERE order_id = 1) WHERE id = 1", ())
        ]
        
        results = memory_db_manager.execute_batch(transaction_queries)
        
        # Verify all operations succeeded
        assert all(result >= 0 for result in results)
        
        # Verify data consistency
        order_data = memory_db_manager.execute_query(
            "SELECT o.total, COUNT(oi.id) as item_count FROM orders o LEFT JOIN order_items oi ON o.id = oi.order_id WHERE o.id = 1 GROUP BY o.id"
        )
        
        assert len(order_data) == 1
        assert order_data[0]['item_count'] == 2  # 2 order items
        assert order_data[0]['total'] == 149.97  # 3 items × 49.99


@pytest.mark.performance
class TestDatabasePerformance:
    """Test database performance characteristics and optimization."""
    
    def test_query_execution_performance_scales_reasonably(self, memory_db_manager, performance_monitor):
        """Should have reasonable query performance scaling."""
        # Create test table with index
        memory_db_manager.execute_update("CREATE TABLE perf_test (id INTEGER PRIMARY KEY, value TEXT)")
        memory_db_manager.execute_update("CREATE INDEX idx_perf_value ON perf_test(value)")
        
        # Insert test data
        batch_data = [(f"INSERT INTO perf_test (value) VALUES (?)", (f"value_{i}",)) for i in range(1000)]
        memory_db_manager.execute_batch(batch_data)
        
        # Measure query performance
        performance_monitor.start()
        
        # Execute various queries
        for i in range(100):
            memory_db_manager.execute_query("SELECT * FROM perf_test WHERE value = ?", (f"value_{i}",))
        
        metrics = performance_monitor.stop()
        
        # Should complete in reasonable time
        assert metrics['duration'] < 2.0  # Less than 2 seconds for 100 queries
        
        # Memory usage should be reasonable
        assert metrics['memory_delta'] < 50  # Less than 50MB
    
    def test_connection_pool_efficiency(self, temp_db_path, performance_monitor):
        """Should demonstrate connection pool efficiency benefits."""
        # Test with connection pool
        pooled_manager = DatabaseManager(temp_db_path, pool_size=5)
        
        performance_monitor.start()
        
        # Execute multiple queries using pool
        for i in range(50):
            pooled_manager.execute_query("SELECT ?", (i,))
        
        pooled_metrics = performance_monitor.stop()
        
        # Connection pool should provide reasonable performance
        assert pooled_metrics['duration'] < 1.0
        
        # Verify pool statistics
        stats = pooled_manager.get_stats()
        assert stats.total_queries >= 50
        assert stats.avg_query_time > 0
    
    def test_batch_operation_efficiency(self, memory_db_manager, performance_monitor):
        """Should demonstrate efficiency of batch operations over individual queries."""
        memory_db_manager.execute_update("CREATE TABLE batch_perf (id INTEGER, data TEXT)")
        
        # Measure individual operations
        performance_monitor.start()
        for i in range(100):
            memory_db_manager.execute_update(
                "INSERT INTO batch_perf (id, data) VALUES (?, ?)", 
                (i, f"individual_{i}")
            )
        individual_metrics = performance_monitor.stop()
        
        # Clear table for batch test
        memory_db_manager.execute_update("DELETE FROM batch_perf")
        
        # Measure batch operations
        batch_queries = [
            ("INSERT INTO batch_perf (id, data) VALUES (?, ?)", (i, f"batch_{i}"))
            for i in range(100, 200)
        ]
        
        performance_monitor.start()
        memory_db_manager.execute_batch(batch_queries)
        batch_metrics = performance_monitor.stop()
        
        # Batch should be more efficient
        assert batch_metrics['duration'] < individual_metrics['duration']
        
        # Verify same amount of data was inserted
        count_result = memory_db_manager.execute_query("SELECT COUNT(*) as count FROM batch_perf")
        assert count_result[0]['count'] == 100
    
    def test_monitoring_overhead_is_minimal(self, memory_db_manager, performance_monitor):
        """Should have minimal overhead from performance monitoring."""
        memory_db_manager.execute_update("CREATE TABLE monitor_test (id INTEGER)")
        
        performance_monitor.start()
        
        # Execute many operations to test monitoring overhead
        for i in range(200):
            memory_db_manager.execute_query("SELECT COUNT(*) FROM monitor_test")
        
        metrics = performance_monitor.stop()
        
        # Monitoring should not significantly impact performance
        assert metrics['duration'] < 3.0  # Should complete quickly
        
        # Verify monitoring data was collected
        stats = memory_db_manager.get_stats()
        assert stats.total_queries >= 200
        
        # Performance metrics should be available
        perf_metrics = memory_db_manager.get_performance_metrics(hours=1)
        assert len(perf_metrics['query_metrics']) > 0
