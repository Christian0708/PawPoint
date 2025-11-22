"""
CLI - Command-line interface for CloudSim distributed storage system
Provides commands for managing nodes, monitoring metrics, and system operations
"""

import argparse
import sys
from typing import Optional
from config_loader import ConfigLoader
from node_factory import NodeFactory
from metrics_collector import MetricsCollector
from capacity_evaluator import CapacityEvaluator
from logger import CloudSimLogger, get_logger


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
        
        self.logger.info("CLI components initialized")
    
    def cmd_start(self, args):
        """Start nodes command"""
        if not self.factory:
            self.setup()
        
        if args.nodes:
            # Start specific nodes
            for node_id in args.nodes:
                node = self.factory.get_node(node_id)
                if node:
                    if not node.is_alive():
                        node.start()
                        print(f"Started node: {node_id}")
                    else:
                        print(f"Node {node_id} is already running")
                else:
                    print(f"Node {node_id} not found")
        else:
            # Start all nodes
            self.factory.start_all_nodes()
            print("All nodes started")
    
    def cmd_stop(self, args):
        """Stop nodes command"""
        if not self.factory:
            self.setup()
        
        if args.nodes:
            # Stop specific nodes
            for node_id in args.nodes:
                node = self.factory.get_node(node_id)
                if node:
                    node.stop(graceful=args.graceful, timeout=args.timeout)
                    node.join(timeout=3.0)
                    print(f"Stopped node: {node_id}")
                else:
                    print(f"Node {node_id} not found")
        else:
            # Stop all nodes
            self.factory.stop_all_nodes(graceful=args.graceful, timeout=args.timeout)
            print("All nodes stopped")
    
    def cmd_status(self, args):
        """Status command"""
        if not self.factory:
            self.setup()
        
        if args.node:
            # Status of specific node
            node = self.factory.get_node(args.node)
            if node:
                is_running = node.is_alive() or node.running
                storage_util = node.get_storage_utilization() if is_running else {}
                print(f"\nNode: {args.node}")
                print(f"Status: {'Running' if is_running else 'Stopped'}")
                print(f"Storage: {storage_util.get('utilization_percent', 0):.2f}%")
                print(f"Files: {storage_util.get('files_stored', 0)}")
            else:
                print(f"Node {args.node} not found")
        else:
            # Status of all nodes
            stats = self.factory.get_factory_stats()
            print(f"\nTotal Nodes: {stats['total_nodes']}")
            print(f"Running: {stats['running_nodes']}")
            print(f"Stopped: {stats['stopped_nodes']}")
            print(f"\nNode IDs: {', '.join(stats['node_ids'])}")
    
    def cmd_list(self, args):
        """List nodes command"""
        if not self.factory:
            self.setup()
        
        nodes = self.factory.get_all_nodes()
        if not nodes:
            print("No nodes found")
            return
        
        print(f"\n{'Node ID':<15} {'Status':<10} {'Host':<15} {'Port':<10}")
        print("-" * 50)
        
        for node in nodes:
            node_id = node.node_id
            is_running = node.is_alive() or node.running
            status = "Running" if is_running else "Stopped"
            host = node.host
            port = node.port
            
            print(f"{node_id:<15} {status:<10} {host:<15} {port:<10}")
    
    def cmd_info(self, args):
        """Info command"""
        if not self.factory:
            self.setup()
        
        if args.node:
            # Info for specific node
            node = self.factory.get_node(args.node)
            if not node:
                print(f"Node {args.node} not found")
                return
            
            config = self.factory.node_configs.get(args.node, {})
            storage_util = node.get_storage_utilization() if (node.is_alive() or node.running) else {}
            network_util = node.get_network_utilization() if (node.is_alive() or node.running) else {}
            
            print(f"\n=== Node Information: {args.node} ===")
            print(f"Host: {config.get('host', 'unknown')}")
            print(f"Port: {config.get('port', 'unknown')}")
            print(f"Status: {'Running' if (node.is_alive() or node.running) else 'Stopped'}")
            print(f"\nResources:")
            print(f"  CPU: {config.get('cpu_capacity', 0)} vCPUs")
            print(f"  Memory: {config.get('memory_capacity', 0)} GB")
            print(f"  Storage: {config.get('storage_capacity', 0)} GB")
            print(f"  Bandwidth: {config.get('bandwidth', 0) / 1000000 if config.get('bandwidth') else 0} Mbps")
            print(f"\nUtilization:")
            print(f"  Storage: {storage_util.get('utilization_percent', 0):.2f}%")
            print(f"  Network: {network_util.get('utilization_percent', 0):.2f}%")
        else:
            # System info
            stats = self.factory.get_factory_stats()
            resources = self.factory.get_aggregated_resources()
            
            print(f"\n=== System Information ===")
            print(f"Total Nodes: {stats['total_nodes']}")
            print(f"Running Nodes: {stats['running_nodes']}")
            print(f"\nTotal Resources:")
            print(f"  CPU: {resources['total_cpu']} vCPUs")
            print(f"  Memory: {resources['total_memory_gb']} GB")
            print(f"  Storage: {resources['total_storage_gb']} GB")
            print(f"  Bandwidth: {resources['total_bandwidth_mbps']} Mbps")
            print(f"\nStorage Utilization: {resources['storage_utilization_percent']:.2f}%")
    
    def cmd_create(self, args):
        """Create nodes command"""
        if not self.factory:
            self.setup()
        
        config_file = self.config.get("nodes.config_file", "nodes_config.json")
        nodes = self.factory.create_nodes_from_config(config_file)
        
        if nodes:
            print(f"Created {len(nodes)} nodes")
            if args.start:
                self.factory.start_all_nodes()
                print("All nodes started")
        else:
            print("No nodes created")
    
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
        start_parser.set_defaults(func=self.cmd_start)
        
        # Stop command
        stop_parser = subparsers.add_parser('stop', help='Stop nodes')
        stop_parser.add_argument('nodes', nargs='*', help='Node IDs to stop (all if not specified)')
        stop_parser.add_argument('--graceful', action='store_true', default=True, help='Graceful shutdown')
        stop_parser.add_argument('--timeout', type=float, default=5.0, help='Shutdown timeout in seconds')
        stop_parser.set_defaults(func=self.cmd_stop)
        
        # Status command
        status_parser = subparsers.add_parser('status', help='Show node status')
        status_parser.add_argument('--node', help='Specific node ID')
        status_parser.set_defaults(func=self.cmd_status)
        
        # List command
        list_parser = subparsers.add_parser('list', help='List all nodes')
        list_parser.set_defaults(func=self.cmd_list)
        
        # Info command
        info_parser = subparsers.add_parser('info', help='Show detailed information')
        info_parser.add_argument('--node', help='Specific node ID')
        info_parser.set_defaults(func=self.cmd_info)
        
        # Create command
        create_parser = subparsers.add_parser('create', help='Create nodes from config')
        create_parser.add_argument('--start', action='store_true', help='Start nodes after creation')
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

