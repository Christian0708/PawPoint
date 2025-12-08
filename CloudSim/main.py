"""
CloudSim Distributed Storage System - Service Entry Point
Sets up and runs the cloud infrastructure service

This service:
- Starts the network service
- Loads existing nodes from state
- Starts all system components (metrics, capacity evaluation)
- Keeps the system running for CLI operations
"""

import time
import os
import sys
import signal
import io

# Set UTF-8 encoding for Windows console
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

from config_loader import ConfigLoader
from node_factory import NodeFactory
from metrics_collector import MetricsCollector
from capacity_evaluator import CapacityEvaluator, AlertLevel
from logger import CloudSimLogger, get_logger
from network_service import NetworkService


class CloudSimService:
    """Main service that runs the CloudSim infrastructure"""
    
    def __init__(self, config_path: str = "config.yaml"):
        """Initialize the service"""
        import os
        if not os.path.exists(config_path) and os.path.exists(os.path.join(os.path.dirname(__file__), 'config.yaml')):
            config_path = os.path.join(os.path.dirname(__file__), 'config.yaml')
        self.config_path = config_path
        self.config: ConfigLoader = None
        self.factory: NodeFactory = None
        self.metrics: MetricsCollector = None
        self.capacity: CapacityEvaluator = None
        self.network_service: NetworkService = None
        self.logger = None
        self.running = False
    
    def initialize(self):
        """Initialize all system components"""
        import os
        print("="*80)
        print("CloudSim Distributed Storage System - Service")
        print("="*80)
        print()
        
        # Load configuration
        print("[1/6] Loading configuration...")
        self.config = ConfigLoader(self.config_path)
        self.config.load()
        
        # Setup logging
        CloudSimLogger.setup_logging(self.config)
        self.logger = get_logger("CloudSim.Service")
        self.logger.info("Initializing CloudSim service")
        print("[OK] Configuration loaded")
        print()
        
        # Initialize NodeFactory (loads existing nodes from state)
        print("[2/6] Initializing node factory...")
        start_port = self.config.get("node_factory.start_port", 5000)
        port_range = self.config.get("node_factory.port_range_size", 1000)
        storage_root = os.path.abspath(self.config.get("storage.base_directory", "storage"))
        state_file = self.config.get("nodes_state_file", "nodes_state.json")
        self.factory = NodeFactory(start_port=start_port, port_range_size=port_range, state_file=state_file, storage_base_dir=storage_root)
        print(f"[OK] NodeFactory initialized (loaded {len(self.factory.get_all_nodes())} node(s) from state)")
        print()
        
        # Initialize MetricsCollector
        print("[3/6] Initializing metrics collector...")
        max_history = self.config.get("metrics.max_history", 1000)
        self.metrics = MetricsCollector(self.factory, max_history=max_history)
        print("[OK] MetricsCollector initialized")
        print()
        
        # Initialize CapacityEvaluator
        print("[4/6] Initializing capacity evaluator...")
        self.capacity = CapacityEvaluator(self.factory)
        
        # Configure capacity thresholds from config
        capacity_thresholds = self.config.get("capacity.thresholds.global", [])
        for threshold in capacity_thresholds:
            percent = threshold.get("percent", 0)
            level_str = threshold.get("level", "INFO")
            level = getattr(AlertLevel, level_str.upper(), AlertLevel.INFO)
            description = threshold.get("description", "")
            self.capacity.add_threshold(percent, level, description)
        
        print(f"[OK] CapacityEvaluator initialized ({len(capacity_thresholds)} thresholds configured)")
        print()
        
        # Initialize NetworkService
        print("[5/6] Initializing network service...")
        discovery_port = self.config.get("network.discovery.port", 9999)
        broadcast_interval = self.config.get("network.discovery.broadcast_interval_seconds", 30.0)
        network_name = self.config.get("network.name", "CloudSim_Storage_Network")
        node_timeout = self.config.get("network.discovery.node_timeout_seconds", 90.0)
        self.network_service = NetworkService(
            discovery_port=discovery_port,
            broadcast_interval=broadcast_interval,
            network_name=network_name,
            node_timeout=node_timeout
        )
        print("[OK] NetworkService initialized")
        print()
        
        # Start network service
        print("[6/6] Starting network service...")
        self.network_service.start()
        if self.network_service.running:
            print(f"[OK] Network service started on port {discovery_port}")
        else:
            print("[WARNING] Network service failed to start")
        print()
    
    def start(self):
        """Start all system components"""
        if self.running:
            print("[WARNING] Service is already running")
            return
        
        self.running = True
        
        # Do not auto-start nodes; leave control to CLI
        existing_nodes = self.factory.get_all_nodes()
        if existing_nodes:
            print(f"[INFO] {len(existing_nodes)} node(s) present. Nodes are NOT auto-started.")
            print("       Use CLI to start/stop nodes at will:")
            print("       - python cli.py start [node_ids]")
            print("       - python cli.py stop [node_ids]")
        else:
            print("[INFO] No nodes found. Use CLI to create and start nodes:")
            print("       python cli.py create --node-id node1 --cpu 4 --memory 8 --storage 50 --bandwidth 500")
        print()
        
        # Start metrics collection
        metrics_enabled = self.config.get("metrics.enabled", True)
        if metrics_enabled:
            collection_interval = self.config.get("metrics.collection_interval_seconds", 5.0)
            self.metrics.start_auto_collection(interval=collection_interval)
            print(f"[OK] Metrics collection started (interval: {collection_interval}s)")
        print()
        
        # Enable node discovery if configured
        discovery_enabled = self.config.get("network.discovery.enabled", True)
        if discovery_enabled and existing_nodes:
            discovery_port = self.config.get("network.discovery.port", 9999)
            broadcast_interval = self.config.get("network.discovery.broadcast_interval_seconds", 30.0)
            self.factory.enable_discovery(discovery_port=discovery_port, broadcast_interval=broadcast_interval)
            print(f"[OK] Node discovery enabled")
        print()
        
        # Display system status
        self._display_status()
    
    def _display_status(self):
        """Display current system status"""
        print("="*80)
        print("System Status")
        print("="*80)
        
        # Network status
        network_status = self.network_service.get_network_status()
        print(f"Network: {network_status['network_name']} - {'Running' if network_status['running'] else 'Stopped'}")
        print(f"  Discovery Port: {network_status['discovery_port']}")
        print(f"  Registered Nodes: {network_status['registered_nodes']}")
        
        # Factory stats
        factory_stats = self.factory.get_factory_stats()
        print(f"\nNodes: {factory_stats['total_nodes']} total, {factory_stats['running_nodes']} running")
        
        if factory_stats['total_nodes'] > 0:
            resources = self.factory.get_aggregated_resources()
            print(f"Resources: {resources['total_cpu']} vCPUs, {resources['total_memory_gb']} GB RAM")
            print(f"Storage: {resources['used_storage_gb']:.2f} GB / {resources['total_storage_gb']:.2f} GB ({resources['storage_utilization_percent']:.2f}%)")
        
        print()
        print("="*80)
        print("Service is running. Use CLI commands in a SEPARATE TERMINAL to manage nodes.")
        print("This terminal is now blocked - open a new terminal window for CLI commands.")
        print("Press Ctrl+C in this terminal to stop the service.")
        print("="*80)
        print()
    
    def stop(self):
        """Stop all system components gracefully"""
        if not self.running:
            return
        
        print("\nShutting down CloudSim service...")
        self.running = False
        
        # Stop metrics collection
        if self.metrics:
            self.metrics.stop_auto_collection()
            print("[OK] Metrics collection stopped")
        
        # Stop all nodes
        if self.factory:
            self.factory.stop_all_nodes(graceful=True, timeout=5.0)
            print("[OK] All nodes stopped")
        
        # Stop network service
        if self.network_service:
            self.network_service.stop()
            print("[OK] Network service stopped")
        
        print("[OK] Service shutdown complete")
    
    def run(self):
        """Run the service (keeps process alive)"""
        import os
        # Set up signal handlers for graceful shutdown
        def signal_handler(sig, frame):
            self.stop()
            sys.exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Keep process alive
        try:
            last_mtime = None
            state_file = self.config.get("nodes_state_file", "nodes_state.json")
            while self.running:
                time.sleep(1)
                # Check if network service is still running
                if self.network_service and not self.network_service.running:
                    print("[WARNING] Network service stopped unexpectedly")
                    break
                # Detect node state changes (do not auto-start nodes)
                try:
                    if os.path.exists(state_file):
                        mtime = os.path.getmtime(state_file)
                        if last_mtime is None or mtime > last_mtime:
                            last_mtime = mtime
                            self.factory.load_state_incremental()
                except Exception:
                    pass
        except KeyboardInterrupt:
            signal_handler(None, None)


def main():
    """Main entry point for CloudSim service"""
    import argparse
    
    parser = argparse.ArgumentParser(description="CloudSim Distributed Storage System Service")
    parser.add_argument('--daemon', '-d', action='store_true', 
                       help='Run as daemon (Windows: runs in background, Unix: forks to background)')
    args = parser.parse_args()
    
    service = CloudSimService()
    
    try:
        # Initialize system
        service.initialize()
        
        # Start all components
        service.start()
        
        if args.daemon:
            # Run in background (Windows-compatible)
            if sys.platform == 'win32':
                print("\n[INFO] Running in background mode on Windows")
                print("[INFO] Service is running. Use another terminal for CLI commands.")
                print("[INFO] To stop the service, use: python -c \"import os; os.kill(os.getpid(), signal.SIGTERM)\"")
                print("[INFO] Or find the process and kill it manually.\n")
            else:
                # Unix daemon mode
                import daemon
                with daemon.DaemonContext():
                    service.run()
            return
        
        # Keep service running (foreground)
        service.run()
        
    except Exception as e:
        print(f"\n[ERROR] Service error: {e}")
        import traceback
        traceback.print_exc()
        service.stop()
        sys.exit(1)


if __name__ == "__main__":
    main()
