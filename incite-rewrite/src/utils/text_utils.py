"""
Performance-optimized text utilities for the InciteRewrite platform.
High-performance helper functions for text processing operations.
"""

import re
import time
import asyncio
import functools
import threading
from typing import Dict, List, Tuple, Optional, Any, Union, Set
from collections import Counter, defaultdict
from dataclasses import dataclass
import hashlib
import json
import logging

import numpy as np
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
import multiprocessing
from threading import Lock

# Import AI libraries with fallbacks
try:
    import spacy
    SPACY_AVAILABLE = True
except ImportError:
    SPACY_AVAILABLE = False

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False

logger = logging.getLogger(__name__)

@dataclass
class ProcessingStats:
    """Statistics for text processing operations."""
    total_operations: int = 0
    total_time: float = 0.0
    cache_hits: int = 0
    cache_misses: int = 0
    avg_processing_time: float = 0.0
    peak_memory_usage: float = 0.0

class PerformanceCache:
    """Thread-safe LRU cache with TTL support."""
    
    def __init__(self, maxsize: int = 1000, ttl: int = 3600):
        self.maxsize = maxsize
        self.ttl = ttl
        self.cache: Dict[str, Tuple[Any, float]] = {}
        self.access_times: Dict[str, float] = {}
        self.lock = Lock()
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache if not expired."""
        with self.lock:
            if key in self.cache:
                value, timestamp = self.cache[key]
                if time.time() - timestamp < self.ttl:
                    self.access_times[key] = time.time()
                    return value
                else:
                    # Expired, remove
                    del self.cache[key]
                    del self.access_times[key]
            return None
    
    def set(self, key: str, value: Any):
        """Set value in cache with TTL."""
        with self.lock:
            current_time = time.time()
            
            # Remove oldest items if at capacity
            if len(self.cache) >= self.maxsize:
                # Remove oldest accessed item
                oldest_key = min(self.access_times.keys(), 
                               key=lambda k: self.access_times[k])
                del self.cache[oldest_key]
                del self.access_times[oldest_key]
            
            self.cache[key] = (value, current_time)
            self.access_times[key] = current_time
    
    def clear(self):
        """Clear all cache entries."""
        with self.lock:
            self.cache.clear()
            self.access_times.clear()

class TextPreprocessor:
    """High-performance text preprocessing utilities."""
    
    def __init__(self):
        # Compile regex patterns for performance
        self.patterns = {
            'whitespace': re.compile(r'\s+'),
            'punctuation': re.compile(r'[^\w\s]'),
            'word_boundaries': re.compile(r'\b\w+\b'),
            'sentence_boundaries': re.compile(r'[.!?]+'),
            'paragraph_boundaries': re.compile(r'\n\s*\n'),
            'urls': re.compile(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'),
            'emails': re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'),
            'numbers': re.compile(r'\b\d+(?:\.\d+)?\b'),
            'contractions': re.compile(r'\b\w+\'[a-z]+\b', re.IGNORECASE)
        }
        
        # Common English stop words for fast filtering
        self.stop_words = frozenset([
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
            'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'have',
            'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should',
            'may', 'might', 'must', 'can', 'this', 'that', 'these', 'those', 'i',
            'you', 'he', 'she', 'it', 'we', 'they', 'me', 'him', 'her', 'us', 'them'
        ])
    
    def clean_text_fast(self, text: str) -> str:
        """Ultra-fast text cleaning."""
        if not text:
            return ""
        
        # Remove extra whitespace
        text = self.patterns['whitespace'].sub(' ', text.strip())
        
        # Remove URLs and emails
        text = self.patterns['urls'].sub(' ', text)
        text = self.patterns['emails'].sub(' ', text)
        
        return text
    
    def extract_words_fast(self, text: str, min_length: int = 2) -> List[str]:
        """Fast word extraction with filtering."""
        words = self.patterns['word_boundaries'].findall(text.lower())
        return [w for w in words if len(w) >= min_length and w not in self.stop_words]
    
    def extract_sentences_fast(self, text: str) -> List[str]:
        """Fast sentence extraction."""
        sentences = self.patterns['sentence_boundaries'].split(text)
        return [s.strip() for s in sentences if s.strip()]
    
    def extract_ngrams(self, words: List[str], n: int = 2) -> List[Tuple[str, ...]]:
        """Extract n-grams from word list."""
        if len(words) < n:
            return []
        return [tuple(words[i:i+n]) for i in range(len(words) - n + 1)]

class FastTextAnalyzer:
    """High-performance text analysis with caching and parallel processing."""
    
    def __init__(self, cache_size: int = 1000, enable_parallel: bool = True):
        self.preprocessor = TextPreprocessor()
        self.cache = PerformanceCache(maxsize=cache_size)
        self.enable_parallel = enable_parallel
        self.stats = ProcessingStats()
        self.executor = ThreadPoolExecutor(max_workers=min(4, multiprocessing.cpu_count()))
    
    def _get_cache_key(self, text: str, operation: str) -> str:
        """Generate cache key for operation."""
        text_hash = hashlib.md5(text.encode()).hexdigest()[:16]
        return f"{operation}:{text_hash}"
    
    @functools.lru_cache(maxsize=256)
    def count_syllables_fast(self, word: str) -> int:
        """Fast syllable counting with caching."""
        if not word:
            return 0
        
        word = word.lower()
        vowels = 'aeiouy'
        syllables = 0
        prev_was_vowel = False
        
        for char in word:
            is_vowel = char in vowels
            if is_vowel and not prev_was_vowel:
                syllables += 1
            prev_was_vowel = is_vowel
        
        # Adjust for silent e
        if word.endswith('e') and syllables > 1:
            syllables -= 1
        
        return max(1, syllables)
    
    def calculate_readability_fast(self, text: str) -> Dict[str, float]:
        """Fast readability calculation with basic metrics."""
        cache_key = self._get_cache_key(text, "readability")
        cached_result = self.cache.get(cache_key)
        if cached_result:
            self.stats.cache_hits += 1
            return cached_result
        
        start_time = time.time()
        
        sentences = self.preprocessor.extract_sentences_fast(text)
        words = self.preprocessor.extract_words_fast(text)
        
        if not sentences or not words:
            return {"flesch_reading_ease": 0.0, "avg_sentence_length": 0.0}
        
        # Calculate syllables for all words
        syllables = sum(self.count_syllables_fast(word) for word in words)
        
        # Flesch Reading Ease
        avg_sentence_length = len(words) / len(sentences)
        avg_syllables_per_word = syllables / len(words)
        
        flesch_score = (206.835 - 
                       1.015 * avg_sentence_length - 
                       84.6 * avg_syllables_per_word)
        
        result = {
            "flesch_reading_ease": max(0.0, min(100.0, flesch_score)),
            "avg_sentence_length": avg_sentence_length,
            "avg_syllables_per_word": avg_syllables_per_word,
            "total_syllables": syllables
        }
        
        processing_time = time.time() - start_time
        self.stats.total_time += processing_time
        self.stats.total_operations += 1
        self.stats.cache_misses += 1
        
        self.cache.set(cache_key, result)
        return result
    
    def analyze_word_frequency(self, text: str, top_k: int = 20) -> Dict[str, int]:
        """Fast word frequency analysis."""
        cache_key = self._get_cache_key(text + str(top_k), "word_freq")
        cached_result = self.cache.get(cache_key)
        if cached_result:
            self.stats.cache_hits += 1
            return cached_result
        
        words = self.preprocessor.extract_words_fast(text)
        word_counts = Counter(words)
        result = dict(word_counts.most_common(top_k))
        
        self.cache.set(cache_key, result)
        self.stats.cache_misses += 1
        return result
    
    def detect_patterns(self, text: str) -> Dict[str, Any]:
        """Detect various text patterns efficiently."""
        patterns = {}
        
        # URL and email counts
        patterns['url_count'] = len(self.preprocessor.patterns['urls'].findall(text))
        patterns['email_count'] = len(self.preprocessor.patterns['emails'].findall(text))
        patterns['number_count'] = len(self.preprocessor.patterns['numbers'].findall(text))
        patterns['contraction_count'] = len(self.preprocessor.patterns['contractions'].findall(text))
        
        # Character-level patterns
        patterns['uppercase_ratio'] = sum(c.isupper() for c in text) / len(text) if text else 0
        patterns['punctuation_ratio'] = len([c for c in text if not c.isalnum() and not c.isspace()]) / len(text) if text else 0
        
        return patterns
    
    def batch_analyze(self, texts: List[str], operations: List[str] = None) -> List[Dict[str, Any]]:
        """Batch analyze multiple texts in parallel."""
        if not texts:
            return []
        
        if operations is None:
            operations = ['readability', 'word_freq', 'patterns']
        
        if not self.enable_parallel or len(texts) < 3:
            # Sequential processing for small batches
            return [self._analyze_single(text, operations) for text in texts]
        
        # Parallel processing
        futures = []
        with self.executor:
            for text in texts:
                future = self.executor.submit(self._analyze_single, text, operations)
                futures.append(future)
            
            results = []
            for future in as_completed(futures):
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    logger.error(f"Batch analysis error: {e}")
                    results.append({})
        
        return results
    
    def _analyze_single(self, text: str, operations: List[str]) -> Dict[str, Any]:
        """Analyze single text with specified operations."""
        result = {}
        
        if 'readability' in operations:
            result['readability'] = self.calculate_readability_fast(text)
        
        if 'word_freq' in operations:
            result['word_frequency'] = self.analyze_word_frequency(text)
        
        if 'patterns' in operations:
            result['patterns'] = self.detect_patterns(text)
        
        return result
    
    def get_performance_stats(self) -> ProcessingStats:
        """Get current performance statistics."""
        if self.stats.total_operations > 0:
            self.stats.avg_processing_time = self.stats.total_time / self.stats.total_operations
        
        return self.stats
    
    def clear_cache(self):
        """Clear all caches."""
        self.cache.clear()
        self.count_syllables_fast.cache_clear()

class TextSimilarity:
    """Fast text similarity calculations."""
    
    def __init__(self):
        self.preprocessor = TextPreprocessor()
        
        # Initialize sentence transformer if available
        if SENTENCE_TRANSFORMERS_AVAILABLE:
            try:
                self.sentence_transformer = SentenceTransformer('all-MiniLM-L6-v2')
            except Exception as e:
                logger.warning(f"Failed to load sentence transformer: {e}")
                self.sentence_transformer = None
        else:
            self.sentence_transformer = None
    
    def jaccard_similarity(self, text1: str, text2: str) -> float:
        """Fast Jaccard similarity calculation."""
        words1 = set(self.preprocessor.extract_words_fast(text1))
        words2 = set(self.preprocessor.extract_words_fast(text2))
        
        if not words1 and not words2:
            return 1.0
        
        intersection = len(words1 & words2)
        union = len(words1 | words2)
        
        return intersection / union if union > 0 else 0.0
    
    def cosine_similarity_tfidf(self, texts: List[str]) -> np.ndarray:
        """Fast cosine similarity using TF-IDF vectors."""
        if len(texts) < 2:
            return np.array([[1.0]])
        
        # Create vocabulary
        vocabulary = set()
        word_lists = []
        
        for text in texts:
            words = self.preprocessor.extract_words_fast(text)
            word_lists.append(words)
            vocabulary.update(words)
        
        vocabulary = sorted(vocabulary)
        vocab_size = len(vocabulary)
        word_to_idx = {word: idx for idx, word in enumerate(vocabulary)}
        
        # Calculate TF-IDF vectors
        vectors = np.zeros((len(texts), vocab_size))
        
        for text_idx, words in enumerate(word_lists):
            word_counts = Counter(words)
            total_words = len(words)
            
            # TF calculation
            for word, count in word_counts.items():
                if word in word_to_idx:
                    tf = count / total_words
                    vectors[text_idx, word_to_idx[word]] = tf
        
        # IDF calculation
        doc_frequencies = np.sum(vectors > 0, axis=0)
        idf = np.log(len(texts) / (doc_frequencies + 1))
        
        # Apply IDF
        tfidf_vectors = vectors * idf
        
        # Normalize vectors
        norms = np.linalg.norm(tfidf_vectors, axis=1, keepdims=True)
        norms[norms == 0] = 1  # Avoid division by zero
        tfidf_vectors = tfidf_vectors / norms
        
        # Calculate cosine similarity matrix
        similarity_matrix = np.dot(tfidf_vectors, tfidf_vectors.T)
        
        return similarity_matrix
    
    def semantic_similarity(self, text1: str, text2: str) -> float:
        """Semantic similarity using sentence transformers (if available)."""
        if not self.sentence_transformer:
            # Fallback to Jaccard similarity
            return self.jaccard_similarity(text1, text2)
        
        try:
            embeddings = self.sentence_transformer.encode([text1, text2])
            similarity = np.dot(embeddings[0], embeddings[1]) / (
                np.linalg.norm(embeddings[0]) * np.linalg.norm(embeddings[1])
            )
            return float(similarity)
        except Exception as e:
            logger.error(f"Semantic similarity calculation failed: {e}")
            return self.jaccard_similarity(text1, text2)

class TextMetrics:
    """Comprehensive text metrics calculation."""
    
    def __init__(self):
        self.preprocessor = TextPreprocessor()
        self.analyzer = FastTextAnalyzer()
    
    def calculate_complexity_metrics(self, text: str) -> Dict[str, float]:
        """Calculate text complexity metrics."""
        words = self.preprocessor.extract_words_fast(text)
        sentences = self.preprocessor.extract_sentences_fast(text)
        
        if not words:
            return {
                'lexical_diversity': 0.0,
                'avg_word_length': 0.0,
                'sentence_length_variance': 0.0
            }
        
        # Lexical diversity (Type-Token Ratio)
        unique_words = set(words)
        lexical_diversity = len(unique_words) / len(words)
        
        # Average word length
        avg_word_length = np.mean([len(word) for word in words])
        
        # Sentence length variance
        if sentences:
            sentence_lengths = []
            for sentence in sentences:
                sentence_words = self.preprocessor.extract_words_fast(sentence)
                sentence_lengths.append(len(sentence_words))
            
            sentence_length_variance = np.var(sentence_lengths) if len(sentence_lengths) > 1 else 0.0
        else:
            sentence_length_variance = 0.0
        
        return {
            'lexical_diversity': lexical_diversity,
            'avg_word_length': avg_word_length,
            'sentence_length_variance': sentence_length_variance
        }
    
    def calculate_style_metrics(self, text: str) -> Dict[str, float]:
        """Calculate writing style metrics."""
        patterns = self.analyzer.detect_patterns(text)
        
        # Add more style-specific metrics
        words = self.preprocessor.extract_words_fast(text)
        
        if not words:
            return {
                'formality_score': 0.5,
                'complexity_score': 0.5,
                'objectivity_score': 0.5
            }
        
        # Simple formality score based on contractions and formal words
        contraction_ratio = patterns.get('contraction_count', 0) / len(words)
        formality_score = max(0.0, 1.0 - contraction_ratio * 5)
        
        # Complexity score based on word length and syllables
        avg_word_length = np.mean([len(word) for word in words])
        complexity_score = min(1.0, avg_word_length / 10.0)
        
        # Basic objectivity score (simplified)
        subjective_words = ['think', 'feel', 'believe', 'opinion', 'seems', 'appears']
        subjective_count = sum(1 for word in words if word in subjective_words)
        objectivity_score = max(0.0, 1.0 - subjective_count / len(words) * 10)
        
        return {
            'formality_score': formality_score,
            'complexity_score': complexity_score,
            'objectivity_score': objectivity_score,
            'contraction_ratio': contraction_ratio,
            'uppercase_ratio': patterns.get('uppercase_ratio', 0.0),
            'punctuation_ratio': patterns.get('punctuation_ratio', 0.0)
        }

class TextUtilsManager:
    """Main manager class for all text utilities."""
    
    def __init__(self, 
                 cache_size: int = 1000,
                 enable_parallel: bool = True,
                 enable_redis: bool = True,
                 redis_host: str = "localhost",
                 redis_port: int = 6379):
        """Initialize text utilities manager."""
        
        self.preprocessor = TextPreprocessor()
        self.analyzer = FastTextAnalyzer(cache_size, enable_parallel)
        self.similarity = TextSimilarity()
        self.metrics = TextMetrics()
        
        # Initialize Redis if available and enabled
        self.redis_client = None
        if enable_redis and REDIS_AVAILABLE:
            try:
                self.redis_client = redis.Redis(host=redis_host, port=redis_port, decode_responses=True)
                self.redis_client.ping()
                logger.info("Redis client initialized for text utils")
            except Exception as e:
                logger.warning(f"Redis not available for text utils: {e}")
        
        self.performance_monitor = {
            'total_requests': 0,
            'total_time': 0.0,
            'peak_memory': 0.0,
            'error_count': 0
        }
    
    def comprehensive_analysis(self, text: str, include_similarity: bool = False) -> Dict[str, Any]:
        """Perform comprehensive text analysis."""
        start_time = time.time()
        
        try:
            result = {}
            
            # Basic analysis
            result['readability'] = self.analyzer.calculate_readability_fast(text)
            result['word_frequency'] = self.analyzer.analyze_word_frequency(text)
            result['patterns'] = self.analyzer.detect_patterns(text)
            result['complexity'] = self.metrics.calculate_complexity_metrics(text)
            result['style'] = self.metrics.calculate_style_metrics(text)
            
            # Optional similarity analysis (expensive)
            if include_similarity:
                sentences = self.preprocessor.extract_sentences_fast(text)
                if len(sentences) > 1:
                    similarity_matrix = self.similarity.cosine_similarity_tfidf(sentences)
                    result['internal_similarity'] = {
                        'avg_similarity': float(np.mean(similarity_matrix[np.triu_indices_from(similarity_matrix, k=1)])),
                        'coherence_score': float(np.mean(np.diagonal(similarity_matrix, offset=1)))
                    }
            
            processing_time = time.time() - start_time
            result['processing_time'] = processing_time
            
            # Update performance monitoring
            self.performance_monitor['total_requests'] += 1
            self.performance_monitor['total_time'] += processing_time
            
            return result
            
        except Exception as e:
            logger.error(f"Comprehensive analysis failed: {e}")
            self.performance_monitor['error_count'] += 1
            raise
    
    def batch_comprehensive_analysis(self, texts: List[str]) -> List[Dict[str, Any]]:
        """Batch comprehensive analysis with optimizations."""
        if not texts:
            return []
        
        # Use parallel processing for large batches
        if len(texts) > 10:
            with ThreadPoolExecutor(max_workers=min(4, len(texts))) as executor:
                futures = [
                    executor.submit(self.comprehensive_analysis, text)
                    for text in texts
                ]
                
                results = []
                for future in as_completed(futures):
                    try:
                        result = future.result()
                        results.append(result)
                    except Exception as e:
                        logger.error(f"Batch analysis item failed: {e}")
                        results.append({})
                
                return results
        else:
            # Sequential processing for small batches
            return [self.comprehensive_analysis(text) for text in texts]
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get performance summary for all utilities."""
        analyzer_stats = self.analyzer.get_performance_stats()
        
        return {
            'manager_stats': self.performance_monitor,
            'analyzer_stats': {
                'total_operations': analyzer_stats.total_operations,
                'avg_processing_time': analyzer_stats.avg_processing_time,
                'cache_hits': analyzer_stats.cache_hits,
                'cache_misses': analyzer_stats.cache_misses,
                'cache_hit_rate': analyzer_stats.cache_hits / (analyzer_stats.cache_hits + analyzer_stats.cache_misses) if (analyzer_stats.cache_hits + analyzer_stats.cache_misses) > 0 else 0.0
            },
            'redis_available': self.redis_client is not None,
            'sentence_transformer_available': self.similarity.sentence_transformer is not None,
            'spacy_available': SPACY_AVAILABLE
        }
    
    def optimize_performance(self) -> Dict[str, str]:
        """Analyze performance and provide optimization suggestions."""
        perf_summary = self.get_performance_summary()
        suggestions = []
        
        # Check cache performance
        cache_hit_rate = perf_summary['analyzer_stats']['cache_hit_rate']
        if cache_hit_rate < 0.3:
            suggestions.append("Low cache hit rate. Consider increasing cache size or TTL.")
        
        # Check processing times
        avg_time = perf_summary['analyzer_stats']['avg_processing_time']
        if avg_time > 0.1:
            suggestions.append("High average processing time. Consider enabling parallel processing or Redis caching.")
        
        # Check error rate
        total_requests = perf_summary['manager_stats']['total_requests']
        error_count = perf_summary['manager_stats']['error_count']
        if total_requests > 0 and error_count / total_requests > 0.05:
            suggestions.append("High error rate detected. Check logs for common failure patterns.")
        
        # Check feature availability
        if not perf_summary['redis_available']:
            suggestions.append("Redis not available. Enable Redis for better caching performance.")
        
        if not perf_summary['sentence_transformer_available']:
            suggestions.append("Sentence transformers not available. Install for better semantic analysis.")
        
        return {
            'performance_summary': perf_summary,
            'optimization_suggestions': suggestions,
            'status': 'optimal' if not suggestions else 'needs_optimization'
        }
    
    def clear_all_caches(self):
        """Clear all caches across utilities."""
        self.analyzer.clear_cache()
        
        if self.redis_client:
            try:
                # Clear only our keys (with text utils prefix)
                keys = self.redis_client.keys("text_utils:*")
                if keys:
                    self.redis_client.delete(*keys)
                logger.info(f"Cleared {len(keys)} Redis cache entries")
            except Exception as e:
                logger.error(f"Failed to clear Redis cache: {e}")

# Global instance for easy access
text_utils = TextUtilsManager()