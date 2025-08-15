import os
from typing import Optional


class AppConfig:
    """Application configuration from environment variables."""
    
    def __init__(self):
        # NetBox configuration
        self.netbox_url = os.getenv('NETBOX_URL')
        self.netbox_token = os.getenv('NETBOX_TOKEN')
        
        # FortiGate configuration
        self.fortigate_host = os.getenv('FGT_HOST')
        self.fortigate_token = os.getenv('FGT_TOKEN')
        
        # Microsoft Graph/Intune configuration
        self.graph_tenant_id = os.getenv('GRAPH_TENANT_ID')
        self.graph_client_id = os.getenv('GRAPH_CLIENT_ID')
        self.graph_client_secret = os.getenv('GRAPH_CLIENT_SECRET')
        
        # ESET configuration
        self.eset_base_url = os.getenv('ESET_BASE_URL')
        self.eset_token = os.getenv('ESET_TOKEN')
        
        # Sync configuration
        self.sync_interval_cron = os.getenv('SYNC_INTERVAL_CRON', '0 */6 * * *')
        self.delete_grace_days = int(os.getenv('DELETE_GRACE_DAYS', '7'))
        
        # Database configuration
        self.database_url = os.getenv('DATABASE_URL', 'sqlite:///netbox_sync.db')
        
        # Logging configuration
        self.log_level = os.getenv('LOG_LEVEL', 'INFO')
        
        # Rate limiting
        self.api_rate_limit = int(os.getenv('API_RATE_LIMIT', '10'))
        self.api_retry_attempts = int(os.getenv('API_RETRY_ATTEMPTS', '3'))
        self.api_backoff_factor = float(os.getenv('API_BACKOFF_FACTOR', '1.0'))
        
        # Validate required fields
        required_fields = [
            ('netbox_url', self.netbox_url),
            ('netbox_token', self.netbox_token),
            ('fortigate_host', self.fortigate_host),
            ('fortigate_token', self.fortigate_token),
            ('graph_tenant_id', self.graph_tenant_id),
            ('graph_client_id', self.graph_client_id),
            ('graph_client_secret', self.graph_client_secret),
        ]
        
        missing_fields = [name for name, value in required_fields if not value]
        if missing_fields:
            raise ValueError(f"Missing required environment variables: {', '.join(missing_fields)}")