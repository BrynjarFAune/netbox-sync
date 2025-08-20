import logging
from typing import Dict, List, Any, Optional
import json

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
        self.base_url = f"{config.fortigate_host}"
        self.headers = {
            'Authorization': f'Bearer {config.fortigate_token}',
            'Content-Type': 'application/json'
        }
    
    def get_devices(self) -> List[Dict[str, Any]]:
        """Get devices from FortiGate using the working endpoint."""
        try:
            response = self.get(f"{self.base_url}/monitor/user/device/query", headers=self.headers)
            data = response.json()
            return data.get('results', [])
        except Exception as e:
            logger.error(f"Error fetching devices: {e}")
            raise
    
    def get_interfaces(self) -> List[Dict[str, Any]]:
        """Get all interfaces."""
        try:
            response = self.get(f"{self.base_url}/cmdb/system/interface", headers=self.headers)
            data = response.json()
            return data.get('results', [])
        except Exception as e:
            logger.error(f"Error fetching interfaces: {e}")
            raise
    
    def get_interface_status(self) -> List[Dict[str, Any]]:
        """Get interface status information."""
        try:
            response = self.get(f"{self.base_url}/monitor/system/interface", headers=self.headers)
            data = response.json()
            return data.get('results', [])
        except Exception as e:
            logger.error(f"Error fetching interface status: {e}")
            raise
    
    def get_vlans(self) -> List[Dict[str, Any]]:
        """Get all VLANs."""
        try:
            response = self.get(f"{self.base_url}/cmdb/system/interface", headers=self.headers)
            data = response.json()
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
            response = self.get(f"{self.base_url}/monitor/router/ipv4", headers=self.headers)
            data = response.json()
            return data.get('results', [])
        except Exception as e:
            logger.error(f"Error fetching routes: {e}")
            raise
    
    def get_dhcp_leases(self) -> List[Dict[str, Any]]:
        """Get DHCP lease information."""
        try:
            response = self.get(f"{self.base_url}/monitor/system/dhcp", headers=self.headers)
            data = response.json()
            return data.get('results', [])
        except Exception as e:
            logger.error(f"Error fetching DHCP leases: {e}")
            raise
    
    def get_arp_table(self) -> List[Dict[str, Any]]:
        """Get ARP table."""
        try:
            response = self.get(f"{self.base_url}/monitor/system/arp", headers=self.headers)
            data = response.json()
            return data.get('results', [])
        except Exception as e:
            logger.error(f"Error fetching ARP table: {e}")
            raise
    
    def get_firewall_addresses(self) -> List[Dict[str, Any]]:
        """Get firewall address objects."""
        try:
            response = self.get(f"{self.base_url}/cmdb/firewall/address", headers=self.headers)
            data = response.json()
            return data.get('results', [])
        except Exception as e:
            logger.error(f"Error fetching firewall addresses: {e}")
            raise
    
    def get_firewall_address_groups(self) -> List[Dict[str, Any]]:
        """Get firewall address groups."""
        try:
            response = self.get(f"{self.base_url}/cmdb/firewall/addrgrp", headers=self.headers)
            data = response.json()
            return data.get('results', [])
        except Exception as e:
            logger.error(f"Error fetching firewall address groups: {e}")
            raise