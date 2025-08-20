#!/usr/bin/env python3
"""Debug script to view collected data without NetBox sync."""

import json
import os
from dotenv import load_dotenv

load_dotenv()

# Import workers
from src.netbox_infra_sync.config import AppConfig
from src.netbox_infra_sync.workers.fortigate import FortiGateWorker
from src.netbox_infra_sync.workers.intune import IntuneWorker
from src.netbox_infra_sync.workers.eset import ESETWorker

def test_fortigate():
    """Test FortiGate data collection."""
    print("=== FORTIGATE DATA ===")
    try:
        config = AppConfig()
        worker = FortiGateWorker(config)
        data = worker.fetch_data()
        
        print(f"Devices: {len(data.get('devices', []))}")
        print(f"Interfaces: {len(data.get('interfaces', []))}")
        print(f"IP Addresses: {len(data.get('ip_addresses', []))}")
        print(f"VLANs: {len(data.get('vlans', []))}")
        print(f"Prefixes: {len(data.get('prefixes', []))}")
        
        # Save to file for inspection
        with open('/tmp/fortigate_data.json', 'w') as f:
            json.dump(data, f, indent=2, default=str)
        print("Data saved to /tmp/fortigate_data.json")
        
        # Show sample device
        if data.get('devices'):
            print("\nSample Device:")
            device = data['devices'][0]
            print(f"  Name: {device.name}")
            print(f"  Type: {device.device_type}")
            print(f"  Source: {device.source}")
            print(f"  External ID: {device.external_id}")
        
    except Exception as e:
        print(f"FortiGate error: {e}")

def test_intune():
    """Test Intune data collection."""
    print("\n=== INTUNE DATA ===")
    try:
        config = AppConfig()
        worker = IntuneWorker(config)
        data = worker.fetch_data()
        
        print(f"Devices: {len(data.get('devices', []))}")
        
        # Save to file for inspection
        with open('/tmp/intune_data.json', 'w') as f:
            json.dump(data, f, indent=2, default=str)
        print("Data saved to /tmp/intune_data.json")
        
        # Show sample devices
        if data.get('devices'):
            print(f"\nSample of {min(3, len(data['devices']))} devices:")
            for device in data['devices'][:3]:
                print(f"  - {device.name} ({device.external_id})")
                print(f"    Owner: {device.owner}")
                print(f"    Compliance: {device.compliance_status}")
        
    except Exception as e:
        print(f"Intune error: {e}")

def test_eset():
    """Test ESET data collection."""
    print("\n=== ESET DATA ===")
    try:
        config = AppConfig()
        worker = ESETWorker(config)
        data = worker.fetch_data()
        
        print(f"Devices: {len(data.get('devices', []))}")
        print(f"Interfaces: {len(data.get('interfaces', []))}")
        
        # Save to file for inspection
        with open('/tmp/eset_data.json', 'w') as f:
            json.dump(data, f, indent=2, default=str)
        print("Data saved to /tmp/eset_data.json")
        
    except Exception as e:
        print(f"ESET error: {e}")

if __name__ == "__main__":
    print("Testing data collection from all sources...\n")
    test_fortigate()
    test_intune() 
    test_eset()
    print("\n=== SUMMARY ===")
    print("Check these files for detailed data:")
    print("- /tmp/fortigate_data.json")
    print("- /tmp/intune_data.json") 
    print("- /tmp/eset_data.json")