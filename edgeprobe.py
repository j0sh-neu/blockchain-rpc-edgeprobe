import os
import yaml
import sqlite3
import time
import statistics
from datetime import datetime, timedelta
import requests
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from typing import List, Dict, Optional, Any
import uvicorn
import threading
import psutil
import signal
import sys

def handle_sigterm(*args):
    """Handle SIGTERM gracefully to allow proper cleanup."""
    print("Received SIGTERM, shutting down...")
    # You could add additional cleanup here if needed
    sys.exit(0)

# Register the signal handler
signal.signal(signal.SIGTERM, handle_sigterm)

# --- Models ---
class SimpleLatency(BaseModel):
    provider_name: str
    endpoint: str
    latency_ms: float
    timestamp: float

class AdvancedLatency(BaseModel):
    provider_name: str
    endpoint: str
    method: str
    complexity: str
    latency_ms: float
    success: bool
    timestamp: float

class DailyAggregation(BaseModel):
    provider_name: str
    endpoint: str
    test_type: str  # 'simple' or 'advanced'
    method: Optional[str] = None
    date: str
    p50_latency: float
    p90_latency: float
    total_pings: int
    success_rate: float

# --- Configuration ---
class ConfigManager:
    DEFAULT_CONFIG_PATH = 'config.yaml'
    
    @classmethod
    def load_config(cls, config_path: str = None) -> Dict:
        """Load configuration from YAML file with secure defaults."""
        path = config_path or cls.DEFAULT_CONFIG_PATH
        
        default_config = {
            'rpc_providers': [
                {
                    'name': 'Llama RPC',
                    'url': 'https://eth.llamarpc.com',
                    'methods': {
                        'simple_test': {
                            'method': 'eth_blockNumber',
                            'params': [],
                            'ping_interval': 60
                        },
                        'advanced_test': {
                            'enabled': True,
                            'ping_interval': 3600,  # hourly
                            'methods': {
                                'block_details': {
                                    'enabled': True,
                                    'method': 'eth_getBlockByNumber',
                                    'params': ['latest', True],
                                    'complexity': 'medium'
                                },
                                'account_balance': {
                                    'enabled': True,
                                    'method': 'eth_getBalance',
                                    'params': ['0x742d35Cc6634C0532925a3b844Bc454e4438f44e', 'latest'],
                                    'complexity': 'medium'
                                },
                                'latest_logs': {
                                    'enabled': False,
                                    'method': 'eth_getLogs',
                                    'params': [{'fromBlock': 'latest', 'toBlock': 'latest'}],
                                    'complexity': 'high'
                                }
                            }
                        }
                    }
                },
                {
                    'name': 'DRPC',
                    'url': 'https://eth.drpc.org',
                    'methods': {
                        'simple_test': {
                            'method': 'eth_blockNumber',
                            'params': [],
                            'ping_interval': 60
                        },
                        'advanced_test': {
                            'enabled': True,
                            'ping_interval': 3600,  # hourly
                            'methods': {
                                'block_details': {
                                    'enabled': True,
                                    'method': 'eth_getBlockByNumber',
                                    'params': ['latest', True],
                                    'complexity': 'medium'
                                },
                                'account_balance': {
                                    'enabled': True,
                                    'method': 'eth_getBalance',
                                    'params': ['0x742d35Cc6634C0532925a3b844Bc454e4438f44e', 'latest'],
                                    'complexity': 'medium'
                                }
                            }
                        }
                    }
                }
            ],
            'global_settings': {
                'database_path': os.environ.get('DATABASE_PATH', 'latency_tracker.db'),
                'api_host': '0.0.0.0',
                'api_port': 8000,
                'simple_data_retention_days': 7,
                'advanced_data_retention_days': 14,
                'aggregation_retention_days': 90
            }
        }
        
        # Create default config if not exists
        if not os.path.exists(path):
            with open(path, 'w') as f:
                yaml.safe_dump(default_config, f)
            return default_config
        
        # Load existing config
        try:
            with open(path, 'r') as f:
                user_config = yaml.safe_load(f)
            
            # Simple merge strategy
            return user_config
        except Exception as e:
            print(f"Error reading config: {e}")
            return default_config

# --- Service Status ---
class ServiceStatus:
    def __init__(self):
        self.startup_time = time.time()
        self.last_simple_ping_time = None
        self.last_advanced_ping_time = None
        self.last_maintenance_time = None
        self.thread_status = {
            'simple_monitor': True,
            'advanced_monitor': True,
            'maintenance': True
        }
    
    def update_simple_ping(self):
        """Update timestamp of last simple ping."""
        self.last_simple_ping_time = time.time()
    
    def update_advanced_ping(self):
        """Update timestamp of last advanced ping."""
        self.last_advanced_ping_time = time.time()
    
    def update_maintenance(self):
        """Update timestamp of last maintenance run."""
        self.last_maintenance_time = time.time()
    
    def set_thread_status(self, thread_name, status):
        """Update status of a monitoring thread."""
        if thread_name in self.thread_status:
            self.thread_status[thread_name] = status
    
    def get_status(self):
        """
        Get comprehensive service status.
        Returns OK if all critical components are functioning.
        """
        now = time.time()
        uptime_seconds = now - self.startup_time
        
        # Convert to human-readable format
        uptime_str = str(timedelta(seconds=int(uptime_seconds)))
        
        # Check if simple monitoring is working
        simple_status = "OK"
        simple_last_run = "Never"
        
        if self.last_simple_ping_time:
            simple_age = now - self.last_simple_ping_time
            simple_last_run = str(timedelta(seconds=int(simple_age)))
            
            # If no ping in last 5 minutes, mark as problem
            if simple_age > 300:  # 5 minutes
                simple_status = "WARNING"
            
            # If no ping in last 15 minutes, mark as critical
            if simple_age > 900:  # 15 minutes
                simple_status = "CRITICAL"
        else:
            simple_status = "UNKNOWN"
        
        # Similarly check advanced monitoring
        advanced_status = "OK"
        advanced_last_run = "Never"
        
        if self.last_advanced_ping_time:
            advanced_age = now - self.last_advanced_ping_time
            advanced_last_run = str(timedelta(seconds=int(advanced_age)))
            
            # If no ping in last 2 hours, mark as problem
            if advanced_age > 7200:  # 2 hours
                advanced_status = "WARNING"
            
            # If no ping in last 4 hours, mark as critical
            if advanced_age > 14400:  # 4 hours
                advanced_status = "CRITICAL"
        else:
            advanced_status = "UNKNOWN"
            
        # Check thread status
        thread_health = all(self.thread_status.values())
        
        # Get system stats
        system_stats = {
            'cpu_percent': psutil.cpu_percent(),
            'memory_percent': psutil.virtual_memory().percent,
            'disk_percent': psutil.disk_usage('/').percent
        }
        
        # Determine overall status
        overall_status = "OK"
        
        if simple_status == "WARNING" or advanced_status == "WARNING":
            overall_status = "WARNING"
            
        if simple_status == "CRITICAL" or advanced_status == "CRITICAL":
            overall_status = "CRITICAL"
            
        if not thread_health:
            overall_status = "CRITICAL"
            
        # Create status object
        status = {
            'status': overall_status,
            'uptime': uptime_str,
            'components': {
                'simple_monitor': {
                    'status': simple_status,
                    'last_run': simple_last_run
                },
                'advanced_monitor': {
                    'status': advanced_status,
                    'last_run': advanced_last_run
                },
                'threads': {
                    'status': "OK" if thread_health else "CRITICAL",
                    'details': self.thread_status
                }
            },
            'system': system_stats,
            'timestamp': datetime.now().isoformat()
        }
        
        return status

# --- Database Management ---
class LatencyTracker:
    def __init__(self, db_path='latency_tracker.db'):
        self.db_path = db_path
        self._create_tables()

    def _create_tables(self):
        """Create database tables for both test types."""
        with sqlite3.connect(self.db_path) as conn:
            # Simple latency test table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS simple_latency (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    provider_name TEXT,
                    endpoint TEXT,
                    latency_ms REAL,
                    success INTEGER,
                    timestamp REAL
                )
            ''')
            
            # Advanced latency test table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS advanced_latency (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    provider_name TEXT,
                    endpoint TEXT,
                    method TEXT,
                    complexity TEXT,
                    latency_ms REAL,
                    success INTEGER,
                    timestamp REAL
                )
            ''')
            
            # Daily aggregations table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS daily_latency_aggregation (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    provider_name TEXT,
                    endpoint TEXT,
                    test_type TEXT,
                    method TEXT,
                    date TEXT,
                    p50_latency REAL,
                    p90_latency REAL,
                    total_pings INTEGER,
                    success_rate REAL
                )
            ''')
            
            # Create unique index for aggregation
            conn.execute('''
                CREATE UNIQUE INDEX IF NOT EXISTS idx_daily_aggregation 
                ON daily_latency_aggregation 
                (provider_name, endpoint, test_type, method, date)
            ''')

    def record_simple_ping(self, provider_name: str, endpoint: str, 
                          latency_ms: float, success: bool = True):
        """Record a simple blockHeight ping."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                '''INSERT INTO simple_latency 
                (provider_name, endpoint, latency_ms, success, timestamp) 
                VALUES (?, ?, ?, ?, ?)''', 
                (provider_name, endpoint, latency_ms, 1 if success else 0, time.time())
            )

    def record_advanced_ping(self, provider_name: str, endpoint: str, 
                            method: str, complexity: str,
                            latency_ms: float, success: bool = True):
        """Record an advanced method ping."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                '''INSERT INTO advanced_latency 
                (provider_name, endpoint, method, complexity, latency_ms, success, timestamp) 
                VALUES (?, ?, ?, ?, ?, ?, ?)''', 
                (provider_name, endpoint, method, complexity, 
                 latency_ms, 1 if success else 0, time.time())
            )

    def aggregate_daily_latency(self):
        """Aggregate daily latency for both test types."""
        today = datetime.now().strftime('%Y-%m-%d')
        
        with sqlite3.connect(self.db_path) as conn:
            # Aggregate simple tests
            self._aggregate_simple_tests(conn, today)
            
            # Aggregate advanced tests
            self._aggregate_advanced_tests(conn, today)
            
    def _aggregate_simple_tests(self, conn, date):
        """Aggregate simple test metrics."""
        # Get distinct providers
        providers = conn.execute(
            '''SELECT DISTINCT provider_name, endpoint FROM simple_latency 
            WHERE DATE(timestamp, 'unixepoch') = DATE(?)''', 
            (date,)
        ).fetchall()
        
        for provider_name, endpoint in providers:
            # Get latencies and success rate
            data = conn.execute(
                '''SELECT latency_ms, success FROM simple_latency 
                WHERE provider_name = ? AND endpoint = ? 
                AND DATE(timestamp, 'unixepoch') = DATE(?)''', 
                (provider_name, endpoint, date)
            ).fetchall()
            
            if not data:
                continue
                
            # Only use successful pings for latency calculations
            latencies = [row[0] for row in data if row[1] == 1 and row[0] > 0]
            total_requests = len(data)
            success_rate = len(latencies) / total_requests if total_requests else 0
            
            # Only calculate metrics if we have successful latency data
            if latencies:
                p50 = statistics.median(latencies)
                p90 = self._calculate_percentile(latencies, 90)
                
                # Insert aggregation
                conn.execute(
                    '''INSERT OR REPLACE INTO daily_latency_aggregation 
                    (provider_name, endpoint, test_type, method, date, 
                    p50_latency, p90_latency, total_pings, success_rate) 
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''', 
                    (provider_name, endpoint, 'simple', 'eth_blockNumber', 
                     date, p50, p90, total_requests, success_rate)
                )
            else:
                # Record the failure rate but with null latency values
                conn.execute(
                    '''INSERT OR REPLACE INTO daily_latency_aggregation 
                    (provider_name, endpoint, test_type, method, date, 
                    p50_latency, p90_latency, total_pings, success_rate) 
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''', 
                    (provider_name, endpoint, 'simple', 'eth_blockNumber', 
                     date, None, None, total_requests, success_rate)
                )
    
    def _aggregate_advanced_tests(self, conn, date):
        """Aggregate advanced test metrics by method."""
        # Get distinct providers and methods
        provider_methods = conn.execute(
            '''SELECT DISTINCT provider_name, endpoint, method FROM advanced_latency 
            WHERE DATE(timestamp, 'unixepoch') = DATE(?)''', 
            (date,)
        ).fetchall()
        
        for provider_name, endpoint, method in provider_methods:
            # Get latencies and success rate for this method
            data = conn.execute(
                '''SELECT latency_ms, success FROM advanced_latency 
                WHERE provider_name = ? AND endpoint = ? AND method = ?
                AND DATE(timestamp, 'unixepoch') = DATE(?)''', 
                (provider_name, endpoint, method, date)
            ).fetchall()
            
            if not data:
                continue
                
            # Only use successful pings with valid latency values for calculations
            latencies = [row[0] for row in data if row[1] == 1 and row[0] > 0]
            total_requests = len(data)
            success_rate = len(latencies) / total_requests if total_requests else 0
            
            # Only calculate metrics if we have successful latency data
            if latencies:
                p50 = statistics.median(latencies)
                p90 = self._calculate_percentile(latencies, 90)
                
                # Insert aggregation
                conn.execute(
                    '''INSERT OR REPLACE INTO daily_latency_aggregation 
                    (provider_name, endpoint, test_type, method, date, 
                    p50_latency, p90_latency, total_pings, success_rate) 
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''', 
                    (provider_name, endpoint, 'advanced', method, 
                     date, p50, p90, total_requests, success_rate)
                )
            else:
                # Record the failure rate but with null latency values
                conn.execute(
                    '''INSERT OR REPLACE INTO daily_latency_aggregation 
                    (provider_name, endpoint, test_type, method, date, 
                    p50_latency, p90_latency, total_pings, success_rate) 
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''', 
                    (provider_name, endpoint, 'advanced', method, 
                     date, None, None, total_requests, success_rate)
                )
    
    def _calculate_percentile(self, data, percentile):
        """Calculate specific percentile."""
        if not data:
            return 0
        size = len(data)
        sorted_data = sorted(data)
        index = int(percentile/100 * size)
        return sorted_data[max(0, min(size-1, index))]

    def prune_data(self, simple_days: int = 7, advanced_days: int = 14, 
                  aggregation_days: int = 90):
        """Prune data based on retention settings."""
        with sqlite3.connect(self.db_path) as conn:
            # Prune simple data
            simple_cutoff = time.time() - (simple_days * 24 * 60 * 60)
            conn.execute(
                'DELETE FROM simple_latency WHERE timestamp < ?', 
                (simple_cutoff,)
            )
            
            # Prune advanced data
            advanced_cutoff = time.time() - (advanced_days * 24 * 60 * 60)
            conn.execute(
                'DELETE FROM advanced_latency WHERE timestamp < ?', 
                (advanced_cutoff,)
            )
            
            # Prune aggregation data
            agg_cutoff_date = (datetime.now() - timedelta(days=aggregation_days)).strftime('%Y-%m-%d')
            conn.execute(
                'DELETE FROM daily_latency_aggregation WHERE date < ?', 
                (agg_cutoff_date,)
            )

    def get_latency_data(self, test_type: str, days: int = 7, 
                       provider: Optional[str] = None, 
                       method: Optional[str] = None) -> List[Dict]:
        """
        Get latency data from aggregated results.
        
        :param test_type: 'simple' or 'advanced'
        :param days: Number of days to retrieve
        :param provider: Optional provider filter
        :param method: Optional method filter
        :return: Aggregated latency data
        """
        query = '''
            SELECT provider_name, endpoint, test_type, method, date, 
                   p50_latency, p90_latency, total_pings, success_rate 
            FROM daily_latency_aggregation 
            WHERE test_type = ?
        '''
        params = [test_type]
        
        if provider:
            query += " AND provider_name = ?"
            params.append(provider)
            
        if method and test_type == 'advanced':
            query += " AND method = ?"
            params.append(method)
            
        query += " ORDER BY date DESC LIMIT ?"
        params.append(days * 100)  # High limit to cover all providers/methods
        
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            results = conn.execute(query, params).fetchall()
            
            return [dict(row) for row in results]

# --- RPC Testing Functions ---
def ping_simple_rpc(url: str, method: str, params: List = None) -> Dict:
    """
    Ping an RPC endpoint with a simple method call.
    
    :param url: RPC URL
    :param method: RPC method name
    :param params: RPC params
    :return: Latency and success information
    """
    payload = {
        "jsonrpc": "2.0",
        "method": method,
        "params": params or [],
        "id": 1
    }
    
    try:
        start_time = time.time()
        response = requests.post(url, json=payload, timeout=5)
        
        # Check for HTTP errors
        if response.status_code >= 400:
            return {
                'latency_ms': -1,
                'success': False,
                'error': f"HTTP error: {response.status_code}"
            }
            
        response_json = response.json()
        
        # Check for JSON-RPC error
        if 'error' in response_json:
            return {
                'latency_ms': -1,
                'success': False,
                'error': f"RPC error: {response_json['error']}"
            }
            
        # Only measure latency for successful responses
        latency = (time.time() - start_time) * 1000  # Convert to milliseconds
        return {
            'latency_ms': latency,
            'success': True
        }
    except requests.Timeout:
        return {
            'latency_ms': -1,
            'success': False,
            'error': "Request timed out"
        }
    except requests.RequestException as e:
        return {
            'latency_ms': -1,
            'success': False,
            'error': str(e)
        }

def ping_advanced_rpc(url: str, methods: Dict) -> List[Dict]:
    """
    Ping an RPC endpoint with multiple advanced methods.
    
    :param url: RPC URL
    :param methods: Dict of methods to test
    :return: List of results for each method
    """
    results = []
    
    for method_name, method_config in methods.items():
        if not method_config.get('enabled', True):
            continue
            
        # Prepare request
        payload = {
            "jsonrpc": "2.0",
            "method": method_config['method'],
            "params": method_config['params'],
            "id": 1
        }
        
        try:
            start_time = time.time()
            response = requests.post(url, json=payload, timeout=10)
            
            # Check for HTTP errors
            if response.status_code >= 400:
                results.append({
                    'method': method_name,
                    'complexity': method_config['complexity'],
                    'latency_ms': -1,
                    'success': False,
                    'error': f"HTTP error: {response.status_code}"
                })
                continue
                
            response_json = response.json()
            
            # Check for JSON-RPC error
            if 'error' in response_json:
                results.append({
                    'method': method_name,
                    'complexity': method_config['complexity'],
                    'latency_ms': -1,
                    'success': False,
                    'error': f"RPC error: {response_json['error']}"
                })
                continue
                
            # Only measure latency for successful responses
            latency = (time.time() - start_time) * 1000  # Convert to milliseconds
            results.append({
                'method': method_name,
                'complexity': method_config['complexity'],
                'latency_ms': latency,
                'success': True
            })
        
        except requests.Timeout:
            results.append({
                'method': method_name,
                'complexity': method_config['complexity'],
                'latency_ms': -1,
                'success': False,
                'error': "Request timed out"
            })
        except requests.RequestException as e:
            results.append({
                'method': method_name,
                'complexity': method_config['complexity'],
                'latency_ms': -1,
                'success': False,
                'error': str(e)
            })
    
    return results

# --- Monitoring Threads ---
def simple_monitor_thread(tracker: LatencyTracker, providers: List[Dict], service_status: ServiceStatus):
    """
    Continuously monitor providers with simple latency tests.
    
    :param tracker: LatencyTracker instance
    :param providers: List of provider configurations
    :param service_status: ServiceStatus instance
    """
    while True:
        try:
            for provider in providers:
                simple_config = provider['methods']['simple_test']
                result = ping_simple_rpc(
                    provider['url'], 
                    simple_config['method'],
                    simple_config['params']
                )
                
                tracker.record_simple_ping(
                    provider_name=provider['name'],
                    endpoint=provider['url'],
                    latency_ms=result['latency_ms'],
                    success=result['success']
                )
                
                # Update status
                service_status.update_simple_ping()
                
                # Sleep according to provider interval
                time.sleep(simple_config['ping_interval'])
                
            # Set thread status to healthy
            service_status.set_thread_status('simple_monitor', True)
            
        except Exception as e:
            print(f"Simple monitor error: {e}")
            service_status.set_thread_status('simple_monitor', False)
            time.sleep(30)  # Wait before restarting

def advanced_monitor_thread(tracker: LatencyTracker, providers: List[Dict], service_status: ServiceStatus):
    """
    Monitor providers with advanced tests at their scheduled intervals.
    
    :param tracker: LatencyTracker instance
    :param providers: List of provider configurations
    :param service_status: ServiceStatus instance
    """
    while True:
        try:
            for provider in providers:
                advanced_config = provider['methods']['advanced_test']
                
                # Skip if advanced testing is disabled
                if not advanced_config.get('enabled', True):
                    continue
                    
                # Run all enabled advanced methods
                results = ping_advanced_rpc(
                    provider['url'],
                    advanced_config['methods']
                )
                
                # Record each method's result
                for result in results:
                    if 'method' in result:
                        tracker.record_advanced_ping(
                            provider_name=provider['name'],
                            endpoint=provider['url'],
                            method=result['method'],
                            complexity=result['complexity'],
                            latency_ms=result['latency_ms'],
                            success=result['success']
                        )
                
                # Update status
                service_status.update_advanced_ping()
                
                # Sleep according to advanced interval
                time.sleep(advanced_config['ping_interval'])
                
            # Set thread status to healthy
            service_status.set_thread_status('advanced_monitor', True)
            
        except Exception as e:
            print(f"Advanced monitor error: {e}")
            service_status.set_thread_status('advanced_monitor', False)
            time.sleep(30)  # Wait before restarting

def daily_maintenance_thread(tracker: LatencyTracker, config: Dict, service_status: ServiceStatus):
    """Run maintenance tasks daily."""
    while True:
        try:
            # Run at midnight
            current_time = datetime.now()
            next_midnight = (current_time + timedelta(days=1)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            
            # Sleep until midnight
            sleep_seconds = (next_midnight - current_time).total_seconds()
            time.sleep(sleep_seconds)
            
            # Perform maintenance
            tracker.aggregate_daily_latency()
            tracker.prune_data(
                simple_days=config['global_settings'].get('simple_data_retention_days', 7),
                advanced_days=config['global_settings'].get('advanced_data_retention_days', 14),
                aggregation_days=config['global_settings'].get('aggregation_retention_days', 90)
            )
            
            # Update status
            service_status.update_maintenance()
            
            # Set thread status to healthy
            service_status.set_thread_status('maintenance', True)
            
        except Exception as e:
            print(f"Daily maintenance error: {e}")
            service_status.set_thread_status('maintenance', False)
            time.sleep(30)  # Wait before restarting

# --- FastAPI App ---
app = FastAPI(title="Dual-Tier RPC Edge Probe")
service_status = ServiceStatus()

@app.get("/providers")
async def get_providers():
    """Get configured providers."""
    return [{
        'name': provider['name'], 
        'url': provider['url']
    } for provider in config['rpc_providers']]

@app.get("/simple-latency")
async def get_simple_latency(
    days: int = Query(7, ge=1, le=90),
    provider: Optional[str] = None):
    """Get simple latency data."""
    return tracker.get_latency_data('simple', days, provider)

@app.get("/advanced-latency")
async def get_advanced_latency(
    days: int = Query(7, ge=1, le=90),
    provider: Optional[str] = None,
    method: Optional[str] = None):
    """Get advanced latency data."""
    return tracker.get_latency_data('advanced', days, provider, method)

@app.get("/methods")
async def get_available_methods():
    """Get available test methods from configuration."""
    methods = {}
    
    for provider in config['rpc_providers']:
        simple = provider['methods']['simple_test']
        advanced = provider['methods']['advanced_test']
        
        if provider['name'] not in methods:
            methods[provider['name']] = {
                'simple': simple['method'],
                'advanced': []
            }
        
        # Add enabled advanced methods
        for method_name, method_config in advanced['methods'].items():
            if method_config.get('enabled', True):
                methods[provider['name']]['advanced'].append({
                    'name': method_name,
                    'method': method_config['method'],
                    'complexity': method_config['complexity']
                })
    
    return methods

@app.get("/status")
async def get_status():
    """Get service status."""
    return service_status.get_status()

@app.get("/health")
async def health_check():
    """
    Simple health check endpoint.
    Returns 200 if service is operational, 503 if critical issues detected.
    """
    status = service_status.get_status()
    
    if status['status'] == "CRITICAL":
        raise HTTPException(status_code=503, detail="Service unavailable")
    
    return {"status": "OK"}

# --- Main Execution ---
if __name__ == "__main__":
    # Load configuration
    config = ConfigManager.load_config()
    
    # Initialize tracker
    tracker = LatencyTracker(config['global_settings']['database_path'])
    
    # Start monitoring threads
    simple_thread = threading.Thread(
        target=simple_monitor_thread,
        args=(tracker, config['rpc_providers'], service_status),
        daemon=True
    )
    
    advanced_thread = threading.Thread(
        target=advanced_monitor_thread,
        args=(tracker, config['rpc_providers'], service_status),
        daemon=True
    )
    
    maintenance_thread = threading.Thread(
        target=daily_maintenance_thread,
        args=(tracker, config, service_status),
        daemon=True
    )
    
    # Start all threads
    simple_thread.start()
    advanced_thread.start()
    maintenance_thread.start()
    
    # Run the API server
    app_port = int(os.environ.get('PORT', config['global_settings']['api_port']))
    uvicorn.run(
        app,
        host="0.0.0.0",  # Always bind to all interfaces in container environments
        port=app_port
    )