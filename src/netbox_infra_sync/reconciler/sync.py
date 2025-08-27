import logging
import hashlib
import json
import time
from typing import Dict, List, Any

from ..config import AppConfig
from ..api.netbox_client import NetBoxClient
from ..storage.database import DatabaseManager
from ..models.canonical import (
    CanonicalDevice, CanonicalInterface, CanonicalIPAddress,
    CanonicalVLAN, CanonicalPrefix, SyncResult, DeviceType
)

logger = logging.getLogger(__name__)


class Reconciler:
    """Reconciles canonical data with NetBox."""
    
    def __init__(self, config: AppConfig):
        self.config = config
        self.netbox_client = NetBoxClient(config)
        self.db_manager = DatabaseManager(config.database_url)
        # Ensure database is initialized
        self.db_manager.init_database()
    
    def _calculate_hash(self, data: Any) -> str:
        """Calculate SHA256 hash of data for change detection."""
        if hasattr(data, 'dict'):
            # Pydantic model
            data_str = json.dumps(data.dict(), sort_keys=True, default=str)
        else:
            data_str = json.dumps(data, sort_keys=True, default=str)
        return hashlib.sha256(data_str.encode()).hexdigest()
    
    def reconcile_fortigate_data(self, data: Dict[str, List[Any]]) -> List[SyncResult]:
        """Reconcile FortiGate data with NetBox."""
        results = []
        
        # Reconcile devices
        results.append(self._reconcile_devices(data.get('devices', []), 'fortigate'))
        
        # Reconcile VLANs
        results.append(self._reconcile_vlans(data.get('vlans', []), 'fortigate'))
        
        # Reconcile prefixes
        results.append(self._reconcile_prefixes(data.get('prefixes', []), 'fortigate'))
        
        # Reconcile interfaces
        results.append(self._reconcile_interfaces(data.get('interfaces', []), 'fortigate'))
        
        # Reconcile IP addresses
        results.append(self._reconcile_ip_addresses(data.get('ip_addresses', []), 'fortigate'))
        
        return results
    
    def reconcile_intune_data(self, data: Dict[str, List[Any]]) -> List[SyncResult]:
        """Reconcile Intune data with NetBox."""
        results = []
        
        # Reconcile devices
        results.append(self._reconcile_devices(data.get('devices', []), 'intune'))
        
        return results
    
    def reconcile_eset_data(self, data: Dict[str, List[Any]]) -> List[SyncResult]:
        """Reconcile ESET data with NetBox."""
        results = []
        
        # Reconcile devices
        results.append(self._reconcile_devices(data.get('devices', []), 'eset'))
        
        # Reconcile interfaces
        results.append(self._reconcile_interfaces(data.get('interfaces', []), 'eset'))
        
        return results
    
    def _reconcile_devices(self, devices: List[CanonicalDevice], source: str) -> SyncResult:
        """Reconcile devices with NetBox."""
        start_time = time.time()
        created = updated = deleted = 0
        errors = []
        
        with self.db_manager.get_session() as session:
            sync_run = self.db_manager.create_sync_run(session, source, 'devices')
            
            try:
                current_external_ids = []
                
                for device in devices:
                    try:
                        current_external_ids.append(device.external_id)
                        data_hash = self._calculate_hash(device)
                        
                        # Check if device has changed
                        existing_state = self.db_manager.get_sync_state(
                            session, source, 'device', device.external_id
                        )
                        
                        if existing_state and existing_state.data_hash == data_hash:
                            # No changes, just update last_seen
                            self.db_manager.update_sync_state(
                                session, source, 'device', device.external_id, data_hash
                            )
                            continue
                        
                        # Prepare NetBox device data
                        netbox_device_data = self._prepare_netbox_device_data(device)
                        
                        # Create or update in NetBox
                        netbox_device = self.netbox_client.create_or_update_device(netbox_device_data)
                        netbox_id = str(netbox_device.get('id'))
                        
                        # Update state and mapping
                        self.db_manager.update_sync_state(
                            session, source, 'device', device.external_id, data_hash, netbox_id
                        )
                        self.db_manager.update_object_mapping(
                            session, source, 'device', device.external_id, netbox_id
                        )
                        
                        if existing_state:
                            updated += 1
                            logger.debug(f"Updated device: {device.name}")
                        else:
                            created += 1
                            logger.info(f"Created device: {device.name}")
                            
                    except Exception as e:
                        error_msg = f"Error processing device {device.name}: {e}"
                        errors.append(error_msg)
                        logger.error(error_msg)
                
                # Mark stale objects
                self.db_manager.mark_stale_objects(session, source, 'device', current_external_ids)
                
                duration = time.time() - start_time
                self.db_manager.complete_sync_run(
                    session, sync_run, created, updated, deleted, errors
                )
                session.commit()
                
                result = SyncResult(
                    source=source,
                    sync_type='devices',
                    created=created,
                    updated=updated,
                    deleted=deleted,
                    errors=errors,
                    duration_seconds=duration
                )
                
                logger.info(
                    f"{source} devices sync: created={created}, updated={updated}, "
                    f"errors={len(errors)}, duration={duration:.2f}s"
                )
                
                return result
                
            except Exception as e:
                self.db_manager.fail_sync_run(session, sync_run, str(e))
                session.commit()
                raise
    
    def _prepare_netbox_device_data(self, device: CanonicalDevice) -> Dict[str, Any]:
        """Prepare device data for NetBox API."""
        data = {
            'name': device.name,
            'site': self.netbox_client.get_or_create_site()
        }
        
        # Set device type - ALWAYS ensure we have one
        device_type_id = None
        if device.manufacturer and device.model:
            try:
                device_type_id = self.netbox_client.get_or_create_device_type(
                    device.manufacturer, device.model
                )
                logger.info(f"Using device type for {device.manufacturer} {device.model}")
            except Exception as e:
                logger.warning(f"Could not create device type for {device.manufacturer} {device.model}: {e}")
        
        # ALWAYS set fallback device type if none was set
        if not device_type_id:
            try:
                device_type_id = self.netbox_client.get_or_create_device_type("Generic", "Unknown")
                logger.info(f"Using default device type for {device.name}")
            except Exception as e:
                logger.error(f"Could not create default device type: {e}")
                # Last resort - use any existing device type
                device_type_id = 1  # Assume ID 1 exists
        
        # MUST have a device type
        data['device_type'] = device_type_id
        
        # Set device role based on device type
        role_mapping = {
            DeviceType.FIREWALL: ('Firewall', 'f44336'),
            DeviceType.PHYSICAL: ('Server', '2196f3'),
            DeviceType.VIRTUAL: ('Virtual Machine', '9c27b0')
        }
        
        # ALWAYS ensure we have a role
        role_name, role_color = role_mapping.get(device.device_type, ('Server', '2196f3'))
        role_id = None
        try:
            role_id = self.netbox_client.get_or_create_device_role(role_name, role_color)
        except Exception as e:
            logger.warning(f"Could not create device role {role_name}: {e}")
            # Set default role if creation failed
            try:
                role_id = self.netbox_client.get_or_create_device_role("Server", "2196f3")
                logger.info(f"Using default role 'Server' for {device.name}")
            except Exception as e2:
                logger.error(f"Could not create default device role: {e2}")
                # Last resort - use any existing role
                role_id = 1  # Assume ID 1 exists
        
        # MUST have a role
        data['role'] = role_id
        
        # Add serial number if available
        if device.serial_number:
            data['serial'] = device.serial_number
        
        # Add custom fields
        custom_fields = device.custom_fields.copy()
        custom_fields.update({
            'external_id': device.external_id,
            'source': device.source,
            'owner': device.owner or '',
            'compliance_status': device.compliance_status.value if device.compliance_status else '',
            'av_status': device.av_status or ''
        })
        data['custom_fields'] = custom_fields
        
        return data
    
    def _reconcile_interfaces(self, interfaces: List[CanonicalInterface], source: str) -> SyncResult:
        """Reconcile interfaces with NetBox."""
        start_time = time.time()
        created = updated = 0
        errors = []
        
        with self.db_manager.get_session() as session:
            sync_run = self.db_manager.create_sync_run(session, source, 'interfaces')
            
            try:
                for interface in interfaces:
                    try:
                        # Get device NetBox ID
                        device_mapping = self.db_manager.get_object_mapping(
                            session, source, 'device', interface.device_external_id
                        )
                        
                        if not device_mapping:
                            errors.append(f"Device not found for interface {interface.name}: {interface.device_external_id}")
                            continue
                        
                        # Prepare interface data
                        interface_data = {
                            'device': int(device_mapping.netbox_id),
                            'name': interface.name,
                            'description': interface.description or '',
                            'mac_address': interface.mac_address,
                            'mtu': interface.mtu,
                            'tags': [{'name': tag} for tag in interface.tags]
                        }
                        
                        # Create or update interface
                        netbox_interface = self.netbox_client.create_or_update_interface(interface_data)
                        
                        if netbox_interface:
                            created += 1 if 'created' in str(netbox_interface) else 0
                            updated += 1 if 'updated' in str(netbox_interface) else 0
                            
                    except Exception as e:
                        error_msg = f"Error processing interface {interface.name}: {e}"
                        errors.append(error_msg)
                        logger.error(error_msg)
                
                duration = time.time() - start_time
                self.db_manager.complete_sync_run(
                    session, sync_run, created, updated, 0, errors
                )
                session.commit()
                
                result = SyncResult(
                    source=source,
                    sync_type='interfaces',
                    created=created,
                    updated=updated,
                    errors=errors,
                    duration_seconds=duration
                )
                
                logger.info(
                    f"{source} interfaces sync: created={created}, updated={updated}, "
                    f"errors={len(errors)}, duration={duration:.2f}s"
                )
                
                return result
                
            except Exception as e:
                self.db_manager.fail_sync_run(session, sync_run, str(e))
                session.commit()
                raise
    
    def _reconcile_vlans(self, vlans: List[CanonicalVLAN], source: str) -> SyncResult:
        """Reconcile VLANs with NetBox."""
        start_time = time.time()
        created = updated = 0
        errors = []
        
        with self.db_manager.get_session() as session:
            sync_run = self.db_manager.create_sync_run(session, source, 'vlans')
            
            try:
                for vlan in vlans:
                    try:
                        vlan_data = {
                            'vid': vlan.vlan_id,
                            'name': vlan.name,
                            'description': vlan.description or '',
                            'tags': [{'name': f'source:{source}'}]
                        }
                        
                        netbox_vlan = self.netbox_client.get_or_create_vlan(vlan_data)
                        created += 1 if netbox_vlan else 0
                        
                    except Exception as e:
                        error_msg = f"Error processing VLAN {vlan.name}: {e}"
                        errors.append(error_msg)
                        logger.error(error_msg)
                
                duration = time.time() - start_time
                self.db_manager.complete_sync_run(
                    session, sync_run, created, updated, 0, errors
                )
                session.commit()
                
                return SyncResult(
                    source=source,
                    sync_type='vlans',
                    created=created,
                    updated=updated,
                    errors=errors,
                    duration_seconds=duration
                )
                
            except Exception as e:
                self.db_manager.fail_sync_run(session, sync_run, str(e))
                session.commit()
                raise
    
    def _reconcile_prefixes(self, prefixes: List[CanonicalPrefix], source: str) -> SyncResult:
        """Reconcile prefixes with NetBox."""
        start_time = time.time()
        created = updated = 0
        errors = []
        
        with self.db_manager.get_session() as session:
            sync_run = self.db_manager.create_sync_run(session, source, 'prefixes')
            
            try:
                for prefix in prefixes:
                    try:
                        prefix_data = {
                            'prefix': prefix.prefix,
                            'description': prefix.description or ''
                        }
                        
                        netbox_prefix = self.netbox_client.create_or_update_prefix(prefix_data)
                        created += 1 if netbox_prefix else 0
                        
                    except Exception as e:
                        error_msg = f"Error processing prefix {prefix.prefix}: {e}"
                        errors.append(error_msg)
                        logger.error(error_msg)
                
                duration = time.time() - start_time
                self.db_manager.complete_sync_run(
                    session, sync_run, created, updated, 0, errors
                )
                session.commit()
                
                return SyncResult(
                    source=source,
                    sync_type='prefixes',
                    created=created,
                    updated=updated,
                    errors=errors,
                    duration_seconds=duration
                )
                
            except Exception as e:
                self.db_manager.fail_sync_run(session, sync_run, str(e))
                session.commit()
                raise
    
    def _reconcile_ip_addresses(self, ip_addresses: List[CanonicalIPAddress], source: str) -> SyncResult:
        """Reconcile IP addresses with NetBox."""
        start_time = time.time()
        created = updated = 0
        errors = []
        
        with self.db_manager.get_session() as session:
            sync_run = self.db_manager.create_sync_run(session, source, 'ip_addresses')
            
            try:
                for ip in ip_addresses:
                    try:
                        # Determine assignment method
                        assignment_method = 'unknown'
                        if hasattr(ip, 'lease_type') and ip.lease_type:
                            if ip.lease_type == 'leased':
                                assignment_method = 'dhcp'
                            elif ip.lease_type == 'reserved':
                                assignment_method = 'reserved'
                        elif hasattr(ip, 'assignment_type') and ip.assignment_type:
                            assignment_method = ip.assignment_type
                        
                        ip_data = {
                            'address': ip.address,
                            'description': ip.description or '',
                            'status': ip.status or 'active'
                        }
                        
                        netbox_ip = self.netbox_client.create_or_update_ip_address(ip_data)
                        
                        # Try to assign IP to interface if we have interface info
                        if hasattr(ip, 'interface_name') and ip.interface_name and netbox_ip:
                            try:
                                # Find the device for this IP (will need to enhance this logic)
                                self._assign_ip_to_device_interface(netbox_ip, ip, source)
                            except Exception as assign_error:
                                logger.warning(f"Could not assign IP {ip.address} to interface {ip.interface_name}: {assign_error}")
                        created += 1 if 'created' in str(netbox_ip).lower() else 0
                        updated += 1 if 'updated' in str(netbox_ip).lower() else 0
                        
                    except Exception as e:
                        error_msg = f"Error processing IP address {ip.address}: {e}"
                        errors.append(error_msg)
                        logger.error(error_msg)
                
                duration = time.time() - start_time
                self.db_manager.complete_sync_run(
                    session, sync_run, created, updated, 0, errors
                )
                session.commit()
                
                return SyncResult(
                    source=source,
                    sync_type='ip_addresses',
                    created=created,
                    updated=updated,
                    errors=errors,
                    duration_seconds=duration
                )
                
            except Exception as e:
                self.db_manager.fail_sync_run(session, sync_run, str(e))
                session.commit()
                raise
    
    def _assign_ip_to_device_interface(self, netbox_ip: Dict[str, Any], ip: CanonicalIPAddress, source: str):
        """Assign IP address to device interface, creating interface if needed."""
        try:
            # Find device mapping for this IP
            device_external_id = None
            device_netbox_id = None
            
            # Try to find device by hostname or other identifier
            if hasattr(ip, 'device_name') and ip.device_name:
                device_external_id = ip.device_name
            elif hasattr(ip, 'hostname') and ip.hostname:
                device_external_id = ip.hostname
            
            # If no device info on IP, try to infer from DHCP lease data
            if not device_external_id and hasattr(ip, 'client_hostname') and ip.client_hostname:
                device_external_id = ip.client_hostname
            
            # Get device NetBox ID from mapping
            if device_external_id:
                with self.db_manager.get_session() as session:
                    device_mapping = self.db_manager.get_object_mapping(
                        session, source, 'device', device_external_id
                    )
                    if device_mapping:
                        device_netbox_id = int(device_mapping.netbox_id)
            
            if not device_netbox_id:
                logger.warning(f"Could not find device for IP {ip.address}, skipping interface assignment")
                return
            
            # Determine interface name
            interface_name = getattr(ip, 'interface_name', None)
            if not interface_name:
                # Create a generic interface name for DHCP leases
                if hasattr(ip, 'lease_type') and ip.lease_type:
                    interface_name = 'lan'  # Default FortiGate LAN interface
                else:
                    interface_name = 'mgmt'  # Default management interface
            
            # Get or create interface
            interface_id = self.netbox_client.get_or_create_device_interface(
                device_id=device_netbox_id,
                interface_name=interface_name,
                interface_type='virtual',  # Most FortiGate interfaces are virtual
                auto_generated=True  # Mark as auto-generated since we created it
            )
            
            # Assign IP to interface
            if interface_id:
                self.netbox_client.assign_ip_to_interface(netbox_ip['id'], interface_id)
                logger.info(f"Assigned IP {ip.address} to interface {interface_name} on device ID {device_netbox_id}")
            
        except Exception as e:
            logger.error(f"Error in _assign_ip_to_device_interface for IP {ip.address}: {e}")
            raise