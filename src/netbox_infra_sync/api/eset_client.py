import logging
from typing import Dict, List, Any, Optional

from ..config import AppConfig
from .base import RateLimitedClient

logger = logging.getLogger(__name__)


class ESETClient(RateLimitedClient):
    """ESET PROTECT API client."""
    
    def __init__(self, config: AppConfig):
        super().__init__(
            rate_limit=config.api_rate_limit,
            retry_attempts=config.api_retry_attempts,
            backoff_factor=config.api_backoff_factor
        )
        if not config.eset_base_url or not config.eset_token:
            raise ValueError("ESET configuration is required but not provided")
            
        self.base_url = config.eset_base_url.rstrip('/')
        self.headers = {
            'Authorization': f'Bearer {config.eset_token}',
            'Content-Type': 'application/json'
        }
    
    def get_computers(self) -> List[Dict[str, Any]]:
        """Get all computers from ESET."""
        try:
            url = f"{self.base_url}/api/v1/computers"
            response = self.get(url, headers=self.headers)
            data = response.json()
            return data.get('computers', [])
        except Exception as e:
            logger.error(f"Error fetching computers: {e}")
            raise
    
    def get_computer_details(self, computer_id: str) -> Dict[str, Any]:
        """Get detailed information for a specific computer."""
        try:
            url = f"{self.base_url}/api/v1/computers/{computer_id}"
            response = self.get(url, headers=self.headers)
            return response.json()
        except Exception as e:
            logger.error(f"Error fetching computer details for {computer_id}: {e}")
            raise
    
    def get_threats(self, computer_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get threat information, optionally filtered by computer."""
        try:
            url = f"{self.base_url}/api/v1/threats"
            if computer_id:
                url += f"?computerId={computer_id}"
            
            response = self.get(url, headers=self.headers)
            data = response.json()
            return data.get('threats', [])
        except Exception as e:
            logger.error(f"Error fetching threats: {e}")
            raise
    
    def get_antivirus_status(self) -> List[Dict[str, Any]]:
        """Get antivirus status for all computers."""
        try:
            url = f"{self.base_url}/api/v1/status/antivirus"
            response = self.get(url, headers=self.headers)
            data = response.json()
            return data.get('status', [])
        except Exception as e:
            logger.error(f"Error fetching antivirus status: {e}")
            raise
    
    def get_network_interfaces(self, computer_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get network interface information."""
        try:
            url = f"{self.base_url}/api/v1/network/interfaces"
            if computer_id:
                url += f"?computerId={computer_id}"
                
            response = self.get(url, headers=self.headers)
            data = response.json()
            return data.get('interfaces', [])
        except Exception as e:
            logger.error(f"Error fetching network interfaces: {e}")
            raise
    
    def get_software_inventory(self, computer_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get software inventory."""
        try:
            url = f"{self.base_url}/api/v1/software"
            if computer_id:
                url += f"?computerId={computer_id}"
                
            response = self.get(url, headers=self.headers)
            data = response.json()
            return data.get('software', [])
        except Exception as e:
            logger.error(f"Error fetching software inventory: {e}")
            raise
    
    def get_groups(self) -> List[Dict[str, Any]]:
        """Get computer groups."""
        try:
            url = f"{self.base_url}/api/v1/groups"
            response = self.get(url, headers=self.headers)
            data = response.json()
            return data.get('groups', [])
        except Exception as e:
            logger.error(f"Error fetching groups: {e}")
            raise