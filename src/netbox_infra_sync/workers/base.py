import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, List
from datetime import datetime

from ..config import AppConfig
from ..models.canonical import SyncResult

logger = logging.getLogger(__name__)


class BaseWorker(ABC):
    """Base class for data fetching workers."""
    
    def __init__(self, config: AppConfig):
        self.config = config
        self.source_name = self.__class__.__name__.replace('Worker', '').lower()
    
    @abstractmethod
    def fetch_data(self) -> Dict[str, List[Any]]:
        """Fetch data from the external source."""
        pass
    
    def create_sync_result(self, sync_type: str, created: int = 0, updated: int = 0, 
                          deleted: int = 0, errors: List[str] = None, 
                          duration: float = 0.0) -> SyncResult:
        """Create a sync result object."""
        return SyncResult(
            source=self.source_name,
            sync_type=sync_type,
            created=created,
            updated=updated,
            deleted=deleted,
            errors=errors or [],
            duration_seconds=duration,
            timestamp=datetime.utcnow()
        )
    
    def log_sync_result(self, result: SyncResult):
        """Log the sync result."""
        logger.info(
            f"{self.source_name} {result.sync_type} sync completed: "
            f"created={result.created}, updated={result.updated}, "
            f"deleted={result.deleted}, errors={len(result.errors)}, "
            f"duration={result.duration_seconds:.2f}s"
        )