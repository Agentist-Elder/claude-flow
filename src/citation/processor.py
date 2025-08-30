"""
Legal citation processing engine for InciteRewrite.
Extracts, validates, and normalizes legal citations from text.
"""
import re
from typing import List, Dict, Any, Tuple
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class Citation:
    """Represents a legal citation with metadata."""
    text: str
    citation_type: str
    normalized: str
    confidence: float
    volume: str = None
    reporter: str = None
    page: str = None
    year: str = None
    court: str = None
    
class CitationProcessor:
    """Main citation processing engine."""
    
    def __init__(self):
        self.patterns = self._load_citation_patterns()
        
    def _load_citation_patterns(self) -> Dict[str, List[re.Pattern]]:
        """Load regex patterns for different citation types."""
        patterns = {
            'case_citation': [
                # Standard case citations: Volume Reporter Page (Year)
                re.compile(r'\b(\d{1,4})\s+([A-Za-z\.]+(?:\s+[A-Za-z\.]+)*)\s+(\d{1,4})\s*(?:\((\d{4})\))?', re.IGNORECASE),
                # Supreme Court citations: Volume U.S. Page (Year)
                re.compile(r'\b(\d{1,4})\s+U\.?S\.?\s+(\d{1,4})\s*(?:\((\d{4})\))?', re.IGNORECASE),
                # Federal Reporter citations
                re.compile(r'\b(\d{1,4})\s+F\.?(?:\s?2d|\s?3d)?\s+(\d{1,4})\s*\(([^)]*)\s+(\d{4})\)', re.IGNORECASE),
            ],
            'statute_citation': [
                # U.S.C. citations: Title U.S.C. § Section
                re.compile(r'\b(\d{1,2})\s+U\.?S\.?C\.?\s*§\s*(\d+(?:\.\d+)*)', re.IGNORECASE),
                # Code of Federal Regulations: Title C.F.R. § Section
                re.compile(r'\b(\d{1,2})\s+C\.?F\.?R\.?\s*§\s*(\d+(?:\.\d+)*)', re.IGNORECASE),
                # State statutes: [State] [Code] § Section
                re.compile(r'\b([A-Z]{2,})\s+(?:REV\.?\s+)?(?:STAT\.?|CODE)\s*§?\s*(\d+(?:[.-]\d+)*)', re.IGNORECASE),
            ],
            'constitutional': [
                # U.S. Constitution: U.S. Const. art./amend. Section
                re.compile(r'\bU\.?S\.?\s+CONST\.?\s+(?:art\.?\s*([IVX]+)|amend\.?\s*([IVX]+|\d+))', re.IGNORECASE),
                # State constitutions
                re.compile(r'\b([A-Z]{2,})\s+CONST\.?\s+(?:art\.?\s*([IVX]+)|§\s*(\d+))', re.IGNORECASE),
            ],
            'rule_citation': [
                # Federal Rules: Fed. R. [Type] Rule
                re.compile(r'\bFED\.?\s+R\.?\s+(CIV\.?\s+P\.?|CRIM\.?\s+P\.?|EVID\.?|APP\.?\s+P\.?)\s*(\d+(?:\.\d+)*)', re.IGNORECASE),
                # Local rules
                re.compile(r'\bLOCAL\s+R\.?\s+(\d+(?:\.\d+)*)', re.IGNORECASE),
            ]
        }
        
        # Compile all patterns
        compiled_patterns = {}
        for citation_type, pattern_list in patterns.items():
            compiled_patterns[citation_type] = pattern_list
            
        return compiled_patterns
    
    def extract_citations(self, text: str) -> List[Citation]:
        """Extract all citations from text."""
        citations = []
        
        for citation_type, patterns in self.patterns.items():
            for pattern in patterns:
                matches = pattern.finditer(text)
                
                for match in matches:
                    citation = self._create_citation_from_match(
                        match, citation_type, text
                    )
                    if citation:
                        citations.append(citation)
        
        # Remove duplicates and sort by position in text
        citations = self._deduplicate_citations(citations, text)
        
        logger.info(f"Extracted {len(citations)} citations from text")
        return citations
    
    def _create_citation_from_match(self, match: re.Match, 
                                   citation_type: str, text: str) -> Citation:
        """Create Citation object from regex match."""
        matched_text = match.group(0).strip()
        groups = match.groups()
        
        try:
            if citation_type == 'case_citation':
                return Citation(
                    text=matched_text,
                    citation_type=citation_type,
                    normalized=self._normalize_case_citation(matched_text, groups),
                    confidence=self._calculate_confidence(matched_text, citation_type),
                    volume=groups[0] if groups[0] else None,
                    reporter=groups[1] if len(groups) > 1 and groups[1] else None,
                    page=groups[2] if len(groups) > 2 and groups[2] else None,
                    year=groups[3] if len(groups) > 3 and groups[3] else None
                )
            
            elif citation_type == 'statute_citation':
                return Citation(
                    text=matched_text,
                    citation_type=citation_type,
                    normalized=self._normalize_statute_citation(matched_text, groups),
                    confidence=self._calculate_confidence(matched_text, citation_type)
                )
            
            elif citation_type == 'constitutional':
                return Citation(
                    text=matched_text,
                    citation_type=citation_type,
                    normalized=self._normalize_constitutional_citation(matched_text, groups),
                    confidence=self._calculate_confidence(matched_text, citation_type)
                )
            
            elif citation_type == 'rule_citation':
                return Citation(
                    text=matched_text,
                    citation_type=citation_type,
                    normalized=self._normalize_rule_citation(matched_text, groups),
                    confidence=self._calculate_confidence(matched_text, citation_type)
                )
                
        except Exception as e:
            logger.warning(f"Error creating citation from match: {e}")
            return None
    
    def _normalize_case_citation(self, text: str, groups: Tuple) -> str:
        """Normalize case citation format."""
        try:
            if len(groups) >= 3 and groups[0] and groups[1] and groups[2]:
                volume = groups[0].strip()
                reporter = groups[1].strip().replace(' ', ' ')
                page = groups[2].strip()
                year = f" ({groups[3]})" if len(groups) > 3 and groups[3] else ""
                
                return f"{volume} {reporter} {page}{year}"
            return text
        except:
            return text
    
    def _normalize_statute_citation(self, text: str, groups: Tuple) -> str:
        """Normalize statute citation format."""
        try:
            if len(groups) >= 2:
                title = groups[0].strip()
                section = groups[1].strip()
                
                if 'U.S.C' in text.upper() or 'USC' in text.upper():
                    return f"{title} U.S.C. § {section}"
                elif 'C.F.R' in text.upper() or 'CFR' in text.upper():
                    return f"{title} C.F.R. § {section}"
                else:
                    # Handle generic format
                    return f"{title} U.S.C. § {section}"
                
            return text
        except:
            return text
    
    def _normalize_constitutional_citation(self, text: str, groups: Tuple) -> str:
        """Normalize constitutional citation format."""
        try:
            if 'U.S.' in text.upper() or 'CONST' in text.upper():
                return text.replace('CONST.', 'Const.').replace('  ', ' ')
            return text
        except:
            return text
    
    def _normalize_rule_citation(self, text: str, groups: Tuple) -> str:
        """Normalize rule citation format."""
        try:
            return text.replace('FED.', 'Fed.').replace('  ', ' ')
        except:
            return text
    
    def _calculate_confidence(self, citation_text: str, citation_type: str) -> float:
        """Calculate confidence score for citation match."""
        confidence = 0.5  # Base confidence
        
        # Increase confidence based on citation characteristics
        if citation_type == 'case_citation':
            # Look for year
            if re.search(r'\(\d{4}\)', citation_text):
                confidence += 0.2
            
            # Look for known reporters
            known_reporters = ['U.S.', 'F.2d', 'F.3d', 'S.Ct.', 'L.Ed.']
            for reporter in known_reporters:
                if reporter in citation_text:
                    confidence += 0.2
                    break
            
            # Check format consistency
            if re.search(r'\d+\s+\w+\s+\d+', citation_text):
                confidence += 0.1
        
        elif citation_type == 'statute_citation':
            if 'U.S.C.' in citation_text or 'C.F.R.' in citation_text:
                confidence += 0.3
            if '§' in citation_text:
                confidence += 0.1
        
        elif citation_type == 'constitutional':
            if 'U.S. Const.' in citation_text:
                confidence += 0.3
            if re.search(r'(art\.|amend\.)', citation_text, re.IGNORECASE):
                confidence += 0.2
        
        elif citation_type == 'rule_citation':
            if 'Fed. R.' in citation_text:
                confidence += 0.3
        
        return min(confidence, 1.0)
    
    def _deduplicate_citations(self, citations: List[Citation], text: str) -> List[Citation]:
        """Remove duplicate citations and sort by position."""
        seen = set()
        unique_citations = []
        
        # Sort by position in original text
        citations_with_pos = []
        for citation in citations:
            pos = text.find(citation.text)
            if pos != -1:
                citations_with_pos.append((pos, citation))
        
        citations_with_pos.sort(key=lambda x: x[0])
        
        for pos, citation in citations_with_pos:
            # Use normalized text as deduplication key
            key = citation.normalized.lower().strip()
            if key not in seen:
                seen.add(key)
                unique_citations.append(citation)
        
        return unique_citations
    
    def validate_citation_format(self, citation: Citation) -> Tuple[bool, str]:
        """Validate citation format and return any issues."""
        issues = []
        
        if citation.citation_type == 'case_citation':
            if not citation.volume:
                issues.append("Missing volume number")
            if not citation.reporter:
                issues.append("Missing reporter")
            if not citation.page:
                issues.append("Missing page number")
            
            # Check for reasonable volume/page ranges
            try:
                if citation.volume and int(citation.volume) > 999:
                    issues.append("Volume number seems unusually high")
                if citation.page and int(citation.page) > 9999:
                    issues.append("Page number seems unusually high")
            except ValueError:
                issues.append("Invalid numeric values")
        
        elif citation.citation_type == 'statute_citation':
            if '§' not in citation.text:
                issues.append("Missing section symbol")
        
        is_valid = len(issues) == 0
        return is_valid, "; ".join(issues) if issues else "Valid format"

# Global processor instance
citation_processor = CitationProcessor()