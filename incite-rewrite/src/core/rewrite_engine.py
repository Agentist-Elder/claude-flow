"""
AI-powered rewrite engine with context-aware suggestions and style enhancement.
Provides intelligent text improvement suggestions using transformer models.
"""

import asyncio
import time
import logging
from typing import Dict, List, Tuple, Optional, Any, Union
from dataclasses import dataclass
from enum import Enum
import json
import hashlib

import spacy
from transformers import pipeline, T5Tokenizer, T5ForConditionalGeneration
import torch
from sentence_transformers import SentenceTransformer
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
import redis

from .nlp_processor import NLPProcessor
from .text_analyzer import TextAnalyzer, AdvancedTextAnalysis

logger = logging.getLogger(__name__)

class ImprovementType(Enum):
    """Types of text improvements."""
    CLARITY = "clarity"
    CONCISENESS = "conciseness"
    TONE = "tone"
    GRAMMAR = "grammar"
    VOCABULARY = "vocabulary"
    STRUCTURE = "structure"
    READABILITY = "readability"
    STYLE = "style"

@dataclass
class RewriteSuggestion:
    """A single text improvement suggestion."""
    original_text: str
    suggested_text: str
    improvement_type: ImprovementType
    confidence: float  # 0.0 to 1.0
    reason: str
    start_position: int
    end_position: int
    impact_score: float  # Expected improvement impact

@dataclass
class RewriteOptions:
    """Options for text rewriting."""
    target_tone: str = "neutral"  # neutral, formal, casual, persuasive, etc.
    target_reading_level: str = "general"  # elementary, middle, high, college, graduate
    improve_clarity: bool = True
    improve_conciseness: bool = True
    fix_grammar: bool = True
    enhance_vocabulary: bool = False
    preserve_meaning: bool = True
    max_suggestions: int = 10

@dataclass
class RewriteResult:
    """Complete rewrite analysis and suggestions."""
    original_text: str
    suggestions: List[RewriteSuggestion]
    overall_score: float  # Current text quality score
    potential_improvement: float  # Potential improvement score
    processing_time: float
    options_used: RewriteOptions
    analysis_metadata: Dict[str, Any]

class RewriteEngine:
    """
    AI-powered text rewriting engine with multiple improvement strategies.
    Provides context-aware suggestions for text enhancement.
    """
    
    def __init__(self,
                 text_analyzer: Optional[TextAnalyzer] = None,
                 model_name: str = "t5-small",
                 sentence_model: str = "all-MiniLM-L6-v2",
                 redis_host: str = "localhost",
                 redis_port: int = 6379,
                 enable_cache: bool = True):
        """
        Initialize the rewrite engine with AI models.
        
        Args:
            text_analyzer: TextAnalyzer instance for analysis
            model_name: T5 model for text generation
            sentence_model: Sentence transformer model
            redis_host: Redis host for caching
            redis_port: Redis port  
            enable_cache: Enable result caching
        """
        
        self.text_analyzer = text_analyzer or TextAnalyzer()
        self.model_name = model_name
        self.sentence_model_name = sentence_model
        self.enable_cache = enable_cache
        
        # Initialize models
        self._init_models()
        
        # Initialize caching
        self._init_cache(redis_host, redis_port)
        
        # Predefined improvement patterns
        self._init_improvement_patterns()
        
        logger.info(f"RewriteEngine initialized with model: {model_name}")
    
    def _init_models(self):
        """Initialize AI models for text rewriting."""
        try:
            # T5 model for text generation and paraphrasing
            self.tokenizer = T5Tokenizer.from_pretrained(self.model_name)
            self.t5_model = T5ForConditionalGeneration.from_pretrained(self.model_name)
            
            # Sentence transformer for semantic similarity
            self.sentence_transformer = SentenceTransformer(self.sentence_model_name)
            
            # Grammar correction pipeline
            self.grammar_pipeline = pipeline(
                "text2text-generation",
                model="grammarly/coedit-large",
                tokenizer="grammarly/coedit-large",
                device=-1  # Use CPU for stability
            )
            
            # Style transfer pipelines
            self.paraphrase_pipeline = pipeline(
                "text2text-generation",
                model="tuner007/pegasus_paraphrase",
                tokenizer="tuner007/pegasus_paraphrase",
                device=-1
            )
            
        except Exception as e:
            logger.error(f"Error initializing rewrite models: {e}")
            # Fallback to basic models
            self._init_fallback_models()
    
    def _init_fallback_models(self):
        """Initialize basic fallback models if advanced models fail."""
        logger.warning("Using fallback models for text rewriting")
        
        # Use basic sentence transformer
        try:
            self.sentence_transformer = SentenceTransformer('all-MiniLM-L6-v2')
        except Exception:
            self.sentence_transformer = None
        
        # Disable advanced features
        self.t5_model = None
        self.tokenizer = None
        self.grammar_pipeline = None
        self.paraphrase_pipeline = None
    
    def _init_cache(self, host: str, port: int):
        """Initialize Redis cache for rewrite suggestions."""
        if not self.enable_cache:
            self.redis_client = None
            return
        
        try:
            self.redis_client = redis.Redis(host=host, port=port, decode_responses=True)
            self.redis_client.ping()
            logger.info("Redis cache initialized for rewrite engine")
        except Exception as e:
            logger.warning(f"Redis cache not available: {e}")
            self.redis_client = None
    
    def _init_improvement_patterns(self):
        """Initialize patterns for different types of text improvements."""
        
        # Common wordy phrases and their concise alternatives
        self.conciseness_patterns = {
            "in order to": "to",
            "due to the fact that": "because",
            "in spite of the fact that": "although",
            "at this point in time": "now",
            "for the reason that": "because",
            "in the event that": "if",
            "with regard to": "regarding",
            "in the near future": "soon",
            "at the present time": "now",
            "make an attempt": "try",
            "take into consideration": "consider",
            "come to a conclusion": "conclude",
            "in close proximity to": "near",
            "prior to": "before",
            "subsequent to": "after"
        }
        
        # Weak words that can be strengthened
        self.vocabulary_enhancements = {
            "very good": "excellent",
            "very bad": "terrible", 
            "very big": "enormous",
            "very small": "tiny",
            "very happy": "ecstatic",
            "very sad": "devastated",
            "very tired": "exhausted",
            "very angry": "furious",
            "very surprised": "astonished",
            "very funny": "hilarious",
            "sort of": "somewhat",
            "kind of": "rather",
            "a lot": "many",
            "got": "received/obtained",
            "went": "traveled/proceeded"
        }
        
        # Passive voice patterns (simplified)
        self.passive_indicators = [
            "was", "were", "been", "being", "is", "are", "am"
        ]
        
        # Formal tone replacements
        self.formality_upgrades = {
            "can't": "cannot",
            "won't": "will not", 
            "don't": "do not",
            "isn't": "is not",
            "aren't": "are not",
            "wasn't": "was not",
            "weren't": "were not",
            "hasn't": "has not",
            "haven't": "have not",
            "didn't": "did not",
            "doesn't": "does not",
            "shouldn't": "should not",
            "wouldn't": "would not",
            "couldn't": "could not"
        }
    
    def _get_cache_key(self, text: str, options: RewriteOptions) -> str:
        """Generate cache key for rewrite suggestions."""
        options_str = f"{options.target_tone}_{options.target_reading_level}_{options.improve_clarity}_{options.improve_conciseness}"
        text_hash = hashlib.md5((text + options_str).encode()).hexdigest()
        return f"rewrite:{text_hash}"
    
    def _get_cached_result(self, cache_key: str) -> Optional[RewriteResult]:
        """Retrieve cached rewrite result."""
        if not self.redis_client:
            return None
        
        try:
            cached = self.redis_client.get(cache_key)
            if cached:
                data = json.loads(cached)
                # Reconstruct RewriteResult object
                suggestions = [
                    RewriteSuggestion(
                        original_text=s['original_text'],
                        suggested_text=s['suggested_text'],
                        improvement_type=ImprovementType(s['improvement_type']),
                        confidence=s['confidence'],
                        reason=s['reason'],
                        start_position=s['start_position'],
                        end_position=s['end_position'],
                        impact_score=s['impact_score']
                    ) for s in data['suggestions']
                ]
                
                return RewriteResult(
                    original_text=data['original_text'],
                    suggestions=suggestions,
                    overall_score=data['overall_score'],
                    potential_improvement=data['potential_improvement'],
                    processing_time=data['processing_time'],
                    options_used=RewriteOptions(**data['options_used']),
                    analysis_metadata=data['analysis_metadata']
                )
        except Exception as e:
            logger.warning(f"Cache retrieval error: {e}")
        
        return None
    
    def _cache_result(self, cache_key: str, result: RewriteResult):
        """Cache rewrite result."""
        if not self.redis_client:
            return
        
        try:
            # Convert to serializable format
            data = {
                'original_text': result.original_text,
                'suggestions': [
                    {
                        'original_text': s.original_text,
                        'suggested_text': s.suggested_text,
                        'improvement_type': s.improvement_type.value,
                        'confidence': s.confidence,
                        'reason': s.reason,
                        'start_position': s.start_position,
                        'end_position': s.end_position,
                        'impact_score': s.impact_score
                    } for s in result.suggestions
                ],
                'overall_score': result.overall_score,
                'potential_improvement': result.potential_improvement,
                'processing_time': result.processing_time,
                'options_used': result.options_used.__dict__,
                'analysis_metadata': result.analysis_metadata
            }
            
            self.redis_client.setex(cache_key, 3600, json.dumps(data))
        except Exception as e:
            logger.warning(f"Cache storage error: {e}")
    
    def _find_conciseness_improvements(self, text: str) -> List[RewriteSuggestion]:
        """Find opportunities to make text more concise."""
        suggestions = []
        
        for wordy, concise in self.conciseness_patterns.items():
            if wordy.lower() in text.lower():
                # Find all occurrences
                start = 0
                while True:
                    pos = text.lower().find(wordy.lower(), start)
                    if pos == -1:
                        break
                    
                    suggestion = RewriteSuggestion(
                        original_text=text[pos:pos+len(wordy)],
                        suggested_text=concise,
                        improvement_type=ImprovementType.CONCISENESS,
                        confidence=0.9,
                        reason=f"Replace wordy phrase '{wordy}' with more concise '{concise}'",
                        start_position=pos,
                        end_position=pos + len(wordy),
                        impact_score=0.3
                    )
                    suggestions.append(suggestion)
                    start = pos + len(wordy)
        
        return suggestions
    
    def _find_vocabulary_improvements(self, text: str) -> List[RewriteSuggestion]:
        """Find opportunities to improve vocabulary."""
        suggestions = []
        
        for weak, strong in self.vocabulary_enhancements.items():
            if weak.lower() in text.lower():
                start = 0
                while True:
                    pos = text.lower().find(weak.lower(), start)
                    if pos == -1:
                        break
                    
                    suggestion = RewriteSuggestion(
                        original_text=text[pos:pos+len(weak)],
                        suggested_text=strong,
                        improvement_type=ImprovementType.VOCABULARY,
                        confidence=0.8,
                        reason=f"Replace weak phrase '{weak}' with stronger '{strong}'",
                        start_position=pos,
                        end_position=pos + len(weak),
                        impact_score=0.4
                    )
                    suggestions.append(suggestion)
                    start = pos + len(weak)
        
        return suggestions
    
    def _find_tone_improvements(self, text: str, target_tone: str) -> List[RewriteSuggestion]:
        """Find opportunities to adjust tone."""
        suggestions = []
        
        if target_tone == "formal":
            for informal, formal in self.formality_upgrades.items():
                if informal in text:
                    start = 0
                    while True:
                        pos = text.find(informal, start)
                        if pos == -1:
                            break
                        
                        suggestion = RewriteSuggestion(
                            original_text=informal,
                            suggested_text=formal,
                            improvement_type=ImprovementType.TONE,
                            confidence=0.9,
                            reason=f"Use formal '{formal}' instead of informal '{informal}'",
                            start_position=pos,
                            end_position=pos + len(informal),
                            impact_score=0.2
                        )
                        suggestions.append(suggestion)
                        start = pos + len(informal)
        
        return suggestions
    
    async def _ai_paraphrase_suggestions(self, text: str, max_suggestions: int = 3) -> List[RewriteSuggestion]:
        """Generate AI-powered paraphrase suggestions."""
        suggestions = []
        
        if not self.paraphrase_pipeline:
            return suggestions
        
        try:
            # Split text into sentences for better paraphrasing
            sentences = self.text_analyzer.extract_sentences(text)
            
            for i, sentence in enumerate(sentences[:max_suggestions]):
                if len(sentence.strip()) < 10:  # Skip very short sentences
                    continue
                
                # Generate paraphrase
                paraphrases = self.paraphrase_pipeline(sentence, max_length=150, num_return_sequences=1)
                
                if paraphrases and len(paraphrases) > 0:
                    paraphrased = paraphrases[0]['generated_text']
                    
                    # Calculate semantic similarity to ensure meaning preservation
                    if self.sentence_transformer:
                        orig_embedding = self.sentence_transformer.encode([sentence])
                        para_embedding = self.sentence_transformer.encode([paraphrased])
                        similarity = cosine_similarity(orig_embedding, para_embedding)[0][0]
                        
                        if similarity > 0.7:  # High semantic similarity threshold
                            # Find position in original text
                            start_pos = text.find(sentence)
                            if start_pos != -1:
                                suggestion = RewriteSuggestion(
                                    original_text=sentence,
                                    suggested_text=paraphrased,
                                    improvement_type=ImprovementType.STYLE,
                                    confidence=min(0.9, similarity),
                                    reason="AI-generated alternative phrasing for variety",
                                    start_position=start_pos,
                                    end_position=start_pos + len(sentence),
                                    impact_score=0.5
                                )
                                suggestions.append(suggestion)
            
        except Exception as e:
            logger.error(f"AI paraphrase generation failed: {e}")
        
        return suggestions
    
    def _calculate_text_quality_score(self, analysis: AdvancedTextAnalysis) -> float:
        """Calculate overall text quality score from analysis."""
        factors = []
        
        # Readability factor (0-1, higher is better up to a point)
        if analysis.readability_score > 0:
            readability_factor = min(1.0, analysis.readability_score / 70.0)
            factors.append(readability_factor * 0.3)
        
        # Sentence length factor (penalize very long or very short)
        if analysis.avg_sentence_length > 0:
            optimal_length = 20  # words
            length_factor = 1.0 - abs(analysis.avg_sentence_length - optimal_length) / optimal_length
            length_factor = max(0.0, min(1.0, length_factor))
            factors.append(length_factor * 0.2)
        
        # Lexical diversity factor  
        factors.append(min(1.0, analysis.lexical_diversity * 2) * 0.2)
        
        # Passive voice penalty
        passive_penalty = max(0.0, 1.0 - analysis.passive_voice_percentage / 30.0)
        factors.append(passive_penalty * 0.1)
        
        # Semantic coherence
        factors.append(analysis.semantic_similarity_score * 0.2)
        
        return sum(factors) if factors else 0.5
    
    async def analyze_and_suggest_async(self, text: str, options: RewriteOptions) -> RewriteResult:
        """Asynchronously analyze text and generate improvement suggestions."""
        start_time = time.time()
        
        # Check cache first
        cache_key = self._get_cache_key(text, options)
        cached_result = self._get_cached_result(cache_key)
        if cached_result:
            logger.info("Using cached rewrite suggestions")
            return cached_result
        
        # Perform text analysis
        analysis = await self.text_analyzer.analyze_text_async(text, store_result=False)
        
        # Calculate current quality score
        overall_score = self._calculate_text_quality_score(analysis)
        
        all_suggestions = []
        
        # Find pattern-based improvements
        if options.improve_conciseness:
            conciseness_suggestions = self._find_conciseness_improvements(text)
            all_suggestions.extend(conciseness_suggestions)
        
        if options.enhance_vocabulary:
            vocab_suggestions = self._find_vocabulary_improvements(text)
            all_suggestions.extend(vocab_suggestions)
        
        if options.target_tone != "neutral":
            tone_suggestions = self._find_tone_improvements(text, options.target_tone)
            all_suggestions.extend(tone_suggestions)
        
        # Add AI-powered suggestions if available
        try:
            ai_suggestions = await self._ai_paraphrase_suggestions(text, max_suggestions=3)
            all_suggestions.extend(ai_suggestions)
        except Exception as e:
            logger.error(f"AI suggestion generation failed: {e}")
        
        # Remove duplicates and sort by impact score
        unique_suggestions = []
        seen_positions = set()
        
        for suggestion in sorted(all_suggestions, key=lambda x: x.impact_score, reverse=True):
            pos_key = (suggestion.start_position, suggestion.end_position)
            if pos_key not in seen_positions:
                unique_suggestions.append(suggestion)
                seen_positions.add(pos_key)
        
        # Limit to max suggestions
        final_suggestions = unique_suggestions[:options.max_suggestions]
        
        # Calculate potential improvement
        potential_improvement = sum(s.impact_score * s.confidence for s in final_suggestions) / 10.0
        potential_improvement = min(1.0, potential_improvement)
        
        processing_time = time.time() - start_time
        
        result = RewriteResult(
            original_text=text,
            suggestions=final_suggestions,
            overall_score=overall_score,
            potential_improvement=potential_improvement,
            processing_time=processing_time,
            options_used=options,
            analysis_metadata={
                "analysis_depth": analysis.analysis_depth,
                "word_count": analysis.word_count,
                "readability_score": analysis.readability_score,
                "sentiment_score": analysis.sentiment_score,
                "ai_models_used": bool(self.paraphrase_pipeline),
                "total_patterns_checked": len(self.conciseness_patterns) + len(self.vocabulary_enhancements)
            }
        )
        
        # Cache the result
        self._cache_result(cache_key, result)
        
        logger.info(f"Rewrite analysis completed: {len(final_suggestions)} suggestions in {processing_time:.3f}s")
        return result
    
    def analyze_and_suggest(self, text: str, options: Optional[RewriteOptions] = None) -> RewriteResult:
        """Synchronous wrapper for text rewrite analysis."""
        if options is None:
            options = RewriteOptions()
        
        return asyncio.run(self.analyze_and_suggest_async(text, options))
    
    def apply_suggestions(self, text: str, suggestions: List[RewriteSuggestion], apply_all: bool = False) -> str:
        """Apply selected suggestions to text."""
        if not suggestions:
            return text
        
        # Sort suggestions by position (descending) to avoid position shifting
        sorted_suggestions = sorted(suggestions, key=lambda x: x.start_position, reverse=True)
        
        result_text = text
        applied_count = 0
        
        for suggestion in sorted_suggestions:
            if apply_all or suggestion.confidence > 0.8:
                # Apply the suggestion
                before = result_text[:suggestion.start_position]
                after = result_text[suggestion.end_position:]
                result_text = before + suggestion.suggested_text + after
                applied_count += 1
        
        logger.info(f"Applied {applied_count}/{len(suggestions)} suggestions")
        return result_text
    
    def get_improvement_summary(self, result: RewriteResult) -> Dict[str, Any]:
        """Generate a summary of potential improvements."""
        by_type = {}
        total_impact = 0
        
        for suggestion in result.suggestions:
            imp_type = suggestion.improvement_type.value
            if imp_type not in by_type:
                by_type[imp_type] = {
                    "count": 0,
                    "avg_confidence": 0.0,
                    "total_impact": 0.0
                }
            
            by_type[imp_type]["count"] += 1
            by_type[imp_type]["total_impact"] += suggestion.impact_score * suggestion.confidence
            total_impact += suggestion.impact_score * suggestion.confidence
        
        # Calculate averages
        for imp_type in by_type:
            by_type[imp_type]["avg_confidence"] = sum(
                s.confidence for s in result.suggestions 
                if s.improvement_type.value == imp_type
            ) / by_type[imp_type]["count"]
        
        return {
            "original_score": result.overall_score,
            "potential_score": min(1.0, result.overall_score + result.potential_improvement),
            "total_suggestions": len(result.suggestions),
            "by_type": by_type,
            "estimated_improvement": result.potential_improvement,
            "processing_time": result.processing_time,
            "top_recommendation": result.suggestions[0].improvement_type.value if result.suggestions else None
        }
    
    def batch_analyze(self, texts_and_options: List[Tuple[str, RewriteOptions]]) -> List[RewriteResult]:
        """Batch analyze multiple texts with their respective options."""
        
        async def batch_process():
            tasks = [
                self.analyze_and_suggest_async(text, options) 
                for text, options in texts_and_options
            ]
            return await asyncio.gather(*tasks, return_exceptions=True)
        
        results = asyncio.run(batch_process())
        
        # Filter out exceptions
        valid_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Batch rewrite analysis failed for item {i}: {result}")
            else:
                valid_results.append(result)
        
        return valid_results