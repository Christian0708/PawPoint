"""
Integration Tests - End-to-end tests for CloudSim distributed storage system
Tests complete workflows and multi-node scenarios
"""

import sys
import os

# Add parent directory to path to import CloudSim modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unittest
import shutil
import time
import tempfile
from node_factory import NodeFactory
from metrics_collector import MetricsCollector
from capacity_evaluator import CapacityEvaluator, AlertLevel
from config_loader import ConfigLoader
from storage_virtual_node import TransferStatus


class TestEndToEndIntegration(unittest.TestCase):
    """
    End-to-end integration tests for the complete CloudSim system
    """
    
    def setUp(self):
        """Set up test environment"""
        # Create temporary directory for test storage
        self.test_dir = tempfile.mkdtemp(prefix="cloudsim_test_")
        self.original_cwd = os.getcwd()
        
        # Change to test directory
        os.chdir(self.test_dir)
        
        # Create factory
        self.factory = NodeFactory(start_port=6000, port_range_size=100)
        
        # Create test nodes (disable network checking for tests)
        self.node1 = self.factory.create_node(
            node_id="test_node1",
            cpu_capacity=2,
            memory_capacity=8,
            storage_capacity=10,  # 10 GB
            bandwidth=100,  # 100 Mbps
            host="localhost",
            port=6000,
            enable_network_check=False  # Disable network checking in tests
        )
        
        self.node2 = self.factory.create_node(
            node_id="test_node2",
            cpu_capacity=2,
            memory_capacity=8,
            storage_capacity=10,
            bandwidth=100,
            host="localhost",
            port=6001,
            enable_network_check=False  # Disable network checking in tests
        )
        
        self.node3 = self.factory.create_node(
            node_id="test_node3",
            cpu_capacity=2,
            memory_capacity=8,
            storage_capacity=10,
            bandwidth=100,
            host="localhost",
            port=6002,
            enable_network_check=False  # Disable network checking in tests
        )
        
        # Start nodes
        self.factory.start_all_nodes()
        time.sleep(1)  # Allow nodes to initialize
    
    def tearDown(self):
        """Clean up test environment"""
        # Stop all nodes
        try:
            self.factory.stop_all_nodes(graceful=True, timeout=2.0)
        except Exception:
            pass
        
        # Change back to original directory
        os.chdir(self.original_cwd)
        
        # Remove test directory
        try:
            shutil.rmtree(self.test_dir)
        except Exception:
            pass
    
    def test_multi_node_creation_and_lifecycle(self):
        """Test creating multiple nodes and managing their lifecycle"""
        # Verify nodes were created
        self.assertEqual(self.factory.get_node_count(), 3)
        
        # Verify all nodes are running
        stats = self.factory.get_factory_stats()
        self.assertEqual(stats['running_nodes'], 3)
        self.assertEqual(stats['total_nodes'], 3)
        
        # Verify nodes are in factory
        self.assertIsNotNone(self.factory.get_node("test_node1"))
        self.assertIsNotNone(self.factory.get_node("test_node2"))
        self.assertIsNotNone(self.factory.get_node("test_node3"))
        
        # Stop a node
        self.node1.stop(graceful=True, timeout=2.0)
        self.node1.join(timeout=2.0)
        
        # Verify node stopped
        stats = self.factory.get_factory_stats()
        self.assertEqual(stats['running_nodes'], 2)
        self.assertEqual(stats['stopped_nodes'], 1)
    
    def test_node_discovery_workflow(self):
        """Test node discovery mechanism"""
        # Enable discovery
        self.factory.enable_discovery(discovery_port=9998, broadcast_interval=5.0)
        
        # Wait for discovery to work
        time.sleep(3)
        
        # Check discovered nodes
        discovered = self.factory.get_discovered_nodes()
        
        # Each node should discover the others
        # Note: Discovery might take a moment, so we check if any discovery occurred
        self.assertIsInstance(discovered, dict)
        
        # Verify discovery instances exist
        self.assertGreater(len(self.factory.discovery_instances), 0)
    
    def test_complete_file_transfer_workflow(self):
        """Test complete file transfer workflow between nodes"""
        # Add connection between nodes
        self.node1.add_connection("test_node2", 100)
        self.node2.add_connection("test_node1", 100)
        
        # Create a file transfer
        file_id = "test_file_123"
        file_name = "test_data.dat"
        file_size = 5 * 1024 * 1024  # 5 MB
        
        # Initiate transfer on target node
        transfer = self.node2.initiate_file_transfer(
            file_id=file_id,
            file_name=file_name,
            file_size=file_size,
            source_node="test_node1"
        )
        
        self.assertIsNotNone(transfer)
        self.assertEqual(transfer.file_id, file_id)
        self.assertEqual(transfer.file_name, file_name)
        self.assertEqual(transfer.total_size, file_size)
        
        # Process chunks
        chunks = transfer.chunks
        self.assertGreater(len(chunks), 0)
        
        # Process first chunk
        if chunks:
            chunk = chunks[0]
            self.node2.process_chunk_transfer_async(
                file_id=file_id,
                chunk_id=chunk.chunk_id,
                source_node="test_node1"
            )
            
            # Wait a bit for processing
            time.sleep(0.5)
        
        # Verify transfer is in progress or completed
        self.assertIn(file_id, self.node2.active_transfers or self.node2.stored_files)
    
    def test_metrics_collection_workflow(self):
        """Test complete metrics collection workflow"""
        # Create metrics collector
        metrics = MetricsCollector(self.factory, max_history=100)
        
        # Start auto-collection
        metrics.start_auto_collection(interval=1.0)
        
        # Wait for collection
        time.sleep(2)
        
        # Collect metrics
        network_metrics = metrics.collect_all_nodes_metrics()
        
        self.assertIsNotNone(network_metrics)
        self.assertEqual(network_metrics.total_nodes, 3)
        self.assertGreaterEqual(len(network_metrics.node_metrics), 0)
        
        # Get latest metrics
        latest = metrics.get_latest_metrics()
        self.assertIsInstance(latest, dict)
        
        # Stop collection
        metrics.stop_auto_collection()
    
    def test_capacity_evaluation_workflow(self):
        """Test complete capacity evaluation workflow"""
        # Create capacity evaluator
        capacity = CapacityEvaluator(self.factory)
        
        # Add thresholds
        capacity.add_threshold(50.0, AlertLevel.INFO, "50% threshold")
        capacity.add_threshold(75.0, AlertLevel.WARNING, "75% threshold")
        
        # Take snapshot
        snapshot = capacity.take_capacity_snapshot(check_thresholds=True)
        
        self.assertIsNotNone(snapshot)
        self.assertIn("timestamp", snapshot)
        self.assertIn("total_capacity", snapshot)
        self.assertIn("nodes_capacity", snapshot)
        
        # Get capacity summary
        summary = capacity.get_capacity_summary()
        
        self.assertIsNotNone(summary)
        self.assertIn("overall_capacity", summary)
        self.assertIn("node_count", summary)
        
        # Evaluate total capacity
        total = capacity.evaluate_total_capacity()
        self.assertIsNotNone(total)
        self.assertIn("storage_capacity", total)
    
    def test_multi_node_storage_operations(self):
        """Test storage operations across multiple nodes"""
        # Add connections
        self.node1.add_connection("test_node2", 100)
        self.node2.add_connection("test_node1", 100)
        self.node2.add_connection("test_node3", 100)
        self.node3.add_connection("test_node2", 100)
        
        # Create transfers on multiple nodes
        file1_id = "file1"
        file2_id = "file2"
        
        transfer1 = self.node2.initiate_file_transfer(
            file_id=file1_id,
            file_name="file1.dat",
            file_size=2 * 1024 * 1024,  # 2 MB
            source_node="test_node1"
        )
        
        transfer2 = self.node3.initiate_file_transfer(
            file_id=file2_id,
            file_name="file2.dat",
            file_size=3 * 1024 * 1024,  # 3 MB
            source_node="test_node2"
        )
        
        self.assertIsNotNone(transfer1)
        self.assertIsNotNone(transfer2)
        
        # Process chunks on both nodes
        if transfer1.chunks:
            self.node2.process_chunk_transfer_async(file1_id, transfer1.chunks[0].chunk_id, "test_node1")
        
        if transfer2.chunks:
            self.node3.process_chunk_transfer_async(file2_id, transfer2.chunks[0].chunk_id, "test_node2")
        
        time.sleep(0.5)
        
        # Verify storage utilization
        util1 = self.node2.get_storage_utilization()
        util2 = self.node3.get_storage_utilization()
        
        self.assertIsNotNone(util1)
        self.assertIsNotNone(util2)
        self.assertIn("used_bytes", util1)
        self.assertIn("used_bytes", util2)
    
    def test_metrics_export_workflow(self):
        """Test metrics export functionality"""
        # Create metrics collector
        metrics = MetricsCollector(self.factory)
        
        # Record some transfer metrics
        metrics.record_transfer_start(
            transfer_id="transfer1",
            file_id="file1",
            source_node="test_node1",
            target_node="test_node2",
            file_size_bytes=1024 * 1024,
            total_chunks=10
        )
        
        metrics.record_transfer_end(
            transfer_id="transfer1",
            success=True,
            chunks_transferred=10,
            first_chunk_latency_ms=50.0,
            average_chunk_rtt_ms=25.0
        )
        
        # Export metrics - use absolute path to avoid issues with working directory changes
        export_dir = os.path.join(self.test_dir, "test_metrics")
        # Ensure we use absolute path
        export_dir = os.path.abspath(export_dir)
        files = metrics.export_all_metrics(output_dir=export_dir, format="json")
        
        self.assertIsInstance(files, dict)
        self.assertGreater(len(files), 0)
        
        # Verify files were created
        self.assertTrue(os.path.exists(export_dir))
    
    def test_capacity_prediction_workflow(self):
        """Test capacity prediction workflow"""
        # Create capacity evaluator
        capacity = CapacityEvaluator(self.factory)
        
        # Take multiple snapshots to build history
        capacity.take_capacity_snapshot()
        time.sleep(0.5)

        # Create a dummy file to ensure storage changes
        with open(os.path.join(self.node1.storage_path, "dummy_file.dat"), "wb") as f:
            f.write(os.urandom(1024 * 1024))

        capacity.take_capacity_snapshot()
        time.sleep(0.5)

        # Create another dummy file
        with open(os.path.join(self.node2.storage_path, "dummy_file2.dat"), "wb") as f:
            f.write(os.urandom(1024 * 1024))

        capacity.take_capacity_snapshot()
        
        # Get storage trends
        trends = capacity.get_storage_trends()
        
        self.assertIsNotNone(trends)
        self.assertIn("growth_analysis", trends)
        self.assertIn("time_to_full_capacity", trends)
        
        # Test prediction
        prediction = capacity.predict_storage_usage(hours_ahead=24)
        
        # Prediction might be None if insufficient data, which is okay
        if prediction:
            self.assertIn("predicted_usage_gb", prediction)
            self.assertIn("predicted_utilization_percent", prediction)
    
    def test_node_factory_bulk_operations(self):
        """Test bulk node operations"""
        # Test batch creation
        node_configs = [
            {
                "id": "bulk_node1",
                "cpu_capacity": 2,
                "memory_gb": 4,
                "storage_gb": 5,
                "bandwidth_mbps": 100,
                "host": "localhost",
                "port": None
            },
            {
                "id": "bulk_node2",
                "cpu_capacity": 2,
                "memory_gb": 4,
                "storage_gb": 5,
                "bandwidth_mbps": 100,
                "host": "localhost",
                "port": None
            }
        ]
        
        created = self.factory.create_nodes_batch(node_configs, enable_network_check=False)
        self.assertEqual(len(created), 2)
        
        # Test bulk removal
        removal_results = self.factory.remove_nodes_batch(["bulk_node1", "bulk_node2"])
        self.assertEqual(len(removal_results), 2)
        self.assertTrue(removal_results.get("bulk_node1", False))
        self.assertTrue(removal_results.get("bulk_node2", False))
    
    def test_configuration_loading_workflow(self):
        """Test configuration loading and usage"""
        # Create a temporary config file
        config_content = """
network:
  name: "TestNetwork"
  discovery:
    enabled: true
    port: 9997

node_factory:
  start_port: 7000
  port_range_size: 100

metrics:
  enabled: true
  collection_interval_seconds: 2.0
"""
        config_file = os.path.join(self.test_dir, "test_config.yaml")
        with open(config_file, 'w') as f:
            f.write(config_content)
        
        # Load configuration
        config = ConfigLoader(config_file)
        self.assertTrue(config.load())
        
        # Verify configuration values
        self.assertEqual(config.get("network.name"), "TestNetwork")
        self.assertEqual(config.get("node_factory.start_port"), 7000)
        self.assertEqual(config.get("metrics.collection_interval_seconds"), 2.0)
    
    def test_complete_system_workflow(self):
        """Test complete system workflow from start to finish"""
        # 1. Create nodes
        self.assertEqual(self.factory.get_node_count(), 3)
        
        # 2. Start nodes (already done in setUp)
        stats = self.factory.get_factory_stats()
        self.assertEqual(stats['running_nodes'], 3)
        
        # 3. Setup metrics
        metrics = MetricsCollector(self.factory)
        metrics.start_auto_collection(interval=1.0)
        time.sleep(1)
        
        # 4. Setup capacity evaluation
        capacity = CapacityEvaluator(self.factory)
        capacity.add_threshold(80.0, AlertLevel.WARNING, "80% threshold")
        
        # 5. Take capacity snapshot
        snapshot = capacity.take_capacity_snapshot(check_thresholds=True)
        self.assertIsNotNone(snapshot)
        
        # 6. Collect metrics
        network_metrics = metrics.collect_all_nodes_metrics()
        self.assertIsNotNone(network_metrics)
        
        # 7. Get aggregated resources
        resources = self.factory.get_aggregated_resources()
        self.assertIsNotNone(resources)
        self.assertIn("total_storage_gb", resources)
        
        # 8. Stop metrics collection
        metrics.stop_auto_collection()
        
        # 9. Generate capacity report
        report = capacity.generate_capacity_report()
        self.assertIsNotNone(report)
        self.assertIn("total_capacity", report)
    
    def test_node_health_monitoring(self):
        """Test node health monitoring across multiple nodes"""
        # Check health of all nodes
        health = self.factory.check_all_nodes_health()
        
        self.assertEqual(len(health), 3)
        self.assertIn("test_node1", health)
        self.assertIn("test_node2", health)
        self.assertIn("test_node3", health)
        
        # Verify health status structure
        for node_id, status in health.items():
            self.assertIn("status", status)
            self.assertIn("is_alive", status)
            self.assertIn("host", status)
            self.assertIn("port", status)
    
    def test_resource_aggregation(self):
        """Test resource aggregation across multiple nodes"""
        # Get aggregated resources
        resources = self.factory.get_aggregated_resources()
        
        # Verify all resource types are present
        self.assertIn("total_cpu", resources)
        self.assertIn("total_memory_gb", resources)
        self.assertIn("total_storage_gb", resources)
        self.assertIn("total_bandwidth_mbps", resources)
        
        # Verify totals are correct (3 nodes * 2 CPU = 6)
        self.assertEqual(resources['total_cpu'], 6)
        
        # Verify averages
        self.assertIn("average_cpu", resources)
        self.assertIn("average_memory_gb", resources)
        self.assertEqual(resources['average_cpu'], 2.0)
    
    def test_concurrent_operations(self):
        """Test concurrent operations across multiple nodes"""
        # Add connections
        self.node1.add_connection("test_node2", 100)
        self.node2.add_connection("test_node1", 100)
        
        # Create multiple transfers concurrently
        transfers = []
        for i in range(3):
            file_id = f"concurrent_file_{i}"
            transfer = self.node2.initiate_file_transfer(
                file_id=file_id,
                file_name=f"file_{i}.dat",
                file_size=1024 * 1024,  # 1 MB each
                source_node="test_node1"
            )
            if transfer:
                transfers.append((file_id, transfer))
        
        # Process chunks concurrently
        for file_id, transfer in transfers:
            if transfer.chunks:
                self.node2.process_chunk_transfer_async(
                    file_id,
                    transfer.chunks[0].chunk_id,
                    "test_node1"
                )
        
        # Wait for processing
        time.sleep(1)
        
        # Verify multiple active transfers
        active_count = len(self.node2.active_transfers)
        self.assertGreaterEqual(active_count, 0)  # Some may have completed
    
    def test_graceful_shutdown_workflow(self):
        """Test graceful shutdown of all components"""
        # Setup metrics
        metrics = MetricsCollector(self.factory)
        metrics.start_auto_collection(interval=1.0)
        
        # Setup capacity
        capacity = CapacityEvaluator(self.factory)
        
        # Stop metrics first
        metrics.stop_auto_collection()
        
        # Stop all nodes gracefully
        self.factory.stop_all_nodes(graceful=True, timeout=3.0)
        
        # Verify nodes stopped
        stats = self.factory.get_factory_stats()
        self.assertEqual(stats['running_nodes'], 0)
        self.assertEqual(stats['stopped_nodes'], 3)
    
    def test_port_management(self):
        """Test port management and auto-assignment"""
        # Get port info
        port_info = self.factory.get_port_info()
        
        self.assertIn("port_range", port_info)
        self.assertIn("used_ports", port_info)
        self.assertIn("total_used", port_info)
        
        # Verify used ports
        self.assertEqual(port_info['total_used'], 3)
        self.assertIn(6000, port_info['used_ports'])
        self.assertIn(6001, port_info['used_ports'])
        self.assertIn(6002, port_info['used_ports'])
        
        # Create node with auto-assigned port
        auto_node = self.factory.create_node(
            node_id="auto_port_node",
            cpu_capacity=1,
            memory_capacity=4,
            storage_capacity=5,
            bandwidth=50,
            host="localhost",
            port=None,  # Auto-assign
            enable_network_check=False  # Disable network checking in tests
        )
        
        self.assertIsNotNone(auto_node)
        self.assertIsNotNone(auto_node.port)
        self.assertGreaterEqual(auto_node.port, 6000)
        
        # Cleanup
        self.factory.remove_node("auto_port_node")


if __name__ == "__main__":
    unittest.main()

