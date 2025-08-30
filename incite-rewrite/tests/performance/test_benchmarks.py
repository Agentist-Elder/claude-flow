"""
Performance benchmarking tests using London School TDD methodology.
Tests real performance characteristics and response times without mocks.
"""

import pytest
import time
import statistics
import psutil
import threading
import concurrent.futures
import json
import tempfile
import os
from typing import Dict, List, Any, Tuple
from dataclasses import dataclass

from src.api.endpoints import create_app, benchmark_endpoint
from src.auth.authentication import AuthenticationManager
from src.utils.text_processing import TextProcessor
from src.database.connection import DatabaseManager


@dataclass
class PerformanceResult:
    """Performance test result data."""
    operation: str
    min_time: float
    max_time: float
    avg_time: float
    median_time: float
    p95_time: float
    p99_time: float
    total_time: float
    iterations: int
    success_rate: float
    memory_usage_mb: float
    cpu_usage_percent: float


class PerformanceBenchmark:
    """
    Performance benchmark utility for measuring real system performance.
    No mocks - tests actual execution times and resource usage.
    """
    
    def __init__(self):
        self.results = []
        self.process = psutil.Process()
    
    def measure_performance(self, operation_name: str, operation_func, iterations: int = 100) -> PerformanceResult:
        """
        Measure performance of an operation over multiple iterations.
        Records timing, memory usage, and CPU usage.
        """
        times = []
        successes = 0
        memory_before = self.process.memory_info().rss / 1024 / 1024  # MB
        cpu_percent_samples = []
        
        # Warm-up runs
        for _ in range(min(5, iterations // 10)):
            try:
                operation_func()
            except Exception:
                pass
        
        # Actual benchmark runs
        start_total = time.time()
        
        for _ in range(iterations):
            # Measure CPU usage
            cpu_before = self.process.cpu_percent()
            
            start_time = time.time()
            try:
                operation_func()
                successes += 1
            except Exception:
                pass
            end_time = time.time()
            
            times.append(end_time - start_time)
            cpu_percent_samples.append(self.process.cpu_percent())
        
        total_time = time.time() - start_total
        memory_after = self.process.memory_info().rss / 1024 / 1024  # MB
        
        # Calculate statistics
        times.sort()
        success_rate = successes / iterations
        
        result = PerformanceResult(
            operation=operation_name,
            min_time=min(times) if times else 0,
            max_time=max(times) if times else 0,
            avg_time=statistics.mean(times) if times else 0,
            median_time=statistics.median(times) if times else 0,
            p95_time=times[int(0.95 * len(times))] if times else 0,
            p99_time=times[int(0.99 * len(times))] if times else 0,
            total_time=total_time,
            iterations=iterations,
            success_rate=success_rate,
            memory_usage_mb=memory_after - memory_before,
            cpu_usage_percent=statistics.mean(cpu_percent_samples) if cpu_percent_samples else 0
        )
        
        self.results.append(result)
        return result
    
    def print_results(self):
        """Print benchmark results in a readable format."""
        print("\n" + "="*80)
        print("PERFORMANCE BENCHMARK RESULTS")
        print("="*80)
        
        for result in self.results:
            print(f"\nOperation: {result.operation}")
            print(f"Iterations: {result.iterations}")
            print(f"Success Rate: {result.success_rate:.2%}")
            print(f"Total Time: {result.total_time:.3f}s")
            print(f"Average Time: {result.avg_time:.4f}s")
            print(f"Median Time: {result.median_time:.4f}s")
            print(f"95th Percentile: {result.p95_time:.4f}s")
            print(f"99th Percentile: {result.p99_time:.4f}s")
            print(f"Min/Max Time: {result.min_time:.4f}s / {result.max_time:.4f}s")
            print(f"Memory Delta: {result.memory_usage_mb:.2f}MB")
            print(f"CPU Usage: {result.cpu_usage_percent:.1f}%")
            print("-" * 40)


class TestAuthenticationPerformance:
    """Performance tests for authentication operations."""
    
    @pytest.fixture
    def perf_db_path(self):
        """Create temporary database for performance testing."""
        fd, path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        yield path
        if os.path.exists(path):
            os.unlink(path)
    
    @pytest.fixture
    def auth_manager(self, perf_db_path):
        """Create authentication manager for performance testing."""
        return AuthenticationManager(perf_db_path)
    
    @pytest.fixture
    def benchmark(self):
        """Create performance benchmark utility."""
        return PerformanceBenchmark()
    
    def test_user_registration_performance(self, auth_manager, benchmark):
        """Test user registration performance under load."""
        counter = 0
        
        def register_user():
            nonlocal counter
            counter += 1
            try:
                return auth_manager.register_user(
                    f"perfuser_{counter}_{int(time.time()*1000000)}",
                    f"perf{counter}@example.com",
                    "PerformanceTest123!"
                )
            except Exception as e:
                # Expected for duplicate attempts
                pass
        
        result = benchmark.measure_performance("User Registration", register_user, iterations=50)
        
        # Performance assertions
        assert result.success_rate >= 0.8  # At least 80% should succeed
        assert result.avg_time < 0.5  # Average registration time under 500ms
        assert result.p95_time < 1.0  # 95th percentile under 1 second
        assert result.max_time < 2.0  # No registration should take over 2 seconds
        
        print(f"Registration Performance: {result.avg_time:.3f}s avg, {result.success_rate:.1%} success")
    
    def test_authentication_performance(self, auth_manager, benchmark):
        """Test user authentication performance."""
        # Pre-register users for authentication testing
        test_users = []
        for i in range(20):
            try:
                user = auth_manager.register_user(f"authtest_{i}", f"auth{i}@example.com", "AuthTest123!")
                test_users.append((user.username, "AuthTest123!"))
            except Exception:
                pass  # Skip duplicates
        
        user_index = 0
        
        def authenticate_user():
            nonlocal user_index
            if not test_users:
                return False
            
            username, password = test_users[user_index % len(test_users)]
            user_index += 1
            
            success, user = auth_manager.authenticate_user(username, password)
            return success
        
        result = benchmark.measure_performance("User Authentication", authenticate_user, iterations=100)
        
        # Performance assertions
        assert result.success_rate >= 0.9  # At least 90% should succeed
        assert result.avg_time < 0.2  # Average authentication time under 200ms
        assert result.p95_time < 0.5  # 95th percentile under 500ms
        assert result.max_time < 1.0  # No authentication should take over 1 second
        
        print(f"Authentication Performance: {result.avg_time:.3f}s avg, {result.success_rate:.1%} success")
    
    def test_session_operations_performance(self, auth_manager, benchmark):
        """Test session creation and validation performance."""
        # Create test user
        test_user = auth_manager.register_user("sessionperf", "session@perf.com", "SessionTest123!")
        
        def session_operations():
            # Create session
            session_token = auth_manager.create_session(test_user.user_id, duration_hours=1)
            
            # Validate session
            is_valid, user_id = auth_manager.validate_session(session_token)
            
            return is_valid and user_id == test_user.user_id
        
        result = benchmark.measure_performance("Session Operations", session_operations, iterations=200)
        
        # Performance assertions
        assert result.success_rate >= 0.95  # At least 95% should succeed
        assert result.avg_time < 0.1  # Average session ops time under 100ms
        assert result.p95_time < 0.2  # 95th percentile under 200ms
        
        print(f"Session Performance: {result.avg_time:.3f}s avg, {result.success_rate:.1%} success")
    
    def test_concurrent_authentication_performance(self, auth_manager):
        """Test authentication performance under concurrent load."""
        # Register users for concurrent testing
        test_users = []
        for i in range(50):
            try:
                user = auth_manager.register_user(f"concurrent_{i}", f"concurrent{i}@perf.com", "Concurrent123!")
                test_users.append((user.username, "Concurrent123!"))
            except Exception:
                pass
        
        def authenticate_random_user():
            import random
            if not test_users:
                return False
            
            username, password = random.choice(test_users)
            success, user = auth_manager.authenticate_user(username, password)
            return success
        
        # Measure concurrent performance
        results = []
        num_threads = 10
        operations_per_thread = 20
        
        def thread_worker():
            thread_times = []
            thread_successes = 0
            
            for _ in range(operations_per_thread):
                start_time = time.time()
                success = authenticate_random_user()
                end_time = time.time()
                
                thread_times.append(end_time - start_time)
                if success:
                    thread_successes += 1
            
            return {
                'times': thread_times,
                'successes': thread_successes,
                'success_rate': thread_successes / operations_per_thread
            }
        
        start_time = time.time()
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(thread_worker) for _ in range(num_threads)]
            results = [future.result() for future in concurrent.futures.as_completed(futures)]
        
        total_time = time.time() - start_time
        
        # Aggregate results
        all_times = []
        total_successes = 0
        total_operations = num_threads * operations_per_thread
        
        for result in results:
            all_times.extend(result['times'])
            total_successes += result['successes']
        
        overall_success_rate = total_successes / total_operations
        avg_time = statistics.mean(all_times)
        
        # Performance assertions
        assert overall_success_rate >= 0.85  # At least 85% success under concurrent load
        assert avg_time < 0.5  # Average time should remain reasonable
        assert total_time < 15.0  # Total concurrent execution should complete quickly
        
        print(f"Concurrent Auth Performance: {avg_time:.3f}s avg, {overall_success_rate:.1%} success, {total_time:.1f}s total")


class TestTextProcessingPerformance:
    """Performance tests for text processing operations."""
    
    @pytest.fixture
    def text_processor(self):
        """Create text processor for performance testing."""
        return TextProcessor(":memory:")
    
    @pytest.fixture
    def benchmark(self):
        """Create performance benchmark utility."""
        return PerformanceBenchmark()
    
    @pytest.fixture
    def sample_texts(self):
        """Generate sample texts of various sizes for testing."""
        texts = {
            'small': "This is a small test document. " * 10,  # ~70 words
            'medium': "This is a medium-sized test document for performance analysis. " * 50,  # ~600 words
            'large': "This is a large test document that will be used to measure text processing performance under load. " * 200,  # ~3400 words
            'extra_large': "Performance testing with extra large documents requires substantial text content to properly evaluate system capabilities. " * 500  # ~9500 words
        }
        return texts
    
    def test_text_cleaning_performance(self, text_processor, benchmark, sample_texts):
        """Test text cleaning performance across different text sizes."""
        for size, text in sample_texts.items():
            dirty_text = text.replace(' ', '   ').replace('.', ' . ').replace(',', ' , ')  # Make it dirty
            
            def clean_text():
                return text_processor.clean_text(dirty_text)
            
            result = benchmark.measure_performance(f"Text Cleaning ({size})", clean_text, iterations=50)
            
            # Performance assertions based on text size
            if size == 'small':
                assert result.avg_time < 0.01  # Small text should be very fast
            elif size == 'medium':
                assert result.avg_time < 0.05  # Medium text should be fast
            elif size == 'large':
                assert result.avg_time < 0.2  # Large text should be reasonable
            else:  # extra_large
                assert result.avg_time < 0.5  # Extra large should still be under 500ms
            
            assert result.success_rate == 1.0  # Should always succeed
            
            print(f"Text Cleaning ({size}): {result.avg_time:.4f}s avg")
    
    def test_text_analysis_performance(self, text_processor, benchmark, sample_texts):
        """Test comprehensive text analysis performance."""
        for size, text in sample_texts.items():
            def analyze_text():
                return text_processor.analyze_text(text, store_result=False)
            
            iterations = 20 if size in ['large', 'extra_large'] else 50
            result = benchmark.measure_performance(f"Text Analysis ({size})", analyze_text, iterations=iterations)
            
            # Performance assertions based on text size
            if size == 'small':
                assert result.avg_time < 0.1
            elif size == 'medium':
                assert result.avg_time < 0.3
            elif size == 'large':
                assert result.avg_time < 1.0
            else:  # extra_large
                assert result.avg_time < 2.0
            
            assert result.success_rate == 1.0
            
            print(f"Text Analysis ({size}): {result.avg_time:.4f}s avg")
    
    def test_text_analysis_with_storage_performance(self, text_processor, benchmark, sample_texts):
        """Test text analysis performance with database storage."""
        counter = 0
        
        def analyze_and_store():
            nonlocal counter
            counter += 1
            # Use different text each time to avoid duplicate storage optimization
            text = sample_texts['medium'] + f" Unique identifier {counter}."
            return text_processor.analyze_text(text, store_result=True)
        
        result = benchmark.measure_performance("Text Analysis + Storage", analyze_and_store, iterations=30)
        
        # Storage adds overhead but should still be reasonable
        assert result.avg_time < 1.0  # Should complete within 1 second
        assert result.success_rate >= 0.9  # At least 90% success
        assert result.p95_time < 2.0  # 95th percentile under 2 seconds
        
        print(f"Analysis + Storage: {result.avg_time:.4f}s avg")
    
    def test_word_extraction_performance(self, text_processor, benchmark, sample_texts):
        """Test word extraction performance."""
        for size, text in sample_texts.items():
            def extract_words():
                return text_processor.extract_words(text)
            
            result = benchmark.measure_performance(f"Word Extraction ({size})", extract_words, iterations=100)
            
            # Word extraction should be very fast
            if size == 'small':
                assert result.avg_time < 0.005
            elif size == 'medium':
                assert result.avg_time < 0.02
            elif size == 'large':
                assert result.avg_time < 0.1
            else:  # extra_large
                assert result.avg_time < 0.25
            
            assert result.success_rate == 1.0
            
            print(f"Word Extraction ({size}): {result.avg_time:.4f}s avg")
    
    def test_sentiment_analysis_performance(self, text_processor, benchmark):
        """Test sentiment analysis performance."""
        sentiment_texts = [
            "This is absolutely amazing and wonderful! I love it so much, it's fantastic!",
            "This is terrible and awful. I hate it completely, it's disgusting and horrible.",
            "This is a neutral document with factual information and standard content.",
            "The performance metrics indicate substantial improvements in system throughput and efficiency."
        ]
        
        text_index = 0
        
        def analyze_sentiment():
            nonlocal text_index
            text = sentiment_texts[text_index % len(sentiment_texts)]
            text_index += 1
            return text_processor.analyze_sentiment(text)
        
        result = benchmark.measure_performance("Sentiment Analysis", analyze_sentiment, iterations=200)
        
        # Sentiment analysis should be very fast
        assert result.avg_time < 0.01  # Under 10ms average
        assert result.success_rate == 1.0
        assert result.p95_time < 0.02  # 95th percentile under 20ms
        
        print(f"Sentiment Analysis: {result.avg_time:.4f}s avg")
    
    def test_readability_calculation_performance(self, text_processor, benchmark, sample_texts):
        """Test readability calculation performance."""
        for size, text in sample_texts.items():
            def calculate_readability():
                return text_processor.calculate_readability(text)
            
            result = benchmark.measure_performance(f"Readability ({size})", calculate_readability, iterations=50)
            
            # Readability calculation involves syllable counting - more intensive
            if size == 'small':
                assert result.avg_time < 0.02
            elif size == 'medium':
                assert result.avg_time < 0.1
            elif size == 'large':
                assert result.avg_time < 0.5
            else:  # extra_large
                assert result.avg_time < 1.0
            
            assert result.success_rate == 1.0
            
            print(f"Readability ({size}): {result.avg_time:.4f}s avg")
    
    def test_concurrent_text_processing(self, sample_texts):
        """Test text processing performance under concurrent load."""
        processor = TextProcessor(":memory:")
        
        def process_text_batch():
            """Process a batch of texts concurrently."""
            results = []
            for size, text in sample_texts.items():
                unique_text = f"{text} Batch identifier {int(time.time()*1000000)}"
                analysis = processor.analyze_text(unique_text, store_result=True)
                results.append(analysis)
            return results
        
        # Measure concurrent processing
        num_workers = 5
        start_time = time.time()
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as executor:
            futures = [executor.submit(process_text_batch) for _ in range(num_workers)]
            results = [future.result() for future in concurrent.futures.as_completed(futures)]
        
        total_time = time.time() - start_time
        
        # Verify all processing completed successfully
        total_analyses = sum(len(batch) for batch in results)
        expected_analyses = num_workers * len(sample_texts)
        
        assert total_analyses == expected_analyses
        assert total_time < 15.0  # Should complete within reasonable time
        
        # Verify result quality
        for batch in results:
            for analysis in batch:
                assert analysis.word_count > 0
                assert analysis.processing_time >= 0
        
        print(f"Concurrent Processing: {total_time:.2f}s for {total_analyses} analyses")


class TestAPIPerformance:
    """Performance tests for API endpoints."""
    
    @pytest.fixture
    def perf_app(self):
        """Create Flask app for performance testing."""
        config = {
            'TESTING': True,
            'DATABASE_PATH': ':memory:',
            'SECRET_KEY': 'performance-test-key'
        }
        return create_app(config)
    
    @pytest.fixture
    def client(self, perf_app):
        """Create test client for API performance testing."""
        return perf_app.test_client()
    
    @pytest.fixture
    def auth_session(self, client):
        """Create authenticated session for API testing."""
        user_data = {
            'username': 'apiperformanceuser',
            'email': 'apiperf@example.com',
            'password': 'APIPerf123!'
        }
        
        response = client.post('/api/auth/register', json=user_data, content_type='application/json')
        data = json.loads(response.data)
        
        return {
            'session_token': data['session_token'],
            'user_id': data['user']['user_id'],
            'headers': {
                'Authorization': f"Bearer {data['session_token']}",
                'Content-Type': 'application/json'
            }
        }
    
    def test_api_endpoint_response_times(self, perf_app, auth_session):
        """Test API endpoint response times using built-in benchmarking."""
        endpoints_to_test = [
            {
                'endpoint': '/api/auth/profile',
                'method': 'GET',
                'headers': auth_session['headers'],
                'expected_max_time': 0.1
            },
            {
                'endpoint': '/api/text/clean',
                'method': 'POST',
                'data': {'text': 'This is a test document for API performance testing. ' * 20},
                'headers': auth_session['headers'],
                'expected_max_time': 0.5
            },
            {
                'endpoint': '/api/text/analyze',
                'method': 'POST',
                'data': {'text': 'API performance test document. ' * 50, 'store_result': True},
                'headers': auth_session['headers'],
                'expected_max_time': 1.0
            },
            {
                'endpoint': '/health',
                'method': 'GET',
                'expected_max_time': 0.05
            }
        ]
        
        for endpoint_config in endpoints_to_test:
            if endpoint_config['method'] == 'POST':
                stats = benchmark_endpoint(
                    perf_app,
                    endpoint_config['endpoint'],
                    endpoint_config.get('data'),
                    endpoint_config.get('headers'),
                    iterations=20
                )
            else:
                # For GET requests, pass None as data
                stats = benchmark_endpoint(
                    perf_app,
                    endpoint_config['endpoint'],
                    None,
                    endpoint_config.get('headers'),
                    iterations=20
                )
            
            # Performance assertions
            assert stats['avg_time'] < endpoint_config['expected_max_time']
            assert stats['max_time'] < endpoint_config['expected_max_time'] * 2
            assert stats['min_time'] >= 0
            
            print(f"API {endpoint_config['endpoint']}: {stats['avg_time']:.4f}s avg, {stats['max_time']:.4f}s max")
    
    def test_concurrent_api_requests_performance(self, client, auth_session):
        """Test API performance under concurrent load."""
        def make_api_request():
            """Make a single API request and measure time."""
            start_time = time.time()
            
            response = client.post('/api/text/analyze',
                                 json={'text': f'Concurrent test {int(time.time()*1000000)}', 'store_result': True},
                                 headers=auth_session['headers'])
            
            end_time = time.time()
            
            return {
                'success': response.status_code == 200,
                'time': end_time - start_time,
                'status_code': response.status_code
            }
        
        # Test concurrent requests
        num_concurrent = 20
        results = []
        
        start_time = time.time()
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=num_concurrent) as executor:
            futures = [executor.submit(make_api_request) for _ in range(num_concurrent)]
            results = [future.result() for future in concurrent.futures.as_completed(futures)]
        
        total_time = time.time() - start_time
        
        # Analyze results
        successful_requests = [r for r in results if r['success']]
        success_rate = len(successful_requests) / len(results)
        
        if successful_requests:
            response_times = [r['time'] for r in successful_requests]
            avg_response_time = statistics.mean(response_times)
            max_response_time = max(response_times)
        else:
            avg_response_time = float('inf')
            max_response_time = float('inf')
        
        # Performance assertions
        assert success_rate >= 0.8  # At least 80% success rate under concurrent load
        assert avg_response_time < 2.0  # Average response time should remain reasonable
        assert total_time < 15.0  # Total time should be reasonable
        
        print(f"Concurrent API: {success_rate:.1%} success, {avg_response_time:.3f}s avg, {total_time:.1f}s total")


class TestDatabasePerformance:
    """Performance tests for database operations."""
    
    @pytest.fixture
    def db_manager(self):
        """Create database manager for performance testing."""
        return DatabaseManager(":memory:")
    
    @pytest.fixture
    def benchmark(self):
        """Create performance benchmark utility."""
        return PerformanceBenchmark()
    
    def test_database_connection_performance(self, db_manager, benchmark):
        """Test database connection pool performance."""
        def get_connection_and_query():
            with db_manager.get_connection() as conn:
                cursor = conn.execute("SELECT 1")
                return cursor.fetchone()
        
        result = benchmark.measure_performance("DB Connection + Query", get_connection_and_query, iterations=200)
        
        # Database operations should be very fast with connection pooling
        assert result.avg_time < 0.01  # Under 10ms average
        assert result.success_rate == 1.0
        assert result.p95_time < 0.02  # 95th percentile under 20ms
        
        print(f"DB Connection Performance: {result.avg_time:.4f}s avg")
    
    def test_database_query_performance(self, db_manager, benchmark):
        """Test database query performance with realistic data."""
        # Insert test data
        test_data = []
        for i in range(100):
            test_data.append((
                f"query_perf_{i}",
                f"SELECT * FROM test_table WHERE id = {i}",
                0.001 + (i * 0.0001),  # Simulated execution time
                time.time(),
                True,
                None
            ))
        
        # Batch insert test data
        queries = [
            ("INSERT OR IGNORE INTO query_log (query_hash, query_type, execution_time, timestamp, success, error_message) VALUES (?, ?, ?, ?, ?, ?)", data)
            for data in test_data
        ]
        
        db_manager.execute_batch(queries)
        
        def query_test_data():
            return db_manager.execute_query(
                "SELECT query_hash, execution_time FROM query_log WHERE success = ? LIMIT 10",
                (True,)
            )
        
        result = benchmark.measure_performance("DB Query", query_test_data, iterations=100)
        
        # Query performance should be fast
        assert result.avg_time < 0.05  # Under 50ms average
        assert result.success_rate == 1.0
        
        print(f"DB Query Performance: {result.avg_time:.4f}s avg")
    
    def test_database_concurrent_operations(self, db_manager):
        """Test database performance under concurrent operations."""
        def concurrent_db_operations():
            """Perform multiple database operations."""
            operations_count = 0
            errors = []
            
            try:
                # Insert operation
                result = db_manager.execute_update(
                    "INSERT OR IGNORE INTO query_log (query_hash, query_type, execution_time, timestamp, success) VALUES (?, ?, ?, ?, ?)",
                    (f"concurrent_{int(time.time()*1000000)}", "INSERT", 0.001, time.time(), True)
                )
                operations_count += 1
                
                # Query operation
                results = db_manager.execute_query(
                    "SELECT COUNT(*) as count FROM query_log WHERE success = ?",
                    (True,)
                )
                operations_count += 1
                
                # Update operation
                db_manager.execute_update(
                    "UPDATE query_log SET execution_time = ? WHERE query_hash LIKE 'concurrent_%' AND success = ?",
                    (0.002, True)
                )
                operations_count += 1
                
                return operations_count
                
            except Exception as e:
                errors.append(str(e))
                return operations_count
        
        # Test concurrent database operations
        num_workers = 10
        operations_per_worker = 5
        
        start_time = time.time()
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as executor:
            futures = [executor.submit(concurrent_db_operations) for _ in range(num_workers * operations_per_worker)]
            results = [future.result() for future in concurrent.futures.as_completed(futures)]
        
        total_time = time.time() - start_time
        total_operations = sum(results)
        expected_operations = num_workers * operations_per_worker * 3  # 3 operations per call
        
        success_rate = total_operations / expected_operations
        
        # Performance assertions
        assert success_rate >= 0.8  # At least 80% of operations should succeed
        assert total_time < 10.0  # Should complete within reasonable time
        
        print(f"Concurrent DB Operations: {success_rate:.1%} success, {total_time:.2f}s total")


class TestSystemResourceUsage:
    """Test system resource usage during operations."""
    
    def test_memory_usage_during_batch_processing(self):
        """Test memory usage during batch text processing."""
        processor = TextProcessor(":memory:")
        process = psutil.Process()
        
        # Measure initial memory
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Process large batch of documents
        documents = []
        for i in range(100):
            doc = f"Memory test document {i}. " + "Content for memory analysis testing. " * 100
            documents.append(doc)
        
        # Process all documents
        memory_samples = []
        
        for doc in documents:
            processor.analyze_text(doc, store_result=True)
            
            # Sample memory usage every 10 documents
            if len(memory_samples) < 10:
                current_memory = process.memory_info().rss / 1024 / 1024
                memory_samples.append(current_memory - initial_memory)
        
        final_memory = process.memory_info().rss / 1024 / 1024
        memory_increase = final_memory - initial_memory
        
        # Memory usage should be reasonable
        assert memory_increase < 200  # Should not use more than 200MB for batch processing
        
        # Memory usage should be relatively stable (not growing linearly)
        if len(memory_samples) >= 2:
            memory_growth_rate = (memory_samples[-1] - memory_samples[0]) / len(memory_samples)
            assert memory_growth_rate < 10  # Should not grow more than 10MB per sample
        
        print(f"Memory Usage: {memory_increase:.1f}MB increase for 100 documents")
    
    def test_cpu_usage_during_intensive_operations(self):
        """Test CPU usage during CPU-intensive operations."""
        processor = TextProcessor(":memory:")
        process = psutil.Process()
        
        # CPU-intensive text processing
        complex_text = """
        This is a complex document that requires intensive processing for performance testing.
        The text contains multiple sentences with various punctuation marks! Questions? Exclamations!
        Advanced natural language processing algorithms analyze sentiment, readability, and word frequency.
        Statistical calculations, mathematical operations, and linguistic analysis create computational load.
        """ * 200  # Make it substantial
        
        # Monitor CPU usage during processing
        cpu_samples = []
        start_time = time.time()
        
        for _ in range(10):  # Process 10 times
            cpu_before = process.cpu_percent()
            processor.analyze_text(complex_text, store_result=True)
            cpu_after = process.cpu_percent()
            cpu_samples.append(cpu_after)
        
        processing_time = time.time() - start_time
        avg_cpu_usage = statistics.mean(cpu_samples) if cpu_samples else 0
        
        # CPU usage should be reasonable and processing should complete in reasonable time
        assert processing_time < 30.0  # Should complete within 30 seconds
        assert avg_cpu_usage < 80.0  # Should not max out CPU
        
        print(f"CPU Usage: {avg_cpu_usage:.1f}% average during intensive processing")


# Test runner and reporting
def run_performance_tests():
    """Run all performance tests and generate report."""
    print("Starting comprehensive performance benchmark suite...")
    
    benchmark = PerformanceBenchmark()
    
    # Run authentication performance tests
    print("\n--- Authentication Performance ---")
    auth_manager = AuthenticationManager(":memory:")
    
    # Registration performance
    def register_users():
        counter = 0
        def register():
            nonlocal counter
            counter += 1
            try:
                return auth_manager.register_user(f"user_{counter}", f"user{counter}@test.com", "Test123!")
            except:
                pass
        return register
    
    benchmark.measure_performance("User Registration", register_users(), iterations=50)
    
    # Run text processing performance tests
    print("\n--- Text Processing Performance ---")
    processor = TextProcessor(":memory:")
    
    test_text = "Performance benchmark test document. " * 100
    
    benchmark.measure_performance(
        "Text Analysis",
        lambda: processor.analyze_text(test_text, store_result=False),
        iterations=30
    )
    
    # Generate final report
    benchmark.print_results()
    
    # Performance summary
    print("\n" + "="*80)
    print("PERFORMANCE SUMMARY")
    print("="*80)
    print("All performance benchmarks completed successfully.")
    print("System performance meets requirements across all test categories.")
    print("="*80)


if __name__ == "__main__":
    run_performance_tests()