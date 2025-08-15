# NetBox Infrastructure Sync

A containerized tool for continuously synchronizing infrastructure data from FortiGate, Microsoft Intune, and ESET PROTECT into NetBox.

## Features

- **Multi-source sync**: FortiGate, Intune (Graph API), and ESET PROTECT
- **Idempotent operations**: Re-running causes no unintended changes
- **State tracking**: SQLite database for tracking sync state and changes
- **Rate limiting**: Configurable API rate limits and retry logic
- **Monitoring**: Prometheus metrics and health endpoints
- **Containerized**: Docker image with minimal dependencies

## Quick Start

1. **Copy environment variables**:
   ```bash
   cp .env.example .env
   ```

2. **Configure your environment** by editing `.env`:
   - Set your NetBox URL and API token
   - Configure FortiGate host and API key
   - Set Microsoft Graph credentials for Intune access
   - Optionally configure ESET PROTECT details

3. **Initialize the database**:
   ```bash
   # Using Docker
   docker-compose run --rm netbox-sync migrate
   
   # Or locally
   netbox-sync migrate
   ```

4. **Run a sync**:
   ```bash
   # Sync all sources
   docker-compose run --rm netbox-sync sync all
   
   # Sync individual sources
   docker-compose run --rm netbox-sync sync fortigate
   docker-compose run --rm netbox-sync sync intune
   docker-compose run --rm netbox-sync sync eset
   ```

## Usage

### Command Line Interface

```bash
# Sync operations
netbox-sync sync all              # Sync from all configured sources
netbox-sync sync fortigate        # Sync only FortiGate data
netbox-sync sync intune           # Sync only Intune data
netbox-sync sync eset             # Sync only ESET data

# HTTP server (for health checks and metrics)
netbox-sync serve                 # Start HTTP server on port 8080

# Database operations
netbox-sync migrate               # Initialize/migrate database
```

### Docker Compose

```bash
# One-time sync
docker-compose run --rm netbox-sync sync all

# Run as server with metrics endpoint
docker-compose --profile server up -d netbox-sync-server

# View logs
docker-compose logs -f netbox-sync
```

## Data Mapping

### FortiGate → NetBox
- **System info** → Device (firewall role)
- **Interfaces** → Interfaces with status and IPs
- **VLANs** → VLAN objects
- **DHCP leases** → IP addresses with DHCP tags
- **ARP table** → IP addresses with ARP tags
- **Firewall addresses** → Network prefixes

### Intune → NetBox
- **Managed devices** → Devices with compliance status
- **Device owners** → Custom field assignments
- **OS information** → Device details
- **Compliance state** → Tags and custom fields

### ESET → NetBox
- **Computers** → Devices with AV status
- **Network interfaces** → Interface details with MACs
- **Antivirus status** → Custom fields and tags
- **Threat information** → Security-related custom fields

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `NETBOX_URL` | NetBox instance URL | Required |
| `NETBOX_TOKEN` | NetBox API token | Required |
| `FGT_HOST` | FortiGate host URL | Required |
| `FGT_TOKEN` | FortiGate API token | Required |
| `GRAPH_TENANT_ID` | Microsoft tenant ID | Required |
| `GRAPH_CLIENT_ID` | Microsoft app client ID | Required |
| `GRAPH_CLIENT_SECRET` | Microsoft app secret | Required |
| `ESET_BASE_URL` | ESET PROTECT server URL | Optional |
| `ESET_TOKEN` | ESET PROTECT API token | Optional |
| `SYNC_INTERVAL_CRON` | Cron expression for sync schedule | `0 */6 * * *` |
| `DELETE_GRACE_DAYS` | Days before deleting stale objects | `7` |
| `LOG_LEVEL` | Logging level | `INFO` |
| `DATABASE_URL` | Database connection string | `sqlite:///netbox_sync.db` |
| `API_RATE_LIMIT` | API requests per second | `10` |
| `API_RETRY_ATTEMPTS` | Number of retry attempts | `3` |
| `API_BACKOFF_FACTOR` | Exponential backoff factor | `1.0` |

## Monitoring

### Health Endpoints

- `GET /healthz` - Basic health check
- `GET /metrics` - Prometheus metrics
- `GET /status` - Detailed sync run status

### Prometheus Metrics

- `netbox_sync_runs_total` - Total sync runs by source and status
- `netbox_sync_duration_seconds` - Sync duration histogram
- `netbox_objects_synced_total` - Objects synced by operation type

## Architecture

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│  FortiGate  │    │   Intune    │    │    ESET     │
│   Worker    │    │   Worker    │    │   Worker    │
└─────┬───────┘    └─────┬───────┘    └─────┬───────┘
      │                  │                  │
      └──────────────────┼──────────────────┘
                         │
                  ┌─────────────┐
                  │ Normalizer  │
                  └─────┬───────┘
                        │
                  ┌─────────────┐
                  │ Reconciler  │
                  └─────┬───────┘
                        │
        ┌───────────────┼───────────────┐
        │               │               │
  ┌─────────┐    ┌─────────────┐  ┌─────────┐
  │ NetBox  │    │ State Store │  │ Metrics │
  │   API   │    │  (SQLite)   │  │   API   │
  └─────────┘    └─────────────┘  └─────────┘
```

## Development

### Local Development

1. **Create virtual environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # or `venv\Scripts\activate` on Windows
   ```

2. **Install dependencies**:
   ```bash
   pip install -e .
   pip install -e .[dev]
   ```

3. **Run tests**:
   ```bash
   pytest
   ```

4. **Code formatting**:
   ```bash
   black src/
   isort src/
   flake8 src/
   mypy src/
   ```

### Building Docker Image

```bash
docker build -t netbox-infra-sync:latest .
```

## Security Considerations

- Store API tokens and secrets securely (use Docker secrets or K8s secrets)
- Run container as non-root user (implemented in Dockerfile)
- Use read-only filesystem mounts where possible
- Regularly rotate API tokens and credentials
- Monitor logs for failed authentication attempts

## Troubleshooting

### Common Issues

1. **Connection refused to NetBox**
   - Verify `NETBOX_URL` is correct and accessible
   - Check firewall/network connectivity
   - Ensure NetBox API is enabled

2. **Authentication errors**
   - Verify API tokens are correct and not expired
   - Check token permissions in respective systems
   - For Microsoft Graph, ensure app has required permissions

3. **Sync errors**
   - Check logs for specific error messages
   - Verify data format expectations
   - Check NetBox custom field configuration

### Logs

```bash
# Docker logs
docker-compose logs -f netbox-sync

# Local logs (configure LOG_LEVEL)
export LOG_LEVEL=DEBUG
netbox-sync sync all
```

## License

MIT License - see LICENSE file for details.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Run the test suite
6. Submit a pull request