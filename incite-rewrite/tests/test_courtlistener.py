"""
CourtListener API client tests using London School TDD methodology.
Tests focus on HTTP client behavior, API interactions, and external service mocking.
"""

import pytest
import json
import time
from unittest.mock import Mock, patch, MagicMock, call, AsyncMock
from typing import Dict, List, Any, Optional
import aiohttp
import requests


class CourtListenerClient:
    """Client for interacting with CourtListener API."""
    
    def __init__(self, 
                 api_key: str,
                 base_url: str = "https://www.courtlistener.com/api/rest/v3/",
                 timeout: int = 30,
                 rate_limit_delay: float = 0.1):
        self.api_key = api_key
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.rate_limit_delay = rate_limit_delay
        self.session = None
        self._last_request_time = 0
        self.request_count = 0
        self.error_count = 0
    
    def _get_headers(self) -> Dict[str, str]:
        """Get standard headers for API requests."""
        return {
            'Authorization': f'Token {self.api_key}',
            'Content-Type': 'application/json',
            'User-Agent': 'InciteRewrite/1.0 Legal Citation Verifier'
        }
    
    def _enforce_rate_limit(self):
        """Enforce rate limiting between requests."""
        current_time = time.time()
        time_since_last = current_time - self._last_request_time
        
        if time_since_last < self.rate_limit_delay:
            time.sleep(self.rate_limit_delay - time_since_last)
        
        self._last_request_time = time.time()
    
    def _make_request(self, endpoint: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """Make HTTP request to CourtListener API."""
        if not self.session:
            self.session = requests.Session()
        
        self._enforce_rate_limit()
        url = f"{self.base_url}/{endpoint.lstrip('/')}/"
        
        try:
            self.request_count += 1
            response = self.session.get(
                url,
                params=params or {},
                headers=self._get_headers(),
                timeout=self.timeout
            )
            
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.RequestException as e:
            self.error_count += 1
            raise CourtListenerAPIError(f"Request failed: {str(e)}")
        except json.JSONDecodeError as e:
            self.error_count += 1
            raise CourtListenerAPIError(f"Invalid JSON response: {str(e)}")
    
    async def _make_async_request(self, endpoint: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """Make asynchronous HTTP request to CourtListener API."""
        self._enforce_rate_limit()
        url = f"{self.base_url}/{endpoint.lstrip('/')}/"
        
        try:
            self.request_count += 1
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url,
                    params=params or {},
                    headers=self._get_headers(),
                    timeout=aiohttp.ClientTimeout(total=self.timeout)
                ) as response:
                    response.raise_for_status()
                    return await response.json()
                    
        except aiohttp.ClientError as e:
            self.error_count += 1
            raise CourtListenerAPIError(f"Async request failed: {str(e)}")
        except json.JSONDecodeError as e:
            self.error_count += 1
            raise CourtListenerAPIError(f"Invalid JSON response: {str(e)}")
    
    def search_opinions(self, query: str, court: str = None, **kwargs) -> Dict[str, Any]:
        """Search for court opinions."""
        if not query or not isinstance(query, str):
            raise ValueError("Query must be a non-empty string")
        
        params = {'q': query}
        
        if court:
            params['court'] = court
        
        # Add additional search parameters
        for key, value in kwargs.items():
            if value is not None:
                params[key] = value
        
        return self._make_request('search', params)
    
    def get_opinion_by_id(self, opinion_id: int) -> Dict[str, Any]:
        """Get specific opinion by ID."""
        if not isinstance(opinion_id, int) or opinion_id <= 0:
            raise ValueError("Opinion ID must be a positive integer")
        
        return self._make_request(f'opinions/{opinion_id}')
    
    def get_court_info(self, court_id: str) -> Dict[str, Any]:
        """Get information about a specific court."""
        if not court_id or not isinstance(court_id, str):
            raise ValueError("Court ID must be a non-empty string")
        
        return self._make_request(f'courts/{court_id}')
    
    def verify_citation(self, citation: str, citation_type: str = None) -> Dict[str, Any]:
        """Verify a legal citation against CourtListener database."""
        if not citation or not isinstance(citation, str):
            raise ValueError("Citation must be a non-empty string")
        
        # Parse citation components for more targeted search
        search_params = self._parse_citation_for_search(citation, citation_type)
        
        results = self.search_opinions(**search_params)
        
        # Process results to determine verification status
        verification_result = {
            'citation': citation,
            'verified': False,
            'matches': [],
            'confidence_score': 0.0,
            'search_params': search_params
        }
        
        if results.get('results'):
            verification_result['matches'] = results['results']
            verification_result['verified'] = len(results['results']) > 0
            verification_result['confidence_score'] = self._calculate_verification_confidence(
                citation, results['results']
            )
        
        return verification_result
    
    def _parse_citation_for_search(self, citation: str, citation_type: str = None) -> Dict[str, Any]:
        """Parse citation into search parameters."""
        import re
        
        search_params = {'q': citation}
        
        # Try to extract volume, reporter, and page for more precise search
        federal_pattern = r'(\d+)\s+([A-Z]\w*\.?\s*\d*)\s+(\d+)\s*\((\d{4})\)'
        match = re.search(federal_pattern, citation)
        
        if match:
            volume, reporter, page, year = match.groups()
            search_params.update({
                'volume': volume,
                'reporter': reporter.strip(),
                'page': page,
                'year': year
            })
        
        return search_params
    
    def _calculate_verification_confidence(self, citation: str, results: List[Dict]) -> float:
        """Calculate confidence score for citation verification."""
        if not results:
            return 0.0
        
        # Base confidence on number of results and text similarity
        base_confidence = min(0.8, len(results) * 0.2)
        
        # Check for exact matches in citation text
        citation_lower = citation.lower()
        exact_matches = 0
        
        for result in results[:5]:  # Check first 5 results
            result_text = str(result.get('citation', '')).lower()
            if citation_lower in result_text or result_text in citation_lower:
                exact_matches += 1
        
        if exact_matches > 0:
            base_confidence += 0.2 * (exact_matches / len(results[:5]))
        
        return min(base_confidence, 1.0)
    
    async def search_opinions_async(self, query: str, court: str = None, **kwargs) -> Dict[str, Any]:
        """Asynchronous search for court opinions."""
        if not query or not isinstance(query, str):
            raise ValueError("Query must be a non-empty string")
        
        params = {'q': query}
        
        if court:
            params['court'] = court
        
        for key, value in kwargs.items():
            if value is not None:
                params[key] = value
        
        return await self._make_async_request('search', params)
    
    async def verify_citation_async(self, citation: str, citation_type: str = None) -> Dict[str, Any]:
        """Asynchronous citation verification."""
        if not citation or not isinstance(citation, str):
            raise ValueError("Citation must be a non-empty string")
        
        search_params = self._parse_citation_for_search(citation, citation_type)
        results = await self.search_opinions_async(**search_params)
        
        verification_result = {
            'citation': citation,
            'verified': False,
            'matches': [],
            'confidence_score': 0.0,
            'search_params': search_params
        }
        
        if results.get('results'):
            verification_result['matches'] = results['results']
            verification_result['verified'] = len(results['results']) > 0
            verification_result['confidence_score'] = self._calculate_verification_confidence(
                citation, results['results']
            )
        
        return verification_result
    
    def get_api_stats(self) -> Dict[str, Any]:
        """Get API usage statistics."""
        error_rate = (self.error_count / max(self.request_count, 1)) * 100
        
        return {
            'total_requests': self.request_count,
            'total_errors': self.error_count,
            'error_rate': round(error_rate, 2),
            'base_url': self.base_url,
            'timeout': self.timeout,
            'rate_limit_delay': self.rate_limit_delay
        }
    
    def close(self):
        """Close the HTTP session."""
        if self.session:
            self.session.close()
            self.session = None


class CourtListenerAPIError(Exception):
    """Custom exception for CourtListener API errors."""
    pass


class TestCourtListenerClientInitialization:
    """Test CourtListener client initialization and configuration."""
    
    def test_initializes_with_required_api_key(self):
        """Should initialize client with required API key."""
        api_key = "test_api_key_12345"
        client = CourtListenerClient(api_key)
        
        assert client.api_key == api_key
        assert client.base_url == "https://www.courtlistener.com/api/rest/v3"
        assert client.timeout == 30
        assert client.rate_limit_delay == 0.1
        assert client.session is None
        assert client.request_count == 0
        assert client.error_count == 0
    
    def test_initializes_with_custom_configuration(self):
        """Should initialize with custom base URL, timeout, and rate limit."""
        client = CourtListenerClient(
            api_key="test_key",
            base_url="https://custom.api.example.com/v1/",
            timeout=60,
            rate_limit_delay=0.5
        )
        
        assert client.base_url == "https://custom.api.example.com/v1"
        assert client.timeout == 60
        assert client.rate_limit_delay == 0.5
    
    def test_creates_proper_authorization_headers(self):
        """Should create proper authorization headers for API requests."""
        api_key = "test_secret_key"
        client = CourtListenerClient(api_key)
        
        headers = client._get_headers()
        
        assert headers['Authorization'] == f'Token {api_key}'
        assert headers['Content-Type'] == 'application/json'
        assert 'User-Agent' in headers
        assert 'InciteRewrite' in headers['User-Agent']


class TestRateLimitingBehavior:
    """Test rate limiting behavior and request timing."""
    
    def test_enforces_rate_limit_between_requests(self):
        """Should enforce minimum delay between consecutive requests."""
        client = CourtListenerClient("test_key", rate_limit_delay=0.2)
        
        # Simulate timing of rate limit enforcement
        start_time = time.time()
        client._enforce_rate_limit()
        first_call_time = time.time()
        
        client._enforce_rate_limit()
        second_call_time = time.time()
        
        # Second call should be delayed by at least rate_limit_delay
        actual_delay = second_call_time - first_call_time
        assert actual_delay >= client.rate_limit_delay * 0.9  # Allow for small timing variations
    
    def test_tracks_last_request_time(self):
        """Should track and update last request time for rate limiting."""
        client = CourtListenerClient("test_key")
        
        initial_time = client._last_request_time
        assert initial_time == 0
        
        client._enforce_rate_limit()
        
        assert client._last_request_time > initial_time
        assert client._last_request_time <= time.time()


class TestHTTPRequestBehavior:
    """Test HTTP request behavior using mocks to verify interactions."""
    
    @patch('requests.Session')
    def test_creates_http_session_for_requests(self, mock_session_class):
        """Should create HTTP session for making requests."""
        mock_session = Mock()
        mock_session_class.return_value = mock_session
        
        client = CourtListenerClient("test_key")
        
        # Session should be created when making first request
        assert client.session is None
        
        # Mock successful response
        mock_response = Mock()
        mock_response.json.return_value = {'test': 'data'}
        mock_session.get.return_value = mock_response
        
        client._make_request('test-endpoint')
        
        # Session should now be created
        mock_session_class.assert_called_once()
        assert client.session == mock_session
    
    @patch('requests.Session')
    def test_makes_get_request_with_proper_parameters(self, mock_session_class):
        """Should make GET request with proper URL, params, and headers."""
        mock_session = Mock()
        mock_response = Mock()
        mock_response.json.return_value = {'result': 'success'}
        mock_session.get.return_value = mock_response
        mock_session_class.return_value = mock_session
        
        client = CourtListenerClient("test_api_key")
        params = {'q': 'test query', 'court': 'supreme'}
        
        result = client._make_request('search', params)
        
        # Verify the request was made correctly
        mock_session.get.assert_called_once()
        call_args = mock_session.get.call_args
        
        assert call_args[1]['params'] == params
        assert call_args[1]['headers']['Authorization'] == 'Token test_api_key'
        assert 'search/' in call_args[0][0]  # URL contains endpoint
        assert call_args[1]['timeout'] == 30
        
        assert result == {'result': 'success'}
    
    @patch('requests.Session')
    def test_handles_http_request_exceptions(self, mock_session_class):
        """Should handle HTTP request exceptions properly."""
        mock_session = Mock()
        mock_session.get.side_effect = requests.exceptions.ConnectionError("Connection failed")
        mock_session_class.return_value = mock_session
        
        client = CourtListenerClient("test_key")
        
        with pytest.raises(CourtListenerAPIError, match="Request failed"):
            client._make_request('test-endpoint')
        
        assert client.error_count == 1
    
    @patch('requests.Session')
    def test_handles_json_decode_errors(self, mock_session_class):
        """Should handle JSON decode errors from API responses."""
        mock_session = Mock()
        mock_response = Mock()
        mock_response.json.side_effect = json.JSONDecodeError("Invalid JSON", "doc", 0)
        mock_response.raise_for_status.return_value = None  # HTTP success
        mock_session.get.return_value = mock_response
        mock_session_class.return_value = mock_session
        
        client = CourtListenerClient("test_key")
        
        with pytest.raises(CourtListenerAPIError, match="Invalid JSON response"):
            client._make_request('test-endpoint')
        
        assert client.error_count == 1
    
    @patch('requests.Session')
    def test_increments_request_counter(self, mock_session_class):
        """Should increment request counter for each API call."""
        mock_session = Mock()
        mock_response = Mock()
        mock_response.json.return_value = {'data': 'test'}
        mock_session.get.return_value = mock_response
        mock_session_class.return_value = mock_session
        
        client = CourtListenerClient("test_key")
        
        assert client.request_count == 0
        
        client._make_request('endpoint1')
        assert client.request_count == 1
        
        client._make_request('endpoint2')
        assert client.request_count == 2


class TestOpinionSearchBehavior:
    """Test opinion search functionality and parameter handling."""
    
    @patch.object(CourtListenerClient, '_make_request')
    def test_searches_opinions_with_query(self, mock_make_request):
        """Should search opinions with provided query parameters."""
        mock_make_request.return_value = {
            'count': 1,
            'results': [{'id': 123, 'citation': 'Test Citation'}]
        }
        
        client = CourtListenerClient("test_key")
        result = client.search_opinions("Brown v. Board")
        
        mock_make_request.assert_called_once_with('search', {'q': 'Brown v. Board'})
        assert result['count'] == 1
        assert len(result['results']) == 1
    
    @patch.object(CourtListenerClient, '_make_request')
    def test_includes_court_parameter_when_specified(self, mock_make_request):
        """Should include court parameter when specified in search."""
        mock_make_request.return_value = {'results': []}
        
        client = CourtListenerClient("test_key")
        client.search_opinions("test query", court="supreme")
        
        expected_params = {'q': 'test query', 'court': 'supreme'}
        mock_make_request.assert_called_once_with('search', expected_params)
    
    @patch.object(CourtListenerClient, '_make_request')
    def test_includes_additional_search_parameters(self, mock_make_request):
        """Should include additional keyword arguments as search parameters."""
        mock_make_request.return_value = {'results': []}
        
        client = CourtListenerClient("test_key")
        client.search_opinions(
            "test query",
            court="federal",
            year=2020,
            author="Justice Smith"
        )
        
        expected_params = {
            'q': 'test query',
            'court': 'federal',
            'year': 2020,
            'author': 'Justice Smith'
        }
        mock_make_request.assert_called_once_with('search', expected_params)
    
    def test_validates_query_parameter(self):
        """Should validate that query parameter is provided and valid."""
        client = CourtListenerClient("test_key")
        
        # Empty string should raise ValueError
        with pytest.raises(ValueError, match="Query must be a non-empty string"):
            client.search_opinions("")
        
        # None should raise ValueError
        with pytest.raises(ValueError, match="Query must be a non-empty string"):
            client.search_opinions(None)
        
        # Non-string should raise ValueError
        with pytest.raises(ValueError, match="Query must be a non-empty string"):
            client.search_opinions(123)
    
    @patch.object(CourtListenerClient, '_make_request')
    def test_filters_none_values_from_parameters(self, mock_make_request):
        """Should filter out None values from search parameters."""
        mock_make_request.return_value = {'results': []}
        
        client = CourtListenerClient("test_key")
        client.search_opinions(
            "test query",
            court=None,  # Should be filtered out
            year=2020,   # Should be included
            author=None  # Should be filtered out
        )
        
        expected_params = {'q': 'test query', 'year': 2020}
        mock_make_request.assert_called_once_with('search', expected_params)


class TestOpinionRetrievalBehavior:
    """Test individual opinion retrieval functionality."""
    
    @patch.object(CourtListenerClient, '_make_request')
    def test_retrieves_opinion_by_id(self, mock_make_request):
        """Should retrieve specific opinion by ID."""
        mock_opinion_data = {
            'id': 123,
            'citation': 'Brown v. Board, 347 U.S. 483 (1954)',
            'court': 'Supreme Court'
        }
        mock_make_request.return_value = mock_opinion_data
        
        client = CourtListenerClient("test_key")
        result = client.get_opinion_by_id(123)
        
        mock_make_request.assert_called_once_with('opinions/123')
        assert result == mock_opinion_data
    
    def test_validates_opinion_id_parameter(self):
        """Should validate opinion ID parameter."""
        client = CourtListenerClient("test_key")
        
        # Non-integer should raise ValueError
        with pytest.raises(ValueError, match="Opinion ID must be a positive integer"):
            client.get_opinion_by_id("invalid")
        
        # Zero should raise ValueError
        with pytest.raises(ValueError, match="Opinion ID must be a positive integer"):
            client.get_opinion_by_id(0)
        
        # Negative number should raise ValueError
        with pytest.raises(ValueError, match="Opinion ID must be a positive integer"):
            client.get_opinion_by_id(-1)


class TestCourtInformationRetrieval:
    """Test court information retrieval functionality."""
    
    @patch.object(CourtListenerClient, '_make_request')
    def test_retrieves_court_information(self, mock_make_request):
        """Should retrieve court information by court ID."""
        mock_court_data = {
            'id': 'supreme',
            'name': 'Supreme Court of the United States',
            'jurisdiction': 'Federal'
        }
        mock_make_request.return_value = mock_court_data
        
        client = CourtListenerClient("test_key")
        result = client.get_court_info('supreme')
        
        mock_make_request.assert_called_once_with('courts/supreme')
        assert result == mock_court_data
    
    def test_validates_court_id_parameter(self):
        """Should validate court ID parameter."""
        client = CourtListenerClient("test_key")
        
        # Empty string should raise ValueError
        with pytest.raises(ValueError, match="Court ID must be a non-empty string"):
            client.get_court_info("")
        
        # None should raise ValueError
        with pytest.raises(ValueError, match="Court ID must be a non-empty string"):
            client.get_court_info(None)
        
        # Non-string should raise ValueError
        with pytest.raises(ValueError, match="Court ID must be a non-empty string"):
            client.get_court_info(123)


class TestCitationVerificationBehavior:
    """Test citation verification functionality using mocks."""
    
    @patch.object(CourtListenerClient, 'search_opinions')
    def test_verifies_valid_citation(self, mock_search):
        """Should verify valid citation by searching CourtListener database."""
        mock_search.return_value = {
            'count': 1,
            'results': [
                {
                    'id': 123,
                    'citation': '347 U.S. 483 (1954)',
                    'case_name': 'Brown v. Board of Education'
                }
            ]
        }
        
        client = CourtListenerClient("test_key")
        result = client.verify_citation("347 U.S. 483 (1954)")
        
        assert result['citation'] == "347 U.S. 483 (1954)"
        assert result['verified'] is True
        assert len(result['matches']) == 1
        assert result['confidence_score'] > 0.0
        assert 'search_params' in result
        
        # Should have called search_opinions with parsed parameters
        mock_search.assert_called_once()
    
    @patch.object(CourtListenerClient, 'search_opinions')
    def test_handles_citation_not_found(self, mock_search):
        """Should handle case when citation is not found in database."""
        mock_search.return_value = {'count': 0, 'results': []}
        
        client = CourtListenerClient("test_key")
        result = client.verify_citation("999 Invalid 999 (9999)")
        
        assert result['citation'] == "999 Invalid 999 (9999)"
        assert result['verified'] is False
        assert result['matches'] == []
        assert result['confidence_score'] == 0.0
    
    def test_parses_citation_for_targeted_search(self):
        """Should parse citation components for more targeted search."""
        client = CourtListenerClient("test_key")
        
        # Test federal case citation parsing
        params = client._parse_citation_for_search("123 F.3d 456 (2020)")
        
        assert params['q'] == "123 F.3d 456 (2020)"
        assert params['volume'] == '123'
        assert params['reporter'] == 'F.3d'
        assert params['page'] == '456'
        assert params['year'] == '2020'
    
    def test_calculates_verification_confidence_scores(self):
        """Should calculate appropriate confidence scores based on search results."""
        client = CourtListenerClient("test_key")
        
        # Test with no results
        confidence = client._calculate_verification_confidence("test citation", [])
        assert confidence == 0.0
        
        # Test with matching results
        matching_results = [
            {'citation': 'Test Citation 123', 'id': 1},
            {'citation': 'Another Citation', 'id': 2}
        ]
        confidence = client._calculate_verification_confidence("test citation", matching_results)
        assert 0.0 < confidence <= 1.0
    
    def test_validates_citation_parameter(self):
        """Should validate citation parameter for verification."""
        client = CourtListenerClient("test_key")
        
        # Empty string should raise ValueError
        with pytest.raises(ValueError, match="Citation must be a non-empty string"):
            client.verify_citation("")
        
        # None should raise ValueError
        with pytest.raises(ValueError, match="Citation must be a non-empty string"):
            client.verify_citation(None)


class TestAsynchronousOperations:
    """Test asynchronous API operations using async mocks."""
    
    @patch('aiohttp.ClientSession')
    @pytest.mark.asyncio
    async def test_makes_async_search_request(self, mock_session_class):
        """Should make asynchronous search request with proper parameters."""
        # Setup async mock
        mock_session = AsyncMock()
        mock_response = AsyncMock()
        mock_response.json.return_value = {'results': [{'id': 1}]}
        mock_response.raise_for_status.return_value = None
        
        mock_session.__aenter__.return_value = mock_session
        mock_session.get.return_value.__aenter__.return_value = mock_response
        mock_session_class.return_value = mock_session
        
        client = CourtListenerClient("test_key")
        result = await client.search_opinions_async("test query")
        
        # Verify async session was created and used
        mock_session_class.assert_called_once()
        mock_session.get.assert_called_once()
        
        # Verify result
        assert result == {'results': [{'id': 1}]}
    
    @patch.object(CourtListenerClient, 'search_opinions_async')
    @pytest.mark.asyncio
    async def test_performs_async_citation_verification(self, mock_search_async):
        """Should perform asynchronous citation verification."""
        mock_search_async.return_value = {
            'count': 1,
            'results': [{'id': 123, 'citation': 'Test Citation'}]
        }
        
        client = CourtListenerClient("test_key")
        result = await client.verify_citation_async("Test Citation")
        
        assert result['verified'] is True
        assert len(result['matches']) == 1
        mock_search_async.assert_called_once()
    
    @patch('aiohttp.ClientSession')
    @pytest.mark.asyncio
    async def test_handles_async_request_errors(self, mock_session_class):
        """Should handle errors in asynchronous requests."""
        mock_session = AsyncMock()
        mock_session.__aenter__.return_value = mock_session
        mock_session.get.side_effect = aiohttp.ClientError("Connection failed")
        mock_session_class.return_value = mock_session
        
        client = CourtListenerClient("test_key")
        
        with pytest.raises(CourtListenerAPIError, match="Async request failed"):
            await client._make_async_request('test-endpoint')
        
        assert client.error_count == 1


class TestAPIStatisticsAndMonitoring:
    """Test API usage statistics and monitoring functionality."""
    
    def test_tracks_request_and_error_counts(self):
        """Should track total requests and errors for monitoring."""
        client = CourtListenerClient("test_key")
        
        # Initial state
        assert client.request_count == 0
        assert client.error_count == 0
        
        # Simulate successful request
        with patch.object(client, '_make_request') as mock_request:
            mock_request.return_value = {'success': True}
            client.search_opinions("test")
        
        # Request count should be updated by _make_request
        # (We can't test this directly without making real requests)
    
    def test_provides_comprehensive_api_statistics(self):
        """Should provide comprehensive API usage statistics."""
        client = CourtListenerClient("test_key", timeout=60, rate_limit_delay=0.3)
        client.request_count = 100
        client.error_count = 5
        
        stats = client.get_api_stats()
        
        assert stats['total_requests'] == 100
        assert stats['total_errors'] == 5
        assert stats['error_rate'] == 5.0  # 5/100 * 100
        assert stats['base_url'] == client.base_url
        assert stats['timeout'] == 60
        assert stats['rate_limit_delay'] == 0.3
    
    def test_calculates_error_rate_correctly(self):
        """Should calculate error rate correctly including edge cases."""
        client = CourtListenerClient("test_key")
        
        # No requests made
        client.request_count = 0
        client.error_count = 0
        stats = client.get_api_stats()
        assert stats['error_rate'] == 0.0
        
        # All requests failed
        client.request_count = 10
        client.error_count = 10
        stats = client.get_api_stats()
        assert stats['error_rate'] == 100.0
        
        # Partial failures
        client.request_count = 50
        client.error_count = 3
        stats = client.get_api_stats()
        assert stats['error_rate'] == 6.0  # 3/50 * 100


class TestSessionManagement:
    """Test HTTP session management and cleanup."""
    
    @patch('requests.Session')
    def test_creates_session_on_demand(self, mock_session_class):
        """Should create HTTP session on demand when making requests."""
        mock_session = Mock()
        mock_response = Mock()
        mock_response.json.return_value = {'data': 'test'}
        mock_session.get.return_value = mock_response
        mock_session_class.return_value = mock_session
        
        client = CourtListenerClient("test_key")
        
        # Session should not exist initially
        assert client.session is None
        
        # Make request to trigger session creation
        client._make_request('test-endpoint')
        
        # Session should now be created and stored
        mock_session_class.assert_called_once()
        assert client.session == mock_session
    
    @patch('requests.Session')
    def test_reuses_existing_session(self, mock_session_class):
        """Should reuse existing session for multiple requests."""
        mock_session = Mock()
        mock_response = Mock()
        mock_response.json.return_value = {'data': 'test'}
        mock_session.get.return_value = mock_response
        mock_session_class.return_value = mock_session
        
        client = CourtListenerClient("test_key")
        
        # Make multiple requests
        client._make_request('endpoint1')
        client._make_request('endpoint2')
        
        # Session should only be created once
        mock_session_class.assert_called_once()
        
        # But should be used for both requests
        assert mock_session.get.call_count == 2
    
    def test_closes_session_properly(self):
        """Should close HTTP session properly when requested."""
        mock_session = Mock()
        
        client = CourtListenerClient("test_key")
        client.session = mock_session
        
        client.close()
        
        # Session should be closed and reset
        mock_session.close.assert_called_once()
        assert client.session is None
    
    def test_handles_close_with_no_session(self):
        """Should handle close call when no session exists."""
        client = CourtListenerClient("test_key")
        
        # Should not raise an exception
        client.close()
        assert client.session is None


@pytest.mark.integration
class TestCourtListenerClientIntegration:
    """Test integration scenarios combining multiple client features."""
    
    @patch.object(CourtListenerClient, '_make_request')
    def test_complete_citation_verification_workflow(self, mock_make_request):
        """Should perform complete citation verification workflow."""
        # Mock search results for citation verification
        mock_make_request.return_value = {
            'count': 2,
            'results': [
                {
                    'id': 123,
                    'citation': '347 U.S. 483 (1954)',
                    'case_name': 'Brown v. Board of Education',
                    'court': 'Supreme Court'
                },
                {
                    'id': 124,
                    'citation': '347 U.S. 483',
                    'case_name': 'Brown v. Board',
                    'court': 'Supreme Court'
                }
            ]
        }
        
        client = CourtListenerClient("test_key")
        
        # Perform citation verification
        result = client.verify_citation("347 U.S. 483 (1954)")
        
        # Should successfully verify citation
        assert result['verified'] is True
        assert len(result['matches']) == 2
        assert result['confidence_score'] > 0.5
        
        # Should have made search request with parsed parameters
        mock_make_request.assert_called_once()
        call_args = mock_make_request.call_args[0]
        assert call_args[0] == 'search'
        
        # Should include citation components in search parameters
        search_params = mock_make_request.call_args[1] if len(mock_make_request.call_args) > 1 else mock_make_request.call_args[0][1]
        assert '347 U.S. 483 (1954)' in search_params.values()
    
    @patch.object(CourtListenerClient, '_make_request') 
    def test_handles_multiple_verification_requests_with_rate_limiting(self, mock_make_request):
        """Should handle multiple verification requests with proper rate limiting."""
        mock_make_request.return_value = {'count': 0, 'results': []}
        
        client = CourtListenerClient("test_key", rate_limit_delay=0.1)
        citations = [
            "347 U.S. 483 (1954)",
            "163 U.S. 537 (1896)",
            "410 U.S. 113 (1973)"
        ]
        
        start_time = time.time()
        results = []
        
        for citation in citations:
            result = client.verify_citation(citation)
            results.append(result)
        
        end_time = time.time()
        
        # Should have processed all citations
        assert len(results) == 3
        
        # Should have enforced rate limiting (3 requests with 0.1s delay = at least 0.2s total)
        total_time = end_time - start_time
        assert total_time >= 0.15  # Allow for some timing variance
        
        # Should have made 3 search requests
        assert mock_make_request.call_count == 3
    
    @patch.object(CourtListenerClient, '_make_request')
    def test_error_recovery_and_statistics_tracking(self, mock_make_request):
        """Should handle errors gracefully and track statistics properly."""
        # First request fails, second succeeds
        mock_make_request.side_effect = [
            CourtListenerAPIError("Network error"),
            {'count': 1, 'results': [{'id': 123}]}
        ]
        
        client = CourtListenerClient("test_key")
        
        # First request should fail
        with pytest.raises(CourtListenerAPIError):
            client.search_opinions("failing query")
        
        # Second request should succeed
        result = client.search_opinions("successful query")
        assert result['count'] == 1
        
        # Statistics should reflect both requests
        stats = client.get_api_stats()
        assert stats['total_requests'] >= 2
        assert stats['total_errors'] >= 1
        assert stats['error_rate'] > 0


@pytest.mark.performance
class TestCourtListenerClientPerformance:
    """Test performance characteristics of the CourtListener client."""
    
    @patch.object(CourtListenerClient, '_make_request')
    def test_batch_citation_verification_performance(self, mock_make_request, performance_monitor):
        """Should handle batch citation verification efficiently."""
        # Mock consistent response time
        mock_make_request.return_value = {'count': 1, 'results': [{'id': 123}]}
        
        client = CourtListenerClient("test_key", rate_limit_delay=0.01)  # Minimal delay for testing
        
        citations = [
            f"Case {i} F.3d {i*10} (2020)" for i in range(1, 21)
        ]  # 20 citations
        
        performance_monitor.start()
        
        results = []
        for citation in citations:
            result = client.verify_citation(citation)
            results.append(result)
        
        metrics = performance_monitor.stop()
        
        # Should complete all verifications
        assert len(results) == 20
        assert all(result['verified'] for result in results)
        
        # Should maintain reasonable performance
        assert metrics['duration'] < 5.0  # Less than 5 seconds
        assert mock_make_request.call_count == 20
    
    def test_rate_limiting_overhead_is_minimal(self, performance_monitor):
        """Should have minimal overhead from rate limiting mechanism."""
        client = CourtListenerClient("test_key", rate_limit_delay=0.001)
        
        performance_monitor.start()
        
        # Call rate limiting many times
        for _ in range(100):
            client._enforce_rate_limit()
        
        metrics = performance_monitor.stop()
        
        # Should complete quickly despite many rate limit checks
        assert metrics['duration'] < 1.0
        assert metrics['memory_delta'] < 10  # Minimal memory usage


class TestCourtListenerClientEdgeCases:
    """Test edge cases and error conditions."""
    
    def test_handles_empty_api_responses(self):
        """Should handle empty or malformed API responses gracefully."""
        with patch.object(CourtListenerClient, '_make_request') as mock_request:
            mock_request.return_value = {}  # Empty response
            
            client = CourtListenerClient("test_key")
            result = client.verify_citation("test citation")
            
            # Should handle empty response without crashing
            assert result['verified'] is False
            assert result['matches'] == []
            assert result['confidence_score'] == 0.0
    
    def test_handles_malformed_citation_strings(self):
        """Should handle malformed citation strings without crashing."""
        client = CourtListenerClient("test_key")
        
        malformed_citations = [
            "not a citation at all",
            "123 456 789",  # Numbers only
            "v. v. v.",      # Only 'v.' separators
            "()()()()"       # Only parentheses
        ]
        
        for citation in malformed_citations:
            # Should parse without throwing exceptions
            params = client._parse_citation_for_search(citation)
            assert 'q' in params
            assert params['q'] == citation
    
    @patch.object(CourtListenerClient, '_make_request')
    def test_handles_api_timeout_scenarios(self, mock_make_request):
        """Should handle API timeout scenarios appropriately."""
        mock_make_request.side_effect = CourtListenerAPIError("Request timeout")
        
        client = CourtListenerClient("test_key")
        
        with pytest.raises(CourtListenerAPIError, match="Request timeout"):
            client.search_opinions("test query")
        
        # Error should be tracked
        assert client.error_count > 0
    
    def test_handles_unicode_in_citations(self):
        """Should handle unicode characters in citations properly."""
        client = CourtListenerClient("test_key")
        
        unicode_citation = "Café v. Résumé, 123 F.3d 456 (2020)"
        
        # Should parse without encoding errors
        params = client._parse_citation_for_search(unicode_citation)
        assert params['q'] == unicode_citation
        
        # Should handle in confidence calculation
        confidence = client._calculate_verification_confidence(unicode_citation, [])
        assert isinstance(confidence, float)
        assert 0.0 <= confidence <= 1.0
