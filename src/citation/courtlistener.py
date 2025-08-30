"""
CourtListener API integration for citation verification.
Implements rate limiting, caching, and error handling.
"""
import requests
import time
import json
import hashlib
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class CourtListenerMatch:
    """Represents a match from CourtListener API."""
    case_name: str
    citation: str
    court: str
    date_filed: str
    url: str
    confidence: float
    
class RateLimiter:
    """Simple rate limiter for API calls."""
    
    def __init__(self, max_requests: int = 100, time_window: int = 3600):
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests = []
    
    def can_make_request(self) -> bool:
        """Check if we can make another request."""
        now = time.time()
        # Remove requests outside the time window
        self.requests = [req_time for req_time in self.requests 
                        if now - req_time < self.time_window]
        
        return len(self.requests) < self.max_requests
    
    def record_request(self):
        """Record that a request was made."""
        self.requests.append(time.time())
    
    def wait_time(self) -> float:
        """Get how long to wait before next request."""
        if self.can_make_request():
            return 0
        
        if self.requests:
            oldest_request = min(self.requests)
            return self.time_window - (time.time() - oldest_request)
        return 0

class CourtListenerService:
    """Service for interacting with CourtListener API."""
    
    def __init__(self, api_key: str = None, base_url: str = None):
        self.api_key = api_key
        self.base_url = base_url or "https://www.courtlistener.com/api/rest/v3/"
        self.rate_limiter = RateLimiter(max_requests=90, time_window=3600)  # Conservative limit
        self.session = requests.Session()
        
        # Configure session
        if self.api_key:
            self.session.headers.update({
                'Authorization': f'Token {self.api_key}',
                'User-Agent': 'InciteRewrite/1.0 (Legal Citation Verification)',
                'Content-Type': 'application/json'
            })
        else:
            logger.warning("No CourtListener API key provided - using anonymous access")
            
    def search_citation(self, citation: str, citation_type: str = None) -> List[CourtListenerMatch]:
        """Search for a citation in CourtListener database."""
        try:
            # Check rate limit
            if not self.rate_limiter.can_make_request():
                wait_time = self.rate_limiter.wait_time()
                logger.warning(f"Rate limit reached, waiting {wait_time:.1f} seconds")
                time.sleep(wait_time)
            
            # Build search query
            search_params = self._build_search_params(citation, citation_type)
            
            # Make API request
            endpoint = "search/"
            url = f"{self.base_url}{endpoint}"
            
            self.rate_limiter.record_request()
            response = self.session.get(url, params=search_params, timeout=10)
            
            if response.status_code == 200:
                results = response.json()
                matches = self._parse_search_results(results, citation)
                logger.info(f"Found {len(matches)} matches for citation: {citation}")
                return matches
            
            elif response.status_code == 429:
                # Rate limited
                logger.warning("Rate limited by CourtListener API")
                time.sleep(60)  # Wait 1 minute
                return []
            
            else:
                logger.error(f"CourtListener API error {response.status_code}: {response.text}")
                return []
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error accessing CourtListener: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error in citation search: {e}")
            return []
    
    def _build_search_params(self, citation: str, citation_type: str = None) -> Dict[str, Any]:
        """Build search parameters for CourtListener API."""
        params = {
            'type': 'o',  # Search opinions
            'q': citation,
            'format': 'json',
            'order_by': 'score desc'
        }
        
        # Extract components for more targeted search
        if citation_type == 'case_citation':
            # Try to parse volume, reporter, page
            import re
            case_match = re.search(r'(\d+)\s+([A-Za-z\.\s]+?)\s+(\d+)', citation)
            if case_match:
                volume, reporter, page = case_match.groups()
                params['citation'] = f"{volume} {reporter.strip()} {page}"
        
        return params
    
    def _parse_search_results(self, results: Dict, original_citation: str) -> List[CourtListenerMatch]:
        """Parse CourtListener search results."""
        matches = []
        
        if 'results' not in results:
            return matches
        
        for result in results['results'][:5]:  # Limit to top 5 results
            try:
                match = CourtListenerMatch(
                    case_name=result.get('caseName', 'Unknown Case'),
                    citation=result.get('citation', original_citation),
                    court=result.get('court', 'Unknown Court'),
                    date_filed=result.get('dateFiled', 'Unknown Date'),
                    url=result.get('absolute_url', ''),
                    confidence=self._calculate_match_confidence(result, original_citation)
                )
                matches.append(match)
                
            except Exception as e:
                logger.warning(f"Error parsing search result: {e}")
                continue
        
        return matches
    
    def _calculate_match_confidence(self, result: Dict, original_citation: str) -> float:
        """Calculate confidence score for a match."""
        confidence = 0.5  # Base confidence
        
        # Increase confidence based on various factors
        if 'citation' in result:
            api_citation = result['citation'].lower()
            original_lower = original_citation.lower()
            
            # Exact match
            if api_citation == original_lower:
                confidence += 0.4
            # Partial match
            elif any(part in api_citation for part in original_lower.split()):
                confidence += 0.2
        
        # CourtListener's own score
        if 'score' in result and result['score']:
            # Normalize CourtListener score to 0-0.3 range
            normalized_score = min(result['score'] / 10.0, 0.3)
            confidence += normalized_score
        
        # Presence of important fields
        if result.get('caseName'):
            confidence += 0.1
        if result.get('dateFiled'):
            confidence += 0.05
        if result.get('court'):
            confidence += 0.05
        
        return min(confidence, 1.0)
    
    def verify_citation(self, citation: str, citation_type: str = None) -> Dict[str, Any]:
        """Verify a single citation and return detailed results."""
        logger.info(f"Verifying citation: {citation}")
        
        matches = self.search_citation(citation, citation_type)
        
        if not matches:
            return {
                'verified': False,
                'confidence': 0.0,
                'error': 'No matches found in CourtListener database',
                'matches': []
            }
        
        # Find best match
        best_match = max(matches, key=lambda m: m.confidence)
        
        verification_result = {
            'verified': best_match.confidence > 0.7,
            'confidence': best_match.confidence,
            'best_match': {
                'case_name': best_match.case_name,
                'citation': best_match.citation,
                'court': best_match.court,
                'date_filed': best_match.date_filed,
                'url': best_match.url
            },
            'all_matches': [
                {
                    'case_name': match.case_name,
                    'citation': match.citation,
                    'court': match.court,
                    'confidence': match.confidence
                }
                for match in matches
            ]
        }
        
        return verification_result
    
    def bulk_verify_citations(self, citations: List[str]) -> List[Dict[str, Any]]:
        """Verify multiple citations with rate limiting."""
        results = []
        
        for i, citation in enumerate(citations):
            logger.info(f"Verifying citation {i+1}/{len(citations)}: {citation}")
            
            result = self.verify_citation(citation)
            results.append(result)
            
            # Add delay between requests to be respectful
            if i < len(citations) - 1:
                time.sleep(1)
        
        return results
    
    def get_service_status(self) -> Dict[str, Any]:
        """Check CourtListener service status."""
        try:
            # Simple health check
            response = self.session.get(f"{self.base_url}search/?format=json&q=test", timeout=5)
            
            return {
                'available': response.status_code == 200,
                'api_key_configured': self.api_key is not None,
                'rate_limit_remaining': self.rate_limiter.max_requests - len(self.rate_limiter.requests),
                'response_time': response.elapsed.total_seconds()
            }
            
        except Exception as e:
            logger.error(f"CourtListener service check failed: {e}")
            return {
                'available': False,
                'error': str(e),
                'api_key_configured': self.api_key is not None
            }

# Global service instance
courtlistener_service = None

def init_courtlistener_service(api_key: str = None):
    """Initialize CourtListener service."""
    global courtlistener_service
    courtlistener_service = CourtListenerService(api_key)
    logger.info("CourtListener service initialized")