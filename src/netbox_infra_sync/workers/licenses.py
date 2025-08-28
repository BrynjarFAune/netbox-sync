import logging
import time
from typing import Dict, List, Any
from collections import defaultdict

from .base import BaseWorker
from ..api.intune_client import IntuneClient

logger = logging.getLogger(__name__)


class LicenseWorker(BaseWorker):
    """Worker for extracting license data from Intune devices."""
    
    def __init__(self, config):
        super().__init__(config)
        self.intune_client = IntuneClient(config)
    
    def fetch_data(self) -> Dict[str, List[Any]]:
        """Extract license data from existing Intune device data."""
        start_time = time.time()
        data = {
            'licenses': [],
            'license_instances': []
        }
        errors = []
        
        try:
            logger.info("Fetching license data from Intune managed devices...")
            
            # Get managed devices to extract user information
            managed_devices = self.intune_client.get_managed_devices()
            logger.info(f"Found {len(managed_devices)} managed devices")
            
            # Get all available SKUs (license types)
            subscribed_skus = self.intune_client.get_subscribed_skus()
            logger.info(f"Found {len(subscribed_skus)} subscribed SKUs")
            
            # Create license definitions from SKUs
            for sku in subscribed_skus:
                try:
                    license_data = {
                        'name': sku.get('skuPartNumber', 'Unknown'),
                        'vendor_name': 'Microsoft',
                        'sku_id': sku.get('skuId'),
                        'total_licenses': sku.get('prepaidUnits', {}).get('enabled', 0),
                        'consumed_licenses': sku.get('consumedUnits', 0),
                        'service_plans': sku.get('servicePlans', [])
                    }
                    data['licenses'].append(license_data)
                    logger.debug(f"Added license: {license_data['name']}")
                except Exception as e:
                    errors.append(f"Error processing SKU {sku.get('skuId')}: {e}")
                    logger.error(f"Error processing SKU: {e}")
            
            # Extract unique users from devices
            unique_users = {}
            for device in managed_devices:
                user_email = device.get('userPrincipalName') or device.get('emailAddress')
                if user_email and user_email not in unique_users:
                    unique_users[user_email] = {
                        'email': user_email,
                        'display_name': device.get('userDisplayName'),
                        'user_id': device.get('userId'),
                        'devices': []
                    }
                if user_email:
                    unique_users[user_email]['devices'].append(device.get('deviceName'))
            
            logger.info(f"Found {len(unique_users)} unique users from devices")
            
            # Create license instances by getting user license assignments
            license_assignments = defaultdict(list)
            processed_users = 0
            
            for user_email, user_info in unique_users.items():
                try:
                    # Get user's assigned licenses
                    user_licenses = self.intune_client.get_user_licenses(user_email)
                    
                    for license in user_licenses:
                        sku_id = license.get('skuId')
                        
                        # Find matching license from our SKU data
                        matching_license = None
                        for sku in subscribed_skus:
                            if sku.get('skuId') == sku_id:
                                matching_license = sku
                                break
                        
                        if matching_license:
                            license_instance = {
                                'license_name': matching_license.get('skuPartNumber', 'Unknown'),
                                'license_sku_id': sku_id,
                                'assigned_to_email': user_email,
                                'assigned_to_name': user_info['display_name'],
                                'user_id': user_info['user_id'],
                                'assigned_devices': user_info['devices'],
                                'disabled_plans': license.get('disabledPlans', [])
                            }
                            data['license_instances'].append(license_instance)
                            license_assignments[sku_id].append(user_email)
                            
                            logger.debug(f"Added license instance: {license_instance['license_name']} -> {user_email}")
                    
                    processed_users += 1
                    if processed_users % 50 == 0:
                        logger.info(f"Processed {processed_users}/{len(unique_users)} users...")
                        
                except Exception as e:
                    errors.append(f"Error processing licenses for user {user_email}: {e}")
                    logger.error(f"Error processing user {user_email}: {e}")
            
            duration = time.time() - start_time
            logger.info(f"License data fetch completed in {duration:.2f}s")
            
            # Log summary
            logger.info(
                f"License fetch summary: licenses={len(data['licenses'])}, "
                f"instances={len(data['license_instances'])}, "
                f"users_processed={processed_users}, "
                f"errors={len(errors)}"
            )
            
            if errors:
                logger.warning(f"License fetch completed with {len(errors)} errors")
                for error in errors[:5]:  # Log first 5 errors
                    logger.warning(f"Error: {error}")
            
            return data
            
        except Exception as e:
            logger.error(f"Critical error in license data fetch: {e}")
            raise