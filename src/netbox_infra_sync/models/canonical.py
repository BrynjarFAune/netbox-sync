from datetime import datetime
from typing import Dict, List, Optional
from enum import Enum
from pydantic import BaseModel, Field


class DeviceType(str, Enum):
    """Device type enumeration."""
    PHYSICAL = "physical"
    VIRTUAL = "virtual"
    FIREWALL = "firewall"


class ComplianceStatus(str, Enum):
    """Device compliance status."""
    COMPLIANT = "compliant"
    NON_COMPLIANT = "non_compliant"
    UNKNOWN = "unknown"


class InterfaceStatus(str, Enum):
    """Interface status."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    UNKNOWN = "unknown"


class CanonicalDevice(BaseModel):
    """Canonical device model."""
    external_id: str
    source: str  # 'intune', 'eset', 'fortigate'
    name: str
    device_type: DeviceType
    manufacturer: Optional[str] = None
    model: Optional[str] = None
    serial_number: Optional[str] = None
    
    # Device-specific fields
    owner: Optional[str] = None
    compliance_status: Optional[ComplianceStatus] = None
    operating_system: Optional[str] = None
    os_version: Optional[str] = None
    
    # Security fields
    av_status: Optional[str] = None
    last_seen: Optional[datetime] = None
    
    # Custom fields for NetBox
    custom_fields: Dict[str, str] = Field(default_factory=dict)
    tags: List[str] = Field(default_factory=list)
    
    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class CanonicalInterface(BaseModel):
    """Canonical interface model."""
    device_external_id: str
    name: str
    mac_address: Optional[str] = None
    description: Optional[str] = None
    status: InterfaceStatus = InterfaceStatus.UNKNOWN
    mtu: Optional[int] = None
    
    # Network details
    ip_addresses: List[str] = Field(default_factory=list)
    vlan_id: Optional[int] = None
    
    # Custom fields
    custom_fields: Dict[str, str] = Field(default_factory=dict)
    tags: List[str] = Field(default_factory=list)
    
    # Metadata
    source: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class CanonicalIPAddress(BaseModel):
    """Canonical IP address model."""
    address: str  # CIDR notation
    description: Optional[str] = None
    status: str = "active"
    
    # Assignment
    device_external_id: Optional[str] = None
    interface_name: Optional[str] = None
    
    # DHCP/ARP details
    mac_address: Optional[str] = None
    lease_type: Optional[str] = None  # 'dhcp', 'static', 'arp'
    
    # Metadata
    source: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class CanonicalVLAN(BaseModel):
    """Canonical VLAN model."""
    vlan_id: int
    name: str
    description: Optional[str] = None
    
    # Network details
    tenant: Optional[str] = None
    
    # Metadata
    source: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class CanonicalPrefix(BaseModel):
    """Canonical network prefix model."""
    prefix: str  # CIDR notation
    description: Optional[str] = None
    vlan_id: Optional[int] = None
    
    # Metadata
    source: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class SyncResult(BaseModel):
    """Result of a sync operation."""
    source: str
    sync_type: str  # 'devices', 'interfaces', 'ip_addresses', etc.
    created: int = 0
    updated: int = 0
    deleted: int = 0
    errors: List[str] = Field(default_factory=list)
    duration_seconds: float = 0.0
    timestamp: datetime = Field(default_factory=datetime.utcnow)