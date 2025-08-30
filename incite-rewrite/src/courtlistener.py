import requests
import time
from typing import List, Dict

class CourtListenerClient:
    def __init__(self, api_token: str):
        self.api_token = api_token
        self.base_url = 'https://www.courtlistener.com/api/rest/v4'
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Token {api_token}'
        })
        self.last_request_time = 0
        self.citations_this_minute = []
    
    def verify_citations(self, citations: List[str]) -> List[Dict]:
        results = []
        
        for i in range(0, len(citations), 250):
            batch = citations[i:i+250]
            self._enforce_rate_limit(len(batch))
            text = ' '.join([f'{c}.' for c in batch])
            
            try:
                response = self.session.post(
                    f'{self.base_url}/citation-lookup/',
                    data={'text': text},
                    timeout=30
                )
                
                if response.status_code == 429:
                    time.sleep(60)
                    response = self.session.post(
                        f'{self.base_url}/citation-lookup/',
                        data={'text': text},
                        timeout=30
                    )
                
                if response.status_code == 200:
                    api_results = response.json()
                    
                    for j, citation in enumerate(batch):
                        if j < len(api_results):
                            result = api_results[j]
                            found = bool(result.get('clusters', []))
                            confidence = 0
                            case_name = ''
                            url = ''
                            
                            if found and result['clusters']:
                                cluster = result['clusters'][0]
                                case_name = cluster.get('case_name', '')
                                absolute_url = cluster.get('absolute_url', '')
                                if absolute_url:
                                    url = f'https://www.courtlistener.com{absolute_url}'
                                
                                confidence = 100
                                returned_citation = result.get('citation', '')
                                if returned_citation != citation:
                                    confidence -= 20
                                if not case_name:
                                    confidence -= 15
                                if len(result.get('clusters', [])) > 1:
                                    confidence -= 10
                            
                            results.append({
                                'citation': citation,
                                'found': found,
                                'confidence': confidence,
                                'case_name': case_name,
                                'url': url
                            })
                        else:
                            results.append({
                                'citation': citation,
                                'found': False,
                                'confidence': 0,
                                'case_name': '',
                                'url': ''
                            })
                else:
                    for citation in batch:
                        results.append({
                            'citation': citation,
                            'found': False,
                            'confidence': 0,
                            'case_name': '',
                            'url': '',
                            'error': f'API error: {response.status_code}'
                        })
                        
            except requests.exceptions.Timeout:
                for citation in batch:
                    results.append({
                        'citation': citation,
                        'found': False,
                        'confidence': 0,
                        'case_name': '',
                        'url': '',
                        'error': 'CourtListener timeout - try again'
                    })
            except requests.exceptions.ConnectionError:
                for citation in batch:
                    results.append({
                        'citation': citation,
                        'found': False,
                        'confidence': 0,
                        'case_name': '',
                        'url': '',
                        'error': 'Cannot reach CourtListener - check connection'
                    })
            except Exception as e:
                for citation in batch:
                    results.append({
                        'citation': citation,
                        'found': False,
                        'confidence': 0,
                        'case_name': '',
                        'url': '',
                        'error': f'Verification error: {str(e)[:50]}'
                    })
        
        return results
    
    def _enforce_rate_limit(self, num_citations: int):
        current_time = time.time()
        self.citations_this_minute = [
            t for t in self.citations_this_minute 
            if current_time - t < 60
        ]
        
        if len(self.citations_this_minute) + num_citations > 60:
            wait_time = 60 - (current_time - self.citations_this_minute[0])
            if wait_time > 0:
                time.sleep(wait_time + 1)
                self.citations_this_minute = []
        
        for _ in range(num_citations):
            self.citations_this_minute.append(current_time)