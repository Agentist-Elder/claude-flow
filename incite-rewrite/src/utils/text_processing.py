"""
Text processing utilities with validation and analysis.
London School TDD approach - testing real behavior and interactions.
"""

import re
import hashlib
import statistics
from typing import Dict, List, Optional, Tuple
from collections import Counter
import sqlite3
from dataclasses import dataclass
import time


@dataclass
class TextAnalysis:
    """Text analysis results."""
    word_count: int
    character_count: int
    sentence_count: int
    paragraph_count: int
    avg_word_length: float
    readability_score: float
    common_words: Dict[str, int]
    sentiment_score: float
    processing_time: float


class TextProcessor:
    """
    Text processing engine with real validation and database operations.
    Tests verify actual text processing behavior without mocks.
    """
    
    def __init__(self, db_path: str = ":memory:"):
        self.db_path = db_path
        self._init_database()
        self.stop_words = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 
            'for', 'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 
            'been', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 
            'would', 'could', 'should', 'may', 'might', 'must', 'can'
        }
    
    def _init_database(self) -> None:
        """Initialize text processing database."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS text_documents (
                    doc_id TEXT PRIMARY KEY,
                    content TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    word_count INTEGER,
                    character_count INTEGER,
                    processed_at REAL,
                    analysis_data TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS word_frequency (
                    doc_id TEXT,
                    word TEXT,
                    frequency INTEGER,
                    position_avg REAL,
                    FOREIGN KEY (doc_id) REFERENCES text_documents (doc_id)
                )
            """)
            conn.commit()
    
    def clean_text(self, text: str) -> str:
        """Clean and normalize text content."""
        if not isinstance(text, str):
            raise ValueError("Input must be a string")
        
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text.strip())
        
        # Normalize punctuation spacing
        text = re.sub(r'\s*([.!?])\s*', r'\1 ', text)
        text = re.sub(r'\s*([,;:])\s*', r'\1 ', text)
        
        # Remove special characters but keep basic punctuation
        text = re.sub(r'[^\w\s.!?,:;-]', '', text)
        
        return text.strip()
    
    def extract_words(self, text: str) -> List[str]:
        """Extract words from text with proper tokenization."""
        cleaned_text = self.clean_text(text)
        words = re.findall(r'\b[a-zA-Z]+\b', cleaned_text.lower())
        return [word for word in words if len(word) > 1]
    
    def extract_sentences(self, text: str) -> List[str]:
        """Extract sentences from text."""
        sentences = re.split(r'[.!?]+', text.strip())
        return [s.strip() for s in sentences if s.strip()]
    
    def extract_paragraphs(self, text: str) -> List[str]:
        """Extract paragraphs from text."""
        paragraphs = re.split(r'\n\s*\n', text.strip())
        return [p.strip() for p in paragraphs if p.strip()]
    
    def calculate_readability(self, text: str) -> float:
        """Calculate Flesch Reading Ease score."""
        sentences = self.extract_sentences(text)
        words = self.extract_words(text)
        
        if not sentences or not words:
            return 0.0
        
        # Count syllables (approximation)
        syllables = sum(self._count_syllables(word) for word in words)
        
        # Flesch Reading Ease formula
        if len(sentences) == 0 or len(words) == 0:
            return 0.0
        
        score = (206.835 - 
                1.015 * (len(words) / len(sentences)) - 
                84.6 * (syllables / len(words)))
        
        return max(0.0, min(100.0, score))
    
    def _count_syllables(self, word: str) -> int:
        """Approximate syllable count for a word."""
        word = word.lower()
        vowels = 'aeiouy'
        syllable_count = 0
        previous_was_vowel = False
        
        for char in word:
            is_vowel = char in vowels
            if is_vowel and not previous_was_vowel:
                syllable_count += 1
            previous_was_vowel = is_vowel
        
        # Handle silent e
        if word.endswith('e') and syllable_count > 1:
            syllable_count -= 1
        
        return max(1, syllable_count)
    
    def analyze_sentiment(self, text: str) -> float:
        """Simple sentiment analysis using word patterns."""
        positive_words = {
            'good', 'great', 'excellent', 'amazing', 'wonderful', 'fantastic',
            'love', 'like', 'enjoy', 'happy', 'pleased', 'satisfied', 'perfect',
            'best', 'awesome', 'brilliant', 'outstanding', 'superb', 'magnificent'
        }
        
        negative_words = {
            'bad', 'terrible', 'awful', 'horrible', 'disgusting', 'hate',
            'dislike', 'angry', 'frustrated', 'disappointed', 'worst', 'pathetic',
            'useless', 'broken', 'failed', 'wrong', 'error', 'problem', 'issue'
        }
        
        words = self.extract_words(text)
        if not words:
            return 0.0
        
        positive_count = sum(1 for word in words if word in positive_words)
        negative_count = sum(1 for word in words if word in negative_words)
        
        # Normalize to -1 to 1 scale
        total_sentiment_words = positive_count + negative_count
        if total_sentiment_words == 0:
            return 0.0
        
        return (positive_count - negative_count) / len(words) * 10
    
    def analyze_text(self, text: str, store_result: bool = True) -> TextAnalysis:
        """
        Comprehensive text analysis with real processing and validation.
        Tests verify actual analysis calculations and database storage.
        """
        start_time = time.time()
        
        if not text or not isinstance(text, str):
            raise ValueError("Text must be a non-empty string")
        
        # Extract components
        words = self.extract_words(text)
        sentences = self.extract_sentences(text)
        paragraphs = self.extract_paragraphs(text)
        
        # Calculate metrics
        word_count = len(words)
        character_count = len(text)
        sentence_count = len(sentences)
        paragraph_count = len(paragraphs)
        
        # Calculate average word length
        avg_word_length = statistics.mean(len(word) for word in words) if words else 0.0
        
        # Calculate readability
        readability_score = self.calculate_readability(text)
        
        # Find common words (excluding stop words)
        filtered_words = [word for word in words if word not in self.stop_words]
        common_words = dict(Counter(filtered_words).most_common(10))
        
        # Sentiment analysis
        sentiment_score = self.analyze_sentiment(text)
        
        processing_time = time.time() - start_time
        
        analysis = TextAnalysis(
            word_count=word_count,
            character_count=character_count,
            sentence_count=sentence_count,
            paragraph_count=paragraph_count,
            avg_word_length=avg_word_length,
            readability_score=readability_score,
            common_words=common_words,
            sentiment_score=sentiment_score,
            processing_time=processing_time
        )
        
        # Store in database if requested
        if store_result:
            self._store_analysis(text, analysis)
        
        return analysis
    
    def _store_analysis(self, text: str, analysis: TextAnalysis) -> str:
        """Store text and analysis in database."""
        import json
        
        doc_id = hashlib.sha256(text.encode()).hexdigest()[:16]
        content_hash = hashlib.sha256(text.encode()).hexdigest()
        analysis_data = json.dumps({
            'readability_score': analysis.readability_score,
            'sentiment_score': analysis.sentiment_score,
            'common_words': analysis.common_words,
            'avg_word_length': analysis.avg_word_length,
            'processing_time': analysis.processing_time
        })
        
        with sqlite3.connect(self.db_path) as conn:
            # Store document
            conn.execute("""
                INSERT OR REPLACE INTO text_documents 
                (doc_id, content, content_hash, word_count, character_count, processed_at, analysis_data)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (doc_id, text, content_hash, analysis.word_count, 
                 analysis.character_count, time.time(), analysis_data))
            
            # Store word frequencies
            conn.execute("DELETE FROM word_frequency WHERE doc_id = ?", (doc_id,))
            
            words = self.extract_words(text)
            word_positions = {}
            for i, word in enumerate(words):
                if word not in word_positions:
                    word_positions[word] = []
                word_positions[word].append(i)
            
            for word, positions in word_positions.items():
                frequency = len(positions)
                position_avg = statistics.mean(positions) if positions else 0.0
                
                conn.execute("""
                    INSERT INTO word_frequency (doc_id, word, frequency, position_avg)
                    VALUES (?, ?, ?, ?)
                """, (doc_id, word, frequency, position_avg))
            
            conn.commit()
        
        return doc_id
    
    def get_document_analysis(self, doc_id: str) -> Optional[Dict]:
        """Retrieve stored document analysis."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT content, analysis_data, processed_at FROM text_documents
                WHERE doc_id = ?
            """, (doc_id,))
            row = cursor.fetchone()
            
            if not row:
                return None
            
            import json
            content, analysis_data, processed_at = row
            analysis = json.loads(analysis_data)
            
            return {
                'doc_id': doc_id,
                'content': content,
                'processed_at': processed_at,
                'analysis': analysis
            }
    
    def search_documents_by_word(self, word: str) -> List[Dict]:
        """Search documents containing a specific word."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT d.doc_id, d.content, w.frequency, w.position_avg
                FROM text_documents d
                JOIN word_frequency w ON d.doc_id = w.doc_id
                WHERE w.word = ?
                ORDER BY w.frequency DESC
            """, (word.lower(),))
            
            results = []
            for row in cursor.fetchall():
                results.append({
                    'doc_id': row[0],
                    'content': row[1][:200] + '...' if len(row[1]) > 200 else row[1],
                    'frequency': row[2],
                    'position_avg': row[3]
                })
            
            return results