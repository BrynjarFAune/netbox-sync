import logging
from typing import Dict, List, Any, Optional
import msal

from ..config import AppConfig
from .base import RateLimitedClient

logger = logging.getLogger(__name__)


class IntuneClient(RateLimitedClient):
    """Microsoft Graph/Intune API client."""
    
    def __init__(self, config: AppConfig):
        super().__init__(
            rate_limit=config.api_rate_limit,
            retry_attempts=config.api_retry_attempts,
            backoff_factor=config.api_backoff_factor
        )
        self.config = config
        self.base_url = "https://graph.microsoft.com/v1.0"
        self.app = msal.ConfidentialClientApplication(
            config.graph_client_id,
            authority=f"https://login.microsoftonline.com/{config.graph_tenant_id}",
            client_credential=config.graph_client_secret
        )
        self._access_token = None
    
    def _get_access_token(self) -> str:
        """Get or refresh access token."""
        if not self._access_token:
            result = self.app.acquire_token_for_client(
                scopes=["https://graph.microsoft.com/.default"]
            )
            if "access_token" in result:
                self._access_token = result["access_token"]
            else:
                raise Exception(f"Failed to acquire token: {result.get('error_description')}")
        return self._access_token
    
    def _get_headers(self) -> Dict[str, str]:
        """Get authorization headers."""
        return {
            'Authorization': f'Bearer {self._get_access_token()}',
            'Content-Type': 'application/json'
        }
    
    def get_managed_devices(self, filter_str: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all managed devices from Intune."""
        try:
            url = f"{self.base_url}/deviceManagement/managedDevices"
            if filter_str:
                url += f"?$filter={filter_str}"
            
            devices = []
            while url:
                response = self.get(url, headers=self._get_headers())
                data = response.json()
                devices.extend(data.get('value', []))
                url = data.get('@odata.nextLink')
            
            return devices
        except Exception as e:
            logger.error(f"Error fetching managed devices: {e}")
            # Token might be expired, retry once
            self._access_token = None
            try:
                response = self.get(url, headers=self._get_headers())
                data = response.json()
                return data.get('value', [])
            except Exception as retry_e:
                logger.error(f"Retry failed: {retry_e}")
                raise
    
    def get_device_compliance_policies(self) -> List[Dict[str, Any]]:
        """Get device compliance policies."""
        try:
            url = f"{self.base_url}/deviceManagement/deviceCompliancePolicies"
            response = self.get(url, headers=self._get_headers())
            data = response.json()
            return data.get('value', [])
        except Exception as e:
            logger.error(f"Error fetching compliance policies: {e}")
            raise
    
    def get_device_configurations(self) -> List[Dict[str, Any]]:
        """Get device configurations."""
        try:
            url = f"{self.base_url}/deviceManagement/deviceConfigurations"
            response = self.get(url, headers=self._get_headers())
            data = response.json()
            return data.get('value', [])
        except Exception as e:
            logger.error(f"Error fetching device configurations: {e}")
            raise
    
    def get_device_compliance_status(self, device_id: str) -> Dict[str, Any]:
        """Get compliance status for a specific device."""
        try:
            url = f"{self.base_url}/deviceManagement/managedDevices/{device_id}/deviceCompliancePolicyStates"
            response = self.get(url, headers=self._get_headers())
            data = response.json()
            return data.get('value', [])
        except Exception as e:
            logger.error(f"Error fetching device compliance status: {e}")
            raise
    
    def get_azure_ad_devices(self) -> List[Dict[str, Any]]:
        """Get Azure AD devices."""
        try:
            url = f"{self.base_url}/devices"
            
            devices = []
            while url:
                response = self.get(url, headers=self._get_headers())
                data = response.json()
                devices.extend(data.get('value', []))
                url = data.get('@odata.nextLink')
            
            return devices
        except Exception as e:
            logger.error(f"Error fetching Azure AD devices: {e}")
            raise
    
    def get_users(self) -> List[Dict[str, Any]]:
        """Get user information."""
        try:
            url = f"{self.base_url}/users"
            
            users = []
            while url:
                response = self.get(url, headers=self._get_headers())
                data = response.json()
                users.extend(data.get('value', []))
                url = data.get('@odata.nextLink')
            
            return users
        except Exception as e:
            logger.error(f"Error fetching users: {e}")
            raise
    
    def get_user_licenses(self, user_email: str) -> List[Dict[str, Any]]:
        """Get license assignments for a specific user."""
        try:
            # Get user by email first
            user_response = self.get(f"{self.base_url}/users/{user_email}", headers=self._get_headers())
            user = user_response.json()
            
            # Get user with license details
            licenses_response = self.get(f"{self.base_url}/users/{user['id']}", headers=self._get_headers())
            user_with_licenses = licenses_response.json()
            
            return user_with_licenses.get('assignedLicenses', [])
            
        except Exception as e:
            logger.error(f"Error fetching licenses for user {user_email}: {e}")
            return []
    
    def get_subscribed_skus(self) -> List[Dict[str, Any]]:
        """Get all subscribed SKUs (available licenses)."""
        try:
            response = self.get(f"{self.base_url}/subscribedSkus", headers=self._get_headers())
            data = response.json()
            return data.get('value', [])
        except Exception as e:
            logger.error(f"Error fetching subscribed SKUs: {e}")
            return []