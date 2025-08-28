import logging
from typing import Dict, List, Any, Optional
import pynetbox

from ..config import AppConfig
from .base import RateLimitedClient
from .netbox_plugins.base import PluginClientMixin
from .netbox_plugins.licenses_client import LicensesPluginClient

logger = logging.getLogger(__name__)


class NetBoxClient(PluginClientMixin):
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
        
        # Initialize plugin clients
        self.licenses = LicensesPluginClient(self)
    
    def get_or_create_device_type(self, manufacturer: str, model: str) -> int:
        """Get or create device type."""
        try:
            import re
            
            # Create a proper slug for manufacturer: lowercase, replace spaces/special chars with hyphens, remove multiple hyphens
            mfg_slug = re.sub(r'[^a-z0-9]+', '-', manufacturer.lower()).strip('-')
            
            # Get or create manufacturer
            mfg = self.api.dcim.manufacturers.get(name=manufacturer)
            if not mfg:
                try:
                    mfg = self.api.dcim.manufacturers.create(name=manufacturer, slug=mfg_slug)
                    logger.info(f"Created manufacturer: {manufacturer}")
                except Exception as e:
                    # If slug conflict, try to find existing by slug
                    if "slug already exists" in str(e):
                        mfg = self.api.dcim.manufacturers.get(slug=mfg_slug)
                        logger.info(f"Found existing manufacturer by slug: {manufacturer}")
                    else:
                        raise
            
            # Try to find existing device type by model first (since manufacturer query might be flaky)
            existing_types = self.api.dcim.device_types.filter(model=model)
            for dt in existing_types:
                if dt.manufacturer.name == manufacturer:
                    return dt.id
            
            # Create new device type if not found
            # Create a proper slug: lowercase, replace spaces/special chars with hyphens, remove multiple hyphens  
            model_slug = re.sub(r'[^a-z0-9]+', '-', model.lower()).strip('-')
            slug = f"{mfg_slug}-{model_slug}".strip('-')
            
            dev_type = self.api.dcim.device_types.create(
                manufacturer=mfg.id,
                model=model,
                slug=slug
            )
            logger.info(f"Created device type: {manufacturer} {model}")
            return dev_type.id
        except Exception as e:
            logger.error(f"Error creating device type {manufacturer} {model}: {e}")
            # Return a default device type instead of failing
            try:
                default_type = self.api.dcim.device_types.get(model="Unknown")
                if default_type:
                    logger.warning(f"Using default device type for {manufacturer} {model}")
                    return default_type.id
            except:
                pass
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
                logger.info(f"Created device role: {name}")
            return role.id
        except Exception as e:
            logger.error(f"Error creating device role {name}: {e}")
            # Try to return a default role instead of failing
            try:
                default_role = self.api.dcim.device_roles.get(name="Server")
                if default_role:
                    logger.warning(f"Using default role 'Server' for {name}")
                    return default_role.id
            except:
                pass
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
                for device in devices:
                    existing = device
                    break
            
            if not existing and device_data.get('name'):
                try:
                    existing = self.api.dcim.devices.get(name=device_data['name'])
                except Exception as e:
                    if "returned more than one result" in str(e):
                        # Multiple devices with same name, filter by site
                        site_id = device_data.get('site', self.get_or_create_site())
                        devices = self.api.dcim.devices.filter(name=device_data['name'], site=site_id)
                        existing = devices[0] if devices else None
                    else:
                        existing = None
            
            if existing:
                # Update existing device
                for key, value in device_data.items():
                    if key not in ['id', 'location']:  # Skip location to avoid validation errors
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
    
    def get_tag_id(self, tag_name: str) -> int:
        """Get tag ID by name."""
        try:
            tag = self.api.extras.tags.get(name=tag_name)
            if tag:
                return tag.id
            else:
                logger.warning(f"Tag '{tag_name}' not found")
                return None
        except Exception as e:
            logger.error(f"Error getting tag {tag_name}: {e}")
            return None
    
    def create_or_update_ip_address(self, ip_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create or update IP address in NetBox IPAM."""
        try:
            # Find existing IP address
            existing = self.api.ipam.ip_addresses.get(address=ip_data['address'])
            
            if existing:
                # Update existing IP address
                for key, value in ip_data.items():
                    if key != 'id':
                        setattr(existing, key, value)
                existing.save()
                logger.info(f"Updated IP address: {ip_data.get('address')}")
                return existing.serialize()
            else:
                # Create new IP address
                new_ip = self.api.ipam.ip_addresses.create(ip_data)
                logger.info(f"Created IP address: {ip_data.get('address')}")
                return new_ip.serialize()
                
        except Exception as e:
            logger.error(f"Error creating/updating IP address: {e}")
            raise
    
    def create_or_update_prefix(self, prefix_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create or update network prefix in NetBox IPAM."""
        try:
            # Find existing prefix
            existing = self.api.ipam.prefixes.get(prefix=prefix_data['prefix'])
            
            if existing:
                # Update existing prefix
                for key, value in prefix_data.items():
                    if key != 'id':
                        setattr(existing, key, value)
                existing.save()
                logger.info(f"Updated prefix: {prefix_data.get('prefix')}")
                return existing.serialize()
            else:
                # Create new prefix
                new_prefix = self.api.ipam.prefixes.create(prefix_data)
                logger.info(f"Created prefix: {prefix_data.get('prefix')}")
                return new_prefix.serialize()
                
        except Exception as e:
            logger.error(f"Error creating/updating prefix: {e}")
            raise
    
    def create_interface(self, interface_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create interface in NetBox."""
        try:
            new_interface = self.api.dcim.interfaces.create(interface_data)
            logger.info(f"Created interface: {interface_data.get('name')} on device {interface_data.get('device')}")
            return new_interface.serialize()
        except Exception as e:
            logger.error(f"Error creating interface: {e}")
            raise
    
    def get_or_create_device_interface(self, device_id: int, interface_name: str, 
                                     interface_type: str = 'virtual', auto_generated: bool = False) -> int:
        """Get existing interface or create new one for device."""
        try:
            # Try to find existing interface
            existing = self.api.dcim.interfaces.get(device=device_id, name=interface_name)
            if existing:
                logger.info(f"Found existing interface: {interface_name}")
                return existing.id
            
            # Create new interface
            interface_data = {
                'device': device_id,
                'name': interface_name,
                'type': interface_type,
                'enabled': True,
                'description': f'Auto-generated interface from FortiGate sync' if auto_generated else '',
                'custom_fields': {
                    'auto_generated': auto_generated
                }
            }
            
            interface = self.create_interface(interface_data)
            logger.info(f"Created interface: {interface_name} ({'auto-generated' if auto_generated else 'manual'})")
            return interface['id']
            
        except Exception as e:
            logger.error(f"Error getting/creating interface {interface_name}: {e}")
            raise
    
    def assign_ip_to_interface(self, ip_address_id: int, interface_id: int) -> Dict[str, Any]:
        """Assign IP address to interface in NetBox."""
        try:
            # Get the IP address object
            ip_obj = self.api.ipam.ip_addresses.get(ip_address_id)
            if not ip_obj:
                raise ValueError(f"IP address with ID {ip_address_id} not found")
            
            # Update the IP address to assign it to the interface
            ip_obj.assigned_object_type = 'dcim.interface'
            ip_obj.assigned_object_id = interface_id
            ip_obj.save()
            
            logger.info(f"Assigned IP {ip_obj.address} to interface ID {interface_id}")
            return ip_obj.serialize()
            
        except Exception as e:
            logger.error(f"Error assigning IP to interface: {e}")
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
            existing_vlans = self.api.ipam.vlans.filter(vid=vid, name=name)
            existing = existing_vlans[0] if existing_vlans else None
            
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
    
    def get_or_create_contact(self, contact_data: Dict[str, Any]) -> Dict[str, Any]:
        """Get or create contact in NetBox."""
        try:
            email = contact_data.get('email')
            name = contact_data.get('name', '')
            
            # Find existing contact by email
            existing = None
            if email:
                contacts = list(self.api.tenancy.contacts.filter(email=email))
                existing = contacts[0] if contacts else None
            
            if not existing and name:
                contacts = list(self.api.tenancy.contacts.filter(name=name))
                existing = contacts[0] if contacts else None
            
            if existing:
                # Update existing contact
                for key, value in contact_data.items():
                    if key not in ['id'] and value:
                        setattr(existing, key, value)
                existing.save()
                logger.info(f"Updated contact: {name} ({email})")
                return existing.serialize()
            else:
                # Create new contact
                new_contact = self.api.tenancy.contacts.create(contact_data)
                logger.info(f"Created contact: {name} ({email})")
                return new_contact.serialize()
                
        except Exception as e:
            logger.error(f"Error creating/updating contact: {e}")
            raise
    
    def assign_device_contact(self, device_name: str, contact_id: int) -> bool:
        """Assign a contact to a device."""
        try:
            # Find the device
            device = self.api.dcim.devices.get(name=device_name)
            if not device:
                logger.warning(f"Device {device_name} not found for contact assignment")
                return False
            
            # Assign contact
            device.primary_contact = contact_id
            device.save()
            logger.info(f"Assigned contact ID {contact_id} to device {device_name}")
            return True
            
        except Exception as e:
            logger.error(f"Error assigning contact to device {device_name}: {e}")
            return False
    
    def delete_stale_objects(self, source: str, grace_days: int = 7):
        """Delete objects marked as stale for more than grace_days."""
        # This would implement soft-delete logic based on tags
        # For now, we'll skip implementation as it requires careful handling
        logger.info(f"Stale object cleanup for source {source} (grace period: {grace_days} days)")
        # TODO: Implement stale object cleanup
    
    # HTTP methods for plugin support
    def get(self, endpoint: str, **kwargs):
        """Make GET request to NetBox API."""
        url = f"{self.config.netbox_url.rstrip('/')}{endpoint}"
        headers = {'Authorization': f'Token {self.config.netbox_token}'}
        return self.client.get(url, headers=headers, **kwargs)
    
    def post(self, endpoint: str, **kwargs):
        """Make POST request to NetBox API."""
        url = f"{self.config.netbox_url.rstrip('/')}{endpoint}"
        headers = {'Authorization': f'Token {self.config.netbox_token}', 'Content-Type': 'application/json'}
        return self.client.post(url, headers=headers, **kwargs)
    
    def patch(self, endpoint: str, **kwargs):
        """Make PATCH request to NetBox API."""
        url = f"{self.config.netbox_url.rstrip('/')}{endpoint}"
        headers = {'Authorization': f'Token {self.config.netbox_token}', 'Content-Type': 'application/json'}
        return self.client.patch(url, headers=headers, **kwargs)