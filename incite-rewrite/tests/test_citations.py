"""
Citation extraction and verification tests using London School TDD.
Tests focus on citation pattern recognition, validation, and legal document processing.
"""

import pytest
import re
from unittest.mock import Mock, patch, MagicMock, call
from typing import Dict, List, Any, Optional


class CitationExtractor:
    """Citation extraction service for legal documents."""
    
    def __init__(self, patterns_file: Optional[str] = None):
        self.patterns_file = patterns_file
        self.citation_patterns = self._load_citation_patterns()
        self.extracted_citations = []
    
    def _load_citation_patterns(self) -> Dict[str, str]:
        """Load citation regex patterns for different legal sources."""
        return {
            'federal_case': r'(\d+)\s+([A-Z]\w*\.?\s*\d*)\s+(\d+)\s*\((\d{4})\)',
            'state_case': r'(\d+)\s+([A-Z]\w*\.?\s*\d*)\s+(\d+)\s*\(([A-Z]\w*\.?)\s+(\d{4})\)',
            'federal_statute': r'(\d+)\s+U\.?S\.?C\.?\s+§?\s*(\d+)',
            'cfr': r'(\d+)\s+C\.?F\.?R\.?\s+§?\s*(\d+)',
            'supreme_court': r'(\d+)\s+U\.?S\.?\s+(\d+)\s*\((\d{4})\)',
            'circuit_court': r'(\d+)\s+F\.(\d)d\s+(\d+)\s*\(([^)]+)\s+(\d{4})\)',
            'district_court': r'(\d+)\s+F\. Supp\. (\dd?)?\s+(\d+)\s*\(([^)]+)\s+(\d{4})\)'
        }
    
    def extract_citations(self, text: str, citation_types: List[str] = None) -> List[Dict[str, Any]]:
        """Extract legal citations from text."""
        if not text or not isinstance(text, str):
            raise ValueError("Text must be a non-empty string")
        
        citations = []
        types_to_extract = citation_types or list(self.citation_patterns.keys())
        
        for citation_type in types_to_extract:
            if citation_type not in self.citation_patterns:
                continue
                
            pattern = self.citation_patterns[citation_type]
            matches = re.finditer(pattern, text, re.IGNORECASE)
            
            for match in matches:
                citation = {
                    'type': citation_type,
                    'text': match.group(0),
                    'groups': match.groups(),
                    'start_pos': match.start(),
                    'end_pos': match.end(),
                    'confidence': self._calculate_confidence(citation_type, match)
                }
                citations.append(citation)
        
        self.extracted_citations = citations
        return citations
    
    def _calculate_confidence(self, citation_type: str, match: re.Match) -> float:
        """Calculate confidence score for extracted citation."""
        base_confidence = 0.8
        
        # Adjust confidence based on citation type specificity
        type_adjustments = {
            'supreme_court': 0.1,
            'federal_case': 0.05,
            'federal_statute': 0.05,
            'state_case': -0.05,
            'circuit_court': 0.0,
            'district_court': 0.0,
            'cfr': -0.1
        }
        
        confidence = base_confidence + type_adjustments.get(citation_type, 0.0)
        
        # Adjust for match quality
        if len(match.groups()) >= 3:  # More capture groups generally mean better match
            confidence += 0.1
        
        return min(max(confidence, 0.0), 1.0)
    
    def validate_citation_format(self, citation: Dict[str, Any]) -> bool:
        """Validate that citation follows proper legal citation format."""
        if not citation or not isinstance(citation, dict):
            return False
        
        required_fields = ['type', 'text', 'groups']
        if not all(field in citation for field in required_fields):
            return False
        
        # Type-specific validation
        citation_type = citation['type']
        groups = citation['groups']
        
        if citation_type == 'supreme_court':
            return len(groups) >= 3 and groups[0].isdigit() and groups[1].isdigit()
        
        elif citation_type == 'federal_case':
            return len(groups) >= 4 and groups[0].isdigit() and groups[2].isdigit()
        
        elif citation_type == 'federal_statute':
            return len(groups) >= 2 and groups[0].isdigit() and groups[1].isdigit()
        
        return True  # Basic validation passed
    
    def normalize_citation(self, citation: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize citation format for consistency."""
        if not self.validate_citation_format(citation):
            raise ValueError("Invalid citation format")
        
        normalized = citation.copy()
        citation_type = citation['type']
        groups = citation['groups']
        
        if citation_type == 'supreme_court':
            normalized['volume'] = groups[0]
            normalized['page'] = groups[1]
            normalized['year'] = groups[2] if len(groups) > 2 else None
            normalized['reporter'] = 'U.S.'
        
        elif citation_type == 'federal_case':
            normalized['volume'] = groups[0]
            normalized['reporter'] = groups[1].strip()
            normalized['page'] = groups[2]
            normalized['year'] = groups[3] if len(groups) > 3 else None
        
        elif citation_type == 'federal_statute':
            normalized['title'] = groups[0]
            normalized['section'] = groups[1]
            normalized['source'] = 'U.S.C.'
        
        # Add standard fields
        normalized['normalized_text'] = self._format_normalized_citation(normalized)
        normalized['is_normalized'] = True
        
        return normalized
    
    def _format_normalized_citation(self, citation: Dict[str, Any]) -> str:
        """Format citation in standard legal citation format."""
        citation_type = citation['type']
        
        if citation_type == 'supreme_court':
            return f"{citation['volume']} U.S. {citation['page']} ({citation.get('year', '')})"
        
        elif citation_type == 'federal_case':
            return f"{citation['volume']} {citation['reporter']} {citation['page']} ({citation.get('year', '')})"
        
        elif citation_type == 'federal_statute':
            return f"{citation['title']} U.S.C. § {citation['section']}"
        
        return citation.get('text', '')
    
    def get_citation_statistics(self) -> Dict[str, Any]:
        """Get statistics about extracted citations."""
        if not self.extracted_citations:
            return {'total_citations': 0, 'by_type': {}, 'avg_confidence': 0.0}
        
        by_type = {}
        total_confidence = 0.0
        
        for citation in self.extracted_citations:
            citation_type = citation['type']
            by_type[citation_type] = by_type.get(citation_type, 0) + 1
            total_confidence += citation.get('confidence', 0.0)
        
        return {
            'total_citations': len(self.extracted_citations),
            'by_type': by_type,
            'avg_confidence': total_confidence / len(self.extracted_citations),
            'unique_types': len(by_type)
        }


class TestCitationExtractorInitialization:
    """Test citation extractor initialization and setup."""
    
    def test_initializes_with_default_patterns(self):
        """Should initialize with default citation patterns."""
        extractor = CitationExtractor()
        
        assert extractor.patterns_file is None
        assert isinstance(extractor.citation_patterns, dict)
        assert len(extractor.citation_patterns) > 0
        assert 'federal_case' in extractor.citation_patterns
        assert 'supreme_court' in extractor.citation_patterns
        assert extractor.extracted_citations == []
    
    def test_initializes_with_custom_patterns_file(self):
        """Should initialize with custom patterns file path."""
        extractor = CitationExtractor(patterns_file="/custom/patterns.json")
        
        assert extractor.patterns_file == "/custom/patterns.json"
        # Should still load default patterns if custom file loading fails
        assert isinstance(extractor.citation_patterns, dict)
    
    def test_loads_standard_legal_citation_patterns(self):
        """Should load standard legal citation regex patterns."""
        extractor = CitationExtractor()
        patterns = extractor.citation_patterns
        
        # Verify essential citation types are present
        essential_types = [
            'federal_case', 'state_case', 'federal_statute',
            'supreme_court', 'circuit_court', 'district_court', 'cfr'
        ]
        
        for citation_type in essential_types:
            assert citation_type in patterns
            assert isinstance(patterns[citation_type], str)
            # Verify it's a valid regex pattern
            assert re.compile(patterns[citation_type]) is not None


class TestFederalCaseCitationExtraction:
    """Test extraction of federal case citations."""
    
    def test_extracts_basic_federal_case_citation(self):
        """Should extract basic federal case citation format."""
        extractor = CitationExtractor()
        text = "See Smith v. Jones, 123 F.3d 456 (2020), for precedent."
        
        citations = extractor.extract_citations(text, ['federal_case'])
        
        assert len(citations) == 1
        citation = citations[0]
        assert citation['type'] == 'federal_case'
        assert '123 F.3d 456 (2020)' in citation['text']
        assert citation['groups'][0] == '123'  # Volume
        assert 'F.3d' in citation['groups'][1]  # Reporter
        assert citation['groups'][2] == '456'  # Page
        assert citation['groups'][3] == '2020'  # Year
    
    def test_extracts_multiple_federal_citations_from_text(self):
        """Should extract multiple federal case citations from single text."""
        extractor = CitationExtractor()
        text = """
        The court relied on Smith v. Jones, 123 F.3d 456 (2020), 
        and also cited Brown v. Davis, 789 F.2d 123 (1985).
        """
        
        citations = extractor.extract_citations(text, ['federal_case'])
        
        assert len(citations) == 2
        
        # Verify both citations were extracted
        citation_texts = [c['text'] for c in citations]
        assert any('123 F.3d 456' in text for text in citation_texts)
        assert any('789 F.2d 123' in text for text in citation_texts)
    
    def test_handles_various_federal_reporter_formats(self):
        """Should handle different federal reporter abbreviation formats."""
        extractor = CitationExtractor()
        test_cases = [
            "123 F.3d 456 (2020)",
            "456 F.2d 789 (1990)", 
            "789 F. Supp. 123 (1985)",
            "321 F.Supp.2d 654 (2010)"
        ]
        
        for case_text in test_cases:
            text = f"See {case_text} for reference."
            citations = extractor.extract_citations(text)
            
            # Should extract at least one citation
            assert len(citations) >= 1
            
            # Should find the citation text
            found = any(case_text in c['text'] for c in citations)
            assert found, f"Failed to extract: {case_text}"


class TestSupremeCourtCitationExtraction:
    """Test extraction of Supreme Court citations."""
    
    def test_extracts_supreme_court_citation(self):
        """Should extract Supreme Court citation in standard format."""
        extractor = CitationExtractor()
        text = "The landmark case Brown v. Board, 347 U.S. 483 (1954), changed everything."
        
        citations = extractor.extract_citations(text, ['supreme_court'])
        
        assert len(citations) == 1
        citation = citations[0]
        assert citation['type'] == 'supreme_court'
        assert '347 U.S. 483 (1954)' in citation['text']
        assert citation['groups'][0] == '347'  # Volume
        assert citation['groups'][1] == '483'  # Page
        assert citation['groups'][2] == '1954'  # Year
    
    def test_handles_us_reporter_abbreviation_variations(self):
        """Should handle various U.S. reporter abbreviation formats."""
        extractor = CitationExtractor()
        variations = [
            "347 U.S. 483 (1954)",
            "347 US 483 (1954)", 
            "347 U.S 483 (1954)"
        ]
        
        for variation in variations:
            text = f"See {variation} for details."
            citations = extractor.extract_citations(text, ['supreme_court'])
            
            assert len(citations) >= 1
            found = any(citation['type'] == 'supreme_court' for citation in citations)
            assert found, f"Failed to extract Supreme Court citation: {variation}"


class TestStatuteCitationExtraction:
    """Test extraction of statutory citations."""
    
    def test_extracts_federal_statute_citation(self):
        """Should extract federal statute citations."""
        extractor = CitationExtractor()
        text = "Under 42 U.S.C. § 1983, plaintiffs may seek relief."
        
        citations = extractor.extract_citations(text, ['federal_statute'])
        
        assert len(citations) == 1
        citation = citations[0]
        assert citation['type'] == 'federal_statute'
        assert '42 U.S.C. § 1983' in citation['text'] or '42 U.S.C. 1983' in citation['text']
        assert citation['groups'][0] == '42'  # Title
        assert citation['groups'][1] == '1983'  # Section
    
    def test_handles_usc_abbreviation_variations(self):
        """Should handle various U.S.C. abbreviation formats."""
        extractor = CitationExtractor()
        variations = [
            "42 U.S.C. § 1983",
            "42 USC § 1983",
            "42 U.S.C. 1983",
            "42 USC 1983"
        ]
        
        for variation in variations:
            text = f"See {variation} for statutory authority."
            citations = extractor.extract_citations(text, ['federal_statute'])
            
            assert len(citations) >= 1
            found = any(citation['type'] == 'federal_statute' for citation in citations)
            assert found, f"Failed to extract statute: {variation}"


class TestCFRCitationExtraction:
    """Test extraction of Code of Federal Regulations citations."""
    
    def test_extracts_cfr_citation(self):
        """Should extract CFR citations."""
        extractor = CitationExtractor()
        text = "The regulation at 29 C.F.R. § 1630.2 defines disability."
        
        citations = extractor.extract_citations(text, ['cfr'])
        
        assert len(citations) == 1
        citation = citations[0]
        assert citation['type'] == 'cfr'
        assert '29 C.F.R.' in citation['text']
        assert citation['groups'][0] == '29'  # Title
        assert citation['groups'][1] == '1630.2'  # Section
    
    def test_handles_cfr_abbreviation_variations(self):
        """Should handle various CFR abbreviation formats."""
        extractor = CitationExtractor()
        variations = [
            "29 C.F.R. § 1630.2",
            "29 CFR § 1630.2",
            "29 C.F.R. 1630.2",
            "29 CFR 1630.2"
        ]
        
        for variation in variations:
            text = f"See {variation} for regulatory guidance."
            citations = extractor.extract_citations(text, ['cfr'])
            
            assert len(citations) >= 1
            found = any(citation['type'] == 'cfr' for citation in citations)
            assert found, f"Failed to extract CFR: {variation}"


class TestCitationValidation:
    """Test citation format validation functionality."""
    
    def test_validates_complete_citation_structure(self):
        """Should validate citation has required fields and structure."""
        extractor = CitationExtractor()
        
        valid_citation = {
            'type': 'supreme_court',
            'text': '347 U.S. 483 (1954)',
            'groups': ('347', '483', '1954')
        }
        
        assert extractor.validate_citation_format(valid_citation) is True
    
    def test_rejects_incomplete_citation_structure(self):
        """Should reject citations missing required fields."""
        extractor = CitationExtractor()
        
        incomplete_citations = [
            {},  # Empty
            {'type': 'supreme_court'},  # Missing text and groups
            {'text': '347 U.S. 483'},  # Missing type and groups
            {'groups': ('347', '483')},  # Missing type and text
            None,  # None value
            "invalid"  # Wrong type
        ]
        
        for citation in incomplete_citations:
            assert extractor.validate_citation_format(citation) is False
    
    def test_validates_type_specific_citation_requirements(self):
        """Should validate type-specific citation requirements."""
        extractor = CitationExtractor()
        
        # Valid Supreme Court citation
        supreme_court_citation = {
            'type': 'supreme_court',
            'text': '347 U.S. 483 (1954)',
            'groups': ('347', '483', '1954')
        }
        assert extractor.validate_citation_format(supreme_court_citation) is True
        
        # Invalid Supreme Court citation (non-numeric volume)
        invalid_supreme_court = {
            'type': 'supreme_court',
            'text': 'ABC U.S. 483 (1954)',
            'groups': ('ABC', '483', '1954')
        }
        assert extractor.validate_citation_format(invalid_supreme_court) is False
    
    def test_validates_federal_case_citation_format(self):
        """Should validate federal case citation requirements."""
        extractor = CitationExtractor()
        
        valid_federal_case = {
            'type': 'federal_case',
            'text': '123 F.3d 456 (2020)',
            'groups': ('123', 'F.3d', '456', '2020')
        }
        assert extractor.validate_citation_format(valid_federal_case) is True
        
        invalid_federal_case = {
            'type': 'federal_case',
            'text': 'ABC F.3d XYZ (2020)',
            'groups': ('ABC', 'F.3d', 'XYZ', '2020')
        }
        assert extractor.validate_citation_format(invalid_federal_case) is False


class TestCitationNormalization:
    """Test citation normalization and standardization."""
    
    def test_normalizes_supreme_court_citation(self):
        """Should normalize Supreme Court citation to standard format."""
        extractor = CitationExtractor()
        
        citation = {
            'type': 'supreme_court',
            'text': '347 U.S. 483 (1954)',
            'groups': ('347', '483', '1954')
        }
        
        normalized = extractor.normalize_citation(citation)
        
        assert normalized['volume'] == '347'
        assert normalized['page'] == '483'
        assert normalized['year'] == '1954'
        assert normalized['reporter'] == 'U.S.'
        assert normalized['normalized_text'] == '347 U.S. 483 (1954)'
        assert normalized['is_normalized'] is True
    
    def test_normalizes_federal_case_citation(self):
        """Should normalize federal case citation to standard format."""
        extractor = CitationExtractor()
        
        citation = {
            'type': 'federal_case',
            'text': '123 F.3d 456 (2020)',
            'groups': ('123', 'F.3d', '456', '2020')
        }
        
        normalized = extractor.normalize_citation(citation)
        
        assert normalized['volume'] == '123'
        assert normalized['reporter'] == 'F.3d'
        assert normalized['page'] == '456'
        assert normalized['year'] == '2020'
        assert normalized['normalized_text'] == '123 F.3d 456 (2020)'
        assert normalized['is_normalized'] is True
    
    def test_normalizes_federal_statute_citation(self):
        """Should normalize federal statute citation to standard format."""
        extractor = CitationExtractor()
        
        citation = {
            'type': 'federal_statute',
            'text': '42 U.S.C. § 1983',
            'groups': ('42', '1983')
        }
        
        normalized = extractor.normalize_citation(citation)
        
        assert normalized['title'] == '42'
        assert normalized['section'] == '1983'
        assert normalized['source'] == 'U.S.C.'
        assert normalized['normalized_text'] == '42 U.S.C. § 1983'
        assert normalized['is_normalized'] is True
    
    def test_rejects_normalization_of_invalid_citations(self):
        """Should reject normalization of invalid citations."""
        extractor = CitationExtractor()
        
        invalid_citation = {
            'type': 'supreme_court',
            'text': 'Invalid citation',
            # Missing required groups
        }
        
        with pytest.raises(ValueError, match="Invalid citation format"):
            extractor.normalize_citation(invalid_citation)


class TestCitationConfidenceScoring:
    """Test citation confidence scoring mechanism."""
    
    def test_calculates_confidence_scores(self):
        """Should calculate appropriate confidence scores for citations."""
        extractor = CitationExtractor()
        
        # Create mock match object
        mock_match = Mock()
        mock_match.groups.return_value = ('347', '483', '1954')
        
        # Test different citation types
        supreme_court_confidence = extractor._calculate_confidence('supreme_court', mock_match)
        federal_case_confidence = extractor._calculate_confidence('federal_case', mock_match)
        cfr_confidence = extractor._calculate_confidence('cfr', mock_match)
        
        # Supreme Court should have higher confidence
        assert supreme_court_confidence > federal_case_confidence
        assert federal_case_confidence > cfr_confidence
        
        # All scores should be between 0 and 1
        for score in [supreme_court_confidence, federal_case_confidence, cfr_confidence]:
            assert 0.0 <= score <= 1.0
    
    def test_adjusts_confidence_based_on_match_quality(self):
        """Should adjust confidence based on number of captured groups."""
        extractor = CitationExtractor()
        
        # Mock matches with different numbers of groups
        few_groups_match = Mock()
        few_groups_match.groups.return_value = ('123',)
        
        many_groups_match = Mock()
        many_groups_match.groups.return_value = ('123', 'F.3d', '456', '2020')
        
        few_confidence = extractor._calculate_confidence('federal_case', few_groups_match)
        many_confidence = extractor._calculate_confidence('federal_case', many_groups_match)
        
        # More groups should result in higher confidence
        assert many_confidence > few_confidence


class TestCitationStatistics:
    """Test citation extraction statistics and reporting."""
    
    def test_provides_extraction_statistics(self):
        """Should provide comprehensive statistics about extracted citations."""
        extractor = CitationExtractor()
        text = """
        The court in Brown v. Board, 347 U.S. 483 (1954), relied on 
        Smith v. Jones, 123 F.3d 456 (2020), and 42 U.S.C. § 1983.
        """
        
        citations = extractor.extract_citations(text)
        stats = extractor.get_citation_statistics()
        
        assert stats['total_citations'] == len(citations)
        assert stats['total_citations'] > 0
        assert isinstance(stats['by_type'], dict)
        assert stats['avg_confidence'] > 0.0
        assert stats['unique_types'] > 0
    
    def test_handles_empty_citation_list(self):
        """Should handle statistics for empty citation list."""
        extractor = CitationExtractor()
        stats = extractor.get_citation_statistics()
        
        assert stats['total_citations'] == 0
        assert stats['by_type'] == {}
        assert stats['avg_confidence'] == 0.0
        assert stats['unique_types'] == 0
    
    def test_counts_citations_by_type_accurately(self):
        """Should accurately count citations by type."""
        extractor = CitationExtractor()
        text = """
        Brown v. Board, 347 U.S. 483 (1954)
        Smith v. Jones, 123 F.3d 456 (2020)
        Davis v. Wilson, 789 F.2d 123 (1985)
        42 U.S.C. § 1983
        29 C.F.R. § 1630.2
        """
        
        citations = extractor.extract_citations(text)
        stats = extractor.get_citation_statistics()
        
        # Should have multiple types represented
        assert 'supreme_court' in stats['by_type']
        assert stats['by_type'].get('supreme_court', 0) >= 1
        
        # Federal cases should be counted
        federal_case_count = stats['by_type'].get('federal_case', 0)
        assert federal_case_count >= 1
        
        # Statutes should be counted
        statute_count = stats['by_type'].get('federal_statute', 0) + stats['by_type'].get('cfr', 0)
        assert statute_count >= 1


class TestCitationExtractionEdgeCases:
    """Test edge cases and error handling in citation extraction."""
    
    def test_handles_empty_text_input(self):
        """Should handle empty text input appropriately."""
        extractor = CitationExtractor()
        
        with pytest.raises(ValueError, match="Text must be a non-empty string"):
            extractor.extract_citations("")
    
    def test_handles_none_text_input(self):
        """Should handle None text input appropriately."""
        extractor = CitationExtractor()
        
        with pytest.raises(ValueError, match="Text must be a non-empty string"):
        
        extractor.extract_citations(None)
    
    def test_handles_non_string_text_input(self):
        """Should handle non-string text input appropriately."""
        extractor = CitationExtractor()
        
        with pytest.raises(ValueError, match="Text must be a non-empty string"):
            extractor.extract_citations(12345)
    
    def test_handles_text_with_no_citations(self):
        """Should handle text containing no legal citations."""
        extractor = CitationExtractor()
        text = "This is just regular text with no legal citations at all."
        
        citations = extractor.extract_citations(text)
        
        assert isinstance(citations, list)
        assert len(citations) == 0
    
    def test_handles_malformed_citation_patterns(self):
        """Should handle text with citation-like but malformed patterns."""
        extractor = CitationExtractor()
        text = """
        This looks like 123 Something 456 (2020) but isn't a real citation.
        Also this: ABC U.S. XYZ (YYYY) is malformed.
        """
        
        citations = extractor.extract_citations(text)
        
        # Should either extract nothing or extract with low confidence
        for citation in citations:
            if citation['confidence'] > 0.5:
                # If extracted with high confidence, should be valid
                assert extractor.validate_citation_format(citation)
    
    def test_handles_very_long_text(self):
        """Should handle very long text without performance issues."""
        extractor = CitationExtractor()
        
        # Create long text with embedded citations
        base_text = "This is filler text. " * 1000
        citation_text = "Brown v. Board, 347 U.S. 483 (1954), is important."
        long_text = base_text + citation_text + base_text
        
        # Should complete without error
        citations = extractor.extract_citations(long_text)
        
        # Should find the embedded citation
        assert len(citations) >= 1
        supreme_court_citations = [c for c in citations if c['type'] == 'supreme_court']
        assert len(supreme_court_citations) >= 1
    
    def test_handles_unicode_and_special_characters(self):
        """Should handle unicode and special characters in legal text."""
        extractor = CitationExtractor()
        text = """
        The case Café v. Résumé, 347 U.S. 483 (1954), involved international law.
        See also § 42 U.S.C. § 1983 for statutory authority.
        """
        
        # Should complete without encoding errors
        citations = extractor.extract_citations(text)
        
        # Should extract citations despite unicode characters
        assert len(citations) >= 1


class TestCitationTypeFiltering:
    """Test filtering citations by type during extraction."""
    
    def test_extracts_only_specified_citation_types(self):
        """Should extract only specified citation types when filtered."""
        extractor = CitationExtractor()
        text = """
        Brown v. Board, 347 U.S. 483 (1954)
        Smith v. Jones, 123 F.3d 456 (2020)
        42 U.S.C. § 1983
        """
        
        # Extract only Supreme Court citations
        supreme_only = extractor.extract_citations(text, ['supreme_court'])
        
        # Should only contain Supreme Court citations
        for citation in supreme_only:
            assert citation['type'] == 'supreme_court'
        
        assert len(supreme_only) >= 1
    
    def test_extracts_multiple_specified_types(self):
        """Should extract multiple specified citation types."""
        extractor = CitationExtractor()
        text = """
        Brown v. Board, 347 U.S. 483 (1954)
        Smith v. Jones, 123 F.3d 456 (2020)
        42 U.S.C. § 1983
        29 C.F.R. § 1630.2
        """
        
        # Extract cases and statutes
        selected_types = ['supreme_court', 'federal_case', 'federal_statute']
        citations = extractor.extract_citations(text, selected_types)
        
        # Should contain only the specified types
        extracted_types = set(citation['type'] for citation in citations)
        assert extracted_types.issubset(set(selected_types))
        
        # Should not contain CFR citations since they weren't requested
        assert 'cfr' not in extracted_types
    
    def test_handles_unknown_citation_types_gracefully(self):
        """Should handle requests for unknown citation types gracefully."""
        extractor = CitationExtractor()
        text = "Brown v. Board, 347 U.S. 483 (1954)"
        
        # Request unknown citation type along with valid one
        citations = extractor.extract_citations(text, ['supreme_court', 'unknown_type'])
        
        # Should extract the valid type and ignore the unknown one
        assert len(citations) >= 1
        assert all(citation['type'] in extractor.citation_patterns for citation in citations)


@pytest.mark.integration
class TestCitationExtractionIntegration:
    """Test integration of citation extraction with other components."""
    
    def test_integrates_with_text_processor(self, memory_text_processor):
        """Should integrate citation extraction with text processing workflow."""
        extractor = CitationExtractor()
        legal_text = """
        In Brown v. Board of Education, 347 U.S. 483 (1954), the Supreme Court 
        held that separate educational facilities are inherently unequal. 
        This decision overturned Plessy v. Ferguson, 163 U.S. 537 (1896).
        """
        
        # Process text and extract citations
        text_analysis = memory_text_processor.analyze_text(legal_text, store_result=True)
        citations = extractor.extract_citations(legal_text)
        
        # Both should succeed and provide complementary data
        assert text_analysis.word_count > 0
        assert len(citations) >= 2  # Should find both cases
        
        # Citations should reference specific parts of the analyzed text
        for citation in citations:
            assert citation['start_pos'] < len(legal_text)
            assert citation['end_pos'] <= len(legal_text)
            assert citation['start_pos'] < citation['end_pos']
    
    def test_citation_extraction_with_document_storage(self, temp_db_path):
        """Should support storing citation data alongside document analysis."""
        from src.utils.text_processing import TextProcessor
        
        processor = TextProcessor(temp_db_path)
        extractor = CitationExtractor()
        
        legal_text = "See Smith v. Jones, 123 F.3d 456 (2020), for precedent."
        
        # Analyze and store text
        analysis = processor.analyze_text(legal_text, store_result=True)
        citations = extractor.extract_citations(legal_text)
        
        # Should be able to retrieve the document
        documents = processor.search_documents_by_word('Smith')
        assert len(documents) >= 1
        
        # Citations should complement the stored analysis
        assert len(citations) >= 1
        assert any('123 F.3d 456' in c['text'] for c in citations)


@pytest.mark.performance 
class TestCitationExtractionPerformance:
    """Test citation extraction performance with large documents."""
    
    def test_extraction_performance_scales_reasonably(self, performance_monitor):
        """Should have reasonable performance scaling with document size."""
        extractor = CitationExtractor()
        
        # Small document with citations
        small_text = "Brown v. Board, 347 U.S. 483 (1954). " * 10
        
        # Large document with citations
        large_text = "Brown v. Board, 347 U.S. 483 (1954). " * 1000
        
        # Measure small document processing
        performance_monitor.start()
        small_citations = extractor.extract_citations(small_text)
        small_metrics = performance_monitor.stop()
        
        # Measure large document processing
        performance_monitor.start()
        large_citations = extractor.extract_citations(large_text)
        large_metrics = performance_monitor.stop()
        
        # Should scale reasonably (not exponentially)
        assert large_metrics['duration'] < small_metrics['duration'] * 200
        
        # Should find more citations in larger document
        assert len(large_citations) > len(small_citations)
    
    def test_handles_documents_with_many_citations(self, performance_monitor):
        """Should handle documents with many different citation types efficiently."""
        extractor = CitationExtractor()
        
        # Create text with many different citation types
        citation_examples = [
            "Brown v. Board, 347 U.S. 483 (1954)",
            "Smith v. Jones, 123 F.3d 456 (2020)", 
            "Davis v. Wilson, 789 F.2d 123 (1985)",
            "42 U.S.C. § 1983",
            "29 C.F.R. § 1630.2",
            "Title VII, 42 U.S.C. § 2000e"
        ]
        
        # Repeat each citation type multiple times
        many_citations_text = " ".join(citation_examples * 50)
        
        performance_monitor.start()
        citations = extractor.extract_citations(many_citations_text)
        metrics = performance_monitor.stop()
        
        # Should complete in reasonable time
        assert metrics['duration'] < 5.0  # Less than 5 seconds
        
        # Should extract many citations
        assert len(citations) >= 100
        
        # Memory usage should be reasonable
        assert metrics['memory_delta'] < 100  # Less than 100MB
