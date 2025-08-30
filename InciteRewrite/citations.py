import eyecite
import re

class CitationExtractor:
    def extract_citations(self, text: str) -> list:
        citations = eyecite.get_citations(text)
        results = []
        seen = set()
        
        for cite in citations:
            if hasattr(cite, 'corrected_citation'):
                citation_str = cite.corrected_citation()
            else:
                citation_str = str(cite)
            
            # Clean up citation string
            citation_str = citation_str.strip()
            if citation_str and citation_str not in seen:
                seen.add(citation_str)
                results.append(citation_str)
        
        return results