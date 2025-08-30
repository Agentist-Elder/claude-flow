"""
Advanced NLP processor with spaCy, transformers, and real ML algorithms.
Production-grade natural language processing for text analysis and improvement.
"""

import spacy
import nltk
import time
import asyncio
import logging
import functools
from typing import Dict, List, Tuple, Optional, Any, Union
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager

import numpy as np
import pandas as pd
from textblob import TextBlob
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import KMeans
from sklearn.metrics.pairwise import cosine_similarity
from transformers import pipeline, AutoTokenizer, AutoModel
import torch
import gensim
from gensim import corpora
from gensim.models import LdaModel
import textstat
import langdetect
from sentence_transformers import SentenceTransformer
import redis
import json
import hashlib

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass 
class NLPAnalysis:
    """Comprehensive NLP analysis results."""
    # Basic metrics
    language: str
    word_count: int
    sentence_count: int
    paragraph_count: int
    
    # Advanced linguistic features
    pos_tags: List[Tuple[str, str]]
    named_entities: List[Dict[str, str]]
    noun_phrases: List[str]
    dependency_relations: List[Dict[str, Any]]
    
    # Readability metrics
    flesch_reading_ease: float
    flesch_kincaid_grade: float
    gunning_fog: float
    smog_index: float
    coleman_liau: float
    automated_readability: float
    
    # Sentiment and emotion
    sentiment_polarity: float  # -1 to 1
    sentiment_subjectivity: float  # 0 to 1
    emotion_scores: Dict[str, float]
    
    # Semantic analysis
    topics: List[Dict[str, Any]]
    keywords: List[Tuple[str, float]]
    semantic_similarity_score: float
    
    # Style and complexity
    lexical_diversity: float
    avg_sentence_length: float
    syllable_complexity: float
    passive_voice_percentage: float
    
    # Processing metadata
    processing_time: float
    model_versions: Dict[str, str]
    confidence_scores: Dict[str, float]


class NLPProcessor:
    """
    Production-grade NLP processor with multiple ML models and caching.
    Implements real AI algorithms for comprehensive text analysis.
    """
    
    def __init__(self, 
                 spacy_model: str = "en_core_web_sm",
                 transformer_model: str = "distilbert-base-uncased", 
                 sentence_model: str = "all-MiniLM-L6-v2",
                 redis_host: str = "localhost",
                 redis_port: int = 6379,
                 cache_ttl: int = 3600):
        """Initialize NLP processor with multiple AI models."""
        
        self.spacy_model_name = spacy_model
        self.transformer_model_name = transformer_model
        self.sentence_model_name = sentence_model
        
        # Initialize models
        self._init_models()
        
        # Initialize caching
        self._init_cache(redis_host, redis_port, cache_ttl)
        
        # Thread pool for parallel processing
        self.executor = ThreadPoolExecutor(max_workers=4)
        
        logger.info(f"NLP Processor initialized with models: spaCy={spacy_model}, transformer={transformer_model}")
    
    def _init_models(self):
        """Initialize all ML models."""
        try:
            # SpaCy model for linguistic analysis
            self.nlp = spacy.load(self.spacy_model_name)
            
            # Transformer models for semantic analysis
            self.sentiment_pipeline = pipeline(
                "sentiment-analysis",
                model="cardiffnlp/twitter-roberta-base-sentiment-latest",
                return_all_scores=True
            )
            
            self.emotion_pipeline = pipeline(
                "text-classification",
                model="j-hartmann/emotion-english-distilroberta-base",
                return_all_scores=True
            )
            
            # Sentence transformer for semantic similarity
            self.sentence_transformer = SentenceTransformer(self.sentence_model_name)
            
            # Download required NLTK data
            try:
                nltk.data.find('tokenizers/punkt')
            except LookupError:
                nltk.download('punkt')
            
            try:
                nltk.data.find('corpora/stopwords')
            except LookupError:
                nltk.download('stopwords')
                
            try:
                nltk.data.find('taggers/averaged_perceptron_tagger')
            except LookupError:
                nltk.download('averaged_perceptron_tagger')
            
            # TF-IDF vectorizer for keyword extraction
            self.tfidf = TfidfVectorizer(
                max_features=1000,
                stop_words='english',
                ngram_range=(1, 2)
            )
            
        except Exception as e:
            logger.error(f"Error initializing models: {e}")
            raise
    
    def _init_cache(self, host: str, port: int, ttl: int):
        """Initialize Redis cache for performance optimization."""
        try:
            self.redis_client = redis.Redis(host=host, port=port, decode_responses=True)
            self.cache_ttl = ttl
            # Test connection
            self.redis_client.ping()
            logger.info("Redis cache initialized successfully")
        except Exception as e:
            logger.warning(f"Redis cache not available: {e}. Falling back to no caching.")
            self.redis_client = None
    
    def _get_cache_key(self, text: str, analysis_type: str = "full") -> str:
        """Generate cache key for text analysis."""
        text_hash = hashlib.md5(text.encode()).hexdigest()
        return f"nlp:{analysis_type}:{text_hash}"
    
    def _get_cached_result(self, cache_key: str) -> Optional[Dict]:
        """Retrieve cached analysis result."""
        if not self.redis_client:
            return None
        
        try:
            cached = self.redis_client.get(cache_key)
            if cached:
                return json.loads(cached)
        except Exception as e:
            logger.warning(f"Cache retrieval error: {e}")
        
        return None
    
    def _cache_result(self, cache_key: str, result: Dict):
        """Cache analysis result."""
        if not self.redis_client:
            return
        
        try:
            self.redis_client.setex(
                cache_key,
                self.cache_ttl,
                json.dumps(result, default=str)
            )
        except Exception as e:
            logger.warning(f"Cache storage error: {e}")
    
    @functools.lru_cache(maxsize=128)
    def detect_language(self, text: str) -> str:
        """Detect text language using ML."""
        try:
            if len(text.strip()) < 10:
                return "en"  # Default for short text
            return langdetect.detect(text)
        except Exception:
            return "en"
    
    def extract_linguistic_features(self, text: str) -> Dict[str, Any]:
        """Extract comprehensive linguistic features using spaCy."""
        doc = self.nlp(text)
        
        # POS tags
        pos_tags = [(token.text, token.pos_) for token in doc]
        
        # Named entities
        named_entities = [
            {
                "text": ent.text,
                "label": ent.label_,
                "start": ent.start_char,
                "end": ent.end_char,
                "description": spacy.explain(ent.label_)
            }
            for ent in doc.ents
        ]
        
        # Noun phrases
        noun_phrases = [chunk.text for chunk in doc.noun_chunks]
        
        # Dependency relations
        dependency_relations = [
            {
                "text": token.text,
                "dep": token.dep_,
                "head": token.head.text,
                "children": [child.text for child in token.children]
            }
            for token in doc
        ]
        
        return {
            "pos_tags": pos_tags,
            "named_entities": named_entities,
            "noun_phrases": noun_phrases,
            "dependency_relations": dependency_relations,
            "sentences": [sent.text for sent in doc.sents]
        }
    
    def calculate_advanced_readability(self, text: str) -> Dict[str, float]:
        """Calculate multiple readability metrics using textstat."""
        return {
            "flesch_reading_ease": textstat.flesch_reading_ease(text),
            "flesch_kincaid_grade": textstat.flesch_kincaid_grade(text),
            "gunning_fog": textstat.gunning_fog(text),
            "smog_index": textstat.smog_index(text),
            "coleman_liau": textstat.coleman_liau_index(text),
            "automated_readability": textstat.automated_readability_index(text),
            "dale_chall": textstat.dale_chall_readability_score(text),
            "difficult_words": textstat.difficult_words(text),
            "linsear_write": textstat.linsear_write_formula(text),
            "text_standard": textstat.text_standard(text, float_output=True)
        }
    
    def analyze_sentiment_emotion(self, text: str) -> Dict[str, Any]:
        """Advanced sentiment and emotion analysis using transformers."""
        # Sentiment analysis
        sentiment_results = self.sentiment_pipeline(text)
        sentiment_scores = {result['label']: result['score'] for result in sentiment_results[0]}
        
        # Convert to polarity scale (-1 to 1)
        if 'NEGATIVE' in sentiment_scores and 'POSITIVE' in sentiment_scores:
            polarity = sentiment_scores['POSITIVE'] - sentiment_scores['NEGATIVE']
        else:
            polarity = 0.0
        
        # Emotion analysis
        emotion_results = self.emotion_pipeline(text)
        emotion_scores = {result['label']: result['score'] for result in emotion_results[0]}
        
        # TextBlob for additional sentiment features
        blob = TextBlob(text)
        
        return {
            "sentiment_polarity": polarity,
            "sentiment_subjectivity": blob.sentiment.subjectivity,
            "emotion_scores": emotion_scores,
            "transformer_sentiment": sentiment_scores,
            "textblob_polarity": blob.sentiment.polarity
        }
    
    def extract_topics_keywords(self, text: str, num_topics: int = 3) -> Dict[str, Any]:
        """Extract topics and keywords using LDA and TF-IDF."""
        # Preprocess text
        doc = self.nlp(text)
        # Keep only meaningful tokens (nouns, verbs, adjectives)
        tokens = [
            token.lemma_.lower() 
            for token in doc 
            if not token.is_stop and not token.is_punct and token.pos_ in ['NOUN', 'VERB', 'ADJ']
            and len(token.text) > 2
        ]
        
        if len(tokens) < 5:  # Not enough tokens for meaningful analysis
            return {
                "topics": [],
                "keywords": [],
                "topic_coherence": 0.0
            }
        
        try:
            # LDA topic modeling
            dictionary = corpora.Dictionary([tokens])
            corpus = [dictionary.doc2bow(tokens)]
            
            lda_model = LdaModel(
                corpus=corpus,
                id2word=dictionary,
                num_topics=min(num_topics, len(tokens) // 2),
                random_state=42,
                passes=10,
                alpha='auto',
                per_word_topics=True
            )
            
            # Extract topics
            topics = []
            for idx, topic in lda_model.print_topics():
                topic_words = [word.split('*')[1].replace('"', '').strip() for word in topic.split(' + ')]
                topics.append({
                    "id": idx,
                    "words": topic_words[:5],  # Top 5 words
                    "coherence": 0.0  # Simplified for this implementation
                })
            
            # TF-IDF keywords
            sentences = [sent.text for sent in doc.sents]
            if len(sentences) > 0:
                tfidf_matrix = self.tfidf.fit_transform(sentences)
                feature_names = self.tfidf.get_feature_names_out()
                scores = tfidf_matrix.sum(axis=0).A1
                keyword_scores = list(zip(feature_names, scores))
                keywords = sorted(keyword_scores, key=lambda x: x[1], reverse=True)[:10]
            else:
                keywords = []
            
            return {
                "topics": topics,
                "keywords": keywords,
                "topic_coherence": sum(topic.get("coherence", 0) for topic in topics) / len(topics) if topics else 0.0
            }
            
        except Exception as e:
            logger.warning(f"Topic modeling error: {e}")
            return {
                "topics": [],
                "keywords": [],
                "topic_coherence": 0.0
            }
    
    def calculate_style_metrics(self, text: str) -> Dict[str, float]:
        """Calculate advanced style and complexity metrics."""
        doc = self.nlp(text)
        
        # Word-level metrics
        words = [token for token in doc if not token.is_punct and not token.is_space]
        sentences = list(doc.sents)
        
        # Lexical diversity (Type-Token Ratio)
        unique_words = set(token.lemma_.lower() for token in words if not token.is_stop)
        lexical_diversity = len(unique_words) / len(words) if words else 0.0
        
        # Average sentence length
        avg_sentence_length = len(words) / len(sentences) if sentences else 0.0
        
        # Syllable complexity
        syllable_counts = []
        for token in words:
            if token.is_alpha:
                syllables = textstat.syllable_count(token.text)
                syllable_counts.append(syllables)
        
        syllable_complexity = np.mean(syllable_counts) if syllable_counts else 0.0
        
        # Passive voice detection
        passive_count = 0
        for token in doc:
            if token.dep_ == "auxpass" or (token.dep_ == "nsubjpass"):
                passive_count += 1
        
        passive_voice_percentage = (passive_count / len(sentences)) * 100 if sentences else 0.0
        
        return {
            "lexical_diversity": lexical_diversity,
            "avg_sentence_length": avg_sentence_length,
            "syllable_complexity": syllable_complexity,
            "passive_voice_percentage": passive_voice_percentage
        }
    
    def calculate_semantic_similarity(self, text: str, reference_texts: List[str] = None) -> float:
        """Calculate semantic similarity using sentence transformers."""
        if not reference_texts:
            # If no reference, calculate internal coherence
            doc = self.nlp(text)
            sentences = [sent.text for sent in doc.sents if len(sent.text.strip()) > 10]
            
            if len(sentences) < 2:
                return 1.0  # Perfect coherence for single sentence
            
            # Calculate pairwise similarities between sentences
            embeddings = self.sentence_transformer.encode(sentences)
            similarity_matrix = cosine_similarity(embeddings)
            
            # Average similarity (excluding diagonal)
            mask = np.ones_like(similarity_matrix, dtype=bool)
            np.fill_diagonal(mask, False)
            return similarity_matrix[mask].mean()
        else:
            # Calculate similarity to reference texts
            all_texts = [text] + reference_texts
            embeddings = self.sentence_transformer.encode(all_texts)
            
            target_embedding = embeddings[0].reshape(1, -1)
            reference_embeddings = embeddings[1:]
            
            similarities = cosine_similarity(target_embedding, reference_embeddings)
            return similarities.mean()
    
    async def analyze_text_async(self, text: str) -> NLPAnalysis:
        """Asynchronous text analysis with parallel processing."""
        start_time = time.time()
        
        # Check cache first
        cache_key = self._get_cache_key(text)
        cached_result = self._get_cached_result(cache_key)
        
        if cached_result:
            logger.info("Using cached analysis result")
            return NLPAnalysis(**cached_result)
        
        # Language detection
        language = self.detect_language(text)
        
        # Run parallel analysis tasks
        loop = asyncio.get_event_loop()
        
        # Create futures for parallel execution
        linguistic_future = loop.run_in_executor(
            self.executor, self.extract_linguistic_features, text
        )
        readability_future = loop.run_in_executor(
            self.executor, self.calculate_advanced_readability, text
        )
        sentiment_future = loop.run_in_executor(
            self.executor, self.analyze_sentiment_emotion, text
        )
        topics_future = loop.run_in_executor(
            self.executor, self.extract_topics_keywords, text
        )
        style_future = loop.run_in_executor(
            self.executor, self.calculate_style_metrics, text
        )
        similarity_future = loop.run_in_executor(
            self.executor, self.calculate_semantic_similarity, text
        )
        
        # Wait for all tasks to complete
        linguistic_features = await linguistic_future
        readability_metrics = await readability_future
        sentiment_emotion = await sentiment_future
        topics_keywords = await topics_future
        style_metrics = await style_future
        semantic_similarity = await similarity_future
        
        processing_time = time.time() - start_time
        
        # Compile analysis results
        analysis = NLPAnalysis(
            # Basic metrics
            language=language,
            word_count=len(linguistic_features["pos_tags"]),
            sentence_count=len(linguistic_features["sentences"]),
            paragraph_count=text.count('\n\n') + 1,
            
            # Linguistic features
            pos_tags=linguistic_features["pos_tags"][:50],  # Limit for serialization
            named_entities=linguistic_features["named_entities"],
            noun_phrases=linguistic_features["noun_phrases"][:20],
            dependency_relations=linguistic_features["dependency_relations"][:30],
            
            # Readability
            flesch_reading_ease=readability_metrics["flesch_reading_ease"],
            flesch_kincaid_grade=readability_metrics["flesch_kincaid_grade"],
            gunning_fog=readability_metrics["gunning_fog"],
            smog_index=readability_metrics["smog_index"],
            coleman_liau=readability_metrics["coleman_liau"],
            automated_readability=readability_metrics["automated_readability"],
            
            # Sentiment and emotion
            sentiment_polarity=sentiment_emotion["sentiment_polarity"],
            sentiment_subjectivity=sentiment_emotion["sentiment_subjectivity"],
            emotion_scores=sentiment_emotion["emotion_scores"],
            
            # Topics and keywords
            topics=topics_keywords["topics"],
            keywords=topics_keywords["keywords"],
            semantic_similarity_score=semantic_similarity,
            
            # Style metrics
            lexical_diversity=style_metrics["lexical_diversity"],
            avg_sentence_length=style_metrics["avg_sentence_length"],
            syllable_complexity=style_metrics["syllable_complexity"],
            passive_voice_percentage=style_metrics["passive_voice_percentage"],
            
            # Metadata
            processing_time=processing_time,
            model_versions={
                "spacy": self.spacy_model_name,
                "transformer": self.transformer_model_name,
                "sentence_transformer": self.sentence_model_name
            },
            confidence_scores={
                "overall": min(1.0, max(0.1, 1.0 - processing_time / 10.0)),
                "sentiment": max(sentiment_emotion["emotion_scores"].values()) if sentiment_emotion["emotion_scores"] else 0.5,
                "topics": topics_keywords["topic_coherence"]
            }
        )
        
        # Cache the result
        self._cache_result(cache_key, analysis.__dict__)
        
        logger.info(f"Text analysis completed in {processing_time:.3f}s")
        return analysis
    
    def analyze_text(self, text: str) -> NLPAnalysis:
        """Synchronous wrapper for text analysis."""
        return asyncio.run(self.analyze_text_async(text))
    
    def batch_analyze(self, texts: List[str], max_workers: int = 4) -> List[NLPAnalysis]:
        """Batch process multiple texts efficiently."""
        start_time = time.time()
        
        async def batch_process():
            semaphore = asyncio.Semaphore(max_workers)
            
            async def process_with_semaphore(text):
                async with semaphore:
                    return await self.analyze_text_async(text)
            
            tasks = [process_with_semaphore(text) for text in texts]
            return await asyncio.gather(*tasks)
        
        results = asyncio.run(batch_process())
        
        batch_time = time.time() - start_time
        logger.info(f"Batch analysis of {len(texts)} texts completed in {batch_time:.3f}s")
        
        return results
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get performance metrics for monitoring."""
        metrics = {
            "models_loaded": {
                "spacy": self.nlp is not None,
                "sentiment": hasattr(self, 'sentiment_pipeline'),
                "emotion": hasattr(self, 'emotion_pipeline'),
                "sentence_transformer": hasattr(self, 'sentence_transformer')
            },
            "cache_available": self.redis_client is not None,
            "executor_threads": self.executor._threads if self.executor._threads else 0
        }
        
        if self.redis_client:
            try:
                info = self.redis_client.info()
                metrics["cache_stats"] = {
                    "connected_clients": info.get("connected_clients", 0),
                    "used_memory": info.get("used_memory", 0),
                    "keyspace_hits": info.get("keyspace_hits", 0),
                    "keyspace_misses": info.get("keyspace_misses", 0)
                }
            except Exception as e:
                metrics["cache_stats"] = {"error": str(e)}
        
        return metrics
    
    def __del__(self):
        """Cleanup resources."""
        if hasattr(self, 'executor'):
            self.executor.shutdown(wait=True)