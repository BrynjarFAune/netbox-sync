import logging
import time
from typing import Dict, List, Any

from .base import BaseWorker
from ..api.intune_client import IntuneClient
from ..models.normalizer import DataNormalizer
from ..models.canonical import CanonicalDevice

logger = logging.getLogger(__name__)


class IntuneWorker(BaseWorker):
    """Worker for fetching data from Microsoft Intune."""
    
    def __init__(self, config):
        super().__init__(config)
        self.client = IntuneClient(config)
        self.normalizer = DataNormalizer()
    
    def fetch_data(self) -> Dict[str, List[Any]]:
        """Fetch all data from Intune."""
        start_time = time.time()
        data = {
            'devices': [],
            'interfaces': [],  # Intune doesn't provide interface details
            'ip_addresses': [],  # Intune doesn't provide IP details
            'vlans': [],
            'prefixes': []
        }
        errors = []
        
        try:
            # Get managed devices
            logger.info("Fetching Intune managed devices...")
            managed_devices = self.client.get_managed_devices()
            
            # Track unique contacts for creation
            contacts_to_create = {}
            
            for device in managed_devices:
                try:
                    canonical_device = self.normalizer.normalize_intune_device(device)
                    data['devices'].append(canonical_device)
                    
                    # Extract contact information if available
                    user_email = device.get('userPrincipalName') or device.get('emailAddress')
                    user_name = device.get('userDisplayName')
                    user_id = device.get('userId')
                    
                    if user_email and user_email not in contacts_to_create:
                        contacts_to_create[user_email] = {
                            'name': user_name or user_email.split('@')[0].replace('.', ' ').title(),
                            'email': user_email,
                            'description': f'Contact from Intune (User ID: {user_id})',
                            'device_name': device.get('deviceName')  # Track for assignment
                        }
                    elif user_email and device.get('deviceName'):
                        # Add device to existing contact
                        if 'devices' not in contacts_to_create[user_email]:
                            contacts_to_create[user_email]['devices'] = []
                        contacts_to_create[user_email]['devices'].append(device.get('deviceName'))
                        
                except Exception as e:
                    errors.append(f"Error normalizing device {device.get('deviceName', 'unknown')}: {e}")
                    logger.error(f"Error processing Intune device: {e}")
            
            # Store contacts for later processing
            data['contacts'] = list(contacts_to_create.values())
            
            # Get Azure AD devices for additional context
            logger.info("Fetching Azure AD devices...")
            try:
                azure_devices = self.client.get_azure_ad_devices()
                
                # Create lookup for Azure AD device details
                azure_lookup = {dev.get('deviceId'): dev for dev in azure_devices}
                
                # Enrich managed devices with Azure AD data
                for device in data['devices']:
                    azure_device = azure_lookup.get(device.external_id)
                    if azure_device:
                        # Add additional Azure AD information
                        if not device.operating_system and azure_device.get('operatingSystem'):
                            device.operating_system = azure_device['operatingSystem']
                        if not device.os_version and azure_device.get('operatingSystemVersion'):
                            device.os_version = azure_device['operatingSystemVersion']
                        
                        # Add Azure AD specific tags
                        device.tags.append(f"azure_ad_trust_type:{azure_device.get('trustType', 'unknown')}")
                        if azure_device.get('isManaged'):
                            device.tags.append('azure_ad_managed')
                        
            except Exception as e:
                errors.append(f"Error fetching Azure AD devices: {e}")
                logger.error(f"Error fetching Azure AD devices: {e}")
            
            duration = time.time() - start_time
            logger.info(f"Intune data fetch completed in {duration:.2f}s")
            
            # Log summary
            logger.info(
                f"Intune fetch summary: devices={len(data['devices'])}, "
                f"errors={len(errors)}"
            )
            
            if errors:
                logger.warning(f"Intune fetch completed with {len(errors)} errors")
                for error in errors[:5]:  # Log first 5 errors
                    logger.warning(f"Error: {error}")
            
            return data
            
        except Exception as e:
            logger.error(f"Critical error in Intune data fetch: {e}")
            raise