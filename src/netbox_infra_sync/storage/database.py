import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from sqlalchemy import create_engine, Column, String, Integer, DateTime, Text, Float, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
import json

logger = logging.getLogger(__name__)

Base = declarative_base()


class SyncState(Base):
    """Track sync state and hashes for idempotent operations."""
    __tablename__ = 'sync_state'
    
    id = Column(Integer, primary_key=True)
    source = Column(String(50), nullable=False)
    object_type = Column(String(50), nullable=False)
    external_id = Column(String(255), nullable=False)
    data_hash = Column(String(64), nullable=False)  # SHA256 hash of normalized data
    netbox_id = Column(String(255))  # NetBox object ID
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_seen = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        {'extend_existing': True}
    )


class SyncRun(Base):
    """Track sync run history and results."""
    __tablename__ = 'sync_runs'
    
    id = Column(Integer, primary_key=True)
    source = Column(String(50), nullable=False)
    sync_type = Column(String(50), nullable=False)
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)
    status = Column(String(20), default='running')  # running, completed, failed
    created_count = Column(Integer, default=0)
    updated_count = Column(Integer, default=0)
    deleted_count = Column(Integer, default=0)
    error_count = Column(Integer, default=0)
    errors = Column(Text)  # JSON array of error messages
    duration_seconds = Column(Float)
    
    __table_args__ = (
        {'extend_existing': True}
    )


class ObjectMapping(Base):
    """Map external IDs to NetBox IDs."""
    __tablename__ = 'object_mappings'
    
    id = Column(Integer, primary_key=True)
    source = Column(String(50), nullable=False)
    object_type = Column(String(50), nullable=False)
    external_id = Column(String(255), nullable=False)
    netbox_id = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        {'extend_existing': True}
    )


class StaleObject(Base):
    """Track objects that may need deletion."""
    __tablename__ = 'stale_objects'
    
    id = Column(Integer, primary_key=True)
    source = Column(String(50), nullable=False)
    object_type = Column(String(50), nullable=False)
    external_id = Column(String(255), nullable=False)
    netbox_id = Column(String(255), nullable=False)
    marked_stale_at = Column(DateTime, default=datetime.utcnow)
    deleted_at = Column(DateTime)
    
    __table_args__ = (
        {'extend_existing': True}
    )


class DatabaseManager:
    """Database manager for state storage."""
    
    def __init__(self, database_url: str):
        self.engine = create_engine(database_url, echo=False)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
    
    def init_database(self):
        """Initialize database tables."""
        Base.metadata.create_all(bind=self.engine)
        logger.info("Database initialized successfully")
    
    def get_session(self) -> Session:
        """Get database session."""
        return self.SessionLocal()
    
    def get_sync_state(self, session: Session, source: str, object_type: str, 
                      external_id: str) -> Optional[SyncState]:
        """Get sync state for an object."""
        return session.query(SyncState).filter(
            SyncState.source == source,
            SyncState.object_type == object_type,
            SyncState.external_id == external_id
        ).first()
    
    def update_sync_state(self, session: Session, source: str, object_type: str,
                         external_id: str, data_hash: str, netbox_id: str = None):
        """Update or create sync state."""
        state = self.get_sync_state(session, source, object_type, external_id)
        
        if state:
            state.data_hash = data_hash
            state.last_seen = datetime.utcnow()
            if netbox_id:
                state.netbox_id = netbox_id
        else:
            state = SyncState(
                source=source,
                object_type=object_type,
                external_id=external_id,
                data_hash=data_hash,
                netbox_id=netbox_id,
                last_seen=datetime.utcnow()
            )
            session.add(state)
    
    def create_sync_run(self, session: Session, source: str, sync_type: str) -> SyncRun:
        """Create a new sync run record."""
        sync_run = SyncRun(
            source=source,
            sync_type=sync_type,
            started_at=datetime.utcnow()
        )
        session.add(sync_run)
        session.flush()  # Get the ID
        return sync_run
    
    def complete_sync_run(self, session: Session, sync_run: SyncRun, 
                         created: int = 0, updated: int = 0, deleted: int = 0,
                         errors: List[str] = None):
        """Complete a sync run."""
        sync_run.completed_at = datetime.utcnow()
        sync_run.status = 'completed'
        sync_run.created_count = created
        sync_run.updated_count = updated
        sync_run.deleted_count = deleted
        sync_run.error_count = len(errors) if errors else 0
        sync_run.errors = json.dumps(errors) if errors else None
        
        if sync_run.started_at:
            duration = (sync_run.completed_at - sync_run.started_at).total_seconds()
            sync_run.duration_seconds = duration
    
    def fail_sync_run(self, session: Session, sync_run: SyncRun, error: str):
        """Mark sync run as failed."""
        sync_run.completed_at = datetime.utcnow()
        sync_run.status = 'failed'
        sync_run.errors = json.dumps([error])
        
        if sync_run.started_at:
            duration = (sync_run.completed_at - sync_run.started_at).total_seconds()
            sync_run.duration_seconds = duration
    
    def get_object_mapping(self, session: Session, source: str, object_type: str,
                          external_id: str) -> Optional[ObjectMapping]:
        """Get object mapping."""
        return session.query(ObjectMapping).filter(
            ObjectMapping.source == source,
            ObjectMapping.object_type == object_type,
            ObjectMapping.external_id == external_id
        ).first()
    
    def create_object_mapping(self, session: Session, source: str, object_type: str,
                            external_id: str, netbox_id: str):
        """Create object mapping."""
        mapping = ObjectMapping(
            source=source,
            object_type=object_type,
            external_id=external_id,
            netbox_id=netbox_id
        )
        session.add(mapping)
    
    def update_object_mapping(self, session: Session, source: str, object_type: str,
                            external_id: str, netbox_id: str):
        """Update or create object mapping."""
        mapping = self.get_object_mapping(session, source, object_type, external_id)
        
        if mapping:
            mapping.netbox_id = netbox_id
            mapping.updated_at = datetime.utcnow()
        else:
            self.create_object_mapping(session, source, object_type, external_id, netbox_id)
    
    def mark_stale_objects(self, session: Session, source: str, object_type: str,
                          current_external_ids: List[str]):
        """Mark objects as stale if they weren't seen in current sync."""
        # Get all existing mappings for this source/type
        existing_mappings = session.query(ObjectMapping).filter(
            ObjectMapping.source == source,
            ObjectMapping.object_type == object_type
        ).all()
        
        for mapping in existing_mappings:
            if mapping.external_id not in current_external_ids:
                # Check if already marked as stale
                existing_stale = session.query(StaleObject).filter(
                    StaleObject.source == source,
                    StaleObject.object_type == object_type,
                    StaleObject.external_id == mapping.external_id,
                    StaleObject.deleted_at.is_(None)
                ).first()
                
                if not existing_stale:
                    stale_obj = StaleObject(
                        source=source,
                        object_type=object_type,
                        external_id=mapping.external_id,
                        netbox_id=mapping.netbox_id,
                        marked_stale_at=datetime.utcnow()
                    )
                    session.add(stale_obj)
                    logger.info(f"Marked {source} {object_type} {mapping.external_id} as stale")
    
    def get_stale_objects(self, session: Session, grace_days: int = 7) -> List[StaleObject]:
        """Get objects that have been stale for more than grace_days."""
        cutoff_date = datetime.utcnow() - timedelta(days=grace_days)
        return session.query(StaleObject).filter(
            StaleObject.marked_stale_at < cutoff_date,
            StaleObject.deleted_at.is_(None)
        ).all()


def init_database(database_url: str):
    """Initialize database with tables."""
    manager = DatabaseManager(database_url)
    manager.init_database()
    return manager