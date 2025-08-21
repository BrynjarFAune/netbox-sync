# NetBox Infrastructure Sync

A containerized tool for continuously synchronizing NetBox with FortiGate, Microsoft Intune, and ESET infrastructure data.

## Overview

NetBox Infrastructure Sync automatically keeps your NetBox instance up-to-date with real-time data from multiple infrastructure sources:

- **FortiGate**: VLANs, prefixes, interfaces, routes, ARP/DHCP leases
- **Microsoft Intune**: Device inventory, owners, OS information, compliance status
- **ESET**: Network interface details, antivirus status, last-seen timestamps

### Key Features

- ≥95% infrastructure reflected in NetBox within 24 hours (configurable)
- Full sync completes in <5 minutes for current estate
- Idempotent operations - re-running causes no unintended changes
- Complete audit trail of creates/updates/deletes
- Prometheus metrics and health checks
- Containerized for easy deployment

## Prerequisites

- Python 3.9+ (for development)
- Docker and Docker Compose (for deployment)
- Access to:
  - NetBox instance with API token
  - FortiGate device with API access
  - Microsoft Graph API (for Intune)
  - ESET Management Console API (optional)

## Quick Start

### Using Docker Compose (Recommended)

1. **Clone the repository:**
   ```bash
   git clone <your-repo-url>
   cd netbox-sync
   ```

2. **Create environment file:**
   ```bash
   cp .env.example .env
   ```

3. **Configure environment variables in `.env`:**
   ```env
   # NetBox configuration
   NETBOX_URL=http://your-netbox-instance:8000
   NETBOX_TOKEN=your_netbox_api_token

   # FortiGate configuration
   FGT_HOST=https://your-fortigate:443
   FGT_TOKEN=your_fortigate_api_key

   # Microsoft Graph/Intune configuration
   GRAPH_TENANT_ID=your_tenant_id
   GRAPH_CLIENT_ID=your_client_id
   GRAPH_CLIENT_SECRET=your_client_secret

   # ESET configuration (optional)
   ESET_BASE_URL=https://your-eset-console
   ESET_TOKEN=your_eset_token

   # Sync configuration
   SYNC_INTERVAL_CRON=0 */6 * * *  # Every 6 hours
   DELETE_GRACE_DAYS=7
   LOG_LEVEL=INFO
   ```

4. **Run one-time sync:**
   ```bash
   docker-compose up netbox-sync
   ```

5. **Run as a server with scheduled syncs:**
   ```bash
   docker-compose --profile server up netbox-sync-server
   ```

### Using Python (Development)

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   pip install -e .
   ```

2. **Initialize database:**
   ```bash
   netbox-sync migrate
   ```

3. **Run sync:**
   ```bash
   # Sync all sources
   netbox-sync sync all

   # Sync specific source
   netbox-sync sync fortigate
   netbox-sync sync intune
   netbox-sync sync eset
   ```

4. **Start HTTP server:**
   ```bash
   netbox-sync serve --port 8080
   ```

## Configuration

### Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `NETBOX_URL` | NetBox instance URL | - | Yes |
| `NETBOX_TOKEN` | NetBox API token | - | Yes |
| `FGT_HOST` | FortiGate host URL | - | Yes |
| `FGT_TOKEN` | FortiGate API key | - | Yes |
| `GRAPH_TENANT_ID` | Azure tenant ID | - | Yes |
| `GRAPH_CLIENT_ID` | Azure app client ID | - | Yes |
| `GRAPH_CLIENT_SECRET` | Azure app client secret | - | Yes |
| `ESET_BASE_URL` | ESET console URL | - | No |
| `ESET_TOKEN` | ESET API token | - | No |
| `SYNC_INTERVAL_CRON` | Cron schedule for syncs | `0 */6 * * *` | No |
| `DELETE_GRACE_DAYS` | Days before hard delete | `7` | No |
| `LOG_LEVEL` | Logging level | `INFO` | No |
| `DATABASE_URL` | Database connection URL | `sqlite:///app/data/netbox_sync.db` | No |
| `API_RATE_LIMIT` | API requests per second | `10` | No |
| `API_RETRY_ATTEMPTS` | Max retry attempts | `3` | No |
| `API_BACKOFF_FACTOR` | Retry backoff factor | `1.0` | No |

### API Access Setup

#### NetBox
1. Navigate to Admin → API Tokens in your NetBox instance
2. Create a new token with appropriate permissions
3. Use the token as `NETBOX_TOKEN`

#### FortiGate
1. Create an API user: `System → Administrators → Create New → REST API Admin`
2. Generate API key and set appropriate access permissions
3. Use the API key as `FGT_TOKEN`

#### Microsoft Graph (Intune)
1. Register an application in Azure AD
2. Grant required permissions:
   - `Device.Read.All`
   - `DeviceManagementManagedDevices.Read.All`
3. Create a client secret
4. Use tenant ID, client ID, and secret in configuration

#### ESET (Optional)
1. Enable API access in ESET Management Console
2. Generate API token with read permissions
3. Configure `ESET_BASE_URL` and `ESET_TOKEN`

## Architecture

The application consists of several key components:

- **Workers**: Fetch data from external sources (FortiGate, Intune, ESET)
- **Normalizer**: Converts source-specific data to canonical schema
- **Reconciler**: Compares canonical data with NetBox and applies changes
- **State Store**: Tracks last-seen hashes and run logs (SQLite/PostgreSQL)
- **API Clients**: Rate-limited, retried connections to external APIs
- **Scheduler**: Cron-like scheduling for automated syncs

## Data Mapping

### FortiGate → NetBox
- VLANs → `ipam.VLAN`
- Prefixes → `ipam.Prefix`
- Interfaces → `dcim.Interface`
- Device info → `dcim.Device`
- Routes → `ipam.Route` (optional)

### Intune → NetBox
- Devices → `dcim.Device` or `virtualization.VirtualMachine`
- Custom fields: `owner`, `compliance_status`, `serial_number`, `device_id`

### ESET → NetBox
- Network details → Interface MAC addresses
- Custom fields: `av_status`, `eset_last_seen`
- Tags for antivirus status

## Monitoring and Health Checks

### Health Check Endpoints
- `GET /healthz` - Basic health check
- `GET /metrics` - Prometheus metrics

### Metrics Available
- Sync operation counts and durations
- API request rates and errors
- Database connection status
- Last successful sync timestamps

### Docker Health Checks
The container includes built-in health checks that verify the HTTP server is responding.

## Development

### Running Tests
```bash
# Install development dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run with coverage
pytest --cov=src/netbox_infra_sync

# Code formatting
black src/
isort src/

# Type checking
mypy src/
```

### Project Structure
```
src/netbox_infra_sync/
├── api/                 # API client implementations
├── models/              # Data models and normalization
├── reconciler/          # Sync logic and reconciliation
├── storage/             # Database and state management
├── workers/             # Source-specific data fetchers
├── config.py           # Configuration management
├── main.py             # CLI entrypoint
└── server.py           # HTTP server for health/metrics
```

## Deployment

### Docker Compose
The included `docker-compose.yml` provides two service configurations:
- `netbox-sync`: One-time sync execution
- `netbox-sync-server`: Continuous server with scheduled syncs

### Kubernetes
For Kubernetes deployment, use the Docker image with:
- ConfigMaps for non-secret configuration
- Secrets for API tokens and credentials
- CronJobs for scheduled syncs
- Deployments for the HTTP server

### Production Considerations
- Use PostgreSQL instead of SQLite for production deployments
- Configure appropriate resource limits
- Set up log aggregation and monitoring
- Use secrets management for sensitive configuration
- Configure network policies for security

## Troubleshooting

### Common Issues

**Sync fails with authentication error:**
- Verify API tokens are correct and not expired
- Check that API users have sufficient permissions

**High memory usage:**
- Reduce `API_RATE_LIMIT` to process data in smaller batches
- Consider using PostgreSQL instead of SQLite for large datasets

**Slow sync performance:**
- Increase `API_RATE_LIMIT` if external APIs can handle it
- Check network latency to external services
- Review database query performance

### Logging
Set `LOG_LEVEL=DEBUG` to enable detailed logging for troubleshooting.

### Debug Commands
```bash
# Check configuration
netbox-sync --help

# Test database connection
netbox-sync migrate

# Sync single source for testing
netbox-sync sync fortigate
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes following the existing code style
4. Add tests for new functionality
5. Run the test suite and ensure all tests pass
6. Submit a pull request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Support

For issues and questions:
1. Check the troubleshooting section above
2. Review existing GitHub issues
3. Create a new issue with detailed information about your problem

## Version History

- **v0.1.0**: Initial release with FortiGate, Intune, and ESET integration