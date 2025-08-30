"""
Unit tests for text processing module using London School TDD methodology.
Tests real text processing behavior, database operations, and actual calculations.
"""

import pytest
import sqlite3
import tempfile
import os
import time
import json
import statistics
from typing import List, Dict

from src.utils.text_processing import (
    TextProcessor,
    TextAnalysis
)
from src.core.text_analyzer import TextAnalyzer, AdvancedTextAnalysis
from src.core.nlp_processor import NLPProcessor
from src.utils.text_utils import TextUtilsManager, FastTextAnalyzer


class TestTextProcessor:
    """
    London School TDD tests for TextProcessor.
    Tests real text processing calculations and database storage behavior.
    """
    
    @pytest.fixture
    def temp_db_path(self):
        """Create temporary database for testing."""
        fd, path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        yield path
        if os.path.exists(path):
            os.unlink(path)
    
    @pytest.fixture
    def text_processor(self, temp_db_path):
        """Create TextProcessor with real database."""
        return TextProcessor(temp_db_path)
    
    @pytest.fixture
    def memory_processor(self):
        """Create TextProcessor with in-memory database."""
        return TextProcessor(":memory:")
    
    @pytest.fixture
    def sample_text(self):
        """Sample text for testing."""
        return """
        This is a sample text for testing purposes. It contains multiple sentences!
        The text has various punctuation marks, and different word lengths. 
        
        This text will be used to test readability, sentiment analysis, and word frequency calculations.
        Some words appear multiple times: text, test, testing, and sample.
        """
    
    @pytest.fixture
    def complex_text(self):
        """Complex text with various features for comprehensive testing."""
        return """
        The quick brown fox jumps over the lazy dog. This pangram contains every letter of the alphabet.
        
        Sentiment analysis should detect positive words like: excellent, amazing, wonderful, and fantastic.
        It should also identify negative words such as: terrible, awful, horrible, and disgusting.
        
        Readability testing involves calculating syllables, sentences, and word complexity.
        Multi-syllabic words like: beautiful, extraordinarily, and comprehensively increase complexity.
        
        Statistical analysis examines word frequency, average lengths, and distribution patterns.
        Numbers and special characters !@#$%^&*() should be handled appropriately.
        """
    
    def test_database_initialization_creates_proper_schema(self, text_processor, temp_db_path):
        """Test database initialization creates correct tables and schema."""
        with sqlite3.connect(temp_db_path) as conn:
            # Check text_documents table
            cursor = conn.execute("PRAGMA table_info(text_documents)")
            doc_columns = {row[1]: row[2] for row in cursor.fetchall()}
            
            expected_doc_columns = {
                'doc_id': 'TEXT',
                'content': 'TEXT',
                'content_hash': 'TEXT',
                'word_count': 'INTEGER',
                'character_count': 'INTEGER',
                'processed_at': 'REAL',
                'analysis_data': 'TEXT'
            }
            
            for col, col_type in expected_doc_columns.items():
                assert col in doc_columns
                assert doc_columns[col] == col_type
            
            # Check word_frequency table
            cursor = conn.execute("PRAGMA table_info(word_frequency)")
            freq_columns = {row[1]: row[2] for row in cursor.fetchall()}
            
            assert 'doc_id' in freq_columns
            assert 'word' in freq_columns
            assert 'frequency' in freq_columns
            assert 'position_avg' in freq_columns
    
    def test_clean_text_removes_extra_whitespace_and_normalizes(self, text_processor):
        """Test text cleaning functionality with real normalization."""
        dirty_text = "  This   has    extra     whitespace.   And  weird   punctuation  !  "
        
        cleaned = text_processor.clean_text(dirty_text)
        
        # Verify whitespace normalization
        assert "   " not in cleaned
        assert "  " not in cleaned
        assert cleaned.startswith("This")
        assert cleaned.endswith("!")
        
        # Verify punctuation normalization
        assert ". " in cleaned
        assert "! " in cleaned
        
        # Test edge cases
        assert text_processor.clean_text("") == ""
        assert text_processor.clean_text("   ") == ""
        
        # Test with non-string input
        with pytest.raises(ValueError, match="Input must be a string"):
            text_processor.clean_text(123)
    
    def test_extract_words_tokenizes_correctly(self, text_processor):
        """Test word extraction with proper tokenization."""
        text = "Hello, World! This is a test. Numbers123 and special-chars should be handled."
        
        words = text_processor.extract_words(text)
        
        # Verify word extraction
        assert "hello" in words  # Should be lowercase
        assert "world" in words
        assert "test" in words
        assert "special" in words
        assert "chars" in words
        
        # Verify filtering (single chars and numbers should be excluded)
        assert "a" not in words  # Single character
        assert "123" not in words  # Pure numbers
        assert "numbers123" not in words  # Mixed alphanumeric
        
        # Verify all words are lowercase and alphabetic
        for word in words:
            assert word.islower()
            assert word.isalpha()
            assert len(word) > 1
    
    def test_extract_sentences_splits_properly(self, text_processor):
        """Test sentence extraction with various punctuation."""
        text = "First sentence. Second sentence! Third sentence? Fourth sentence."
        
        sentences = text_processor.extract_sentences(text)
        
        assert len(sentences) == 4
        assert "First sentence" in sentences[0]
        assert "Second sentence" in sentences[1]
        assert "Third sentence" in sentences[2]
        assert "Fourth sentence" in sentences[3]
        
        # Test with empty text
        assert text_processor.extract_sentences("") == []
        
        # Test with no punctuation
        no_punct = text_processor.extract_sentences("No punctuation here")
        assert len(no_punct) == 1
        assert "No punctuation here" in no_punct[0]
    
    def test_extract_paragraphs_handles_line_breaks(self, text_processor):
        """Test paragraph extraction with various line break patterns."""
        text = """First paragraph line one.
        First paragraph line two.
        
        Second paragraph after double line break.
        
        
        Third paragraph after triple line break."""
        
        paragraphs = text_processor.extract_paragraphs(text)
        
        assert len(paragraphs) == 3
        assert "First paragraph" in paragraphs[0]
        assert "Second paragraph" in paragraphs[1]
        assert "Third paragraph" in paragraphs[2]
    
    def test_syllable_counting_accuracy(self, text_processor):
        """Test syllable counting with known word examples."""
        test_cases = [
            ("cat", 1),
            ("hello", 2),
            ("beautiful", 3),
            ("extraordinary", 5),
            ("the", 1),
            ("apple", 2),
            ("orange", 2),
            ("banana", 3)
        ]
        
        for word, expected_syllables in test_cases:
            actual_syllables = text_processor._count_syllables(word)
            assert actual_syllables == expected_syllables, f"Word '{word}': expected {expected_syllables}, got {actual_syllables}"
        
        # Test edge cases
        assert text_processor._count_syllables("") == 1  # Minimum syllables
        assert text_processor._count_syllables("a") == 1
        assert text_processor._count_syllables("eye") == 1  # Silent e handling
    
    def test_readability_calculation_flesch_score(self, text_processor):
        """Test readability calculation using Flesch Reading Ease formula."""
        # Simple text should have high readability
        simple_text = "The cat sits. The dog runs. They play."
        simple_score = text_processor.calculate_readability(simple_text)
        
        # Complex text should have lower readability
        complex_text = "Extraordinarily sophisticated individuals comprehensively analyze multifaceted situations. Comprehensive understanding necessitates extensive vocabulary."
        complex_score = text_processor.calculate_readability(complex_text)
        
        # Simple text should score higher (easier to read)
        assert simple_score > complex_score
        
        # Scores should be within valid range (0-100)
        assert 0 <= simple_score <= 100
        assert 0 <= complex_score <= 100
        
        # Test edge cases
        assert text_processor.calculate_readability("") == 0.0
        assert text_processor.calculate_readability("Word.") > 0
    
    def test_sentiment_analysis_detects_positive_negative(self, text_processor):
        """Test sentiment analysis with positive and negative text."""
        positive_text = "This is amazing! I love it. Excellent work, fantastic results, wonderful experience."
        negative_text = "This is terrible! I hate it. Awful work, horrible results, disgusting experience."
        neutral_text = "This is a document. It contains information. The data is presented."
        
        positive_score = text_processor.analyze_sentiment(positive_text)
        negative_score = text_processor.analyze_sentiment(negative_text)
        neutral_score = text_processor.analyze_sentiment(neutral_text)
        
        # Positive text should have positive score
        assert positive_score > 0
        
        # Negative text should have negative score
        assert negative_score < 0
        
        # Neutral text should have neutral score (close to 0)
        assert abs(neutral_score) < abs(positive_score)
        assert abs(neutral_score) < abs(negative_score)
        
        # Test edge cases
        assert text_processor.analyze_sentiment("") == 0.0
        assert text_processor.analyze_sentiment("the a an") == 0.0  # Only stop words
    
    def test_analyze_text_comprehensive_analysis(self, text_processor, sample_text):
        """Test comprehensive text analysis with all metrics."""
        analysis = text_processor.analyze_text(sample_text, store_result=False)
        
        # Verify analysis object type
        assert isinstance(analysis, TextAnalysis)
        
        # Verify all metrics are calculated
        assert analysis.word_count > 0
        assert analysis.character_count > 0
        assert analysis.sentence_count > 0
        assert analysis.paragraph_count > 0
        assert analysis.avg_word_length > 0
        assert 0 <= analysis.readability_score <= 100
        assert isinstance(analysis.common_words, dict)
        assert analysis.processing_time >= 0
        
        # Verify word count accuracy
        expected_words = text_processor.extract_words(sample_text)
        assert analysis.word_count == len(expected_words)
        
        # Verify character count
        assert analysis.character_count == len(sample_text)
        
        # Verify sentence count
        expected_sentences = text_processor.extract_sentences(sample_text)
        assert analysis.sentence_count == len(expected_sentences)
        
        # Verify paragraph count
        expected_paragraphs = text_processor.extract_paragraphs(sample_text)
        assert analysis.paragraph_count == len(expected_paragraphs)
        
        # Verify average word length calculation
        words = text_processor.extract_words(sample_text)
        expected_avg_length = statistics.mean(len(word) for word in words) if words else 0.0
        assert abs(analysis.avg_word_length - expected_avg_length) < 0.01
    
    def test_analyze_text_common_words_accuracy(self, text_processor, complex_text):
        """Test common words identification and frequency counting."""
        analysis = text_processor.analyze_text(complex_text, store_result=False)
        
        # Verify common_words is a dictionary with word counts
        assert isinstance(analysis.common_words, dict)
        assert len(analysis.common_words) <= 10  # Should return top 10
        
        # Verify words are filtered (no stop words)
        for word in analysis.common_words:
            assert word not in text_processor.stop_words
        
        # Verify counts are accurate
        all_words = text_processor.extract_words(complex_text)
        filtered_words = [word for word in all_words if word not in text_processor.stop_words]
        
        for word, count in analysis.common_words.items():
            expected_count = filtered_words.count(word)
            assert count == expected_count
    
    def test_analyze_text_with_database_storage(self, text_processor, temp_db_path, sample_text):
        """Test text analysis with database storage enabled."""
        analysis = text_processor.analyze_text(sample_text, store_result=True)
        
        # Verify analysis was performed
        assert isinstance(analysis, TextAnalysis)
        
        # Verify database storage
        with sqlite3.connect(temp_db_path) as conn:
            # Check document storage
            cursor = conn.execute("SELECT COUNT(*) FROM text_documents")
            doc_count = cursor.fetchone()[0]
            assert doc_count == 1
            
            # Verify document data
            cursor = conn.execute("""
                SELECT content, word_count, character_count, analysis_data 
                FROM text_documents LIMIT 1
            """)
            row = cursor.fetchone()
            
            assert row[0] == sample_text
            assert row[1] == analysis.word_count
            assert row[2] == analysis.character_count
            
            # Verify analysis data is valid JSON
            analysis_data = json.loads(row[3])
            assert 'readability_score' in analysis_data
            assert 'sentiment_score' in analysis_data
            assert 'common_words' in analysis_data
            
            # Check word frequency storage
            cursor = conn.execute("SELECT COUNT(*) FROM word_frequency")
            word_count = cursor.fetchone()[0]
            assert word_count > 0  # Should have stored word frequencies
    
    def test_analyze_text_input_validation(self, text_processor):
        """Test text analysis input validation."""
        # Test empty string
        with pytest.raises(ValueError, match="Text must be a non-empty string"):
            text_processor.analyze_text("")
        
        # Test None input
        with pytest.raises(ValueError, match="Text must be a non-empty string"):
            text_processor.analyze_text(None)
        
        # Test non-string input
        with pytest.raises(ValueError, match="Text must be a non-empty string"):
            text_processor.analyze_text(123)
    
    def test_store_and_retrieve_document_analysis(self, text_processor, sample_text):
        """Test storing and retrieving document analysis."""
        # Analyze and store text
        analysis = text_processor.analyze_text(sample_text, store_result=True)
        
        # Calculate expected doc_id
        import hashlib
        expected_doc_id = hashlib.sha256(sample_text.encode()).hexdigest()[:16]
        
        # Retrieve stored analysis
        stored_doc = text_processor.get_document_analysis(expected_doc_id)
        
        assert stored_doc is not None
        assert stored_doc['doc_id'] == expected_doc_id
        assert stored_doc['content'] == sample_text
        assert 'processed_at' in stored_doc
        assert 'analysis' in stored_doc
        
        # Verify analysis data matches
        stored_analysis = stored_doc['analysis']
        assert stored_analysis['readability_score'] == analysis.readability_score
        assert stored_analysis['sentiment_score'] == analysis.sentiment_score
        assert stored_analysis['common_words'] == analysis.common_words
    
    def test_get_document_analysis_nonexistent(self, text_processor):
        """Test retrieving non-existent document returns None."""
        result = text_processor.get_document_analysis("nonexistent_doc_id")
        assert result is None
    
    def test_search_documents_by_word(self, text_processor):
        """Test document search functionality."""
        # Store multiple documents
        doc1 = "The quick brown fox jumps over the lazy dog"
        doc2 = "A brown bear walks through the forest"
        doc3 = "The lazy cat sleeps all day"
        
        text_processor.analyze_text(doc1, store_result=True)
        text_processor.analyze_text(doc2, store_result=True)
        text_processor.analyze_text(doc3, store_result=True)
        
        # Search for word "brown"
        results = text_processor.search_documents_by_word("brown")
        
        # Should find 2 documents containing "brown"
        assert len(results) == 2
        
        # Verify results contain expected data
        for result in results:
            assert 'doc_id' in result
            assert 'content' in result
            assert 'frequency' in result
            assert 'position_avg' in result
            assert "brown" in result['content'].lower()
        
        # Search should be case insensitive
        results_upper = text_processor.search_documents_by_word("BROWN")
        assert len(results_upper) == 2
        
        # Search for non-existent word
        no_results = text_processor.search_documents_by_word("elephant")
        assert len(no_results) == 0
    
    def test_word_frequency_position_tracking(self, text_processor):
        """Test word frequency and position tracking accuracy."""
        text = "test word test another test word final test"
        
        # Analyze text and store
        text_processor.analyze_text(text, store_result=True)
        
        # Check word frequency database entries
        with sqlite3.connect(text_processor.db_path) as conn:
            # Check "test" frequency and position
            cursor = conn.execute("""
                SELECT frequency, position_avg FROM word_frequency 
                WHERE word = 'test'
            """)
            row = cursor.fetchone()
            
            assert row is not None
            assert row[0] == 4  # "test" appears 4 times
            
            # Verify position average calculation
            words = text_processor.extract_words(text)
            test_positions = [i for i, word in enumerate(words) if word == 'test']
            expected_avg_position = statistics.mean(test_positions)
            assert abs(row[1] - expected_avg_position) < 0.01
            
            # Check "word" frequency
            cursor = conn.execute("""
                SELECT frequency FROM word_frequency 
                WHERE word = 'word'
            """)
            row = cursor.fetchone()
            assert row[0] == 2  # "word" appears 2 times
    
    def test_duplicate_document_handling(self, text_processor):
        """Test handling of duplicate documents."""
        text = "This is a test document for duplicate handling."
        
        # Analyze same text twice
        analysis1 = text_processor.analyze_text(text, store_result=True)
        analysis2 = text_processor.analyze_text(text, store_result=True)
        
        # Should produce same results
        assert analysis1.word_count == analysis2.word_count
        assert analysis1.readability_score == analysis2.readability_score
        
        # Check database - should have one record (replaced)
        with sqlite3.connect(text_processor.db_path) as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM text_documents")
            count = cursor.fetchone()[0]
            assert count == 1  # Should replace, not duplicate
    
    def test_concurrent_text_processing(self, memory_processor):
        """Test concurrent text processing operations."""
        import threading
        import concurrent.futures
        
        texts = [f"This is test document number {i} for concurrent processing." for i in range(20)]
        results = []
        errors = []
        
        def process_text(text):
            try:
                analysis = memory_processor.analyze_text(text, store_result=True)
                results.append(analysis)
            except Exception as e:
                errors.append(e)
        
        # Process texts concurrently
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(process_text, text) for text in texts]
            concurrent.futures.wait(futures)
        
        # Verify all processing succeeded
        assert len(results) == 20
        assert len(errors) == 0
        
        # Verify all results are valid
        for analysis in results:
            assert isinstance(analysis, TextAnalysis)
            assert analysis.word_count > 0
            assert analysis.processing_time >= 0


class TestTextProcessorPerformance:
    """Performance tests for text processing operations."""
    
    @pytest.fixture
    def performance_processor(self):
        """Create processor for performance testing."""
        return TextProcessor(":memory:")
    
    @pytest.fixture
    def large_text(self):
        """Generate large text for performance testing."""
        base_text = "This is a test sentence for performance analysis. " * 100
        return base_text * 10  # 10,000 words approximately
    
    def test_text_cleaning_performance(self, performance_processor, large_text):
        """Test text cleaning performance with large text."""
        start_time = time.time()
        
        cleaned = performance_processor.clean_text(large_text)
        
        end_time = time.time()
        processing_time = end_time - start_time
        
        # Should process large text within reasonable time
        assert processing_time < 1.0  # Less than 1 second
        assert len(cleaned) > 0
    
    def test_word_extraction_performance(self, performance_processor, large_text):
        """Test word extraction performance."""
        start_time = time.time()
        
        words = performance_processor.extract_words(large_text)
        
        end_time = time.time()
        processing_time = end_time - start_time
        
        # Should extract words efficiently
        assert processing_time < 0.5  # Less than 500ms
        assert len(words) > 1000  # Should extract many words
    
    def test_full_analysis_performance(self, performance_processor):
        """Test full text analysis performance."""
        # Generate medium-sized text
        text = "This is a performance test document. " * 200  # ~1200 words
        
        start_time = time.time()
        
        analysis = performance_processor.analyze_text(text, store_result=True)
        
        end_time = time.time()
        processing_time = end_time - start_time
        
        # Should complete analysis within reasonable time
        assert processing_time < 2.0  # Less than 2 seconds
        assert analysis.processing_time < processing_time
        assert analysis.word_count > 0
    
    def test_batch_processing_performance(self, performance_processor):
        """Test performance of processing multiple documents."""
        documents = [f"Document {i}: " + "This is test content. " * 50 for i in range(50)]
        
        start_time = time.time()
        
        analyses = []
        for doc in documents:
            analysis = performance_processor.analyze_text(doc, store_result=True)
            analyses.append(analysis)
        
        end_time = time.time()
        total_time = end_time - start_time
        
        # Should process all documents efficiently
        assert total_time < 10.0  # Less than 10 seconds for 50 documents
        assert len(analyses) == 50
        
        # Average processing time per document
        avg_time = total_time / 50
        assert avg_time < 0.2  # Less than 200ms per document
    
    def test_database_query_performance(self, performance_processor):
        """Test database query performance with many documents."""
        # Store many documents
        for i in range(100):
            text = f"Document {i}: test content with word{i % 10} repeated multiple times."
            performance_processor.analyze_text(text, store_result=True)
        
        # Test search performance
        start_time = time.time()
        
        results = performance_processor.search_documents_by_word("test")
        
        end_time = time.time()
        query_time = end_time - start_time
        
        # Should query efficiently
        assert query_time < 1.0  # Less than 1 second
        assert len(results) > 0


class TestTextAnalysisModel:
    """Test TextAnalysis dataclass behavior."""
    
    def test_text_analysis_creation(self):
        """Test TextAnalysis model creation."""
        common_words = {"test": 5, "word": 3}
        
        analysis = TextAnalysis(
            word_count=100,
            character_count=500,
            sentence_count=10,
            paragraph_count=3,
            avg_word_length=4.5,
            readability_score=75.2,
            common_words=common_words,
            sentiment_score=0.15,
            processing_time=0.025
        )
        
        assert analysis.word_count == 100
        assert analysis.character_count == 500
        assert analysis.sentence_count == 10
        assert analysis.paragraph_count == 3
        assert analysis.avg_word_length == 4.5
        assert analysis.readability_score == 75.2
        assert analysis.common_words == common_words
        assert analysis.sentiment_score == 0.15
        assert analysis.processing_time == 0.025
    
    def test_text_analysis_validation(self):
        """Test TextAnalysis with various data types."""
        # Test with empty common_words
        analysis = TextAnalysis(
            word_count=0,
            character_count=0,
            sentence_count=0,
            paragraph_count=0,
            avg_word_length=0.0,
            readability_score=0.0,
            common_words={},
            sentiment_score=0.0,
            processing_time=0.0
        )
        
        assert analysis.common_words == {}
        assert analysis.sentiment_score == 0.0


class TestTextProcessorIntegration:
    """Integration tests for text processing workflows."""
    
    @pytest.fixture
    def integration_processor(self):
        """Create processor for integration testing."""
        return TextProcessor(":memory:")
    
    def test_complete_document_processing_workflow(self, integration_processor):
        """Test complete workflow from text input to search and retrieval."""
        # Step 1: Process multiple documents
        documents = [
            "The quick brown fox jumps over the lazy dog. This sentence is great!",
            "A brown bear walks through the dark forest. The experience was terrible.",
            "The lazy cat sleeps peacefully all day. What a wonderful sight."
        ]
        
        doc_ids = []
        for doc in documents:
            analysis = integration_processor.analyze_text(doc, store_result=True)
            
            # Calculate doc_id for verification
            import hashlib
            doc_id = hashlib.sha256(doc.encode()).hexdigest()[:16]
            doc_ids.append(doc_id)
            
            # Verify analysis results
            assert analysis.word_count > 0
            assert analysis.sentiment_score != 0  # Should have sentiment
        
        # Step 2: Search documents by word
        brown_results = integration_processor.search_documents_by_word("brown")
        assert len(brown_results) == 2  # Two docs contain "brown"
        
        lazy_results = integration_processor.search_documents_by_word("lazy")
        assert len(lazy_results) == 2  # Two docs contain "lazy"
        
        # Step 3: Retrieve specific document analysis
        for doc_id in doc_ids:
            retrieved = integration_processor.get_document_analysis(doc_id)
            assert retrieved is not None
            assert 'analysis' in retrieved
            assert retrieved['analysis']['sentiment_score'] != 0
        
        # Step 4: Verify sentiment analysis accuracy
        positive_doc = documents[2]  # Contains "wonderful"
        negative_doc = documents[1]  # Contains "terrible"
        
        positive_id = hashlib.sha256(positive_doc.encode()).hexdigest()[:16]
        negative_id = hashlib.sha256(negative_doc.encode()).hexdigest()[:16]
        
        positive_analysis = integration_processor.get_document_analysis(positive_id)
        negative_analysis = integration_processor.get_document_analysis(negative_id)
        
        positive_sentiment = positive_analysis['analysis']['sentiment_score']
        negative_sentiment = negative_analysis['analysis']['sentiment_score']
        
        # Positive document should have higher sentiment score
        assert positive_sentiment > negative_sentiment
    
    def test_text_processing_with_real_world_content(self, integration_processor):
        """Test processing real-world style content."""
        real_world_text = """
        Machine learning has revolutionized the field of artificial intelligence in recent years.
        The ability to process vast amounts of data and identify patterns has led to breakthrough
        applications in healthcare, finance, and technology.
        
        Natural language processing, a subset of machine learning, enables computers to understand
        and generate human language. This technology powers virtual assistants, translation services,
        and sentiment analysis tools that help businesses understand customer feedback.
        
        However, challenges remain in areas such as bias detection, interpretability, and ethical
        considerations. Researchers continue to work on making AI systems more transparent,
        fair, and beneficial for society as a whole.
        """
        
        analysis = integration_processor.analyze_text(real_world_text, store_result=True)
        
        # Verify comprehensive analysis
        assert analysis.word_count > 50
        assert analysis.sentence_count >= 6
        assert analysis.paragraph_count == 3
        assert 0 <= analysis.readability_score <= 100
        assert len(analysis.common_words) > 0
        
        # Verify professional text characteristics
        assert analysis.avg_word_length > 4.0  # Professional text has longer words
        assert analysis.readability_score < 80  # Technical content is less readable
        
        # Verify database storage and retrieval
        import hashlib
        doc_id = hashlib.sha256(real_world_text.encode()).hexdigest()[:16]
        
        retrieved = integration_processor.get_document_analysis(doc_id)
        assert retrieved is not None
        assert retrieved['analysis']['word_count'] == analysis.word_count
    
    def test_error_handling_and_recovery(self, integration_processor):
        """Test error handling in various scenarios."""
        # Test with malformed input
        with pytest.raises(ValueError):
            integration_processor.analyze_text("")
        
        with pytest.raises(ValueError):
            integration_processor.analyze_text(None)
        
        # Test with extremely short text
        short_analysis = integration_processor.analyze_text("Hi.", store_result=True)
        assert short_analysis.word_count == 1
        assert short_analysis.sentence_count == 1
        
        # Test with only punctuation
        punct_analysis = integration_processor.analyze_text("!!! ??? ...", store_result=True)
        assert punct_analysis.word_count == 0
        assert punct_analysis.readability_score == 0.0
        
        # Test retrieval of non-existent documents
        assert integration_processor.get_document_analysis("fake_id") is None
        
        # Test search with no results
        no_results = integration_processor.search_documents_by_word("nonexistentword")
        assert len(no_results) == 0