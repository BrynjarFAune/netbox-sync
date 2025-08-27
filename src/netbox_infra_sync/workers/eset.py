import logging
import time
from typing import Dict, List, Any

from .base import BaseWorker
from ..api.eset_client import ESETClient
from ..models.normalizer import DataNormalizer

logger = logging.getLogger(__name__)


class ESETWorker(BaseWorker):
    """Simple worker for fetching data from ESET."""
    
    def __init__(self, config):
        super().__init__(config)
        if not config.eset_username or not config.eset_password:
            logger.warning("ESET configuration not provided, skipping ESET worker")
            self.client = None
            return
        
        self.client = ESETClient(config)
        self.normalizer = DataNormalizer()
    
    def fetch_data(self) -> Dict[str, List[Any]]:
        """Fetch all data from ESET."""
        if not self.client:
            logger.info("ESET client not configured, returning empty data")
            return {
                'devices': [],
                'interfaces': [],
                'ip_addresses': [],
                'vlans': [],
                'prefixes': []
            }
        
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
            logger.info("Fetching ESET devices...")
            raw_devices = self.client.get_devices()
            
            for device in raw_devices:
                try:
                    # Extract basic device info from the complex ESET structure
                    device_data = {
                        'uuid': device.get('uuid'),
                        'hostname': device.get('displayName', 'Unknown'),
                        'device_type': device.get('deviceType', 'Unknown'),
                        'last_seen': device.get('lastSyncTime'),
                        'os_name': device.get('operatingSystem', {}).get('displayName'),
                        'local_ip': device.get('primaryLocalIpAddress'),
                        'public_ip': device.get('publicIpAddress'),
                        'antivirus_status': 'protected',  # Simple default
                        'product_version': '7.x',  # Simple default
                        'threat_count': 0  # Simple default
                    }
                    
                    # Add hardware info if available
                    hardware = device.get('hardwareProfiles', [])
                    if hardware and len(hardware) > 0:
                        bios = hardware[0].get('bios', {})
                        device_data['bios_manufacturer'] = bios.get('manufacturer')
                        device_data['bios_serial'] = bios.get('serialNumber')
                    
                    canonical_device = self.normalizer.normalize_eset_device(device_data)
                    data['devices'].append(canonical_device)
                    
                except Exception as e:
                    errors.append(f"Error processing ESET device {device.get('uuid', 'unknown')}: {e}")
                    logger.error(f"Error processing ESET device: {e}")
            
            duration = time.time() - start_time
            logger.info(f"ESET data fetch completed in {duration:.2f}s")
            logger.info(f"ESET fetch summary: devices={len(data['devices'])}, errors={len(errors)}")
            
            if errors:
                logger.warning(f"ESET fetch completed with {len(errors)} errors")
                for error in errors[:3]:  # Log first 3 errors
                    logger.warning(f"Error: {error}")
            
            return data
            
        except Exception as e:
            logger.error(f"Critical error in ESET data fetch: {e}")
            raise