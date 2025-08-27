import logging
import time
from typing import Dict, List, Any

from .base import BaseWorker
from ..api.fortigate_client import FortiGateClient
from ..models.normalizer import DataNormalizer
from ..models.canonical import CanonicalDevice, CanonicalInterface, CanonicalIPAddress, CanonicalVLAN, CanonicalPrefix

logger = logging.getLogger(__name__)


class FortiGateWorker(BaseWorker):
    """Worker for fetching data from FortiGate."""
    
    def __init__(self, config):
        super().__init__(config)
        self.client = FortiGateClient(config)
        self.normalizer = DataNormalizer()
    
    def fetch_data(self) -> Dict[str, List[Any]]:
        """Fetch all data from FortiGate."""
        start_time = time.time()
        data = {
            'devices': [],
            'interfaces': [],
            'ip_addresses': [],
            'vlans': [],
            'prefixes': []
        }
        errors = []
        
        try:
            # Test connectivity first
            logger.info("Testing FortiGate connectivity...")
            if not self.client.test_connectivity():
                raise Exception("Failed to connect to FortiGate API. Check your configuration.")
            
            logger.info("FortiGate connectivity test passed!")
            
            # Get devices from FortiGate using the working endpoint
            logger.info("Fetching FortiGate devices...")
            devices = self.client.get_devices()
            
            # Process each device
            for device_data in devices:
                try:
                    canonical_device = self.normalizer.normalize_fortigate_device(device_data)
                    data['devices'].append(canonical_device)
                except Exception as e:
                    errors.append(f"Error normalizing device {device_data.get('hostname', 'unknown')}: {e}")
                    logger.error(f"Error processing device: {e}")
            
            # Get interfaces
            logger.info("Fetching FortiGate interfaces...")
            interfaces = self.client.get_interfaces()
            interface_status = self.client.get_interface_status()
            
            logger.info(f"Interfaces type: {type(interfaces)}, length: {len(interfaces) if hasattr(interfaces, '__len__') else 'N/A'}")
            logger.info(f"Interface status type: {type(interface_status)}, length: {len(interface_status) if hasattr(interface_status, '__len__') else 'N/A'}")
            
            # Handle FortiGate interface status format (dict with interface names as keys)
            if isinstance(interface_status, dict):
                # FortiGate returns interface status as {"interface_name": {data}, ...}
                status_lookup = interface_status
            elif isinstance(interface_status, list):
                status_lookup = {iface['name']: iface for iface in interface_status if isinstance(iface, dict) and 'name' in iface}
            else:
                logger.warning(f"Interface status has unexpected format: {type(interface_status)}")
                status_lookup = {}
            
            # Handle case where interfaces might not be a list
            if not isinstance(interfaces, list):
                logger.error(f"Interfaces is not a list: {type(interfaces)}")
                interfaces = []
            
            for interface in interfaces:
                try:
                    # Skip if interface is not a dict
                    if not isinstance(interface, dict):
                        logger.warning(f"Interface is not a dict: {type(interface)}")
                        continue
                        
                    # Merge with status data
                    status_data = status_lookup.get(interface.get('name', ''), {})
                    interface.update(status_data)
                    
                    # Use a default device_id for now (FortiGate device)
                    device_id = "fortigate_device"
                    canonical_interface = self.normalizer.normalize_fortigate_interface(
                        interface, device_id
                    )
                    data['interfaces'].append(canonical_interface)
                except Exception as e:
                    errors.append(f"Error normalizing interface {interface.get('name')}: {e}")
                    logger.error(f"Error processing interface: {e}")
            
            # Get VLANs
            logger.info("Fetching FortiGate VLANs...")
            vlans = self.client.get_vlans()
            for vlan in vlans:
                try:
                    canonical_vlan = self.normalizer.normalize_fortigate_vlan(vlan)
                    data['vlans'].append(canonical_vlan)
                except Exception as e:
                    errors.append(f"Error normalizing VLAN {vlan.get('vlan_id')}: {e}")
                    logger.error(f"Error processing VLAN: {e}")
            
            # Get DHCP leases
            logger.info("Fetching FortiGate DHCP leases...")
            try:
                dhcp_leases = self.client.get_dhcp_leases()
                for lease in dhcp_leases:
                    try:
                        canonical_ip = self.normalizer.normalize_fortigate_dhcp_lease(lease)
                        data['ip_addresses'].append(canonical_ip)
                    except Exception as e:
                        errors.append(f"Error normalizing DHCP lease {lease.get('ip')}: {e}")
                        logger.error(f"Error processing DHCP lease: {e}")
            except Exception as e:
                errors.append(f"Error fetching DHCP leases: {e}")
                logger.error(f"Error fetching DHCP leases: {e}")
            
            # Skip ARP table - endpoint not available on this FortiGate version
            logger.info("Skipping ARP table (endpoint not available on this FortiGate version)")
            
            # Get firewall addresses for prefixes
            logger.info("Fetching FortiGate firewall addresses...")
            try:
                addresses = self.client.get_firewall_addresses()
                for addr in addresses:
                    try:
                        # Convert firewall addresses to prefixes where applicable
                        if addr.get('type') == 'ipmask' and '/' in str(addr.get('subnet', '')):
                            prefix_data = {
                                'subnet': addr['subnet'],
                                'description': f"Firewall address: {addr.get('name', '')}"
                            }
                            canonical_prefix = self.normalizer.normalize_fortigate_prefix(prefix_data)
                            data['prefixes'].append(canonical_prefix)
                    except Exception as e:
                        errors.append(f"Error normalizing firewall address {addr.get('name')}: {e}")
                        logger.error(f"Error processing firewall address: {e}")
            except Exception as e:
                errors.append(f"Error fetching firewall addresses: {e}")
                logger.error(f"Error fetching firewall addresses: {e}")
            
            duration = time.time() - start_time
            logger.info(f"FortiGate data fetch completed in {duration:.2f}s")
            
            # Log summary
            logger.info(
                f"FortiGate fetch summary: devices={len(data['devices'])}, "
                f"interfaces={len(data['interfaces'])}, "
                f"ip_addresses={len(data['ip_addresses'])}, "
                f"vlans={len(data['vlans'])}, "
                f"prefixes={len(data['prefixes'])}, "
                f"errors={len(errors)}"
            )
            
            if errors:
                logger.warning(f"FortiGate fetch completed with {len(errors)} errors")
                for error in errors[:5]:  # Log first 5 errors
                    logger.warning(f"Error: {error}")
            
            return data
            
        except Exception as e:
            logger.error(f"Critical error in FortiGate data fetch: {e}")
            raise