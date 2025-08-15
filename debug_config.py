#!/usr/bin/env python3
import os
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# Print all relevant environment variables
print("Environment variables:")
for key in sorted(os.environ.keys()):
    if any(prefix in key for prefix in ['NETBOX', 'FGT', 'GRAPH']):
        print(f"{key}={os.environ[key]}")

print("\nTrying to load config...")
try:
    from src.netbox_infra_sync.config import AppConfig
    config = AppConfig()
    print("Config loaded successfully!")
    print(f"NetBox URL: {config.netbox_url}")
    print(f"FortiGate Host: {config.fortigate_host}")
except Exception as e:
    print(f"Error loading config: {e}")