"""
Unit tests for citation processor.
"""
import pytest
from src.citation.processor import CitationProcessor, Citation

class TestCitationProcessor:
    
    def setup_method(self):
        """Set up test fixtures."""
        self.processor = CitationProcessor()
    
    def test_extract_case_citations(self):
        """Test extraction of case citations."""
        text = "See Brown v. Board of Education, 347 U.S. 483 (1954) and Miranda v. Arizona, 384 U.S. 436 (1966)."
        
        citations = self.processor.extract_citations(text)
        
        assert len(citations) >= 2
        case_citations = [c for c in citations if c.citation_type == 'case_citation']
        assert len(case_citations) >= 2
        
        # Check for specific citations
        citation_texts = [c.text for c in case_citations]
        assert any('347 U.S. 483' in text for text in citation_texts)
        assert any('384 U.S. 436' in text for text in citation_texts)
    
    def test_extract_statute_citations(self):
        """Test extraction of statute citations."""
        text = "According to 42 U.S.C. § 1983 and 15 U.S.C. § 78j(b), the defendant violated federal law."
        
        citations = self.processor.extract_citations(text)
        
        statute_citations = [c for c in citations if c.citation_type == 'statute_citation']
        assert len(statute_citations) >= 2
        
        citation_texts = [c.text for c in statute_citations]
        assert any('42 U.S.C.' in text for text in citation_texts)
        assert any('15 U.S.C.' in text for text in citation_texts)
    
    def test_confidence_scoring(self):
        """Test confidence scoring algorithm."""
        text = "347 U.S. 483 (1954)"
        citations = self.processor.extract_citations(text)
        
        assert len(citations) >= 1
        citation = citations[0]
        assert citation.confidence > 0.5  # Should have decent confidence
        assert citation.confidence <= 1.0
    
    def test_citation_normalization(self):
        """Test citation normalization."""
        processor = CitationProcessor()
        
        # Test case citation normalization
        normalized = processor._normalize_case_citation("347   U.S.   483", ("347", "U.S.", "483", "1954"))
        assert normalized == "347 U.S. 483 (1954)"
        
        # Test statute citation normalization
        normalized = processor._normalize_statute_citation("42 USC 1983", ("42", "1983"))
        assert "42 U.S.C. § 1983" in normalized
    
    def test_duplicate_removal(self):
        """Test removal of duplicate citations."""
        text = "See 347 U.S. 483 (1954) and later in 347 U.S. 483 (1954) again."
        
        citations = self.processor.extract_citations(text)
        
        # Should deduplicate identical citations
        normalized_citations = [c.normalized for c in citations]
        assert len(set(normalized_citations)) == len(normalized_citations)
    
    def test_citation_validation(self):
        """Test citation format validation."""
        citation = Citation(
            text="347 U.S. 483 (1954)",
            citation_type="case_citation",
            normalized="347 U.S. 483 (1954)",
            confidence=0.9,
            volume="347",
            reporter="U.S.",
            page="483",
            year="1954"
        )
        
        is_valid, message = self.processor.validate_citation_format(citation)
        assert is_valid
        assert "Valid format" in message
    
    def test_invalid_citation_validation(self):
        """Test validation of invalid citations."""
        citation = Citation(
            text="invalid citation",
            citation_type="case_citation", 
            normalized="invalid citation",
            confidence=0.1
        )
        
        is_valid, message = self.processor.validate_citation_format(citation)
        assert not is_valid
        assert "Missing" in message