"""
CLI - Command-line interface for CloudSim distributed storage system
Provides commands for managing nodes, monitoring metrics, and system operations
"""

import argparse
import sys
import time
from typing import Optional
from config_loader import ConfigLoader
from node_factory import NodeFactory
from metrics_collector import MetricsCollector
from capacity_evaluator import CapacityEvaluator
from logger import CloudSimLogger, get_logger
from network_service import NetworkService


class CloudSimCLI:
    """
    Command-line interface for CloudSim distributed storage system
    """
    
    def __init__(self):
        """Initialize CLI"""
        self.config: Optional[ConfigLoader] = None
        self.factory: Optional[NodeFactory] = None
        self.metrics: Optional[MetricsCollector] = None
        self.capacity: Optional[CapacityEvaluator] = None
        self.network_service: Optional[NetworkService] = None
    
    def setup(self, config_path: str = "config.yaml"):
        """
        Setup CLI components
        
        Args:
            config_path: Path to configuration file
        """
        # Load configuration
        self.config = ConfigLoader(config_path)
        self.config.load()
        
        # Setup logging
        CloudSimLogger.setup_logging(self.config)
        self.logger = get_logger("CloudSim.CLI")
        
        # Initialize components
        start_port = self.config.get("node_factory.start_port", 5000)
        port_range = self.config.get("node_factory.port_range_size", 1000)
        
        self.factory = NodeFactory(start_port=start_port, port_range_size=port_range)
        self.metrics = MetricsCollector(self.factory)
        self.capacity = CapacityEvaluator(self.factory)
        
        # Initialize network service (but don't start it automatically)
        discovery_port = self.config.get("network.discovery.port", 9999)
        broadcast_interval = self.config.get("network.discovery.broadcast_interval_seconds", 30.0)
        network_name = self.config.get("network.name", "CloudSim_Storage_Network")
        self.network_service = NetworkService(
            discovery_port=discovery_port,
            broadcast_interval=broadcast_interval,
            network_name=network_name
        )
        
        self.logger.info("CLI components initialized")
    
    def cmd_start(self, args):
        """Start nodes command"""
        if not self.factory:
            self.setup()
        
        # Save state after starting nodes
        if args.nodes:
            # Start specific nodes
            started = 0
            already_running = 0
            for node_id in args.nodes:
                node = self.factory.get_node(node_id)
                if node:
                    if not node.is_alive():
                        try:
                            node.start()
                            print(f"✓ Started node: {node_id}")
                            started += 1
                        except Exception as e:
                            print(f"✗ Error starting node {node_id}: {e}")
                    else:
                        print(f"○ Node {node_id} is already running")
                        already_running += 1
                else:
                    print(f"✗ Node {node_id} not found")
            
            if started > 0 or already_running > 0:
                print(f"\nStarted: {started}, Already running: {already_running}")
        else:
            # Start all nodes
            try:
                self.factory.start_all_nodes()
                print("[OK] All nodes started")
            except Exception as e:
                print(f"[ERROR] Error starting nodes: {e}")
                sys.exit(1)
        
        # If interactive mode, keep process alive
        if hasattr(args, 'interactive') and args.interactive:
            self._run_interactive_mode()
    
    def cmd_stop(self, args):
        """Stop nodes command"""
        if not self.factory:
            self.setup()
        
        if args.nodes:
            # Stop specific nodes
            stopped = 0
            for node_id in args.nodes:
                node = self.factory.get_node(node_id)
                if node:
                    try:
                        node.stop(graceful=args.graceful, timeout=args.timeout)
                        node.join(timeout=3.0)
                        print(f"[OK] Stopped node: {node_id}")
                        stopped += 1
                    except Exception as e:
                        print(f"[ERROR] Error stopping node {node_id}: {e}")
                else:
                    print(f"[ERROR] Node {node_id} not found")
            
            if stopped > 0:
                print(f"\nStopped {stopped} node(s)")
        else:
            # Stop all nodes
            try:
                self.factory.stop_all_nodes(graceful=args.graceful, timeout=args.timeout)
                print("[OK] All nodes stopped")
            except Exception as e:
                print(f"[ERROR] Error stopping nodes: {e}")
                sys.exit(1)
    
    def cmd_restart(self, args):
        """Restart nodes command"""
        if not self.factory:
            self.setup()
        
        if args.nodes:
            # Restart specific nodes
            for node_id in args.nodes:
                node = self.factory.get_node(node_id)
                if node:
                    print(f"Restarting node: {node_id}...")
                    try:
                        # Stop
                        node.stop(graceful=args.graceful, timeout=args.timeout)
                        node.join(timeout=3.0)
                        # Start
                        node.start()
                        print(f"[OK] Restarted node: {node_id}")
                    except Exception as e:
                        print(f"[ERROR] Error restarting node {node_id}: {e}")
                else:
                    print(f"[ERROR] Node {node_id} not found")
        else:
            # Restart all nodes
            print("Restarting all nodes...")
            try:
                self.factory.restart_all_nodes(graceful=args.graceful, timeout=args.timeout)
                print("[OK] All nodes restarted")
            except Exception as e:
                print(f"[ERROR] Error restarting nodes: {e}")
                sys.exit(1)
    
    def cmd_status(self, args):
        """Status command"""
        if not self.factory:
            self.setup()
        
        if args.node:
            # Status of specific node
            node = self.factory.get_node(args.node)
            if not node:
                print(f"Error: Node '{args.node}' not found")
                sys.exit(1)
            
            is_running = node.is_alive() or node.running
            config = self.factory.node_configs.get(args.node, {})
            
            if is_running:
                storage_util = node.get_storage_utilization()
                network_util = node.get_network_utilization()
                performance = node.get_performance_metrics()
            else:
                storage_util = {}
                network_util = {}
                performance = {}
            
            print(f"\n{'='*60}")
            print(f"Node Status: {args.node}")
            print(f"{'='*60}")
            print(f"Status:        {'[RUNNING]' if is_running else '[STOPPED]'}")
            print(f"Host:          {config.get('host', 'unknown')}")
            print(f"Port:          {config.get('port', 'unknown')}")
            
            if is_running:
                print(f"\nStorage:")
                print(f"  Capacity:    {storage_util.get('total_bytes', 0) / (1024**3):.2f} GB")
                print(f"  Used:        {storage_util.get('used_bytes', 0) / (1024**3):.2f} GB")
                print(f"  Available:   {(storage_util.get('total_bytes', 0) - storage_util.get('used_bytes', 0)) / (1024**3):.2f} GB")
                print(f"  Utilization: {storage_util.get('utilization_percent', 0):.2f}%")
                print(f"  Files:       {storage_util.get('files_stored', 0)}")
                print(f"  Chunks:      {storage_util.get('chunk_count', 0)}")
                
                print(f"\nNetwork:")
                print(f"  Utilization: {network_util.get('utilization_percent', 0):.2f}%")
                print(f"  Connections: {len(network_util.get('connections', []))}")
                
                print(f"\nPerformance:")
                print(f"  Transfers:   {performance.get('total_requests_processed', 0)}")
                print(f"  Failed:      {performance.get('failed_transfers', 0)}")
                print(f"  Active:      {performance.get('current_active_transfers', 0)}")
        else:
            # Comprehensive system overview
            self._show_system_overview()
    
    def _show_system_overview(self):
        """Show comprehensive system overview including network and all nodes"""
        print(f"\n{'='*80}")
        print(f"CloudSim System Overview - Everything Running")
        print(f"{'='*80}")
        
        # Network Status
        if not self.network_service:
            self.setup()
        
        network_status = self.network_service.get_network_status()
        print(f"\n[NETWORK SERVICE]")
        print(f"  Status:       {'[RUNNING]' if network_status['running'] else '[STOPPED]'}")
        print(f"  Network:      {network_status['network_name']}")
        print(f"  Discovery:   Port {network_status['discovery_port']}")
        print(f"  Registered:  {network_status['registered_nodes']} node(s)")
        
        if network_status.get('nodes'):
            print(f"  Registered Nodes:")
            for node_id, node_info in network_status['nodes'].items():
                print(f"    - {node_id}: {node_info['host']}:{node_info['port']}")
        
        # Node Factory Status
        stats = self.factory.get_factory_stats()
        nodes = self.factory.get_all_nodes()
        
        print(f"\n[NODES]")
        print(f"  Total:        {stats['total_nodes']}")
        print(f"  Running:      {stats['running_nodes']}")
        print(f"  Stopped:      {stats['stopped_nodes']}")
        
        # Resource Summary
        if stats['total_nodes'] > 0:
            resources = self.factory.get_aggregated_resources()
            print(f"\n[RESOURCES]")
            print(f"  CPU:          {resources['total_cpu']} vCPUs")
            print(f"  Memory:      {resources['total_memory_gb']} GB")
            print(f"  Storage:     {resources['used_storage_gb']:.2f} GB / {resources['total_storage_gb']:.2f} GB")
            print(f"  Utilization: {resources['storage_utilization_percent']:.2f}%")
            print(f"  Bandwidth:   {resources['total_bandwidth_mbps']} Mbps")
        
        # Node Details
        if nodes:
            print(f"\n[NODE DETAILS]")
            print(f"{'Node ID':<20} {'Status':<12} {'Host:Port':<20} {'Storage %':<12} {'Files':<10}")
            print("-" * 80)
            
            for node in nodes:
                node_id = node.node_id
                is_running = node.is_alive() or node.running
                status = "[RUNNING]" if is_running else "[STOPPED]"
                config = self.factory.node_configs.get(node_id, {})
                host_port = f"{config.get('host', 'unknown')}:{config.get('port', 'unknown')}"
                
                if is_running:
                    storage_util = node.get_storage_utilization()
                    storage_pct = f"{storage_util.get('utilization_percent', 0):.2f}%"
                    files = storage_util.get('files_stored', 0)
                else:
                    storage_pct = "N/A"
                    files = 0
                
                print(f"{node_id:<20} {status:<12} {host_port:<20} {storage_pct:<12} {files:<10}")
        
        print(f"\n{'='*80}")
    
    def cmd_list(self, args):
        """List nodes command"""
        if not self.factory:
            self.setup()
        
        nodes = self.factory.get_all_nodes()
        if not nodes:
            print("No nodes found. Use 'create' command to create nodes.")
            return
        
        if args.verbose:
            # Detailed list
            print(f"\n{'='*100}")
            print(f"{'Node ID':<15} {'Status':<12} {'Host':<15} {'Port':<8} {'CPU':<6} {'Memory':<8} {'Storage':<10} {'Bandwidth':<10}")
            print("-" * 100)
            
            for node in nodes:
                node_id = node.node_id
                is_running = node.is_alive() or node.running
                status = "[RUNNING]" if is_running else "[STOPPED]"
                config = self.factory.node_configs.get(node_id, {})
                
                host = config.get('host', 'unknown')
                port = config.get('port', 'unknown')
                cpu = config.get('cpu_capacity', 0)
                memory = f"{config.get('memory_capacity', 0)} GB"
                storage = f"{config.get('storage_capacity', 0)} GB"
                bandwidth = f"{config.get('bandwidth', 0) / 1000000 if config.get('bandwidth') else 0} Mbps"
                
                print(f"{node_id:<15} {status:<12} {host:<15} {port:<8} {cpu:<6} {memory:<8} {storage:<10} {bandwidth:<10}")
        else:
            # Simple list
            print(f"\n{'Node ID':<15} {'Status':<12} {'Host':<15} {'Port':<8}")
            print("-" * 50)
            
            for node in nodes:
                node_id = node.node_id
                is_running = node.is_alive() or node.running
                status = "[RUNNING]" if is_running else "[STOPPED]"
                host = node.host
                port = node.port
                
                print(f"{node_id:<15} {status:<12} {host:<15} {port:<8}")
        
        print(f"\nTotal: {len(nodes)} node(s)")
    
    def cmd_info(self, args):
        """Info command"""
        if not self.factory:
            self.setup()
        
        if args.node:
            # Info for specific node
            node = self.factory.get_node(args.node)
            if not node:
                print(f"Error: Node '{args.node}' not found")
                sys.exit(1)
            
            config = self.factory.node_configs.get(args.node, {})
            is_running = node.is_alive() or node.running
            
            if is_running:
                storage_util = node.get_storage_utilization()
                network_util = node.get_network_utilization()
                performance = node.get_performance_metrics()
            else:
                storage_util = {}
                network_util = {}
                performance = {}
            
            print(f"\n{'='*70}")
            print(f"Node Information: {args.node}")
            print(f"{'='*70}")
            
            print(f"\nBasic Information:")
            print(f"  Host:        {config.get('host', 'unknown')}")
            print(f"  Port:        {config.get('port', 'unknown')}")
            print(f"  Status:      {'✓ Running' if is_running else '✗ Stopped'}")
            
            print(f"\nResource Configuration:")
            print(f"  CPU:         {config.get('cpu_capacity', 0)} vCPUs")
            print(f"  Memory:      {config.get('memory_capacity', 0)} GB")
            print(f"  Storage:     {config.get('storage_capacity', 0)} GB")
            bandwidth_mbps = config.get('bandwidth', 0) / 1000000 if config.get('bandwidth') else 0
            print(f"  Bandwidth:   {bandwidth_mbps} Mbps")
            
            if is_running:
                print(f"\nStorage Utilization:")
                total_gb = storage_util.get('total_bytes', 0) / (1024**3)
                used_gb = storage_util.get('used_bytes', 0) / (1024**3)
                available_gb = total_gb - used_gb
                print(f"  Total:       {total_gb:.2f} GB")
                print(f"  Used:        {used_gb:.2f} GB")
                print(f"  Available:   {available_gb:.2f} GB")
                print(f"  Utilization: {storage_util.get('utilization_percent', 0):.2f}%")
                print(f"  Files:       {storage_util.get('files_stored', 0)}")
                print(f"  Chunks:      {storage_util.get('chunk_count', 0)}")
                
                print(f"\nNetwork Utilization:")
                print(f"  Utilization: {network_util.get('utilization_percent', 0):.2f}%")
                connections = network_util.get('connections', [])
                print(f"  Connections:   {len(connections)}")
                if connections:
                    print(f"    {', '.join(connections)}")
                
                print(f"\nPerformance Metrics:")
                print(f"  Total Transfers:    {performance.get('total_requests_processed', 0)}")
                print(f"  Successful:         {performance.get('total_requests_processed', 0) - performance.get('failed_transfers', 0)}")
                print(f"  Failed:             {performance.get('failed_transfers', 0)}")
                print(f"  Active Transfers:   {performance.get('current_active_transfers', 0)}")
                data_transferred = performance.get('total_data_transferred_bytes', 0) / (1024**3)
                print(f"  Data Transferred:   {data_transferred:.2f} GB")
        else:
            # System info
            stats = self.factory.get_factory_stats()
            resources = self.factory.get_aggregated_resources()
            health = self.factory.check_all_nodes_health()
            
            print(f"\n{'='*70}")
            print(f"System Information")
            print(f"{'='*70}")
            
            print(f"\nNode Summary:")
            print(f"  Total Nodes:    {stats['total_nodes']}")
            print(f"  Running:        {stats['running_nodes']}")
            print(f"  Stopped:        {stats['stopped_nodes']}")
            
            healthy = sum(1 for h in health.values() if h.get('status') == 'running')
            print(f"  Healthy:        {healthy}")
            
            print(f"\nTotal Resources:")
            print(f"  CPU:            {resources['total_cpu']} vCPUs")
            print(f"  Memory:         {resources['total_memory_gb']} GB")
            print(f"  Storage:        {resources['total_storage_gb']} GB")
            print(f"  Bandwidth:      {resources['total_bandwidth_mbps']} Mbps")
            
            print(f"\nStorage Summary:")
            print(f"  Total:          {resources['total_storage_gb']} GB")
            print(f"  Used:           {resources['used_storage_gb']} GB")
            print(f"  Available:      {resources['available_storage_gb']} GB")
            print(f"  Utilization:    {resources['storage_utilization_percent']:.2f}%")
            
            print(f"\nAverages per Node:")
            print(f"  CPU:            {resources['average_cpu']} vCPUs")
            print(f"  Memory:         {resources['average_memory_gb']} GB")
            print(f"  Storage:        {resources['average_storage_gb']} GB")
            print(f"  Bandwidth:      {resources['average_bandwidth_mbps']} Mbps")
    
    def cmd_create(self, args):
        """Create nodes command"""
        if not self.factory:
            self.setup()
        
        created_nodes = []
        
        # If node specifications are provided, create node with those specs
        if args.node_id:
            try:
                node = self.factory.create_node(
                    node_id=args.node_id,
                    cpu_capacity=args.cpu or 2,
                    memory_capacity=args.memory or 4,
                    storage_capacity=args.storage or 10,
                    bandwidth=args.bandwidth or 100,
                    host=args.host or "localhost",
                    port=args.port
                )
                if node:
                    created_nodes.append(node)
                    print(f"Created node: {args.node_id}")
                    print(f"  Host: {args.host or 'localhost'}")
                    print(f"  Port: {node.port}")
                    print(f"  CPU: {args.cpu or 2} vCPUs")
                    print(f"  Memory: {args.memory or 4} GB")
                    print(f"  Storage: {args.storage or 10} GB")
                    print(f"  Bandwidth: {args.bandwidth or 100} Mbps")
            except Exception as e:
                print(f"Error creating node {args.node_id}: {e}")
                import traceback
                traceback.print_exc()
                return
        
        # If count is specified, create multiple nodes with same specs
        elif args.count and args.count > 0:
            base_id = args.base_id or "node"
            for i in range(args.count):
                node_id = f"{base_id}{i+1}"
                try:
                    node = self.factory.create_node(
                        node_id=node_id,
                        cpu_capacity=args.cpu or 2,
                        memory_capacity=args.memory or 4,
                        storage_capacity=args.storage or 10,
                        bandwidth=args.bandwidth or 100,
                        host=args.host or "localhost",
                        port=None  # Auto-assign ports for multiple nodes
                    )
                    if node:
                        created_nodes.append(node)
                        print(f"Created node: {node_id} on port {node.port}")
                except Exception as e:
                    print(f"Error creating node {node_id}: {e}")
        
        # If no node specs provided, show usage
        else:
            print("Error: Node specifications required.")
            print("\nUsage examples:")
            print("  # Create a single node")
            print("  python cli.py create --node-id node1 --cpu 4 --memory 8 --storage 50 --bandwidth 500 --start")
            print("\n  # Create multiple nodes with same specs")
            print("  python cli.py create --count 3 --cpu 2 --memory 4 --storage 20 --bandwidth 100 --start")
            print("\nUse --help for all options")
            return
        
        if created_nodes:
            print(f"\nCreated {len(created_nodes)} node(s)")
            if args.start:
                self.factory.start_all_nodes()
                print("All nodes started")
                print("\n[INFO] Nodes are running. Use 'python cli.py status' to check their status.")
                print("       To keep nodes running, use 'python cli.py start --interactive'")
        else:
            print("No nodes created.")
    
    def cmd_metrics(self, args):
        """Metrics command"""
        if not self.factory or not self.metrics:
            self.setup()
        
        if args.export:
            # Export metrics
            format_type = args.format or self.config.get("metrics.export_format", "json")
            output_dir = args.output or self.config.get("metrics.export_directory", "metrics")
            
            files = self.metrics.export_all_metrics(output_dir=output_dir, format=format_type)
            print(f"Exported metrics to {output_dir}")
            print(f"Files: {len(files)}")
        else:
            # Show metrics
            if args.node:
                latest = self.metrics.get_latest_metrics(node_id=args.node)
                if latest:
                    print(f"\n=== Metrics for {args.node} ===")
                    print(f"Throughput: {latest.get('throughput_mbps', 0):.2f} Mbps")
                    print(f"Latency: {latest.get('average_latency_ms', 0):.2f} ms")
                    print(f"RTT: {latest.get('average_rtt_ms', 0):.2f} ms")
                    print(f"Storage Utilization: {latest.get('storage_utilization_percent', 0):.2f}%")
            else:
                latest = self.metrics.get_latest_metrics()
                if latest:
                    print(f"\n=== Network Metrics ===")
                    print(f"Total Throughput: {latest.get('total_throughput_mbps', 0):.2f} Mbps")
                    print(f"Average Latency: {latest.get('average_latency_ms', 0):.2f} ms")
                    print(f"Average RTT: {latest.get('average_rtt_ms', 0):.2f} ms")
    
    def cmd_capacity(self, args):
        """Capacity command"""
        if not self.factory or not self.capacity:
            self.setup()
        
        if args.report:
            # Generate capacity report
            report = self.capacity.generate_capacity_report(
                include_predictions=True,
                include_alerts=True
            )
            print("\n=== Capacity Report ===")
            print(f"Total Storage: {report['total_capacity']['storage_capacity']['total_gb']} GB")
            print(f"Used: {report['total_capacity']['storage_capacity']['used_gb']} GB")
            print(f"Utilization: {report['total_capacity']['storage_capacity']['utilization_percent']:.2f}%")
        else:
            # Show capacity summary
            summary = self.capacity.get_capacity_summary()
            print("\n=== Capacity Summary ===")
            print(f"Total Nodes: {summary['node_count']}")
            print(f"Storage Utilization: {summary['overall_capacity']['storage_capacity']['utilization_percent']:.2f}%")
    
    def cmd_network(self, args):
        """Network service command"""
        if not self.network_service:
            self.setup()
        
        if args.action == "start":
            if self.network_service.running:
                print("Network service is already running")
            else:
                self.network_service.start()
                if self.network_service.running:
                    print("Network service started")
                    print(f"  Network: {self.network_service.network_name}")
                    print(f"  Discovery Port: {self.network_service.discovery_port}")
                    print("  Nodes can now connect to the cloud")
                else:
                    print("Failed to start network service")
                    return
            
            # Keep process alive for network (network needs to stay running)
            # Otherwise the daemon threads will die when CLI process exits
            self._run_network_interactive_mode()
        
        elif args.action == "stop":
            # Check if network is running in this process
            if self.network_service.running:
                self.network_service.stop()
                print("Network service stopped (this process)")
            else:
                # Check if network is running in another process
                status = self.network_service.get_network_status()
                if status.get('running_in_another_process'):
                    print("Network is running in another process. Attempting to stop it...")
                    success = self._stop_network_in_other_process()
                    if success:
                        print("Network service stopped in other process")
                    else:
                        print("[WARNING] Could not stop network in other process via message.")
                        print("         You may need to:")
                        print("         1. Find the terminal running 'python main.py' or 'network start'")
                        print("         2. Press Ctrl+C in that terminal")
                        print("         3. Or kill Python processes: Get-Process python | Stop-Process -Force")
                else:
                    print("Network service is not running")
        
        elif args.action == "status":
            status = self.network_service.get_network_status()
            print("\n=== Network Status ===")
            print(f"Network Name: {status['network_name']}")
            print(f"Running: {status['running']}")
            print(f"Available: {status['network_available']}")
            print(f"Discovery Port: {status['discovery_port']}")
            print(f"Registered Nodes: {status['registered_nodes']}")
            
            # Show additional info if network is running in another process
            if status.get('running_in_another_process'):
                print("\n[WARNING] Network is running in ANOTHER process!")
                print("         This CLI instance cannot stop it.")
                print("         To stop it:")
                print("         1. Find the terminal running 'python main.py' or 'network start --interactive'")
                print("         2. Press Ctrl+C in that terminal")
                print("         3. Or kill the Python process: Get-Process python | Stop-Process -Force")
            
            if status['nodes']:
                print("\nRegistered Nodes:")
                for node_id, node_info in status['nodes'].items():
                    print(f"  - {node_id}: {node_info['host']}:{node_info['port']}")
    
    def _stop_network_in_other_process(self) -> bool:
        """Attempt to stop network service running in another process by sending shutdown message"""
        try:
            import socket
            import json
            
            # Send shutdown message to network service
            shutdown_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            shutdown_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            shutdown_socket.settimeout(2.0)
            
            shutdown_msg = {
                'type': 'NETWORK_SHUTDOWN',
                'source': 'cli_stop_command',
                'timestamp': time.time()
            }
            
            # Try to send to localhost first, then broadcast
            try:
                shutdown_socket.sendto(
                    json.dumps(shutdown_msg).encode('utf-8'),
                    ('127.0.0.1', self.network_service.discovery_port)
                )
                # Wait a moment for shutdown to process
                time.sleep(1.0)
                shutdown_socket.close()
                
                # Check if network is still running
                time.sleep(0.5)
                status = self.network_service.get_network_status()
                if not status.get('running'):
                    return True
            except Exception as e:
                shutdown_socket.close()
                return False
            
            return False
        except Exception as e:
            print(f"[ERROR] Error sending shutdown message: {e}")
            return False
    
    def _run_network_interactive_mode(self):
        """Run in interactive mode to keep network service alive"""
        import signal
        import time
        
        print("\n" + "="*70)
        print("Interactive Mode - Network service is running")
        print("Press Ctrl+C to stop the network service and exit")
        print("="*70 + "\n")
        
        # Set up signal handler for graceful shutdown
        def signal_handler(sig, frame):
            print("\n\nShutting down network service...")
            try:
                if self.network_service:
                    self.network_service.stop()
            except Exception as e:
                print(f"Error during shutdown: {e}")
            print("Exiting...")
            sys.exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Keep process alive
        try:
            while True:
                time.sleep(1)
                # Check if network service is still running
                if self.network_service and not self.network_service.running:
                    print("\nNetwork service stopped unexpectedly. Exiting...")
                    break
        except KeyboardInterrupt:
            signal_handler(None, None)
    
    def _run_interactive_mode(self):
        """Run in interactive mode to keep nodes alive"""
        import signal
        import time
        
        print("\n" + "="*70)
        print("Interactive Mode - Nodes are running")
        print("Press Ctrl+C to stop all nodes and exit")
        print("="*70 + "\n")
        
        # Set up signal handler for graceful shutdown
        def signal_handler(sig, frame):
            print("\n\nShutting down all nodes...")
            try:
                if self.factory:
                    self.factory.stop_all_nodes(graceful=True, timeout=5.0)
            except Exception as e:
                print(f"Error during shutdown: {e}")
            print("Exiting...")
            sys.exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Keep process alive
        try:
            while True:
                time.sleep(1)
                # Check if any nodes are still running
                if self.factory:
                    running = sum(1 for node in self.factory.get_all_nodes() 
                                if node.is_alive() or node.running)
                    if running == 0:
                        print("\nAll nodes have stopped. Exiting...")
                        break
        except KeyboardInterrupt:
            signal_handler(None, None)
    
    def create_parser(self) -> argparse.ArgumentParser:
        """Create argument parser with all commands"""
        parser = argparse.ArgumentParser(
            description="CloudSim Distributed Storage System CLI",
            formatter_class=argparse.RawDescriptionHelpFormatter
        )
        
        subparsers = parser.add_subparsers(dest='command', help='Available commands')
        
        # Start command
        start_parser = subparsers.add_parser('start', help='Start nodes')
        start_parser.add_argument('nodes', nargs='*', help='Node IDs to start (all if not specified)')
        start_parser.add_argument('--interactive', '-i', action='store_true', 
                                help='Keep process running in interactive mode')
        start_parser.set_defaults(func=self.cmd_start)
        
        # Stop command
        stop_parser = subparsers.add_parser('stop', help='Stop nodes')
        stop_parser.add_argument('nodes', nargs='*', help='Node IDs to stop (all if not specified)')
        stop_parser.add_argument('--graceful', action='store_true', default=True, help='Graceful shutdown')
        stop_parser.add_argument('--timeout', type=float, default=5.0, help='Shutdown timeout in seconds')
        stop_parser.set_defaults(func=self.cmd_stop)
        
        # Restart command
        restart_parser = subparsers.add_parser('restart', help='Restart nodes')
        restart_parser.add_argument('nodes', nargs='*', help='Node IDs to restart (all if not specified)')
        restart_parser.add_argument('--graceful', action='store_true', default=True, help='Graceful shutdown before restart')
        restart_parser.add_argument('--timeout', type=float, default=5.0, help='Shutdown timeout in seconds')
        restart_parser.set_defaults(func=self.cmd_restart)
        
        # Status command
        status_parser = subparsers.add_parser('status', help='Show node status')
        status_parser.add_argument('--node', help='Specific node ID')
        status_parser.set_defaults(func=self.cmd_status)
        
        # List command
        list_parser = subparsers.add_parser('list', help='List all nodes')
        list_parser.add_argument('--verbose', '-v', action='store_true', help='Show detailed information')
        list_parser.set_defaults(func=self.cmd_list)
        
        # Info command
        info_parser = subparsers.add_parser('info', help='Show detailed information')
        info_parser.add_argument('--node', help='Specific node ID')
        info_parser.set_defaults(func=self.cmd_info)
        
        # Create command
        create_parser = subparsers.add_parser('create', 
            help='Create nodes with custom specifications',
            description='Create nodes with your own specifications',
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Examples:
  # Create a single node with custom specs
  python cli.py create --node-id node1 --cpu 4 --memory 8 --storage 50 --bandwidth 500 --start
  
  # Create multiple nodes with same specs
  python cli.py create --count 3 --cpu 2 --memory 4 --storage 20 --bandwidth 100 --start
  
  # Create with custom base ID prefix
  python cli.py create --count 5 --base-id worker --cpu 4 --memory 8 --storage 50 --bandwidth 500 --start
            """)
        create_parser.add_argument('--start', action='store_true', help='Start nodes after creation')
        create_parser.add_argument('--node-id', type=str, help='Node ID for single node creation')
        create_parser.add_argument('--count', type=int, help='Number of nodes to create (for batch creation)')
        create_parser.add_argument('--base-id', type=str, help='Base ID prefix for batch creation (default: "node")')
        create_parser.add_argument('--host', type=str, default='localhost', help='Host address (default: localhost)')
        create_parser.add_argument('--port', type=int, help='Port number (auto-assigned if not specified)')
        create_parser.add_argument('--cpu', type=int, help='CPU capacity in vCPUs (default: 2)')
        create_parser.add_argument('--memory', type=int, help='Memory capacity in GB (default: 4)')
        create_parser.add_argument('--storage', type=int, help='Storage capacity in GB (default: 10)')
        create_parser.add_argument('--bandwidth', type=int, help='Bandwidth in Mbps (default: 100)')
        create_parser.set_defaults(func=self.cmd_create)
        
        # Metrics command
        metrics_parser = subparsers.add_parser('metrics', help='Show or export metrics')
        metrics_parser.add_argument('--node', help='Specific node ID')
        metrics_parser.add_argument('--export', action='store_true', help='Export metrics to file')
        metrics_parser.add_argument('--format', choices=['json', 'csv'], help='Export format')
        metrics_parser.add_argument('--output', help='Output directory')
        metrics_parser.set_defaults(func=self.cmd_metrics)
        
        # Capacity command
        capacity_parser = subparsers.add_parser('capacity', help='Show capacity information')
        capacity_parser.add_argument('--report', action='store_true', help='Generate full capacity report')
        capacity_parser.set_defaults(func=self.cmd_capacity)
        
        # Network command
        network_parser = subparsers.add_parser('network', help='Manage network service (start/stop/status)')
        network_parser.add_argument('action', choices=['start', 'stop', 'status'], 
                                   help='Network action: start, stop, or status')
        network_parser.set_defaults(func=self.cmd_network)
        
        return parser
    
    def run(self, args=None):
        """
        Run CLI with arguments
        
        Args:
            args: Command-line arguments (None = use sys.argv)
        """
        parser = self.create_parser()
        parsed_args = parser.parse_args(args)
        
        if not parsed_args.command:
            parser.print_help()
            return
        
        # Setup components
        self.setup()
        
        # Execute command
        if hasattr(parsed_args, 'func'):
            try:
                parsed_args.func(parsed_args)
            except Exception as e:
                print(f"Error: {e}", file=sys.stderr)
                sys.exit(1)
        else:
            parser.print_help()


def main():
    """Main entry point for CLI"""
    cli = CloudSimCLI()
    cli.run()


if __name__ == "__main__":
    main()

