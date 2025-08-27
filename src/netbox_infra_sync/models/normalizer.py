from typing import Dict, List, Any
from datetime import datetime

from .canonical import (
    CanonicalDevice, CanonicalInterface, CanonicalIPAddress, 
    CanonicalVLAN, CanonicalPrefix, DeviceType, ComplianceStatus, InterfaceStatus
)


class DataNormalizer:
    """Normalizes data from different sources into canonical format."""
    
    @staticmethod
    def normalize_fortigate_device(device_data: Dict[str, Any]) -> CanonicalDevice:
        """Normalize FortiGate device data."""
        import re
        
        hostname = device_data.get('hostname', 'Unknown')
        hardware_vendor = device_data.get('hardware_vendor', 'Unknown')
        hardware_type = device_data.get('hardware_type', 'Unknown')
        hardware_family = device_data.get('hardware_family', 'Unknown')
        os_name = device_data.get('os_name', 'Unknown')
        
        # Detect device type based on hostname patterns and hardware info
        device_type = DeviceType.PHYSICAL
        tags = ['source:fortigate']
        
        # Check for UUID pattern (likely VMs)
        uuid_pattern = re.match(r'^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$', hostname.lower())
        # Check for MAC address pattern (devices without hostname)
        mac_pattern = re.match(r'^([a-f0-9]{2}[:-]){5}[a-f0-9]{2}$', hostname.lower())
        # Check for generic names that suggest VMs
        generic_vm_names = ['valuearray', 'unknown-', 'generic-', 'vm-']
        is_generic_vm = any(name in hostname.lower() for name in generic_vm_names)
        
        if uuid_pattern:
            device_type = DeviceType.VIRTUAL
            tags.extend(['type:vm', 'hostname:uuid'])
        elif mac_pattern:
            device_type = DeviceType.VIRTUAL  # Likely VM without proper hostname
            tags.extend(['type:vm', 'hostname:mac'])
        elif is_generic_vm:
            device_type = DeviceType.VIRTUAL
            tags.extend(['type:vm', 'hostname:generic'])
        elif hardware_family in ['File Server', 'NAS'] or 'Server' in hardware_type:
            device_type = DeviceType.PHYSICAL
            tags.append('type:server')
        elif hardware_family in ['Phone', 'iPhone', 'Tablet']:
            device_type = DeviceType.PHYSICAL
            tags.append('type:mobile')
        elif 'Firewall' in hardware_type or hostname.lower() == 'fortigate':
            device_type = DeviceType.FIREWALL
            tags.append('type:firewall')
        else:
            tags.append('type:workstation')
        
        # Add hardware_family as tag if it provides useful info
        if hardware_family != 'Unknown' and hardware_family:
            tags.append(f'hw_family:{hardware_family.lower().replace(" ", "_")}')
        
        # Add other useful FortiGate metadata as tags
        host_src = device_data.get('host_src', '')
        if host_src:
            tags.append(f'host_src:{host_src}')
            
        purdue_level = device_data.get('purdue_level', '')
        if purdue_level:
            tags.append(f'purdue:{purdue_level}')
        
        return CanonicalDevice(
            external_id=device_data.get('serial', hostname),
            source='fortigate',
            name=hostname,
            device_type=device_type,
            manufacturer=hardware_vendor if hardware_vendor != 'Unknown' else None,
            model=hardware_type if hardware_type != 'Unknown' else None,
            operating_system=os_name if os_name != 'Unknown' else None,
            os_version=device_data.get('version'),
            custom_fields={
                # No custom fields for now - using tags instead
            },
            tags=tags
        )
    
    @staticmethod
    def normalize_intune_device(device_data: Dict[str, Any]) -> CanonicalDevice:
        """Normalize Intune device data."""
        compliance_map = {
            'compliant': ComplianceStatus.COMPLIANT,
            'noncompliant': ComplianceStatus.NON_COMPLIANT,
            'unknown': ComplianceStatus.UNKNOWN
        }
        
        # Build comprehensive tags for Intune metadata
        tags = ['source:intune']
        
        # Add compliance status tag
        compliance_state = device_data.get('complianceState', 'unknown')
        tags.append(f"compliance:{compliance_state}")
        
        # Add enrollment type as tag
        enrollment_type = device_data.get('enrollmentType', '')
        if enrollment_type:
            tags.append(f"enrollment:{enrollment_type.lower().replace(' ', '_')}")
        
        # Add management state as tag
        management_state = device_data.get('managementState', '')
        if management_state:
            tags.append(f"mgmt_state:{management_state.lower().replace(' ', '_')}")
        
        # Add device type tag
        device_type_val = device_data.get('deviceType', 'physical')
        tags.append(f"device_type:{device_type_val}")
        
        # Add owner domain if available
        owner_email = device_data.get('userPrincipalName', '')
        if owner_email and '@' in owner_email:
            domain = owner_email.split('@')[1].lower()
            tags.append(f"owner_domain:{domain}")
        
        return CanonicalDevice(
            external_id=device_data.get('azureADDeviceId', device_data.get('id')),
            source='intune',
            name=device_data.get('deviceName', 'Unknown Device'),
            device_type=DeviceType.PHYSICAL if device_data.get('deviceType') != 'virtual' else DeviceType.VIRTUAL,
            manufacturer=device_data.get('manufacturer'),
            model=device_data.get('model'),
            serial_number=device_data.get('serialNumber'),
            owner=device_data.get('userPrincipalName'),
            compliance_status=compliance_map.get(device_data.get('complianceState', 'unknown'), ComplianceStatus.UNKNOWN),
            operating_system=device_data.get('operatingSystem'),
            os_version=device_data.get('osVersion'),
            last_seen=datetime.fromisoformat(device_data.get('lastSyncDateTime', '').replace('Z', '+00:00')) if device_data.get('lastSyncDateTime') else None,
            custom_fields={
                # No custom fields for now - using tags instead
            },
            tags=tags
        )
    
    @staticmethod
    def normalize_eset_device(device_data: Dict[str, Any]) -> CanonicalDevice:
        """Normalize ESET device data."""
        # Build comprehensive tags for ESET metadata
        tags = ['source:eset']
        
        # Add antivirus status tag
        av_status = device_data.get('antivirus_status', 'unknown')
        tags.append(f"av_status:{av_status}")
        
        # Add ESET product version as tag
        product_version = device_data.get('product_version', '')
        if product_version:
            tags.append(f"eset_version:{product_version}")
        
        # Add threat count as tag if significant
        threat_count = device_data.get('threat_count', 0)
        if threat_count > 0:
            tags.append(f"threat_count:{threat_count}")
        
        return CanonicalDevice(
            external_id=device_data.get('uuid', device_data.get('hostname')),
            source='eset',
            name=device_data.get('hostname', 'Unknown Device'),
            device_type=DeviceType.PHYSICAL,
            operating_system=device_data.get('os_name'),
            os_version=device_data.get('os_version'),
            av_status=device_data.get('antivirus_status', 'unknown'),
            last_seen=datetime.fromisoformat(device_data.get('last_seen', '').replace('Z', '+00:00')) if device_data.get('last_seen') else None,
            custom_fields={
                # No custom fields for now - using tags instead
            },
            tags=tags
        )
    
    @staticmethod
    def normalize_fortigate_interface(interface_data: Dict[str, Any], device_id: str) -> CanonicalInterface:
        """Normalize FortiGate interface data."""
        status_map = {
            'up': InterfaceStatus.ACTIVE,
            'down': InterfaceStatus.INACTIVE
        }
        
        return CanonicalInterface(
            device_external_id=device_id,
            name=interface_data.get('name', ''),
            description=interface_data.get('description'),
            status=status_map.get(interface_data.get('status', 'unknown'), InterfaceStatus.UNKNOWN),
            ip_addresses=interface_data.get('ip_addresses', []),
            vlan_id=interface_data.get('vlan_id'),
            mtu=interface_data.get('mtu'),
            source='fortigate',
            tags=['source:fortigate']
        )
    
    @staticmethod
    def normalize_fortigate_vlan(vlan_data: Dict[str, Any]) -> CanonicalVLAN:
        """Normalize FortiGate VLAN data."""
        return CanonicalVLAN(
            vlan_id=vlan_data.get('vlan_id'),
            name=vlan_data.get('name', f"VLAN-{vlan_data.get('vlan_id')}"),
            description=vlan_data.get('description'),
            source='fortigate'
        )
    
    @staticmethod
    def normalize_fortigate_prefix(prefix_data: Dict[str, Any]) -> CanonicalPrefix:
        """Normalize FortiGate network prefix data."""
        return CanonicalPrefix(
            prefix=prefix_data.get('subnet'),
            description=prefix_data.get('description'),
            vlan_id=prefix_data.get('vlan_id'),
            source='fortigate'
        )
    
    @staticmethod
    def normalize_fortigate_dhcp_lease(lease_data: Dict[str, Any]) -> CanonicalIPAddress:
        """Normalize FortiGate DHCP lease data."""
        ip_addr = CanonicalIPAddress(
            address=f"{lease_data.get('ip')}/32",
            mac_address=lease_data.get('mac'),
            lease_type='dhcp',
            description=f"DHCP lease for {lease_data.get('hostname', 'Unknown')}",
            source='fortigate'
        )
        
        # Add device information for interface assignment
        if lease_data.get('hostname'):
            ip_addr.client_hostname = lease_data.get('hostname')
        
        # Default FortiGate interface for DHCP leases is usually 'lan'
        ip_addr.interface_name = lease_data.get('interface', 'lan')
        
        return ip_addr
    
    @staticmethod
    def normalize_fortigate_arp_entry(arp_data: Dict[str, Any]) -> CanonicalIPAddress:
        """Normalize FortiGate ARP entry data."""
        return CanonicalIPAddress(
            address=f"{arp_data.get('ip')}/32",
            mac_address=arp_data.get('mac'),
            interface_name=arp_data.get('interface'),
            lease_type='arp',
            description='ARP table entry',
            source='fortigate'
        )