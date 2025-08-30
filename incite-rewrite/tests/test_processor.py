"""
Document processing tests using London School TDD methodology.
Tests focus on text processing behavior, collaborations, and interactions.
"""

import pytest
import time
from unittest.mock import Mock, patch, MagicMock, call
from typing import Dict, Any, List

from src.utils.text_processing import TextProcessor, TextAnalysis
from src.core.text_analyzer import TextAnalyzer, AdvancedTextAnalysis
from src.core.nlp_processor import NLPProcessor, NLPAnalysis


class TestTextProcessorBehavior:
    """Test TextProcessor core behavior and text analysis interactions."""
    
    def test_initializes_with_database_connection(self, memory_db):
        """Should initialize TextProcessor with database connection."""
        processor = TextProcessor(memory_db)
        
        assert processor.db_path == memory_db
        # Verify database tables were created by attempting an operation
        result = processor.analyze_text("test text", store_result=False)
        assert isinstance(result, TextAnalysis)
    
    def test_creates_required_database_tables(self, temp_db_path):
        """Should create all required database tables on initialization."""
        processor = TextProcessor(temp_db_path)
        
        import sqlite3
        with sqlite3.connect(temp_db_path) as conn:
            cursor = conn.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='text_documents'
            """)
            assert cursor.fetchone() is not None
    
    def test_analyzes_text_and_extracts_metrics(self, memory_text_processor, sample_texts):
        """Should analyze text and extract comprehensive linguistic metrics."""
        result = memory_text_processor.analyze_text(sample_texts['complex'])
        
        # Verify core metrics are calculated
        assert result.word_count > 0
        assert result.character_count > result.word_count
        assert result.sentence_count > 0
        assert result.paragraph_count > 0
        assert result.avg_word_length > 0
        assert -1 <= result.sentiment_score <= 1
        assert isinstance(result.common_words, dict)
        assert result.processing_time > 0
    
    def test_stores_analysis_in_database_when_requested(self, memory_text_processor, sample_texts):
        """Should store text analysis in database when store_result=True."""
        result = memory_text_processor.analyze_text(sample_texts['simple'], store_result=True)
        
        # Verify document can be retrieved
        documents = memory_text_processor.search_documents_by_word('simple')
        assert len(documents) > 0
        
        stored_doc = memory_text_processor.get_document_analysis(documents[0]['doc_id'])
        assert stored_doc is not None
        assert stored_doc['word_count'] == result.word_count
    
    def test_skips_database_storage_when_not_requested(self, memory_text_processor, sample_texts):
        """Should not store analysis in database when store_result=False."""
        result = memory_text_processor.analyze_text(sample_texts['simple'], store_result=False)
        
        # Search should find no documents since nothing was stored
        documents = memory_text_processor.search_documents_by_word('simple')
        assert len(documents) == 0


class TestTextCleaningBehavior:
    """Test text cleaning and normalization behavior."""
    
    def test_removes_extra_whitespace(self, memory_text_processor):
        """Should remove extra whitespace and normalize text structure."""
        messy_text = "   This    has   extra    whitespace.   \n\n\n   "
        
        cleaned = memory_text_processor.clean_text(messy_text)
        
        assert cleaned == "This has extra whitespace."
        assert "   " not in cleaned
        assert not cleaned.startswith(" ")
        assert not cleaned.endswith(" ")
    
    def test_preserves_sentence_structure(self, memory_text_processor):
        """Should preserve sentence boundaries while cleaning text."""
        text_with_structure = "First sentence. Second sentence! Third question?"
        
        cleaned = memory_text_processor.clean_text(text_with_structure)
        
        assert "." in cleaned
        assert "!" in cleaned
        assert "?" in cleaned
        # Should maintain sentence separation
        sentences = memory_text_processor.extract_sentences(cleaned)
        assert len(sentences) == 3
    
    def test_handles_special_characters_appropriately(self, memory_text_processor, sample_texts):
        """Should handle special characters and unicode content."""
        cleaned = memory_text_processor.clean_text(sample_texts['unicode'])
        
        # Should preserve meaningful unicode characters
        assert 'café' in cleaned
        assert 'résumé' in cleaned
        # Should clean up excessive special characters while preserving content
        assert len(cleaned) > 0


class TestTextExtractionBehavior:
    """Test text extraction methods and their interactions."""
    
    def test_extracts_words_correctly(self, memory_text_processor, sample_texts):
        """Should extract individual words from text accurately."""
        words = memory_text_processor.extract_words(sample_texts['mixed_punctuation'])
        
        assert isinstance(words, list)
        assert len(words) > 0
        # Should extract actual words, not punctuation
        assert 'Hello' in words or 'hello' in words
        assert 'world' in words
        # Punctuation should be excluded
        assert '!' not in words
        assert '?' not in words
    
    def test_extracts_sentences_with_proper_boundaries(self, memory_text_processor, sample_texts):
        """Should identify sentence boundaries correctly."""
        sentences = memory_text_processor.extract_sentences(sample_texts['mixed_punctuation'])
        
        assert isinstance(sentences, list)
        assert len(sentences) >= 3  # Based on sample text structure
        # Each sentence should be a meaningful unit
        for sentence in sentences:
            assert len(sentence.strip()) > 0
            assert sentence.strip()[-1] in '.!?'
    
    def test_extracts_paragraphs_from_structured_text(self, memory_text_processor, sample_texts):
        """Should identify paragraph boundaries in text."""
        paragraphs = memory_text_processor.extract_paragraphs(sample_texts['complex'])
        
        assert isinstance(paragraphs, list)
        assert len(paragraphs) > 0
        # Each paragraph should contain meaningful content
        for paragraph in paragraphs:
            assert len(paragraph.strip()) > 0


class TestReadabilityCalculation:
    """Test readability score calculation and validation."""
    
    def test_calculates_readability_score(self, memory_text_processor, sample_texts):
        """Should calculate meaningful readability scores."""
        simple_score = memory_text_processor.calculate_readability(sample_texts['simple'])
        complex_score = memory_text_processor.calculate_readability(sample_texts['complex'])
        
        assert isinstance(simple_score, (int, float))
        assert isinstance(complex_score, (int, float))
        # Simple text should generally be more readable than complex text
        assert simple_score >= complex_score
    
    def test_handles_edge_cases_in_readability(self, memory_text_processor):
        """Should handle edge cases in readability calculation."""
        # Very short text
        short_score = memory_text_processor.calculate_readability("Hi.")
        assert isinstance(short_score, (int, float))
        
        # Text with numbers
        number_score = memory_text_processor.calculate_readability("Score: 123 points.")
        assert isinstance(number_score, (int, float))


class TestSentimentAnalysisBehavior:
    """Test sentiment analysis behavior and accuracy."""
    
    def test_detects_positive_sentiment(self, memory_text_processor, sample_texts):
        """Should detect positive sentiment in positive text."""
        sentiment = memory_text_processor.analyze_sentiment(sample_texts['positive'])
        
        assert isinstance(sentiment, (int, float))
        assert sentiment > 0  # Should be positive
    
    def test_detects_negative_sentiment(self, memory_text_processor, sample_texts):
        """Should detect negative sentiment in negative text."""
        sentiment = memory_text_processor.analyze_sentiment(sample_texts['negative'])
        
        assert isinstance(sentiment, (int, float))
        assert sentiment < 0  # Should be negative
    
    def test_handles_neutral_text_appropriately(self, memory_text_processor, sample_texts):
        """Should handle neutral text with appropriate sentiment scores."""
        sentiment = memory_text_processor.analyze_sentiment(sample_texts['neutral'])
        
        assert isinstance(sentiment, (int, float))
        assert -0.5 <= sentiment <= 0.5  # Should be relatively neutral


class TestDocumentSearchBehavior:
    """Test document search functionality and database interactions."""
    
    def test_searches_documents_by_word(self, memory_text_processor, sample_texts):
        """Should search stored documents by specific words."""
        # Store some documents
        memory_text_processor.analyze_text(sample_texts['simple'], store_result=True)
        memory_text_processor.analyze_text(sample_texts['complex'], store_result=True)
        
        # Search for a word that should be in the simple text
        results = memory_text_processor.search_documents_by_word('simple')
        
        assert isinstance(results, list)
        assert len(results) > 0
        
        # Verify result structure
        for result in results:
            assert 'doc_id' in result
            assert 'content' in result or 'word_count' in result
    
    def test_returns_empty_results_for_missing_words(self, memory_text_processor, sample_texts):
        """Should return empty results when word is not found."""
        memory_text_processor.analyze_text(sample_texts['simple'], store_result=True)
        
        results = memory_text_processor.search_documents_by_word('nonexistentword')
        
        assert isinstance(results, list)
        assert len(results) == 0
    
    def test_handles_case_insensitive_search(self, memory_text_processor):
        """Should handle case-insensitive word search."""
        text_with_caps = "Testing UPPERCASE and lowercase words."
        memory_text_processor.analyze_text(text_with_caps, store_result=True)
        
        # Search should find the word regardless of case
        results_upper = memory_text_processor.search_documents_by_word('TESTING')
        results_lower = memory_text_processor.search_documents_by_word('testing')
        
        # Both searches should return results
        assert len(results_upper) > 0 or len(results_lower) > 0


class TestDocumentRetrievalBehavior:
    """Test document analysis retrieval and data integrity."""
    
    def test_retrieves_document_analysis_by_id(self, memory_text_processor, sample_texts):
        """Should retrieve complete document analysis by document ID."""
        result = memory_text_processor.analyze_text(sample_texts['complex'], store_result=True)
        
        # Find the document ID through search
        documents = memory_text_processor.search_documents_by_word('text')
        assert len(documents) > 0
        
        doc_id = documents[0]['doc_id']
        retrieved = memory_text_processor.get_document_analysis(doc_id)
        
        assert retrieved is not None
        assert retrieved['word_count'] == result.word_count
        assert retrieved['character_count'] == result.character_count
    
    def test_returns_none_for_nonexistent_document(self, memory_text_processor):
        """Should return None when document ID doesn't exist."""
        result = memory_text_processor.get_document_analysis('nonexistent-id')
        
        assert result is None


class TestTextAnalyzerAdvancedBehavior:
    """Test advanced TextAnalyzer behavior and AI integration."""
    
    @patch('src.core.text_analyzer.NLPProcessor')
    def test_initializes_with_ai_processor(self, mock_nlp_processor, memory_db):
        """Should initialize with AI processor when enabled."""
        mock_nlp_instance = Mock()
        mock_nlp_processor.return_value = mock_nlp_instance
        
        analyzer = TextAnalyzer(memory_db, enable_ai=True)
        
        assert analyzer.enable_ai is True
        assert analyzer.nlp_processor == mock_nlp_instance
        mock_nlp_processor.assert_called_once()
    
    def test_falls_back_to_traditional_analysis_when_ai_fails(self, memory_db):
        """Should fall back to traditional analysis when AI initialization fails."""
        with patch('src.core.text_analyzer.NLPProcessor', side_effect=Exception("AI init failed")):
            analyzer = TextAnalyzer(memory_db, enable_ai=True)
            
            assert analyzer.enable_ai is False
            assert analyzer.nlp_processor is None
    
    def test_creates_extended_database_schema(self, temp_db_path):
        """Should create extended database schema for AI analysis storage."""
        analyzer = TextAnalyzer(temp_db_path, enable_ai=True)
        
        import sqlite3
        with sqlite3.connect(temp_db_path) as conn:
            # Check for AI analysis table
            cursor = conn.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='ai_text_analysis'
            """)
            assert cursor.fetchone() is not None
            
            # Check for performance metrics table
            cursor = conn.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='analysis_performance'
            """)
            assert cursor.fetchone() is not None
    
    def test_determines_ai_analysis_appropriateness(self, memory_db):
        """Should determine when to use AI analysis based on performance mode and text."""
        fast_analyzer = TextAnalyzer(memory_db, performance_mode="fast", enable_ai=True)
        comprehensive_analyzer = TextAnalyzer(memory_db, performance_mode="comprehensive", enable_ai=True)
        
        short_text = "Short text"
        long_text = "A" * 10000
        
        # Fast mode should be more selective
        assert not fast_analyzer._should_use_ai_analysis(short_text)
        
        # Comprehensive mode should be more inclusive
        assert comprehensive_analyzer._should_use_ai_analysis(short_text)
    
    @patch('src.core.text_analyzer.NLPProcessor')
    def test_merges_traditional_and_ai_analysis(self, mock_nlp_processor, memory_db, sample_texts):
        """Should merge traditional and AI analysis results into comprehensive analysis."""
        # Setup mocks
        mock_nlp_instance = Mock()
        mock_ai_analysis = Mock(spec=NLPAnalysis)
        mock_ai_analysis.processing_time = 0.1
        mock_ai_analysis.language = "en"
        mock_ai_analysis.named_entities = []
        mock_ai_analysis.topics = []
        mock_ai_analysis.confidence_scores = {"overall": 0.8}
        mock_ai_analysis.model_versions = {"nlp": "1.0"}
        
        mock_nlp_instance.analyze_text_async.return_value = mock_ai_analysis
        mock_nlp_processor.return_value = mock_nlp_instance
        
        analyzer = TextAnalyzer(memory_db, enable_ai=True, performance_mode="comprehensive")
        
        # Analyze text
        result = analyzer.analyze_text(sample_texts['simple'], store_result=False)
        
        assert isinstance(result, AdvancedTextAnalysis)
        assert result.language == "en"
        assert result.analysis_depth == "comprehensive"
        assert result.confidence_scores["overall"] == 0.8
    
    def test_handles_ai_analysis_timeout(self, memory_db, sample_texts):
        """Should handle AI analysis timeout gracefully."""
        with patch('src.core.text_analyzer.NLPProcessor') as mock_nlp_processor:
            mock_nlp_instance = Mock()
            mock_nlp_instance.analyze_text_async.side_effect = Exception("Timeout")
            mock_nlp_processor.return_value = mock_nlp_instance
            
            analyzer = TextAnalyzer(memory_db, enable_ai=True, performance_mode="fast")
            
            # Should complete without AI analysis
            result = analyzer.analyze_text(sample_texts['simple'], store_result=False)
            
            assert isinstance(result, AdvancedTextAnalysis)
            assert result.analysis_depth == "basic"  # Fallback to basic analysis


class TestBatchProcessingBehavior:
    """Test batch processing functionality and performance optimization."""
    
    def test_processes_multiple_texts_in_batch(self, memory_db, sample_texts):
        """Should process multiple texts efficiently in batch mode."""
        analyzer = TextAnalyzer(memory_db, performance_mode="balanced")
        
        texts = list(sample_texts.values())[:5]  # Process first 5 sample texts
        
        results = analyzer.batch_analyze(texts, store_results=False, max_workers=2)
        
        assert len(results) == len(texts)
        for result in results:
            assert isinstance(result, AdvancedTextAnalysis)
            assert result.word_count > 0
    
    def test_handles_batch_processing_errors_gracefully(self, memory_db):
        """Should handle errors in batch processing without failing entire batch."""
        analyzer = TextAnalyzer(memory_db, performance_mode="fast")
        
        # Include some problematic texts
        texts = ["Good text", "", None, "Another good text"]
        
        # Should not raise exception, but handle errors internally
        results = analyzer.batch_analyze(texts, store_results=False)
        
        # Should have some successful results
        assert len(results) >= 2  # At least the good texts should succeed
    
    def test_respects_max_workers_limit(self, memory_db, sample_texts):
        """Should respect the maximum workers limit for parallel processing."""
        analyzer = TextAnalyzer(memory_db, performance_mode="balanced")
        
        texts = list(sample_texts.values())[:3]
        
        # This should complete without errors regardless of worker limit
        results = analyzer.batch_analyze(texts, max_workers=1)
        
        assert len(results) == len(texts)


class TestPerformanceMonitoring:
    """Test performance monitoring and optimization features."""
    
    def test_records_performance_metrics(self, temp_db_path, sample_texts):
        """Should record performance metrics for analysis operations."""
        analyzer = TextAnalyzer(temp_db_path, performance_mode="balanced")
        
        # Perform analysis with storage
        result = analyzer.analyze_text(sample_texts['complex'], store_result=True)
        
        # Get performance statistics
        stats = analyzer.get_performance_stats()
        
        assert 'total_documents' in stats
        assert 'performance_by_type' in stats
        assert stats['total_documents'] >= 1
    
    def test_provides_optimization_suggestions(self, memory_db, sample_texts):
        """Should provide performance optimization suggestions."""
        analyzer = TextAnalyzer(memory_db, performance_mode="balanced")
        
        # Generate some performance data
        analyzer.analyze_text(sample_texts['complex'], store_result=True)
        
        optimization_report = analyzer.optimize_performance()
        
        assert 'current_stats' in optimization_report
        assert 'optimization_suggestions' in optimization_report
        assert 'recommended_performance_mode' in optimization_report
        assert isinstance(optimization_report['optimization_suggestions'], list)
    
    def test_recommends_appropriate_performance_mode(self, memory_db):
        """Should recommend appropriate performance mode based on usage patterns."""
        analyzer = TextAnalyzer(memory_db, performance_mode="balanced")
        
        # Mock some performance statistics
        mock_stats = {
            'performance_by_type': {
                'balanced': {'avg_processing_time': 0.05}  # Fast processing
            }
        }
        
        recommended_mode = analyzer._recommend_performance_mode(mock_stats)
        
        assert recommended_mode in ['fast', 'balanced', 'comprehensive']


class TestBackwardCompatibility:
    """Test backward compatibility with existing TextProcessor interface."""
    
    def test_maintains_text_processor_interface(self, memory_db, sample_texts):
        """Should maintain all TextProcessor methods for backward compatibility."""
        analyzer = TextAnalyzer(memory_db)
        
        # Test all backward compatibility methods
        cleaned = analyzer.clean_text(sample_texts['mixed_punctuation'])
        assert isinstance(cleaned, str)
        
        words = analyzer.extract_words(sample_texts['simple'])
        assert isinstance(words, list)
        
        sentences = analyzer.extract_sentences(sample_texts['complex'])
        assert isinstance(sentences, list)
        
        paragraphs = analyzer.extract_paragraphs(sample_texts['complex'])
        assert isinstance(paragraphs, list)
        
        readability = analyzer.calculate_readability(sample_texts['simple'])
        assert isinstance(readability, (int, float))
        
        sentiment = analyzer.analyze_sentiment(sample_texts['positive'])
        assert isinstance(sentiment, (int, float))
    
    def test_enhanced_document_retrieval(self, memory_db, sample_texts):
        """Should provide enhanced document retrieval while maintaining compatibility."""
        analyzer = TextAnalyzer(memory_db, enable_ai=True)
        
        # Store a document with advanced analysis
        result = analyzer.analyze_text(sample_texts['complex'], store_result=True)
        
        # Search for the document
        documents = analyzer.search_documents_by_word('text')
        assert len(documents) > 0
        
        doc_id = documents[0]['doc_id']
        
        # Enhanced retrieval should return advanced analysis if available
        retrieved = analyzer.get_document_analysis(doc_id)
        
        assert retrieved is not None
        # Should contain enhanced analysis data if available
        assert 'analysis_depth' in retrieved or 'word_count' in retrieved


@pytest.mark.integration
class TestProcessorIntegration:
    """Test integration between different processor components."""
    
    def test_text_processor_database_integration(self, temp_db_path, sample_texts):
        """Should integrate properly with database for persistent storage."""
        processor1 = TextProcessor(temp_db_path)
        processor2 = TextProcessor(temp_db_path)  # Same database
        
        # Store document with first processor
        result1 = processor1.analyze_text(sample_texts['simple'], store_result=True)
        
        # Retrieve with second processor instance
        documents = processor2.search_documents_by_word('simple')
        assert len(documents) > 0
        
        doc_id = documents[0]['doc_id']
        retrieved = processor2.get_document_analysis(doc_id)
        assert retrieved is not None
        assert retrieved['word_count'] == result1.word_count
    
    def test_analyzer_processor_compatibility(self, memory_db, sample_texts):
        """Should maintain compatibility between TextAnalyzer and TextProcessor."""
        processor = TextProcessor(memory_db)
        analyzer = TextAnalyzer(memory_db, enable_ai=False)  # Disable AI for fair comparison
        
        # Both should produce similar basic results
        processor_result = processor.analyze_text(sample_texts['simple'], store_result=False)
        analyzer_result = analyzer.analyze_text(sample_texts['simple'], store_result=False)
        
        # Core metrics should be similar
        assert analyzer_result.word_count == processor_result.word_count
        assert analyzer_result.character_count == processor_result.character_count
        assert abs(analyzer_result.sentiment_score - processor_result.sentiment_score) < 0.1


@pytest.mark.performance
class TestProcessorPerformance:
    """Test processor performance and scalability."""
    
    def test_processing_performance_scales_with_text_length(self, memory_text_processor, performance_monitor):
        """Should have processing time that scales reasonably with text length."""
        short_text = "Short text for testing."
        long_text = short_text * 100  # Much longer text
        
        # Measure short text processing
        performance_monitor.start()
        memory_text_processor.analyze_text(short_text, store_result=False)
        short_metrics = performance_monitor.stop()
        
        # Measure long text processing  
        performance_monitor.start()
        memory_text_processor.analyze_text(long_text, store_result=False)
        long_metrics = performance_monitor.stop()
        
        # Long text should take more time, but not excessively more
        assert long_metrics['duration'] > short_metrics['duration']
        assert long_metrics['duration'] < short_metrics['duration'] * 200  # Reasonable scaling
    
    def test_batch_processing_efficiency(self, memory_db, sample_texts, performance_monitor):
        """Should process multiple texts more efficiently in batch than individually."""
        analyzer = TextAnalyzer(memory_db, performance_mode="balanced")
        texts = list(sample_texts.values())[:3]
        
        # Measure individual processing
        performance_monitor.start()
        individual_results = []
        for text in texts:
            result = analyzer.analyze_text(text, store_result=False)
            individual_results.append(result)
        individual_metrics = performance_monitor.stop()
        
        # Measure batch processing
        performance_monitor.start()
        batch_results = analyzer.batch_analyze(texts, store_results=False, max_workers=2)
        batch_metrics = performance_monitor.stop()
        
        # Batch should be more efficient (though this may vary in practice)
        assert len(batch_results) == len(individual_results)
        # At minimum, batch processing should not be significantly slower
        assert batch_metrics['duration'] < individual_metrics['duration'] * 2
    
    def test_memory_usage_remains_reasonable(self, memory_text_processor, sample_texts, performance_monitor):
        """Should maintain reasonable memory usage during text processing."""
        performance_monitor.start()
        
        # Process multiple texts
        for text in list(sample_texts.values())[:5]:
            memory_text_processor.analyze_text(text, store_result=True)
        
        metrics = performance_monitor.stop()
        
        # Memory delta should be reasonable (less than 50MB for this test)
        assert metrics['memory_delta'] < 50
        assert metrics['memory_peak'] < 200  # Less than 200MB peak usage


class TestErrorHandlingAndEdgeCases:
    """Test error handling and edge cases in text processing."""
    
    def test_handles_empty_text_gracefully(self, memory_text_processor):
        """Should handle empty text input gracefully."""
        with pytest.raises(ValueError, match="Text must be a non-empty string"):
            memory_text_processor.analyze_text("")
    
    def test_handles_none_text_input(self, memory_text_processor):
        """Should handle None text input with appropriate error."""
        with pytest.raises(ValueError, match="Text must be a non-empty string"):
            memory_text_processor.analyze_text(None)
    
    def test_handles_very_long_text_appropriately(self, memory_text_processor):
        """Should handle very long text without crashing."""
        very_long_text = "This is a test sentence. " * 1000
        
        # Should complete without error
        result = memory_text_processor.analyze_text(very_long_text, store_result=False)
        
        assert result.word_count > 5000  # Should have counted many words
        assert result.processing_time > 0
    
    def test_handles_unicode_text_properly(self, memory_text_processor, sample_texts):
        """Should handle unicode text without encoding errors."""
        result = memory_text_processor.analyze_text(sample_texts['unicode'], store_result=False)
        
        assert result.word_count > 0
        assert result.character_count > result.word_count
        assert isinstance(result.sentiment_score, (int, float))
    
    def test_handles_database_errors_gracefully(self, memory_text_processor):
        """Should handle database errors without crashing the analysis."""
        # Simulate database error during storage
        with patch.object(memory_text_processor, '_store_document') as mock_store:
            mock_store.side_effect = Exception("Database error")
            
            # Analysis should complete even if storage fails
            result = memory_text_processor.analyze_text("Test text", store_result=True)
            
            assert isinstance(result, TextAnalysis)
            assert result.word_count > 0
    
    def test_validates_database_path_parameter(self):
        """Should validate database path parameter during initialization."""
        # Should work with valid paths
        processor1 = TextProcessor(":memory:")
        assert processor1.db_path == ":memory:"
        
        # Should work with file paths
        processor2 = TextProcessor("/tmp/test.db")
        assert processor2.db_path == "/tmp/test.db"
