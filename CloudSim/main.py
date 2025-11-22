"""
CloudSim Distributed Storage System - Main Entry Point
Demonstrates all features of the distributed storage system

This example shows:
- Node creation using NodeFactory
- Configuration management
- Metrics collection
- Capacity evaluation
- Node discovery
- File transfers with real storage
- Performance monitoring
"""

import time
import sys
from config_loader import ConfigLoader
from node_factory import NodeFactory
from metrics_collector import MetricsCollector, MetricType
from capacity_evaluator import CapacityEvaluator, AlertLevel
from logger import CloudSimLogger, get_logger


def main():
    """
    Main demonstration of CloudSim distributed storage system
    """
    print("="*80)
    print("CloudSim Distributed Storage System - Real-World Example")
    print("="*80)
    print()
    
    # Setup logging
    config = ConfigLoader("config.yaml")
    config.load()
    CloudSimLogger.setup_logging(config)
    logger = get_logger("CloudSim.main")
    logger.info("Starting CloudSim demonstration")
    
    # ============================================================================
    # Step 1: Initialize System Components
    # ============================================================================
    print("Step 1: Initializing system components...")
    
    # Create NodeFactory with configuration
    start_port = config.get("node_factory.start_port", 5000)
    port_range = config.get("node_factory.port_range_size", 1000)
    factory = NodeFactory(start_port=start_port, port_range_size=port_range)
    
    # Create MetricsCollector
    metrics = MetricsCollector(factory, max_history=1000)
    
    # Create CapacityEvaluator
    capacity = CapacityEvaluator(factory)
    
    print("✓ System components initialized")
    print()
    
    # ============================================================================
    # Step 2: Create Nodes from Configuration
    # ============================================================================
    print("Step 2: Creating nodes from configuration...")
    
    nodes_config_file = config.get("nodes.config_file", "nodes_config.json")
    created_nodes = factory.create_nodes_from_config(nodes_config_file)
    
    if not created_nodes:
        print("✗ No nodes created. Please check nodes_config.json")
        sys.exit(1)
    
    print(f"✓ Created {len(created_nodes)} nodes:")
    for node in created_nodes:
        config_data = factory.node_configs.get(node.node_id, {})
        print(f"  - {node.node_id}: {config_data.get('host', 'unknown')}:{config_data.get('port', 'unknown')}")
    print()
    
    # ============================================================================
    # Step 3: Enable Node Discovery
    # ============================================================================
    print("Step 3: Enabling node discovery...")
    
    discovery_enabled = config.get("network.discovery.enabled", True)
    if discovery_enabled:
        discovery_port = config.get("network.discovery.port", 9999)
        broadcast_interval = config.get("network.discovery.broadcast_interval_seconds", 30.0)
        factory.enable_discovery(discovery_port=discovery_port, broadcast_interval=broadcast_interval)
        print(f"✓ Node discovery enabled on port {discovery_port}")
    else:
        print("○ Node discovery disabled in configuration")
    print()
    
    # ============================================================================
    # Step 4: Start All Nodes
    # ============================================================================
    print("Step 4: Starting all nodes...")
    
    factory.start_all_nodes()
    print("✓ All nodes started")
    
    # Wait a moment for nodes to initialize
    time.sleep(2)
    print()
    
    # ============================================================================
    # Step 5: Setup Capacity Evaluation
    # ============================================================================
    print("Step 5: Setting up capacity evaluation...")
    
    # Configure capacity thresholds from config
    capacity_thresholds = config.get("capacity.thresholds.global", [])
    for threshold in capacity_thresholds:
        percent = threshold.get("percent", 0)
        level_str = threshold.get("level", "INFO")
        level = getattr(AlertLevel, level_str.upper(), AlertLevel.INFO)
        description = threshold.get("description", "")
        capacity.add_threshold(percent, level, description)
    
    print(f"✓ Configured {len(capacity_thresholds)} capacity thresholds")
    print()
    
    # ============================================================================
    # Step 6: Start Metrics Collection
    # ============================================================================
    print("Step 6: Starting metrics collection...")
    
    metrics_enabled = config.get("metrics.enabled", True)
    if metrics_enabled:
        collection_interval = config.get("metrics.collection_interval_seconds", 5.0)
        metrics.start_auto_collection(interval=collection_interval)
        print(f"✓ Metrics collection started (interval: {collection_interval}s)")
    else:
        print("○ Metrics collection disabled in configuration")
    print()
    
    # ============================================================================
    # Step 7: Display Initial System Status
    # ============================================================================
    print("Step 7: Initial system status...")
    print("-" * 80)
    
    # Factory stats
    factory_stats = factory.get_factory_stats()
    print(f"Total Nodes: {factory_stats['total_nodes']}")
    print(f"Running: {factory_stats['running_nodes']}")
    print(f"Stopped: {factory_stats['stopped_nodes']}")
    
    # Resource summary
    resources = factory.get_aggregated_resources()
    print(f"\nTotal Resources:")
    print(f"  CPU: {resources['total_cpu']} vCPUs")
    print(f"  Memory: {resources['total_memory_gb']} GB")
    print(f"  Storage: {resources['total_storage_gb']} GB")
    print(f"  Bandwidth: {resources['total_bandwidth_mbps']} Mbps")
    print(f"\nStorage Utilization: {resources['storage_utilization_percent']:.2f}%")
    print()
    
    # ============================================================================
    # Step 8: Demonstrate File Transfer (if nodes are available)
    # ============================================================================
    print("Step 8: Demonstrating file transfer capabilities...")
    print("-" * 80)
    
    if len(created_nodes) >= 2:
        source_node = created_nodes[0]
        target_node = created_nodes[1]
        
        print(f"Source: {source_node.node_id}")
        print(f"Target: {target_node.node_id}")
        
        # Simulate a file transfer
        file_size = 10 * 1024 * 1024  # 10MB
        file_name = "demo_file.dat"
        
        # This would normally be done through the network manager
        # For demonstration, we'll show the concept
        print(f"\nSimulating transfer of {file_name} ({file_size / (1024*1024):.2f} MB)...")
        print("(In a real scenario, this would use NetworkManager for actual transfer)")
        print()
    else:
        print("○ Need at least 2 nodes for file transfer demonstration")
        print()
    
    # ============================================================================
    # Step 9: Monitor Metrics
    # ============================================================================
    print("Step 9: Collecting metrics...")
    print("-" * 80)
    
    # Collect metrics from all nodes
    network_metrics = metrics.collect_all_nodes_metrics()
    print(f"Network Metrics (timestamp: {network_metrics.timestamp}):")
    print(f"  Total Throughput: {network_metrics.total_throughput_mbps:.2f} Mbps")
    print(f"  Average Latency: {network_metrics.average_latency_ms:.2f} ms")
    print(f"  Total Transfers: {network_metrics.total_transfers}")
    print(f"  Storage Utilization: {network_metrics.total_storage_utilization_percent:.2f}%")
    print()
    
    # ============================================================================
    # Step 10: Capacity Evaluation
    # ============================================================================
    print("Step 10: Evaluating capacity...")
    print("-" * 80)
    
    # Take capacity snapshot
    snapshot = capacity.take_capacity_snapshot(check_thresholds=True)
    print(f"✓ Capacity snapshot taken")
    
    # Get capacity summary
    summary = capacity.get_capacity_summary()
    print(f"\nCapacity Summary:")
    print(f"  Total Nodes: {summary['node_count']}")
    print(f"  Average Utilization: {summary['utilization_statistics']['average_utilization']:.2f}%")
    
    highest = summary['utilization_statistics']['highest_utilization']
    if highest['node_id']:
        print(f"  Highest Utilization: {highest['node_id']} at {highest['utilization_percent']:.2f}%")
    print()
    
    # ============================================================================
    # Step 11: Check Discovered Nodes
    # ============================================================================
    if discovery_enabled:
        print("Step 11: Checking discovered nodes...")
        print("-" * 80)
        
        # Wait a bit for discovery to work
        time.sleep(3)
        
        discovered = factory.get_discovered_nodes()
        for node_id, discovery_info in discovered.items():
            discovered_nodes = discovery_info.get('discovered_nodes', [])
            if discovered_nodes:
                print(f"Node {node_id} discovered:")
                for disc_node in discovered_nodes:
                    print(f"  - {disc_node['node_id']} at {disc_node['host']}:{disc_node['port']}")
        print()
    
    # ============================================================================
    # Step 12: Display Final Statistics
    # ============================================================================
    print("Step 12: Final system statistics...")
    print("-" * 80)
    
    # Factory stats
    final_stats = factory.get_factory_stats()
    print(f"Nodes: {final_stats['total_nodes']} total, {final_stats['running_nodes']} running")
    
    # Resource summary
    final_resources = factory.get_aggregated_resources()
    print(f"Storage: {final_resources['used_storage_gb']:.2f} GB / {final_resources['total_storage_gb']:.2f} GB")
    print(f"Utilization: {final_resources['storage_utilization_percent']:.2f}%")
    
    # Port info
    port_info = factory.get_port_info()
    print(f"Ports: {port_info['total_used']} used in range {port_info['port_range']}")
    print()
    
    # ============================================================================
    # Step 13: Export Metrics (if enabled)
    # ============================================================================
    metrics_auto_export = config.get("metrics.auto_export", False)
    if metrics_auto_export:
        print("Step 13: Exporting metrics...")
        print("-" * 80)
        
        export_dir = config.get("metrics.export_directory", "metrics")
        export_format = config.get("metrics.export_format", "json")
        
        exported_files = metrics.export_all_metrics(output_dir=export_dir, format=export_format)
        print(f"✓ Exported {len(exported_files)} metric files to {export_dir}/")
        print()
    
    # ============================================================================
    # Step 14: Generate Capacity Report
    # ============================================================================
    print("Step 14: Generating capacity report...")
    print("-" * 80)
    
    report = capacity.generate_capacity_report(
        include_predictions=True,
        include_alerts=True,
        include_history=False
    )
    
    print("Capacity Report Summary:")
    storage_cap = report['total_capacity']['storage_capacity']
    print(f"  Total Storage: {storage_cap['total_gb']} GB")
    print(f"  Used: {storage_cap['used_gb']} GB")
    print(f"  Available: {storage_cap['available_gb']} GB")
    print(f"  Utilization: {storage_cap['utilization_percent']:.2f}%")
    
    if 'alerts' in report and report['alerts']['summary']['total_alerts'] > 0:
        alert_summary = report['alerts']['summary']
        print(f"\n  Alerts: {alert_summary['total_alerts']} total")
        print(f"    Critical: {alert_summary['critical_count']}")
        print(f"    Warning: {alert_summary['warning_count']}")
    print()
    
    # ============================================================================
    # Cleanup and Shutdown
    # ============================================================================
    print("="*80)
    print("Demonstration complete!")
    print("="*80)
    print()
    print("To keep the system running, comment out the shutdown section below.")
    print("Or use the CLI to manage nodes: python -m CloudSim.cli --help")
    print()
    
    # Uncomment the following lines to automatically shut down:
    # print("Shutting down system...")
    # metrics.stop_auto_collection()
    # factory.stop_all_nodes(graceful=True, timeout=5.0)
    # print("✓ System shut down")
    
    logger.info("CloudSim demonstration completed")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n\nError: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
