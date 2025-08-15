import logging
from typing import Dict, List, Any, Optional
import pynetbox

from ..config import AppConfig
from .base import RateLimitedClient

logger = logging.getLogger(__name__)


class NetBoxClient:
    """NetBox API client."""
    
    def __init__(self, config: AppConfig):
        self.config = config
        self.api = pynetbox.api(
            config.netbox_url,
            token=config.netbox_token
        )
        self.client = RateLimitedClient(
            rate_limit=config.api_rate_limit,
            retry_attempts=config.api_retry_attempts,
            backoff_factor=config.api_backoff_factor
        )
    
    def get_or_create_device_type(self, manufacturer: str, model: str) -> int:
        """Get or create device type."""
        try:
            # Get or create manufacturer
            mfg = self.api.dcim.manufacturers.get(name=manufacturer)
            if not mfg:
                mfg = self.api.dcim.manufacturers.create(name=manufacturer, slug=manufacturer.lower().replace(' ', '-'))
            
            # Get or create device type
            dev_type = self.api.dcim.device_types.get(manufacturer=mfg.id, model=model)
            if not dev_type:
                dev_type = self.api.dcim.device_types.create(
                    manufacturer=mfg.id,
                    model=model,
                    slug=f"{manufacturer.lower().replace(' ', '-')}-{model.lower().replace(' ', '-')}"
                )
            
            return dev_type.id
        except Exception as e:
            logger.error(f"Error creating device type {manufacturer} {model}: {e}")
            raise
    
    def get_or_create_site(self, name: str = "Default") -> int:
        """Get or create site."""
        try:
            site = self.api.dcim.sites.get(name=name)
            if not site:
                site = self.api.dcim.sites.create(
                    name=name,
                    slug=name.lower().replace(' ', '-')
                )
            return site.id
        except Exception as e:
            logger.error(f"Error creating site {name}: {e}")
            raise
    
    def get_or_create_device_role(self, name: str, color: str = "9e9e9e") -> int:
        """Get or create device role."""
        try:
            role = self.api.dcim.device_roles.get(name=name)
            if not role:
                role = self.api.dcim.device_roles.create(
                    name=name,
                    slug=name.lower().replace(' ', '-'),
                    color=color
                )
            return role.id
        except Exception as e:
            logger.error(f"Error creating device role {name}: {e}")
            raise
    
    def create_or_update_device(self, device_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create or update device in NetBox."""
        try:
            # Find existing device by custom field or name
            existing = None
            if device_data.get('custom_fields', {}).get('external_id'):
                devices = self.api.dcim.devices.filter(
                    cf_external_id=device_data['custom_fields']['external_id']
                )
                if devices:
                    existing = devices[0]
            
            if not existing and device_data.get('name'):
                existing = self.api.dcim.devices.get(name=device_data['name'])
            
            if existing:
                # Update existing device
                for key, value in device_data.items():
                    if key != 'id':
                        setattr(existing, key, value)
                existing.save()
                logger.info(f"Updated device: {device_data.get('name')}")
                return existing.serialize()
            else:
                # Create new device
                new_device = self.api.dcim.devices.create(device_data)
                logger.info(f"Created device: {device_data.get('name')}")
                return new_device.serialize()
                
        except Exception as e:
            logger.error(f"Error creating/updating device: {e}")
            raise
    
    def create_or_update_interface(self, interface_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create or update interface in NetBox."""
        try:
            device_id = interface_data.get('device')
            name = interface_data.get('name')
            
            # Find existing interface
            existing = self.api.dcim.interfaces.get(device_id=device_id, name=name)
            
            if existing:
                # Update existing interface
                for key, value in interface_data.items():
                    if key != 'id':
                        setattr(existing, key, value)
                existing.save()
                logger.info(f"Updated interface: {name}")
                return existing.serialize()
            else:
                # Create new interface
                new_interface = self.api.dcim.interfaces.create(interface_data)
                logger.info(f"Created interface: {name}")
                return new_interface.serialize()
                
        except Exception as e:
            logger.error(f"Error creating/updating interface: {e}")
            raise
    
    def create_or_update_ip_address(self, ip_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create or update IP address in NetBox."""
        try:
            address = ip_data.get('address')
            
            # Find existing IP address
            existing = self.api.ipam.ip_addresses.get(address=address)
            
            if existing:
                # Update existing IP
                for key, value in ip_data.items():
                    if key != 'id':
                        setattr(existing, key, value)
                existing.save()
                logger.info(f"Updated IP address: {address}")
                return existing.serialize()
            else:
                # Create new IP address
                new_ip = self.api.ipam.ip_addresses.create(ip_data)
                logger.info(f"Created IP address: {address}")
                return new_ip.serialize()
                
        except Exception as e:
            logger.error(f"Error creating/updating IP address: {e}")
            raise
    
    def get_or_create_vlan(self, vlan_data: Dict[str, Any]) -> Dict[str, Any]:
        """Get or create VLAN in NetBox."""
        try:
            vid = vlan_data.get('vid')
            name = vlan_data.get('name')
            
            # Find existing VLAN
            existing = self.api.ipam.vlans.get(vid=vid, name=name)
            
            if existing:
                return existing.serialize()
            else:
                # Create new VLAN
                new_vlan = self.api.ipam.vlans.create(vlan_data)
                logger.info(f"Created VLAN: {name} ({vid})")
                return new_vlan.serialize()
                
        except Exception as e:
            logger.error(f"Error creating VLAN: {e}")
            raise
    
    def get_or_create_prefix(self, prefix_data: Dict[str, Any]) -> Dict[str, Any]:
        """Get or create prefix in NetBox."""
        try:
            prefix = prefix_data.get('prefix')
            
            # Find existing prefix
            existing = self.api.ipam.prefixes.get(prefix=prefix)
            
            if existing:
                return existing.serialize()
            else:
                # Create new prefix
                new_prefix = self.api.ipam.prefixes.create(prefix_data)
                logger.info(f"Created prefix: {prefix}")
                return new_prefix.serialize()
                
        except Exception as e:
            logger.error(f"Error creating prefix: {e}")
            raise
    
    def delete_stale_objects(self, source: str, grace_days: int = 7):
        """Delete objects marked as stale for more than grace_days."""
        # This would implement soft-delete logic based on tags
        # For now, we'll skip implementation as it requires careful handling
        logger.info(f"Stale object cleanup for source {source} (grace period: {grace_days} days)")
        # TODO: Implement stale object cleanup