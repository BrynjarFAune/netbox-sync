import logging
from typing import Dict, List, Any, Optional
import json
import requests
import os

from ..config import AppConfig
from .base import RateLimitedClient

logger = logging.getLogger(__name__)


class FortiGateClient(RateLimitedClient):
    """FortiGate API client."""
    
    def __init__(self, config: AppConfig):
        super().__init__(
            rate_limit=config.api_rate_limit,
            retry_attempts=config.api_retry_attempts,
            backoff_factor=config.api_backoff_factor
        )
        self.base_url = f"{config.fortigate_host.rstrip('/')}/api/v2"
        self.api_token = config.fortigate_token
        self.vdom = config.fortigate_vdom
        self.headers = {
            'Authorization': f'Bearer {config.fortigate_token}',
            'Content-Type': 'application/json'
        }
        # Disable SSL verification for self-signed certs (common with FortiGate)
        self.session.verify = False
        # Suppress SSL warnings
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        # Development mode: save/load responses from JSON files
        self.dev_mode = getattr(config, 'fortigate_dev_mode', os.getenv('FGT_DEV_MODE', 'false').lower() == 'true')
        self.dev_data_dir = os.getenv('FGT_DEV_DATA_DIR', '/app/dev_data')
        if self.dev_mode:
            os.makedirs(self.dev_data_dir, exist_ok=True)
            logger.info(f"FortiGate dev mode enabled, using data directory: {self.dev_data_dir}")
    
    def _get_dev_filename(self, endpoint: str) -> str:
        """Generate filename for dev mode JSON files."""
        # Convert endpoint to safe filename
        safe_endpoint = endpoint.strip('/').replace('/', '_').replace('?', '_')
        return f"{safe_endpoint}.json"
    
    def _save_dev_response(self, endpoint: str, data: Dict[str, Any]) -> None:
        """Save API response to JSON file in dev mode."""
        if not self.dev_mode:
            return
            
        filename = self._get_dev_filename(endpoint)
        filepath = os.path.join(self.dev_data_dir, filename)
        
        try:
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2)
            logger.info(f"Saved FortiGate response to {filepath}")
        except Exception as e:
            logger.error(f"Failed to save dev response: {e}")
    
    def _load_dev_response(self, endpoint: str) -> Optional[Dict[str, Any]]:
        """Load API response from JSON file in dev mode."""
        if not self.dev_mode:
            return None
            
        filename = self._get_dev_filename(endpoint)
        filepath = os.path.join(self.dev_data_dir, filename)
        
        try:
            if os.path.exists(filepath):
                with open(filepath, 'r') as f:
                    data = json.load(f)
                logger.info(f"Loaded FortiGate response from {filepath}")
                return data
        except Exception as e:
            logger.error(f"Failed to load dev response: {e}")
            
        return None

    def _make_request(self, endpoint: str) -> Dict[str, Any]:
        """Make a request to FortiGate API with proper authentication."""
        # In dev mode, try to load from file first
        if self.dev_mode:
            dev_data = self._load_dev_response(endpoint)
            if dev_data is not None:
                return dev_data
        
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        # Add vdom as parameter if needed (some endpoints require it)
        params = {}
        if self.vdom and self.vdom != 'root':
            params['vdom'] = self.vdom
            
        try:
            response = self.get(url, headers=self.headers, params=params if params else None)
            data = response.json()
            
            # Check if FortiGate returned an error
            if 'error' in data:
                error_code = data.get('error', 'Unknown error')
                error_msg = data.get('error_description', 'No description')
                raise Exception(f"FortiGate API error {error_code}: {error_msg}")
            
            # Save response in dev mode
            if self.dev_mode:
                self._save_dev_response(endpoint, data)
                
            return data
        except requests.exceptions.RequestException as e:
            logger.error(f"FortiGate API request failed: {url} - {e}")
            raise
        except Exception as e:
            logger.error(f"FortiGate API error: {e}")
            raise
    
    def test_connectivity(self) -> bool:
        """Test basic connectivity to FortiGate API."""
        try:
            data = self._make_request("/monitor/system/status")
            return 'version' in data
        except Exception as e:
            logger.error(f"FortiGate connectivity test failed: {e}")
            return False
    
    def get_devices(self) -> List[Dict[str, Any]]:
        """Get devices from FortiGate user device monitoring."""
        try:
            data = self._make_request("/monitor/user/device/query")
            return data.get('results', [])
        except Exception as e:
            logger.error(f"Error fetching devices: {e}")
            raise
    
    def get_interfaces(self) -> List[Dict[str, Any]]:
        """Get all interfaces."""
        try:
            data = self._make_request("/cmdb/system/interface")
            return data.get('results', [])
        except Exception as e:
            logger.error(f"Error fetching interfaces: {e}")
            raise
    
    def get_interface_status(self) -> List[Dict[str, Any]]:
        """Get interface status information."""
        try:
            data = self._make_request("/monitor/system/interface")
            return data.get('results', [])
        except Exception as e:
            logger.error(f"Error fetching interface status: {e}")
            raise
    
    def get_vlans(self) -> List[Dict[str, Any]]:
        """Get all VLANs."""
        try:
            data = self._make_request("/cmdb/system/interface")
            vlans = []
            for interface in data.get('results', []):
                if interface.get('vlanid') and interface.get('vlanid') > 0:
                    vlans.append({
                        'vlan_id': interface.get('vlanid'),
                        'name': interface.get('name'),
                        'description': interface.get('description', ''),
                        'interface': interface.get('interface')
                    })
            return vlans
        except Exception as e:
            logger.error(f"Error fetching VLANs: {e}")
            raise
    
    def get_routes(self) -> List[Dict[str, Any]]:
        """Get routing table."""
        try:
            data = self._make_request("/monitor/router/ipv4")
            return data.get('results', [])
        except Exception as e:
            logger.error(f"Error fetching routes: {e}")
            raise
    
    def get_dhcp_leases(self) -> List[Dict[str, Any]]:
        """Get DHCP lease information."""
        try:
            data = self._make_request("/monitor/system/dhcp")
            return data.get('results', [])
        except Exception as e:
            logger.error(f"Error fetching DHCP leases: {e}")
            raise
    
    def get_arp_table(self) -> List[Dict[str, Any]]:
        """Get ARP table."""
        try:
            data = self._make_request("/monitor/system/arp")
            return data.get('results', [])
        except Exception as e:
            logger.error(f"Error fetching ARP table: {e}")
            raise
    
    def get_firewall_addresses(self) -> List[Dict[str, Any]]:
        """Get firewall address objects."""
        try:
            data = self._make_request("/cmdb/firewall/address")
            return data.get('results', [])
        except Exception as e:
            logger.error(f"Error fetching firewall addresses: {e}")
            raise
    
    def get_firewall_address_groups(self) -> List[Dict[str, Any]]:
        """Get firewall address groups."""
        try:
            data = self._make_request("/cmdb/firewall/addrgrp")
            return data.get('results', [])
        except Exception as e:
            logger.error(f"Error fetching firewall address groups: {e}")
            raise