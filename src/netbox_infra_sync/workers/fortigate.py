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
            
            # Create status lookup
            status_lookup = {iface['name']: iface for iface in interface_status}
            
            for interface in interfaces:
                try:
                    # Merge with status data
                    status_data = status_lookup.get(interface['name'], {})
                    interface.update(status_data)
                    
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
            
            # Get ARP table
            logger.info("Fetching FortiGate ARP table...")
            try:
                arp_entries = self.client.get_arp_table()
                for arp in arp_entries:
                    try:
                        canonical_ip = self.normalizer.normalize_fortigate_arp_entry(arp)
                        data['ip_addresses'].append(canonical_ip)
                    except Exception as e:
                        errors.append(f"Error normalizing ARP entry {arp.get('ip')}: {e}")
                        logger.error(f"Error processing ARP entry: {e}")
            except Exception as e:
                errors.append(f"Error fetching ARP table: {e}")
                logger.error(f"Error fetching ARP table: {e}")
            
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