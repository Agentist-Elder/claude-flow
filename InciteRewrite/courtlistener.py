import requests
import time
from typing import List, Dict

class CourtListenerClient:
    def __init__(self, api_token: str):
        self.api_token = api_token
        self.base_url = 'https://www.courtlistener.com/api/rest/v4'
        self.session = requests.Session()
        if api_token:
            self.session.headers.update({
                'Authorization': f'Token {api_token}'
            })
        self.last_request_time = 0
        self.citations_this_minute = []
    
    def verify_citations(self, citations: List[str]) -> List[Dict]:
        results = []
        
        # If no API token, mark all as unverifiable
        if not self.api_token:
            for citation in citations:
                results.append({
                    'citation': citation,
                    'found': False,
                    'case_name': '',
                    'url': '',
                    'error': 'No API token configured'
                })
            return results
        
        # Batch citations (max 250 per request)
        for i in range(0, len(citations), 250):
            batch = citations[i:i+250]
            
            # Rate limiting: 60 citations per minute
            self._enforce_rate_limit(len(batch))
            
            # Create citation text
            text = ' '.join([f'{c}.' for c in batch])
            
            try:
                response = self.session.post(
                    f'{self.base_url}/citation-lookup/',
                    data={'text': text},
                    timeout=30
                )
                
                if response.status_code == 429:
                    # Wait and retry
                    time.sleep(60)
                    response = self.session.post(
                        f'{self.base_url}/citation-lookup/',
                        data={'text': text},
                        timeout=30
                    )
                
                if response.status_code == 200:
                    api_results = response.json()
                    
                    # Match results to citations
                    for j, citation in enumerate(batch):
                        if j < len(api_results):
                            result = api_results[j]
                            found = bool(result.get('clusters', []))
                            case_name = ''
                            url = ''
                            
                            if found and result['clusters']:
                                cluster = result['clusters'][0]
                                case_name = cluster.get('case_name', '')
                                absolute_url = cluster.get('absolute_url', '')
                                if absolute_url:
                                    url = f'https://www.courtlistener.com{absolute_url}'
                            
                            results.append({
                                'citation': citation,
                                'found': found,
                                'case_name': case_name,
                                'url': url
                            })
                        else:
                            results.append({
                                'citation': citation,
                                'found': False,
                                'case_name': '',
                                'url': ''
                            })
                else:
                    # API error - mark all as not found
                    for citation in batch:
                        results.append({
                            'citation': citation,
                            'found': False,
                            'case_name': '',
                            'url': '',
                            'error': f'API error: {response.status_code}'
                        })
                        
            except Exception as e:
                for citation in batch:
                    results.append({
                        'citation': citation,
                        'found': False,
                        'case_name': '',
                        'url': '',
                        'error': str(e)
                    })
        
        return results
    
    def _enforce_rate_limit(self, num_citations: int):
        current_time = time.time()
        
        # Clean old entries (older than 60 seconds)
        self.citations_this_minute = [
            t for t in self.citations_this_minute 
            if current_time - t < 60
        ]
        
        # Check if we'd exceed limit
        if len(self.citations_this_minute) + num_citations > 60:
            wait_time = 60 - (current_time - self.citations_this_minute[0])
            if wait_time > 0:
                time.sleep(wait_time + 1)
                self.citations_this_minute = []
        
        # Record citations
        for _ in range(num_citations):
            self.citations_this_minute.append(current_time)