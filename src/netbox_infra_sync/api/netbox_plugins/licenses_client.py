import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)


class LicensesPluginClient:
    """Client for NetBox licenses plugin."""
    
    def __init__(self, netbox_client):
        self.netbox_client = netbox_client
        self.base_endpoint = '/api/plugins/licenses'
    
    def is_available(self) -> bool:
        """Check if licenses plugin is available."""
        return self.netbox_client.is_plugin_available('licenses')
    
    def get_licenses(self) -> List[Dict[str, Any]]:
        """Get all licenses from NetBox."""
        if not self.is_available():
            logger.warning("Licenses plugin not available")
            return []
        
        try:
            response = self.netbox_client.get(f'{self.base_endpoint}/licenses/')
            data = response.json()
            return data.get('results', [])
        except Exception as e:
            logger.error(f"Failed to get licenses: {e}")
            return []
    
    def get_license_instances(self) -> List[Dict[str, Any]]:
        """Get all license instances from NetBox."""
        if not self.is_available():
            logger.warning("Licenses plugin not available")
            return []
        
        try:
            response = self.netbox_client.get(f'{self.base_endpoint}/licenseinstances/')
            data = response.json()
            return data.get('results', [])
        except Exception as e:
            logger.error(f"Failed to get license instances: {e}")
            return []
    
    def create_or_update_license(self, license_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Create or update a license in NetBox."""
        if not self.is_available():
            logger.warning("Licenses plugin not available, skipping license creation")
            return None
        
        try:
            # Try to find existing license by name and vendor
            existing_licenses = self.get_licenses()
            existing_license = None
            
            for license in existing_licenses:
                if (license.get('name') == license_data.get('name') and 
                    license.get('vendor', {}).get('name') == license_data.get('vendor_name')):
                    existing_license = license
                    break
            
            if existing_license:
                # Update existing license
                license_id = existing_license['id']
                response = self.netbox_client.patch(
                    f'{self.base_endpoint}/licenses/{license_id}/',
                    json=license_data
                )
                logger.info(f"Updated license: {license_data.get('name')}")
                return response.json()
            else:
                # Create new license
                response = self.netbox_client.post(
                    f'{self.base_endpoint}/licenses/',
                    json=license_data
                )
                logger.info(f"Created license: {license_data.get('name')}")
                return response.json()
                
        except Exception as e:
            logger.error(f"Failed to create/update license {license_data.get('name')}: {e}")
            return None
    
    def create_license_instance(self, instance_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Create a license instance in NetBox."""
        if not self.is_available():
            logger.warning("Licenses plugin not available, skipping license instance creation")
            return None
        
        try:
            response = self.netbox_client.post(
                f'{self.base_endpoint}/licenseinstances/',
                json=instance_data
            )
            logger.debug(f"Created license instance for license {instance_data.get('license')}")
            return response.json()
        except Exception as e:
            logger.error(f"Failed to create license instance: {e}")
            return None
    
    def get_license_by_name_and_vendor(self, name: str, vendor_name: str) -> Optional[Dict[str, Any]]:
        """Find a license by name and vendor."""
        licenses = self.get_licenses()
        for license in licenses:
            if (license.get('name') == name and 
                license.get('vendor', {}).get('name') == vendor_name):
                return license
        return None