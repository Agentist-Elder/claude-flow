"""
Comprehensive text analyzer integrating multiple AI models and readability metrics.
Compatible with existing London TDD test suite and extends current functionality.
"""

import time
import asyncio
import logging
import statistics
from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass, asdict
import sqlite3
import json
import hashlib

import numpy as np
import textstat
from textblob import TextBlob
import redis

from .nlp_processor import NLPProcessor, NLPAnalysis
from ..utils.text_processing import TextProcessor, TextAnalysis

logger = logging.getLogger(__name__)

@dataclass
class AdvancedTextAnalysis:
    """Extended text analysis with AI-powered insights."""
    # Basic metrics (compatible with existing TextAnalysis)
    word_count: int
    character_count: int 
    sentence_count: int
    paragraph_count: int
    avg_word_length: float
    readability_score: float
    common_words: Dict[str, int]
    sentiment_score: float
    processing_time: float
    
    # Advanced AI metrics
    language: str
    flesch_kincaid_grade: float
    gunning_fog: float
    smog_index: float
    coleman_liau: float
    automated_readability: float
    
    # NLP insights
    named_entities: List[Dict[str, str]]
    noun_phrases: List[str]
    topics: List[Dict[str, Any]]
    keywords: List[Tuple[str, float]]
    emotion_scores: Dict[str, float]
    
    # Style metrics
    lexical_diversity: float
    syllable_complexity: float
    passive_voice_percentage: float
    semantic_similarity_score: float
    
    # Confidence and metadata
    confidence_scores: Dict[str, float]
    model_versions: Dict[str, str]
    analysis_depth: str  # "basic", "standard", "comprehensive"
    

class TextAnalyzer:
    """
    Advanced text analyzer combining traditional metrics with AI-powered analysis.
    Maintains backward compatibility with existing TextProcessor interface.
    """
    
    def __init__(self, 
                 db_path: str = ":memory:",
                 enable_ai: bool = True,
                 redis_host: str = "localhost",
                 redis_port: int = 6379,
                 performance_mode: str = "balanced"):
        """
        Initialize text analyzer with AI capabilities.
        
        Args:
            db_path: Database path for storage (compatible with existing tests)
            enable_ai: Enable AI-powered analysis features
            redis_host: Redis host for caching
            redis_port: Redis port
            performance_mode: "fast", "balanced", or "comprehensive"
        """
        
        self.db_path = db_path
        self.enable_ai = enable_ai
        self.performance_mode = performance_mode
        
        # Initialize traditional text processor for backward compatibility
        self.text_processor = TextProcessor(db_path)
        
        # Initialize AI processor if enabled
        if enable_ai:
            try:
                self.nlp_processor = NLPProcessor(
                    spacy_model="en_core_web_sm",
                    redis_host=redis_host,
                    redis_port=redis_port
                )
                logger.info("AI-powered text analysis enabled")
            except Exception as e:
                logger.warning(f"AI processor initialization failed: {e}. Falling back to traditional analysis.")
                self.nlp_processor = None
                self.enable_ai = False
        else:
            self.nlp_processor = None
        
        # Performance thresholds based on mode
        self.performance_thresholds = {
            "fast": {"max_chars": 1000, "timeout": 0.1},
            "balanced": {"max_chars": 5000, "timeout": 0.2}, 
            "comprehensive": {"max_chars": 20000, "timeout": 1.0}
        }
        
        # Initialize extended database schema
        self._init_extended_database()
    
    def _init_extended_database(self):
        """Initialize extended database schema for AI analysis results."""
        with sqlite3.connect(self.db_path) as conn:
            # Add AI analysis table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS ai_text_analysis (
                    doc_id TEXT PRIMARY KEY,
                    nlp_analysis TEXT,  -- JSON serialized NLP analysis
                    advanced_metrics TEXT,  -- JSON serialized advanced metrics
                    analysis_depth TEXT DEFAULT 'standard',
                    model_versions TEXT,  -- JSON serialized model info
                    created_at REAL DEFAULT (julianday('now')),
                    FOREIGN KEY (doc_id) REFERENCES text_documents (doc_id)
                )
            """)
            
            # Add performance metrics table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS analysis_performance (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    doc_id TEXT,
                    analysis_type TEXT,
                    processing_time REAL,
                    text_length INTEGER,
                    cache_hit BOOLEAN DEFAULT FALSE,
                    timestamp REAL DEFAULT (julianday('now')),
                    FOREIGN KEY (doc_id) REFERENCES text_documents (doc_id)
                )
            """)
            
            conn.commit()
    
    def _should_use_ai_analysis(self, text: str) -> bool:
        """Determine if AI analysis should be used based on performance mode and text characteristics."""
        if not self.enable_ai or not self.nlp_processor:
            return False
        
        thresholds = self.performance_thresholds[self.performance_mode]
        
        # Check text length threshold
        if len(text) > thresholds["max_chars"]:
            if self.performance_mode == "fast":
                return False
        
        # For very short texts, traditional analysis might be sufficient
        if len(text.strip()) < 50 and self.performance_mode == "fast":
            return False
        
        return True
    
    def _merge_analysis_results(self, 
                               traditional: TextAnalysis, 
                               ai_analysis: Optional[NLPAnalysis] = None) -> AdvancedTextAnalysis:
        """Merge traditional and AI analysis results."""
        
        if ai_analysis:
            # Full AI-enhanced analysis
            return AdvancedTextAnalysis(
                # Traditional metrics
                word_count=traditional.word_count,
                character_count=traditional.character_count,
                sentence_count=traditional.sentence_count,
                paragraph_count=traditional.paragraph_count,
                avg_word_length=traditional.avg_word_length,
                readability_score=traditional.readability_score,
                common_words=traditional.common_words,
                sentiment_score=traditional.sentiment_score,
                processing_time=traditional.processing_time + ai_analysis.processing_time,
                
                # AI-enhanced metrics
                language=ai_analysis.language,
                flesch_kincaid_grade=ai_analysis.flesch_kincaid_grade,
                gunning_fog=ai_analysis.gunning_fog,
                smog_index=ai_analysis.smog_index,
                coleman_liau=ai_analysis.coleman_liau,
                automated_readability=ai_analysis.automated_readability,
                
                # NLP insights
                named_entities=ai_analysis.named_entities,
                noun_phrases=ai_analysis.noun_phrases,
                topics=ai_analysis.topics,
                keywords=ai_analysis.keywords,
                emotion_scores=ai_analysis.emotion_scores,
                
                # Style metrics
                lexical_diversity=ai_analysis.lexical_diversity,
                syllable_complexity=ai_analysis.syllable_complexity,
                passive_voice_percentage=ai_analysis.passive_voice_percentage,
                semantic_similarity_score=ai_analysis.semantic_similarity_score,
                
                # Metadata
                confidence_scores=ai_analysis.confidence_scores,
                model_versions=ai_analysis.model_versions,
                analysis_depth="comprehensive"
            )
        else:
            # Traditional analysis only with basic AI metrics filled with defaults
            return AdvancedTextAnalysis(
                # Traditional metrics
                word_count=traditional.word_count,
                character_count=traditional.character_count,
                sentence_count=traditional.sentence_count,
                paragraph_count=traditional.paragraph_count,
                avg_word_length=traditional.avg_word_length,
                readability_score=traditional.readability_score,
                common_words=traditional.common_words,
                sentiment_score=traditional.sentiment_score,
                processing_time=traditional.processing_time,
                
                # Basic AI metrics using textstat fallbacks
                language="en",
                flesch_kincaid_grade=textstat.flesch_kincaid_grade(traditional.__dict__.get('_original_text', '')),
                gunning_fog=textstat.gunning_fog(traditional.__dict__.get('_original_text', '')),
                smog_index=textstat.smog_index(traditional.__dict__.get('_original_text', '')),
                coleman_liau=textstat.coleman_liau_index(traditional.__dict__.get('_original_text', '')),
                automated_readability=textstat.automated_readability_index(traditional.__dict__.get('_original_text', '')),
                
                # Empty NLP insights
                named_entities=[],
                noun_phrases=[],
                topics=[],
                keywords=[],
                emotion_scores={},
                
                # Basic style metrics
                lexical_diversity=0.0,
                syllable_complexity=0.0,
                passive_voice_percentage=0.0,
                semantic_similarity_score=0.0,
                
                # Default metadata
                confidence_scores={"overall": 0.7, "sentiment": 0.5, "topics": 0.0},
                model_versions={"traditional": "1.0"},
                analysis_depth="basic"
            )
    
    async def analyze_text_async(self, 
                                text: str, 
                                store_result: bool = True,
                                analysis_depth: str = "auto") -> AdvancedTextAnalysis:
        """
        Asynchronous comprehensive text analysis.
        
        Args:
            text: Input text to analyze
            store_result: Whether to store results in database
            analysis_depth: "basic", "standard", "comprehensive", or "auto"
        """
        start_time = time.time()
        
        if not text or not isinstance(text, str):
            raise ValueError("Text must be a non-empty string")
        
        # Determine analysis depth
        if analysis_depth == "auto":
            analysis_depth = self.performance_mode
        
        # Always perform traditional analysis for backward compatibility
        traditional_analysis = self.text_processor.analyze_text(text, store_result=False)
        
        # Store original text for fallback metrics
        traditional_analysis.__dict__['_original_text'] = text
        
        # Perform AI analysis if conditions are met
        ai_analysis = None
        if self._should_use_ai_analysis(text) and analysis_depth in ["standard", "comprehensive"]:
            try:
                ai_start = time.time()
                ai_analysis = await self.nlp_processor.analyze_text_async(text)
                ai_time = time.time() - ai_start
                
                # Skip AI if it's taking too long for the performance mode
                threshold_time = self.performance_thresholds[self.performance_mode]["timeout"]
                if ai_time > threshold_time and self.performance_mode == "fast":
                    logger.warning(f"AI analysis took {ai_time:.3f}s, exceeding threshold {threshold_time}s")
                    ai_analysis = None
            except Exception as e:
                logger.error(f"AI analysis failed: {e}")
                ai_analysis = None
        
        # Merge results
        final_analysis = self._merge_analysis_results(traditional_analysis, ai_analysis)
        
        # Store extended results if requested
        if store_result:
            doc_id = await self._store_advanced_analysis(text, final_analysis)
            final_analysis.__dict__['doc_id'] = doc_id
            
            # Record performance metrics
            await self._record_performance(
                doc_id, 
                final_analysis.analysis_depth,
                final_analysis.processing_time,
                len(text),
                False  # cache_hit - would need additional logic to determine
            )
        
        total_time = time.time() - start_time
        final_analysis.processing_time = total_time
        
        logger.info(f"Text analysis completed: {final_analysis.analysis_depth} depth in {total_time:.3f}s")
        return final_analysis
    
    def analyze_text(self, 
                    text: str, 
                    store_result: bool = True,
                    analysis_depth: str = "auto") -> AdvancedTextAnalysis:
        """Synchronous wrapper for comprehensive text analysis."""
        return asyncio.run(self.analyze_text_async(text, store_result, analysis_depth))
    
    async def _store_advanced_analysis(self, text: str, analysis: AdvancedTextAnalysis) -> str:
        """Store advanced analysis results in extended database schema."""
        doc_id = hashlib.sha256(text.encode()).hexdigest()[:16]
        
        # Prepare serializable data
        nlp_data = {}
        if analysis.analysis_depth == "comprehensive":
            nlp_data = {
                "named_entities": analysis.named_entities,
                "noun_phrases": analysis.noun_phrases,
                "topics": analysis.topics,
                "keywords": analysis.keywords,
                "emotion_scores": analysis.emotion_scores
            }
        
        advanced_metrics = {
            "language": analysis.language,
            "readability_metrics": {
                "flesch_kincaid_grade": analysis.flesch_kincaid_grade,
                "gunning_fog": analysis.gunning_fog,
                "smog_index": analysis.smog_index,
                "coleman_liau": analysis.coleman_liau,
                "automated_readability": analysis.automated_readability
            },
            "style_metrics": {
                "lexical_diversity": analysis.lexical_diversity,
                "syllable_complexity": analysis.syllable_complexity,
                "passive_voice_percentage": analysis.passive_voice_percentage,
                "semantic_similarity_score": analysis.semantic_similarity_score
            },
            "confidence_scores": analysis.confidence_scores
        }
        
        with sqlite3.connect(self.db_path) as conn:
            # Store in traditional table first
            traditional_data = json.dumps({
                'readability_score': analysis.readability_score,
                'sentiment_score': analysis.sentiment_score,
                'common_words': analysis.common_words,
                'avg_word_length': analysis.avg_word_length,
                'processing_time': analysis.processing_time
            })
            
            conn.execute("""
                INSERT OR REPLACE INTO text_documents 
                (doc_id, content, content_hash, word_count, character_count, processed_at, analysis_data)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (doc_id, text, hashlib.sha256(text.encode()).hexdigest(),
                 analysis.word_count, analysis.character_count, time.time(), traditional_data))
            
            # Store advanced analysis
            conn.execute("""
                INSERT OR REPLACE INTO ai_text_analysis
                (doc_id, nlp_analysis, advanced_metrics, analysis_depth, model_versions)
                VALUES (?, ?, ?, ?, ?)
            """, (doc_id, json.dumps(nlp_data), json.dumps(advanced_metrics),
                 analysis.analysis_depth, json.dumps(analysis.model_versions)))
            
            conn.commit()
        
        return doc_id
    
    async def _record_performance(self, 
                                 doc_id: str, 
                                 analysis_type: str,
                                 processing_time: float,
                                 text_length: int,
                                 cache_hit: bool):
        """Record performance metrics for monitoring and optimization."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO analysis_performance 
                (doc_id, analysis_type, processing_time, text_length, cache_hit)
                VALUES (?, ?, ?, ?, ?)
            """, (doc_id, analysis_type, processing_time, text_length, cache_hit))
            conn.commit()
    
    def get_advanced_analysis(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve stored advanced analysis by document ID."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT d.content, d.analysis_data, ai.nlp_analysis, ai.advanced_metrics,
                       ai.analysis_depth, ai.model_versions, ai.created_at
                FROM text_documents d
                LEFT JOIN ai_text_analysis ai ON d.doc_id = ai.doc_id
                WHERE d.doc_id = ?
            """, (doc_id,))
            
            row = cursor.fetchone()
            if not row:
                return None
            
            content, traditional_data, nlp_data, advanced_data, depth, models, created = row
            
            result = {
                'doc_id': doc_id,
                'content': content,
                'created_at': created,
                'analysis_depth': depth or "basic",
                'traditional_analysis': json.loads(traditional_data) if traditional_data else {},
                'nlp_analysis': json.loads(nlp_data) if nlp_data else {},
                'advanced_metrics': json.loads(advanced_data) if advanced_data else {},
                'model_versions': json.loads(models) if models else {}
            }
            
            return result
    
    def batch_analyze(self, 
                     texts: List[str], 
                     store_results: bool = True,
                     max_workers: int = 4) -> List[AdvancedTextAnalysis]:
        """Batch analyze multiple texts with performance optimization."""
        
        if not texts:
            return []
        
        start_time = time.time()
        
        async def batch_process():
            semaphore = asyncio.Semaphore(max_workers)
            
            async def process_with_semaphore(text):
                async with semaphore:
                    return await self.analyze_text_async(text, store_results)
            
            tasks = [process_with_semaphore(text) for text in texts]
            return await asyncio.gather(*tasks, return_exceptions=True)
        
        results = asyncio.run(batch_process())
        
        # Filter out exceptions and log them
        valid_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Batch analysis failed for text {i}: {result}")
            else:
                valid_results.append(result)
        
        batch_time = time.time() - start_time
        logger.info(f"Batch analysis: {len(valid_results)}/{len(texts)} texts completed in {batch_time:.3f}s")
        
        return valid_results
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get comprehensive performance statistics."""
        stats = {
            "traditional_processor": True,
            "ai_processor": self.nlp_processor is not None,
            "performance_mode": self.performance_mode,
            "database_path": self.db_path
        }
        
        # Get database statistics
        with sqlite3.connect(self.db_path) as conn:
            # Traditional documents count
            cursor = conn.execute("SELECT COUNT(*) FROM text_documents")
            stats["total_documents"] = cursor.fetchone()[0]
            
            # AI analysis count
            try:
                cursor = conn.execute("SELECT COUNT(*) FROM ai_text_analysis")
                stats["ai_analyses"] = cursor.fetchone()[0]
            except sqlite3.OperationalError:
                stats["ai_analyses"] = 0
            
            # Performance metrics
            try:
                cursor = conn.execute("""
                    SELECT analysis_type, COUNT(*), AVG(processing_time), AVG(text_length)
                    FROM analysis_performance
                    GROUP BY analysis_type
                """)
                performance_data = cursor.fetchall()
                stats["performance_by_type"] = {
                    row[0]: {
                        "count": row[1],
                        "avg_processing_time": row[2],
                        "avg_text_length": row[3]
                    }
                    for row in performance_data
                }
            except sqlite3.OperationalError:
                stats["performance_by_type"] = {}
        
        # AI processor stats
        if self.nlp_processor:
            stats["ai_performance"] = self.nlp_processor.get_performance_metrics()
        
        return stats
    
    def optimize_performance(self) -> Dict[str, Any]:
        """Analyze current performance and suggest optimizations."""
        stats = self.get_performance_stats()
        suggestions = []
        
        # Analyze processing times
        perf_data = stats.get("performance_by_type", {})
        
        for analysis_type, metrics in perf_data.items():
            avg_time = metrics["avg_processing_time"]
            
            if avg_time > 1.0:
                suggestions.append(f"Consider caching for {analysis_type} analysis (avg: {avg_time:.3f}s)")
            
            if analysis_type == "comprehensive" and avg_time > 2.0:
                suggestions.append("Consider reducing comprehensive analysis scope for better performance")
        
        # Check AI processor performance
        if self.nlp_processor:
            ai_metrics = self.nlp_processor.get_performance_metrics()
            if not ai_metrics.get("cache_available"):
                suggestions.append("Enable Redis caching for significant performance improvement")
        
        return {
            "current_stats": stats,
            "optimization_suggestions": suggestions,
            "recommended_performance_mode": self._recommend_performance_mode(stats)
        }
    
    def _recommend_performance_mode(self, stats: Dict[str, Any]) -> str:
        """Recommend optimal performance mode based on usage patterns."""
        perf_data = stats.get("performance_by_type", {})
        
        if not perf_data:
            return "balanced"
        
        avg_times = [metrics["avg_processing_time"] for metrics in perf_data.values()]
        
        if max(avg_times) < 0.1:
            return "comprehensive"  # Very fast, can afford comprehensive analysis
        elif max(avg_times) > 1.0:
            return "fast"  # Too slow, need to optimize
        else:
            return "balanced"  # Current performance is acceptable
    
    # Backward compatibility methods
    def clean_text(self, text: str) -> str:
        """Backward compatibility wrapper."""
        return self.text_processor.clean_text(text)
    
    def extract_words(self, text: str) -> List[str]:
        """Backward compatibility wrapper."""
        return self.text_processor.extract_words(text)
    
    def extract_sentences(self, text: str) -> List[str]:
        """Backward compatibility wrapper."""
        return self.text_processor.extract_sentences(text)
    
    def extract_paragraphs(self, text: str) -> List[str]:
        """Backward compatibility wrapper."""
        return self.text_processor.extract_paragraphs(text)
    
    def calculate_readability(self, text: str) -> float:
        """Backward compatibility wrapper."""
        return self.text_processor.calculate_readability(text)
    
    def analyze_sentiment(self, text: str) -> float:
        """Backward compatibility wrapper."""
        return self.text_processor.analyze_sentiment(text)
    
    def search_documents_by_word(self, word: str) -> List[Dict]:
        """Backward compatibility wrapper.""" 
        return self.text_processor.search_documents_by_word(word)
    
    def get_document_analysis(self, doc_id: str) -> Optional[Dict]:
        """Enhanced version that returns advanced analysis if available."""
        advanced = self.get_advanced_analysis(doc_id)
        if advanced:
            return advanced
        return self.text_processor.get_document_analysis(doc_id)