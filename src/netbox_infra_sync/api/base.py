import time
import logging
from typing import Dict, Any, Optional
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


logger = logging.getLogger(__name__)


class RateLimitedClient:
    """Base client with rate limiting and retry logic."""
    
    def __init__(self, rate_limit: int = 10, retry_attempts: int = 3, backoff_factor: float = 1.0):
        self.rate_limit = rate_limit
        self.retry_attempts = retry_attempts
        self.backoff_factor = backoff_factor
        self.last_request_time = 0
        
        # Configure session with retries
        self.session = requests.Session()
        retry_strategy = Retry(
            total=retry_attempts,
            status_forcelist=[429, 500, 502, 503, 504],
            backoff_factor=backoff_factor
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
    
    def _rate_limit(self):
        """Enforce rate limiting."""
        if self.rate_limit <= 0:
            return
            
        time_since_last = time.time() - self.last_request_time
        min_interval = 1.0 / self.rate_limit
        
        if time_since_last < min_interval:
            sleep_time = min_interval - time_since_last
            time.sleep(sleep_time)
        
        self.last_request_time = time.time()
    
    def request(self, method: str, url: str, **kwargs) -> requests.Response:
        """Make rate-limited HTTP request."""
        self._rate_limit()
        
        try:
            response = self.session.request(method, url, **kwargs)
            response.raise_for_status()
            return response
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {method} {url} - {e}")
            raise
    
    def get(self, url: str, **kwargs) -> requests.Response:
        """Make GET request."""
        return self.request('GET', url, **kwargs)
    
    def post(self, url: str, **kwargs) -> requests.Response:
        """Make POST request."""
        return self.request('POST', url, **kwargs)
    
    def put(self, url: str, **kwargs) -> requests.Response:
        """Make PUT request."""
        return self.request('PUT', url, **kwargs)
    
    def patch(self, url: str, **kwargs) -> requests.Response:
        """Make PATCH request."""
        return self.request('PATCH', url, **kwargs)
    
    def delete(self, url: str, **kwargs) -> requests.Response:
        """Make DELETE request."""
        return self.request('DELETE', url, **kwargs)