import logging
from http.server import HTTPServer, BaseHTTPRequestHandler
import json
from urllib.parse import urlparse
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

from .config import AppConfig
from .storage.database import DatabaseManager

logger = logging.getLogger(__name__)

# Prometheus metrics
sync_runs_total = Counter('netbox_sync_runs_total', 'Total number of sync runs', ['source', 'sync_type', 'status'])
sync_duration_seconds = Histogram('netbox_sync_duration_seconds', 'Sync run duration', ['source', 'sync_type'])
objects_synced_total = Counter('netbox_objects_synced_total', 'Total objects synced', ['source', 'sync_type', 'operation'])


class HealthHandler(BaseHTTPRequestHandler):
    """HTTP handler for health checks and metrics."""
    
    def __init__(self, *args, config: AppConfig = None, **kwargs):
        self.config = config
        self.db_manager = DatabaseManager(config.database_url) if config else None
        super().__init__(*args, **kwargs)
    
    def do_GET(self):
        """Handle GET requests."""
        parsed_path = urlparse(self.path)
        
        if parsed_path.path == '/healthz':
            self.handle_health()
        elif parsed_path.path == '/metrics':
            self.handle_metrics()
        elif parsed_path.path == '/status':
            self.handle_status()
        else:
            self.send_error(404)
    
    def handle_health(self):
        """Handle health check endpoint."""
        try:
            # Basic health check
            if self.db_manager:
                with self.db_manager.get_session() as session:
                    # Simple database connectivity test
                    session.execute('SELECT 1')
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            
            response = {
                'status': 'healthy',
                'timestamp': '2025-08-14T12:00:00Z'
            }
            
            self.wfile.write(json.dumps(response).encode())
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            self.send_response(503)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            
            response = {
                'status': 'unhealthy',
                'error': str(e),
                'timestamp': '2025-08-14T12:00:00Z'
            }
            
            self.wfile.write(json.dumps(response).encode())
    
    def handle_metrics(self):
        """Handle Prometheus metrics endpoint."""
        try:
            self.send_response(200)
            self.send_header('Content-Type', CONTENT_TYPE_LATEST)
            self.end_headers()
            
            metrics = generate_latest()
            self.wfile.write(metrics)
            
        except Exception as e:
            logger.error(f"Metrics generation failed: {e}")
            self.send_error(500)
    
    def handle_status(self):
        """Handle status endpoint with sync run information."""
        try:
            status_data = {
                'application': 'netbox-infra-sync',
                'version': '0.1.0',
                'sync_runs': []
            }
            
            if self.db_manager:
                with self.db_manager.get_session() as session:
                    # Get recent sync runs
                    from .storage.database import SyncRun
                    recent_runs = session.query(SyncRun).order_by(
                        SyncRun.started_at.desc()
                    ).limit(10).all()
                    
                    for run in recent_runs:
                        status_data['sync_runs'].append({
                            'id': run.id,
                            'source': run.source,
                            'sync_type': run.sync_type,
                            'status': run.status,
                            'started_at': run.started_at.isoformat() if run.started_at else None,
                            'completed_at': run.completed_at.isoformat() if run.completed_at else None,
                            'created_count': run.created_count,
                            'updated_count': run.updated_count,
                            'deleted_count': run.deleted_count,
                            'error_count': run.error_count,
                            'duration_seconds': run.duration_seconds
                        })
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            
            self.wfile.write(json.dumps(status_data, indent=2).encode())
            
        except Exception as e:
            logger.error(f"Status endpoint failed: {e}")
            self.send_error(500)
    
    def log_message(self, format, *args):
        """Override to use proper logging."""
        logger.info(f"{self.address_string()} - {format % args}")


def start_server(config: AppConfig, port: int = 8080):
    """Start the HTTP server."""
    def handler(*args, **kwargs):
        return HealthHandler(*args, config=config, **kwargs)
    
    server = HTTPServer(('0.0.0.0', port), handler)
    logger.info(f"Starting HTTP server on port {port}")
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down HTTP server")
        server.shutdown()