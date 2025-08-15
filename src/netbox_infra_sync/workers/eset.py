import logging
import time
from typing import Dict, List, Any

from .base import BaseWorker
from ..api.eset_client import ESETClient
from ..models.normalizer import DataNormalizer
from ..models.canonical import CanonicalDevice, CanonicalInterface

logger = logging.getLogger(__name__)


class ESETWorker(BaseWorker):
    """Worker for fetching data from ESET PROTECT."""
    
    def __init__(self, config):
        super().__init__(config)
        if not config.eset_base_url or not config.eset_token:
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
            # Get computers
            logger.info("Fetching ESET computers...")
            computers = self.client.get_computers()
            
            # Get antivirus status
            logger.info("Fetching ESET antivirus status...")
            av_status_list = self.client.get_antivirus_status()
            av_status_lookup = {status.get('computerId'): status for status in av_status_list}
            
            # Get threat information
            logger.info("Fetching ESET threat information...")
            threats = self.client.get_threats()
            threat_lookup = {}
            for threat in threats:
                computer_id = threat.get('computerId')
                if computer_id:
                    if computer_id not in threat_lookup:
                        threat_lookup[computer_id] = []
                    threat_lookup[computer_id].append(threat)
            
            for computer in computers:
                try:
                    computer_id = computer.get('id')
                    
                    # Enrich computer data with AV status
                    av_status = av_status_lookup.get(computer_id, {})
                    computer.update({
                        'antivirus_status': av_status.get('status', 'unknown'),
                        'threat_count': len(threat_lookup.get(computer_id, []))
                    })
                    
                    # Get detailed computer info
                    try:
                        details = self.client.get_computer_details(computer_id)
                        computer.update(details)
                    except Exception as e:
                        logger.warning(f"Could not fetch details for computer {computer_id}: {e}")
                    
                    canonical_device = self.normalizer.normalize_eset_device(computer)
                    data['devices'].append(canonical_device)
                    
                    # Get network interfaces for this computer
                    try:
                        interfaces = self.client.get_network_interfaces(computer_id)
                        for interface in interfaces:
                            try:
                                # Create a canonical interface
                                canonical_interface = CanonicalInterface(
                                    device_external_id=canonical_device.external_id,
                                    name=interface.get('name', 'Unknown'),
                                    mac_address=interface.get('macAddress'),
                                    description=interface.get('description'),
                                    ip_addresses=interface.get('ipAddresses', []),
                                    source='eset',
                                    tags=['source:eset']
                                )
                                data['interfaces'].append(canonical_interface)
                            except Exception as e:
                                errors.append(f"Error normalizing interface for {computer_id}: {e}")
                    except Exception as e:
                        logger.warning(f"Could not fetch network interfaces for {computer_id}: {e}")
                        
                except Exception as e:
                    errors.append(f"Error normalizing computer {computer.get('hostname', 'unknown')}: {e}")
                    logger.error(f"Error processing ESET computer: {e}")
            
            duration = time.time() - start_time
            logger.info(f"ESET data fetch completed in {duration:.2f}s")
            
            # Log summary
            logger.info(
                f"ESET fetch summary: devices={len(data['devices'])}, "
                f"interfaces={len(data['interfaces'])}, "
                f"errors={len(errors)}"
            )
            
            if errors:
                logger.warning(f"ESET fetch completed with {len(errors)} errors")
                for error in errors[:5]:  # Log first 5 errors
                    logger.warning(f"Error: {error}")
            
            return data
            
        except Exception as e:
            logger.error(f"Critical error in ESET data fetch: {e}")
            raise