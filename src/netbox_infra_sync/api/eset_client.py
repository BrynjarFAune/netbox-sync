import logging
from typing import List, Dict, Any
import requests

from ..config import AppConfig

logger = logging.getLogger(__name__)


class ESETClient:
    """Simple ESET Management Console API client."""
    
    def __init__(self, config: AppConfig):
        self.config = config
        self.region = config.eset_region
        self.username = config.eset_username
        self.password = config.eset_password
        self.access_token = None
    
    def _get_token(self) -> bool:
        """Get OAuth2 token from ESET."""
        if not self.username or not self.password:
            return False
            
        try:
            url = f"https://{self.region}.business-account.iam.eset.systems/oauth/token"
            
            # Use form data like the Rust code
            data = {
                'grant_type': 'password',
                'username': self.username,
                'password': self.password
            }
            
            response = requests.post(
                url,
                headers={
                    'Accept': 'application/json',
                    'Content-Type': 'application/x-www-form-urlencoded'
                },
                data=data  # requests will URL encode this automatically
            )
            
            if response.status_code == 200:
                token_data = response.json()
                self.access_token = token_data['access_token']
                return True
            else:
                logger.error(f"ESET auth failed: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"ESET authentication error: {e}")
            return False
    
    def test_connection(self) -> bool:
        """Test ESET API connectivity."""
        if not self.username or not self.password:
            logger.warning("ESET configuration not provided")
            return False
        
        return self._get_token()
    
    def get_devices(self) -> List[Dict[str, Any]]:
        """Fetch device list from ESET."""
        if not self.username or not self.password:
            logger.warning("ESET configuration not provided")
            return []
        
        if not self.access_token and not self._get_token():
            return []
        
        try:
            # Get device UUIDs first
            group_url = f"https://{self.region}.device-management.eset.systems/v1/device_groups/00000000-0000-0000-7001-000000000001/devices?recurseSubgroups=true&pageSize=1000"
            
            response = requests.get(
                group_url,
                headers={
                    'Authorization': f'Bearer {self.access_token}',
                    'Content-Type': 'application/json'
                }
            )
            
            if response.status_code != 200:
                logger.error(f"ESET device list error: {response.status_code}")
                return []
            
            device_list = response.json()
            uuids = [d['uuid'] for d in device_list.get('devices', [])]
            
            if not uuids:
                return []
            
            # Get detailed device info in batches
            devices = []
            for i in range(0, len(uuids), 100):
                batch = uuids[i:i+100]
                query = '&'.join([f'devicesUuids={uuid}' for uuid in batch])
                
                detail_url = f"https://{self.region}.device-management.eset.systems/v1/devices:batchGet?{query}"
                
                detail_response = requests.get(
                    detail_url,
                    headers={
                        'Authorization': f'Bearer {self.access_token}',
                        'Accept': 'application/json'
                    }
                )
                
                if detail_response.status_code == 200:
                    batch_data = detail_response.json()
                    devices.extend(batch_data.get('devices', []))
                    
            return devices
                
        except Exception as e:
            logger.error(f"Error fetching ESET devices: {e}")
            return []