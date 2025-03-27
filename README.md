# Blockchain RPC EdgeProbe

A lightweight application for monitoring JSON-RPC endpoint latency with comprehensive metrics collection and analysis.

## Overview

This tool allows you to track and analyze the performance of multiple RPC endpoints by:

- Running simple, frequent latency tests (block height checks)
- Performing comprehensive advanced tests with multiple methods
- Calculating and storing P50/P90 latency metrics
- Providing a simple API for accessing performance data
- Maintaining a status monitoring system

Perfect for blockchain infrastructure monitoring, web3 development, and ensuring reliable RPC connectivity.

## Features

- **Dual-Tier Testing System**:
  - Simple tests: Fast, frequent block height checks
  - Advanced tests: Comprehensive method testing at configurable intervals

- **Performance Metrics**:
  - P50 (median) latency
  - P90 latency
  - Success rates
  - Method-specific performance

- **Smart Data Management**:
  - Raw data retention for recent history
  - Aggregated metrics for long-term trending
  - Configurable retention periods

- **API Access**:
  - Query latency data
  - Filter by provider, method, and time range
  - Monitor application status

- **Flexible Configuration**:
  - Multiple RPC providers
  - Customizable test methods
  - Configurable test frequency
  - Independently adjustable retention settings

## Installation

### Prerequisites

- Python 3.7+
- pip (Python package manager)

### Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/j0sh-neu/blockchain-rpc-edgeprobe.git
   cd blockchain-rpc-edgeprobe
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Run the application:
   ```bash
   python edgeprobe.py
   ```

## Configuration

The application uses a YAML configuration file (`config.yaml`) for all settings. If the file doesn't exist, it will be created with default values on first run.

### Example Configuration

```yaml
rpc_providers:
  - name: 'Llama RPC'
    url: 'https://eth.llamarpc.com'
    methods:
      simple_test:
        method: 'eth_blockNumber'
        params: []
        ping_interval: 60  # seconds
      advanced_test:
        enabled: true
        ping_interval: 3600  # hourly
        methods:
          block_details:
            enabled: true
            method: 'eth_getBlockByNumber'
            params: ['latest', true]
            complexity: 'medium'
          account_balance:
            enabled: true
            method: 'eth_getBalance'
            params: ['0x742d35Cc6634C0532925a3b844Bc454e4438f44e', 'latest']
            complexity: 'medium'
          latest_logs:
            enabled: false
            method: 'eth_getLogs'
            params: [{'fromBlock': 'latest', 'toBlock': 'latest'}]
            complexity: 'high'

  - name: 'DRPC'
    url: 'https://eth.drpc.org'
    methods:
      simple_test:
        method: 'eth_blockNumber'
        params: []
        ping_interval: 60
      advanced_test:
        enabled: true
        ping_interval: 3600
        methods:
          block_details:
            enabled: true
            method: 'eth_getBlockByNumber'
            params: ['latest', true]
            complexity: 'medium'

global_settings:
  database_path: 'latency_tracker.db'
  api_host: '0.0.0.0'
  api_port: 8000
  simple_data_retention_days: 7
  advanced_data_retention_days: 14
  aggregation_retention_days: 90
```

### Configuration Sections

#### RPC Providers

Each RPC provider has the following configuration options:

- `name`: Display name for the provider
- `url`: RPC endpoint URL
- `methods`: Test method configurations
  - `simple_test`: Simple block height test configuration
    - `method`: RPC method name
    - `params`: Parameters to pass with the RPC call
    - `ping_interval`: How often to run the test (in seconds)
  - `advanced_test`: Advanced testing configuration
    - `enabled`: Whether advanced testing is enabled
    - `ping_interval`: How often to run advanced tests (in seconds)
    - `methods`: Individual advanced methods to test
      - `[method_name]`:
        - `enabled`: Whether this specific method is enabled
        - `method`: Actual RPC method name
        - `params`: Parameters for the RPC call
        - `complexity`: Complexity label (low/medium/high)

#### Global Settings

- `database_path`: Path to SQLite database file
- `api_host`: Host to bind the API server to
- `api_port`: Port for the API server
- `simple_data_retention_days`: Days to keep raw simple test data
- `advanced_data_retention_days`: Days to keep raw advanced test data
- `aggregation_retention_days`: Days to keep aggregated metrics

## API Usage

The application provides a RESTful API for accessing latency data.

### Base URL

By default, the API is available at:
```
http://localhost:8000
```

### Endpoints

#### Get Providers

```
GET /providers
```

Returns a list of configured RPC providers.

**Example Response:**
```json
[
  {
    "name": "Llama RPC",
    "url": "https://eth.llamarpc.com"
  },
  {
    "name": "DRPC",
    "url": "https://eth.drpc.org"
  }
]
```

#### Get Simple Latency Data

```
GET /simple-latency?days=7&provider=Llama%20RPC
```

Returns aggregated latency data for simple block height tests.

**Parameters:**
- `days`: Number of days to retrieve (default: 7, max: 90)
- `provider`: (Optional) Filter by provider name

**Example Response:**
```json
[
  {
    "provider_name": "Llama RPC",
    "endpoint": "https://eth.llamarpc.com",
    "test_type": "simple",
    "method": "eth_blockNumber",
    "date": "2025-03-26",
    "p50_latency": 45.2,
    "p90_latency": 67.5,
    "total_pings": 1440,
    "success_rate": 0.998
  }
]
```

#### Get Advanced Latency Data

```
GET /advanced-latency?days=7&provider=DRPC&method=block_details
```

Returns aggregated latency data for advanced method tests.

**Parameters:**
- `days`: Number of days to retrieve (default: 7, max: 90)
- `provider`: (Optional) Filter by provider name
- `method`: (Optional) Filter by method name

**Example Response:**
```json
[
  {
    "provider_name": "DRPC",
    "endpoint": "https://eth.drpc.org",
    "test_type": "advanced",
    "method": "block_details",
    "date": "2025-03-26",
    "p50_latency": 78.3,
    "p90_latency": 125.6,
    "total_pings": 24,
    "success_rate": 0.958
  }
]
```

#### Get Available Methods

```
GET /methods
```

Returns all configured test methods.

**Example Response:**
```json
{
  "Llama RPC": {
    "simple": "eth_blockNumber",
    "advanced": [
      {
        "name": "block_details",
        "method": "eth_getBlockByNumber",
        "complexity": "medium"
      },
      {
        "name": "account_balance",
        "method": "eth_getBalance",
        "complexity": "medium"
      }
    ]
  },
  "DRPC": {
    "simple": "eth_blockNumber",
    "advanced": [
      {
        "name": "block_details",
        "method": "eth_getBlockByNumber",
        "complexity": "medium"
      }
    ]
  }
}
```

### Status Monitoring

The application provides endpoints to check its operational status.

#### Get Detailed Status

```
GET /status
```

Returns comprehensive status information about the application.

**Example Response:**
```json
{
  "status": "OK",
  "uptime": "3 days, 12:45:30",
  "components": {
    "simple_monitor": {
      "status": "OK",
      "last_run": "0:00:45"
    },
    "advanced_monitor": {
      "status": "OK",
      "last_run": "0:30:12"
    },
    "threads": {
      "status": "OK",
      "details": {
        "simple_monitor": true,
        "advanced_monitor": true,
        "maintenance": true
      }
    }
  },
  "system": {
    "cpu_percent": 2.4,
    "memory_percent": 15.7,
    "disk_percent": 45.2
  },
  "timestamp": "2025-03-26T14:30:15.123456"
}
```

**Status Values:**
- `OK`: Everything is functioning normally
- `WARNING`: Potential issues detected
- `CRITICAL`: Service is impaired

#### Health Check

```
GET /health
```

Simple health check endpoint for monitoring tools. Returns HTTP 200 if healthy, HTTP 503 if critical issues detected.

**Example Response (Healthy):**
```json
{
  "status": "OK"
}
```

## Maintenance and Operation

### Running as a Service

To run the application as a background service, you can use systemd on Linux:

1. Create a service file:
   ```bash
   sudo nano /etc/systemd/system/latency-tracker.service
   ```

2. Add the following content:
   ```
   [Unit]
   Description=RPC Latency Tracker
   After=network.target

   [Service]
   User=yourusername
   WorkingDirectory=/path/to/rpc-latency-tracker
   ExecStart=/usr/bin/python3 /path/to/rpc-latency-tracker/latency_tracker.py
   Restart=on-failure
   RestartSec=5s

   [Install]
   WantedBy=multi-user.target
   ```

3. Enable and start the service:
   ```bash
   sudo systemctl enable latency-tracker.service
   sudo systemctl start latency-tracker.service
   ```

### Restarting the Application

#### If running as a service:
```bash
sudo systemctl restart latency-tracker.service
```

#### If running manually:
1. Stop the current process (Ctrl+C)
2. Start it again:
   ```bash
   python latency_tracker.py
   ```

### Viewing Logs

If running as a systemd service:
```bash
sudo journalctl -u latency-tracker.service -f
```

### Database Management

The application uses SQLite for data storage. The database file is specified in the configuration (default: `latency_tracker.db`).

To backup the database:
```bash
cp latency_tracker.db latency_tracker_backup.db
```

## Troubleshooting

### Application Not Starting

1. Check for error messages in the console or logs
2. Verify Python version (3.7+ required)
3. Ensure all dependencies are installed
4. Check if the port is already in use

### API Not Responding

1. Check if the application is running
2. Verify the configured host and port
3. Check your firewall settings
4. Check the status endpoint for component failures

### Inaccurate Latency Data

1. Verify your RPC endpoints are accessible
2. Check for network issues
3. Look at the success rate in the API responses
4. Check for timeout configuration

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.
