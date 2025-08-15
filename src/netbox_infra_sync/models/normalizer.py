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
        return CanonicalDevice(
            external_id=device_data.get('serial', device_data.get('hostname', 'unknown')),
            source='fortigate',
            name=device_data.get('hostname', 'FortiGate'),
            device_type=DeviceType.FIREWALL,
            manufacturer='Fortinet',
            model=device_data.get('model'),
            serial_number=device_data.get('serial'),
            operating_system='FortiOS',
            os_version=device_data.get('version'),
            tags=['source:fortigate', 'type:firewall']
        )
    
    @staticmethod
    def normalize_intune_device(device_data: Dict[str, Any]) -> CanonicalDevice:
        """Normalize Intune device data."""
        compliance_map = {
            'compliant': ComplianceStatus.COMPLIANT,
            'noncompliant': ComplianceStatus.NON_COMPLIANT,
            'unknown': ComplianceStatus.UNKNOWN
        }
        
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
                'device_id': device_data.get('id', ''),
                'enrollment_type': device_data.get('enrollmentType', ''),
                'management_state': device_data.get('managementState', '')
            },
            tags=['source:intune', f"compliance:{device_data.get('complianceState', 'unknown')}"]
        )
    
    @staticmethod
    def normalize_eset_device(device_data: Dict[str, Any]) -> CanonicalDevice:
        """Normalize ESET device data."""
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
                'eset_version': device_data.get('product_version', ''),
                'threat_count': str(device_data.get('threat_count', 0))
            },
            tags=['source:eset', f"av_status:{device_data.get('antivirus_status', 'unknown')}"]
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
        return CanonicalIPAddress(
            address=f"{lease_data.get('ip')}/32",
            mac_address=lease_data.get('mac'),
            lease_type='dhcp',
            description=f"DHCP lease for {lease_data.get('hostname', 'Unknown')}",
            source='fortigate'
        )
    
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