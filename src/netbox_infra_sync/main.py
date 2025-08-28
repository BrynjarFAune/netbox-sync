import logging
import sys
from typing import Optional

import click
from dotenv import load_dotenv

from .config import AppConfig
from .storage.database import init_database
from .workers.fortigate import FortiGateWorker
from .workers.intune import IntuneWorker
from .workers.eset import ESETWorker
from .workers.licenses import LicenseWorker
from .reconciler.sync import Reconciler

load_dotenv()

# Initialize config first to get log level
config = AppConfig()

# Configure logging with the proper level
log_level = getattr(logging, config.log_level.upper(), logging.INFO)
logging.basicConfig(
    level=log_level,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@click.group()
@click.pass_context
def cli(ctx):
    """NetBox Infrastructure Sync Tool."""
    ctx.ensure_object(dict)
    try:
        ctx.obj['config'] = config
    except Exception as e:
        logger.error(f"Configuration error: {e}")
        sys.exit(1)


@cli.command()
@click.argument('source', type=click.Choice(['fortigate', 'intune', 'eset', 'licenses', 'all']))
@click.pass_context
def sync(ctx, source: str):
    """Sync infrastructure data from specified source(s)."""
    config = ctx.obj['config']
    logger.info(f"Starting sync for source: {source}")
    
    try:
        if source == 'fortigate' or source == 'all':
            worker = FortiGateWorker(config)
            data = worker.fetch_data()
            reconciler = Reconciler(config)
            reconciler.reconcile_fortigate_data(data)
            
        if source == 'intune' or source == 'all':
            worker = IntuneWorker(config)
            data = worker.fetch_data()
            reconciler = Reconciler(config)
            reconciler.reconcile_intune_data(data)
            
        if source == 'eset' or source == 'all':
            worker = ESETWorker(config)
            data = worker.fetch_data()
            reconciler = Reconciler(config)
            reconciler.reconcile_eset_data(data)
            
        if source == 'licenses' or source == 'all':
            worker = LicenseWorker(config)
            data = worker.fetch_data()
            reconciler = Reconciler(config)
            reconciler.reconcile_license_data(data)
            
        logger.info(f"Sync completed for source: {source}")
        
    except Exception as e:
        logger.error(f"Sync failed for {source}: {e}")
        sys.exit(1)


@cli.command()
@click.option('--port', default=8080, help='Port to serve on')
@click.pass_context
def serve(ctx, port: int):
    """Start HTTP server for health checks and metrics."""
    from .server import start_server
    config = ctx.obj['config']
    logger.info(f"Starting server on port {port}")
    start_server(config, port)


@cli.command()
@click.pass_context
def migrate(ctx):
    """Initialize or migrate the state database."""
    config = ctx.obj['config']
    logger.info("Initializing database...")
    try:
        init_database(config.database_url)
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        sys.exit(1)


if __name__ == '__main__':
    cli()