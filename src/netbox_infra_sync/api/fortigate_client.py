import logging
from typing import Dict, List, Any, Optional
import json
import requests

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
    
    def _make_request(self, endpoint: str) -> Dict[str, Any]:
        """Make a request to FortiGate API with proper authentication."""
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