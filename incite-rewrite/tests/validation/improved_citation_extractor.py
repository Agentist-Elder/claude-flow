"""
Improved Legal Citation Extractor for Production Validation

Enhanced pattern matching for better accuracy in legal citation recognition.
"""

import re
import hashlib
from typing import Dict, List, Any, Optional
from dataclasses import dataclass


@dataclass
class CitationMatch:
    """Structured citation match result."""
    text: str
    start_position: int
    end_position: int
    jurisdiction: str
    citation_type: str
    confidence: float
    components: Dict[str, str]


class ImprovedLegalCitationExtractor:
    """
    Enhanced legal citation extraction with improved pattern recognition.
    Achieves higher accuracy for production validation requirements.
    """
    
    def __init__(self):
        self.citation_patterns = self._build_comprehensive_patterns()
        self.jurisdiction_indicators = self._build_jurisdiction_indicators()
        self.citation_validators = self._build_citation_validators()
    
    def _build_comprehensive_patterns(self) -> List[Dict[str, Any]]:
        """Build comprehensive citation pattern library."""
        
        patterns = [
            # UK Law Reports - [Year] Citation format
            {
                'pattern': r'([A-Z][A-Za-z\s&.,()]+?)\s+v\.?\s+([A-Za-z\s&.,()]+?)(?:\s+(?:Ltd|plc|Inc|Corp))?\s*\[(\d{4})\]\s*(\d+)?\s*([A-Z]{1,4}\.?[A-Z]?\.?)\s*(\d+)',
                'type': 'uk_modern',
                'jurisdiction': 'UK',
                'confidence': 0.95,
                'groups': ['plaintiff', 'defendant', 'year', 'volume', 'reporter', 'page']
            },
            
            # UK Law Reports - Traditional format
            {
                'pattern': r'([A-Z][A-Za-z\s&.,()]+?)\s+v\.?\s+([A-Za-z\s&.,()]+?)(?:\s+(?:Ltd|plc|Inc|Corp))?\s*\[(\d{4})\]\s*([A-Z]{1,4}\.?[A-Z]?\.?)\s*(\d+)',
                'type': 'uk_traditional', 
                'jurisdiction': 'UK',
                'confidence': 0.90,
                'groups': ['plaintiff', 'defendant', 'year', 'reporter', 'page']
            },
            
            # US Supreme Court - Volume U.S. Page (Year)
            {
                'pattern': r'([A-Z][A-Za-z\s&.,()]+?)\s+v\.?\s+([A-Za-z\s&.,()]+?)(?:\s+(?:Ltd|Inc|Corp))?,?\s*(\d+)\s+U\.?S\.?\s+(\d+)(?:,\s*(\d+))?\s*\((\d{4})\)',
                'type': 'us_supreme',
                'jurisdiction': 'US',
                'confidence': 0.95,
                'groups': ['plaintiff', 'defendant', 'volume', 'page', 'pinpoint', 'year']
            },
            
            # US Federal Courts - Volume F.2d/F.3d Page (Court Year)
            {
                'pattern': r'([A-Z][A-Za-z\s&.,()]+?)\s+v\.?\s+([A-Za-z\s&.,()]+?)(?:\s+(?:Ltd|Inc|Corp))?,?\s*(\d+)\s+F\.?(2d|3d|Supp\.?)\s+(\d+)\s*\(([^)]*?)(\d{4})\)',
                'type': 'us_federal',
                'jurisdiction': 'US',
                'confidence': 0.90,
                'groups': ['plaintiff', 'defendant', 'volume', 'series', 'page', 'court', 'year']
            },
            
            # Canadian cases - [Year] Volume S.C.R. Page
            {
                'pattern': r'([A-Z][A-Za-z\s&.,()]+?)\s+v\.?\s+([A-Za-z\s&.,()]+?)(?:\s+(?:Ltd|Inc|Corp))?,?\s*\[(\d{4})\]\s*(\d+)\s*S\.?C\.?R\.?\s*(\d+)(?:,\s*(\d{4})\s*SCC\s*(\d+))?',
                'type': 'canada_scr',
                'jurisdiction': 'Canada',
                'confidence': 0.90,
                'groups': ['plaintiff', 'defendant', 'year', 'volume', 'page', 'scc_year', 'scc_number']
            },
            
            # Australian cases - (Year) Volume C.L.R. Page
            {
                'pattern': r'([A-Z][A-Za-z\s&.,()]+?)\s+v\.?\s+([A-Za-z\s&.,()]+?)(?:\s+(?:Pty\s+Ltd|Ltd|Inc))?\s*\((\d{4})\)\s*(\d+)\s*C\.?L\.?R\.?\s*(\d+)',
                'type': 'australia_clr',
                'jurisdiction': 'Australia',
                'confidence': 0.90,
                'groups': ['plaintiff', 'defendant', 'year', 'volume', 'page']
            },
            
            # ECHR cases - Name v. Country, Application No. Number (Year)
            {
                'pattern': r'([A-Z][A-Za-z\s&.,()]+?)\s+(?:and\s+Others\s+)?v\.?\s+([A-Za-z\s&.,()]+?)(?:\s+(?:Ltd|Inc))?,?\s*(?:Application|App\.?)\s*No\.?\s*(\d+/\d+)(?:\s*\((\d{4})\))?',
                'type': 'echr',
                'jurisdiction': 'ECHR', 
                'confidence': 0.85,
                'groups': ['applicant', 'respondent', 'application_no', 'year']
            },
            
            # EU cases - Name, Case(s) Number, [Year] E.C.R. Page
            {
                'pattern': r'([A-Z][A-Za-z\s&.,()]+?)\s+(?:and\s+[A-Za-z\s&.,()]+?\s+)?v\.?\s+([A-Za-z\s&.,()]+?)(?:\s+(?:Ltd|Inc))?,?\s*Cases?\s*(C-\d+(?:/\d+)?(?:\s*and\s*C-\d+(?:/\d+)?)*),?\s*\[(\d{4})\]\s*E\.?C\.?R\.?\s*(I-\d+)',
                'type': 'eu_ecj',
                'jurisdiction': 'EU',
                'confidence': 0.85,
                'groups': ['plaintiff', 'defendant', 'case_numbers', 'year', 'ecr_reference']
            }
        ]
        
        return patterns
    
    def _build_jurisdiction_indicators(self) -> Dict[str, List[str]]:
        """Build jurisdiction indicator patterns."""
        return {
            'UK': ['Q.B.', 'A.C.', 'Ch.', 'W.L.R.', 'All E.R.', 'UKHL', 'UKSC'],
            'US': ['U.S.', 'F.2d', 'F.3d', 'F.Supp', 'S.Ct.', 'L.Ed.'],
            'Canada': ['S.C.R.', 'SCC', 'F.C.', 'D.L.R.'],
            'Australia': ['C.L.R.', 'H.C.A.', 'F.C.A.'],
            'ECHR': ['E.H.R.R.', 'Application No.'],
            'EU': ['E.C.R.', 'C.M.L.R.']
        }
    
    def _build_citation_validators(self) -> Dict[str, callable]:
        """Build citation validation functions."""
        return {
            'year_range': lambda year: 1800 <= int(year) <= 2030,
            'volume_reasonable': lambda vol: 1 <= int(vol) <= 2000,
            'page_reasonable': lambda page: 1 <= int(page) <= 99999,
            'has_case_names': lambda text: ' v. ' in text.lower() or ' v ' in text.lower()
        }
    
    def extract_citations(self, text: str) -> List[CitationMatch]:
        """
        Extract legal citations with improved accuracy.
        
        Args:
            text: Input text containing legal citations
            
        Returns:
            List of CitationMatch objects with high accuracy
        """
        if not text or not isinstance(text, str):
            return []
        
        all_matches = []
        
        # Try each pattern
        for pattern_config in self.citation_patterns:
            pattern = pattern_config['pattern']
            matches = re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE)
            
            for match in matches:
                citation_match = self._process_match(match, pattern_config, text)
                if citation_match and self._validate_citation(citation_match):
                    all_matches.append(citation_match)
        
        # Remove duplicates and overlaps
        unique_matches = self._deduplicate_matches(all_matches)
        
        # Sort by position and return top matches
        unique_matches.sort(key=lambda x: x.start_position)
        
        return unique_matches
    
    def _process_match(self, match: re.Match, pattern_config: Dict, text: str) -> Optional[CitationMatch]:
        """Process a regex match into a structured citation."""
        try:
            citation_text = match.group(0).strip()
            groups = match.groups()
            
            # Build components dictionary
            components = {}
            for i, group_name in enumerate(pattern_config.get('groups', [])):
                if i < len(groups) and groups[i]:
                    components[group_name] = groups[i].strip()
            
            # Calculate confidence
            base_confidence = pattern_config.get('confidence', 0.7)
            confidence = self._calculate_match_confidence(citation_text, components, base_confidence)
            
            return CitationMatch(
                text=citation_text,
                start_position=match.start(),
                end_position=match.end(), 
                jurisdiction=pattern_config.get('jurisdiction', 'Unknown'),
                citation_type=pattern_config.get('type', 'case'),
                confidence=confidence,
                components=components
            )
            
        except Exception:
            return None
    
    def _calculate_match_confidence(self, citation_text: str, components: Dict, base_confidence: float) -> float:
        """Calculate confidence score for citation match."""
        confidence = base_confidence
        
        # Bonus for having case names (plaintiff/defendant)
        if 'plaintiff' in components and 'defendant' in components:
            if len(components['plaintiff']) > 3 and len(components['defendant']) > 3:
                confidence += 0.1
        
        # Bonus for having year in reasonable range
        year = components.get('year')
        if year and self.citation_validators['year_range'](year):
            confidence += 0.05
        
        # Bonus for having volume/page numbers
        volume = components.get('volume')
        page = components.get('page')
        if volume and page:
            try:
                if self.citation_validators['volume_reasonable'](volume) and \
                   self.citation_validators['page_reasonable'](page):
                    confidence += 0.05
            except (ValueError, TypeError):
                pass
        
        # Penalty for very short citations
        if len(citation_text) < 20:
            confidence -= 0.1
        
        # Penalty for missing key components
        if not self.citation_validators['has_case_names'](citation_text):
            confidence -= 0.2
        
        return max(0.1, min(1.0, confidence))
    
    def _validate_citation(self, citation: CitationMatch) -> bool:
        """Validate that citation meets minimum quality standards."""
        
        # Minimum confidence threshold
        if citation.confidence < 0.4:
            return False
        
        # Must have reasonable length
        if len(citation.text) < 15:
            return False
        
        # Must contain case name indicators
        if not self.citation_validators['has_case_names'](citation.text):
            return False
        
        # Validate year if present
        year = citation.components.get('year')
        if year:
            try:
                if not self.citation_validators['year_range'](year):
                    return False
            except (ValueError, TypeError):
                return False
        
        return True
    
    def _deduplicate_matches(self, matches: List[CitationMatch]) -> List[CitationMatch]:
        """Remove duplicate and overlapping citations."""
        if not matches:
            return []
        
        # Sort by start position
        matches.sort(key=lambda x: x.start_position)
        
        unique_matches = []
        
        for current_match in matches:
            # Check for overlap with existing matches
            overlaps = False
            
            for existing_match in unique_matches:
                # Check for positional overlap
                if (current_match.start_position < existing_match.end_position and
                    current_match.end_position > existing_match.start_position):
                    
                    # Keep the higher confidence match
                    if current_match.confidence > existing_match.confidence:
                        unique_matches.remove(existing_match)
                        break
                    else:
                        overlaps = True
                        break
                
                # Check for text similarity (fuzzy duplicate)
                if self._texts_are_similar(current_match.text, existing_match.text):
                    if current_match.confidence > existing_match.confidence:
                        unique_matches.remove(existing_match)
                        break
                    else:
                        overlaps = True
                        break
            
            if not overlaps:
                unique_matches.append(current_match)
        
        return unique_matches
    
    def _texts_are_similar(self, text1: str, text2: str, threshold: float = 0.9) -> bool:
        """Check if two citation texts are similar (likely duplicates)."""
        from difflib import SequenceMatcher
        
        # Normalize texts
        normalized1 = ' '.join(text1.split()).lower()
        normalized2 = ' '.join(text2.split()).lower()
        
        similarity = SequenceMatcher(None, normalized1, normalized2).ratio()
        return similarity >= threshold
    
    def get_extraction_stats(self, text: str) -> Dict[str, Any]:
        """Get detailed statistics about citation extraction."""
        citations = self.extract_citations(text)
        
        if not citations:
            return {
                'total_citations': 0,
                'by_jurisdiction': {},
                'by_confidence': {},
                'average_confidence': 0,
                'text_coverage': 0
            }
        
        # Count by jurisdiction
        by_jurisdiction = {}
        for citation in citations:
            jurisdiction = citation.jurisdiction
            by_jurisdiction[jurisdiction] = by_jurisdiction.get(jurisdiction, 0) + 1
        
        # Count by confidence bands
        by_confidence = {'high': 0, 'medium': 0, 'low': 0}
        for citation in citations:
            if citation.confidence >= 0.8:
                by_confidence['high'] += 1
            elif citation.confidence >= 0.6:
                by_confidence['medium'] += 1
            else:
                by_confidence['low'] += 1
        
        # Calculate average confidence
        avg_confidence = sum(c.confidence for c in citations) / len(citations)
        
        # Calculate text coverage (characters covered by citations)
        total_citation_chars = sum(len(c.text) for c in citations)
        text_coverage = (total_citation_chars / len(text)) * 100 if text else 0
        
        return {
            'total_citations': len(citations),
            'by_jurisdiction': by_jurisdiction,
            'by_confidence': by_confidence,
            'average_confidence': round(avg_confidence, 3),
            'text_coverage': round(text_coverage, 2)
        }


def validate_citation_accuracy(extractor: ImprovedLegalCitationExtractor, 
                              test_documents: Dict[str, Dict]) -> Dict[str, Any]:
    """
    Validate citation extraction accuracy against known test cases.
    
    Args:
        extractor: Citation extractor instance
        test_documents: Dictionary of test documents with expected citations
        
    Returns:
        Validation results with accuracy metrics
    """
    
    total_expected = 0
    total_found = 0  
    correct_extractions = 0
    validation_errors = []
    
    for doc_key, doc_data in test_documents.items():
        content = doc_data.get("content", "")
        expected_citations = doc_data.get("expected_citations", [])
        
        if not content or not expected_citations:
            continue
        
        try:
            # Extract citations
            extracted_citations = extractor.extract_citations(content)
            extracted_texts = [c.text for c in extracted_citations]
            
            total_expected += len(expected_citations)
            total_found += len(extracted_citations)
            
            # Check accuracy with fuzzy matching
            for expected in expected_citations:
                found_match = False
                for extracted in extracted_texts:
                    if _fuzzy_match_citations(expected, extracted):
                        correct_extractions += 1
                        found_match = True
                        break
                
                if not found_match:
                    validation_errors.append(f"Missing in {doc_key}: {expected}")
            
        except Exception as e:
            validation_errors.append(f"Error processing {doc_key}: {str(e)}")
    
    # Calculate metrics
    precision = (correct_extractions / total_found) * 100 if total_found > 0 else 0
    recall = (correct_extractions / total_expected) * 100 if total_expected > 0 else 0
    f1_score = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
    
    return {
        'accuracy_percentage': recall,  # Using recall as primary accuracy metric
        'precision': round(precision, 2),
        'recall': round(recall, 2),
        'f1_score': round(f1_score, 2),
        'correct_extractions': correct_extractions,
        'total_expected': total_expected,
        'total_found': total_found,
        'validation_errors': validation_errors[:10],  # Limit errors for display
        'meets_95_percent_target': recall >= 95.0
    }


def _fuzzy_match_citations(expected: str, extracted: str, threshold: float = 0.85) -> bool:
    """Fuzzy match two citations allowing for minor formatting differences."""
    from difflib import SequenceMatcher
    
    # Normalize both citations
    def normalize_citation(citation):
        # Remove extra whitespace, normalize punctuation
        normalized = ' '.join(citation.split())
        normalized = normalized.replace('[', ' [').replace(']', '] ')
        normalized = normalized.replace('(', ' (').replace(')', ') ')
        normalized = ' '.join(normalized.split())  # Clean up extra spaces
        return normalized.lower()
    
    expected_norm = normalize_citation(expected)
    extracted_norm = normalize_citation(extracted)
    
    # Calculate similarity
    similarity = SequenceMatcher(None, expected_norm, extracted_norm).ratio()
    
    # Also check if one contains the other (for partial matches)
    contains_match = (expected_norm in extracted_norm or extracted_norm in expected_norm)
    
    return similarity >= threshold or (contains_match and similarity >= 0.7)


if __name__ == "__main__":
    # Quick test
    extractor = ImprovedLegalCitationExtractor()
    
    test_text = """
    The principle in Carlill v. Carbolic Smoke Ball Company [1893] 1 Q.B. 256 
    was applied in Pharmaceutical Society of Great Britain v. Boots Cash Chemists 
    (Southern) Ltd [1953] 1 Q.B. 401. See also Brown v. Board of Education, 
    347 U.S. 483 (1954).
    """
    
    citations = extractor.extract_citations(test_text)
    stats = extractor.get_extraction_stats(test_text)
    
    print(f"Found {len(citations)} citations:")
    for citation in citations:
        print(f"  - {citation.text} (confidence: {citation.confidence:.2f})")
    
    print(f"\nStats: {stats}")