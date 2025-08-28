import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class PluginClientMixin:
    """Mixin for NetBox plugin detection and client functionality."""
    
    def detect_plugins(self) -> Dict[str, str]:
        """Detect installed NetBox plugins."""
        try:
            response = self.get('/api/plugins/')
            return response.json()
        except Exception as e:
            logger.warning(f"Failed to detect plugins: {e}")
            return {}
    
    def is_plugin_available(self, plugin_endpoint: str) -> bool:
        """Check if specific plugin endpoint exists."""
        plugins = self.detect_plugins()
        return plugin_endpoint in plugins