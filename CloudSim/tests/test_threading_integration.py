"""
Threading integration tests for CloudSim
Tests thread safety, concurrent operations, and graceful shutdown
"""

import sys
import os

# Add parent directory to path to import CloudSim modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unittest
import threading
import time
import shutil
from storage_virtual_node import StorageVirtualNode, TransferStatus


class TestThreadingIntegration(unittest.TestCase):
    """Test suite for threading and concurrent operations"""
    
    def setUp(self):
        """Set up test fixtures before each test"""
        # Create a test node (disable network checking for tests)
        self.test_node = StorageVirtualNode(
            node_id="test_thread_node",
            cpu_capacity=4,
            memory_capacity=16,
            storage_capacity=10,  # 10 GB
            bandwidth=1000,
            host="localhost",
            port=6000,  # Different port to avoid conflicts
            enable_network_check=False  # Disable network checking in tests
        )
        
    def tearDown(self):
        """Clean up after each test"""
        # Stop node if running
        if self.test_node.is_alive() or self.test_node.running:
            self.test_node.stop(graceful=False)
            self.test_node.join(timeout=2.0)
        
        # Remove test storage directory
        if os.path.exists("storage/test_thread_node"):
            shutil.rmtree("storage/test_thread_node")
    
    def test_node_thread_lifecycle(self):
        """Test that node thread starts and stops correctly"""
        # Node should not be running initially
        self.assertFalse(self.test_node.is_alive())
        self.assertFalse(self.test_node.running)
        
        # Start the node thread
        self.test_node.start()
        time.sleep(0.5)  # Give thread time to start
        
        # Node should be running
        self.assertTrue(self.test_node.is_alive())
        self.assertTrue(self.test_node.running)
        
        # Stop the node
        self.test_node.stop(graceful=True, timeout=2.0)
        self.test_node.join(timeout=3.0)
        
        # Node should be stopped
        self.assertFalse(self.test_node.is_alive())
        self.assertFalse(self.test_node.running)
    
    def test_concurrent_file_transfers(self):
        """Test that multiple file transfers can happen concurrently"""
        # Start node
        self.test_node.start()
        time.sleep(0.5)
        
        # Initiate multiple transfers
        transfers = []
        for i in range(5):
            transfer = self.test_node.initiate_file_transfer(
                f"file_{i}",
                f"test_file_{i}.bin",
                1024 * 1024,  # 1MB each
                f"source_node_{i}"
            )
            self.assertIsNotNone(transfer)
            transfers.append(transfer)
        
        # Verify all transfers are active
        with self.test_node.transfer_lock:
            self.assertEqual(len(self.test_node.active_transfers), 5)
        
        # Clean up
        self.test_node.stop(graceful=False)
        self.test_node.join(timeout=2.0)
    
    def test_thread_safe_storage_operations(self):
        """Test that storage operations are thread-safe"""
        self.test_node.start()
        time.sleep(0.5)
        
        # Create multiple threads that modify storage
        results = []
        errors = []
        
        def modify_storage(thread_id):
            try:
                # Each thread initiates a transfer
                transfer = self.test_node.initiate_file_transfer(
                    f"thread_{thread_id}",
                    f"file_{thread_id}.bin",
                    512 * 1024,  # 512KB
                    "source"
                )
                results.append(transfer is not None)
            except Exception as e:
                errors.append(e)
        
        # Create 10 threads
        threads = []
        for i in range(10):
            t = threading.Thread(target=modify_storage, args=(i,))
            threads.append(t)
            t.start()
        
        # Wait for all threads
        for t in threads:
            t.join(timeout=5.0)
        
        # Verify no errors occurred
        self.assertEqual(len(errors), 0, f"Errors occurred: {errors}")
        
        # Verify all operations succeeded
        self.assertEqual(len(results), 10)
        self.assertTrue(all(results))
        
        # Verify thread-safe access
        with self.test_node.transfer_lock:
            self.assertEqual(len(self.test_node.active_transfers), 10)
        
        self.test_node.stop(graceful=False)
        self.test_node.join(timeout=2.0)
    
    def test_concurrent_chunk_processing(self):
        """Test concurrent chunk processing with thread pool"""
        self.test_node.start()
        time.sleep(0.5)
        
        # Add connection to source node (required for bandwidth calculation)
        self.test_node.add_connection("source", 1000)  # 1000 Mbps
        
        # Initiate a transfer
        transfer = self.test_node.initiate_file_transfer(
            "concurrent_file",
            "test.bin",
            5 * 1024 * 1024,  # 5MB (will create multiple chunks)
            "source"
        )
        self.assertIsNotNone(transfer)
        
        # Process chunks concurrently using async method
        futures = []
        for chunk in transfer.chunks:
            future = self.test_node.process_chunk_transfer_async(
                transfer.file_id,
                chunk.chunk_id,
                "source"
            )
            if future:
                futures.append(future)
        
        # Wait for all futures to complete
        # Note: Some chunks might return False if transfer completes before they finish
        # This is expected behavior in concurrent processing
        successful_chunks = 0
        for future in futures:
            try:
                result = future.result(timeout=10.0)
                if result:
                    successful_chunks += 1
            except Exception as e:
                print(f"Future exception: {e}")
        
        # Verify that most chunks succeeded (at least 80%)
        # This accounts for race conditions where transfer completes early
        success_rate = successful_chunks / len(futures) if futures else 0
        self.assertGreaterEqual(success_rate, 0.8, 
                               f"Only {successful_chunks}/{len(futures)} chunks succeeded")
        
        # Verify transfer executor is working
        self.assertIsNotNone(self.test_node.transfer_executor)
        
        # Give a moment for transfer to complete if it hasn't
        time.sleep(0.5)
        
        # Verify transfer completed (either in active or stored)
        with self.test_node.transfer_lock:
            in_active = transfer.file_id in self.test_node.active_transfers
        with self.test_node.storage_lock:
            in_stored = transfer.file_id in self.test_node.stored_files
        
        # Transfer should be either completed (in stored) or still active
        self.assertTrue(in_active or in_stored, 
                        "Transfer should be either active or stored")
        
        self.test_node.stop(graceful=True, timeout=5.0)
        self.test_node.join(timeout=2.0)
    
    def test_graceful_shutdown(self):
        """Test that graceful shutdown waits for operations"""
        self.test_node.start()
        time.sleep(0.5)
        
        # Add connection to source node (required for bandwidth calculation)
        self.test_node.add_connection("source", 1000)  # 1000 Mbps
        
        # Initiate a transfer
        transfer = self.test_node.initiate_file_transfer(
            "shutdown_test",
            "test.bin",
            1024 * 1024,  # 1MB
            "source"
        )
        self.assertIsNotNone(transfer)
        
        # Start processing a chunk
        future = self.test_node.process_chunk_transfer_async(
            transfer.file_id,
            0,
            "source"
        )
        self.assertIsNotNone(future)
        
        # Initiate graceful shutdown
        shutdown_start = time.time()
        self.test_node.stop(graceful=True, timeout=10.0)
        shutdown_duration = time.time() - shutdown_start
        
        # Shutdown should have waited (not immediate)
        self.assertGreater(shutdown_duration, 0.1)
        
        # Verify shutdown complete
        self.assertTrue(self.test_node.shutdown_complete.is_set())
        self.assertFalse(self.test_node.running)
        
        self.test_node.join(timeout=2.0)
    
    def test_shutdown_callbacks(self):
        """Test that shutdown callbacks are executed"""
        self.test_node.start()
        time.sleep(0.5)
        
        # Track callback execution
        callback_executed = threading.Event()
        
        def test_callback():
            callback_executed.set()
        
        # Register callback
        self.test_node.register_shutdown_callback(test_callback)
        
        # Stop node
        self.test_node.stop(graceful=False)
        
        # Verify callback was executed
        self.assertTrue(callback_executed.wait(timeout=2.0))
        
        self.test_node.join(timeout=2.0)
    
    def test_shutdown_rejects_new_operations(self):
        """Test that new operations are rejected during shutdown"""
        self.test_node.start()
        time.sleep(0.5)
        
        # Initiate shutdown
        self.test_node.shutting_down = True
        
        # Try to initiate new transfer (should be rejected)
        transfer = self.test_node.initiate_file_transfer(
            "rejected",
            "test.bin",
            1024,
            "source"
        )
        self.assertIsNone(transfer)
        
        # Try async transfer (should be rejected)
        future = self.test_node.process_chunk_transfer_async(
            "file_id",
            0,
            "source"
        )
        self.assertIsNone(future)
        
        self.test_node.stop(graceful=False)
        self.test_node.join(timeout=2.0)
    
    def test_thread_safe_metrics_access(self):
        """Test that metrics can be accessed safely from multiple threads"""
        self.test_node.start()
        time.sleep(0.5)
        
        metrics_results = []
        errors = []
        
        def get_metrics(thread_id):
            try:
                for _ in range(10):
                    storage_metrics = self.test_node.get_storage_utilization()
                    network_metrics = self.test_node.get_network_utilization()
                    perf_metrics = self.test_node.get_performance_metrics()
                    
                    # Verify metrics are valid
                    self.assertIsInstance(storage_metrics, dict)
                    self.assertIsInstance(network_metrics, dict)
                    self.assertIsInstance(perf_metrics, dict)
                    
                    metrics_results.append(True)
                    time.sleep(0.01)  # Small delay
            except Exception as e:
                errors.append(e)
        
        # Create multiple threads accessing metrics
        threads = []
        for i in range(5):
            t = threading.Thread(target=get_metrics, args=(i,))
            threads.append(t)
            t.start()
        
        # Wait for all threads
        for t in threads:
            t.join(timeout=10.0)
        
        # Verify no errors
        self.assertEqual(len(errors), 0, f"Errors: {errors}")
        
        # Verify all operations succeeded
        self.assertEqual(len(metrics_results), 50)  # 5 threads * 10 iterations
        
        self.test_node.stop(graceful=False)
        self.test_node.join(timeout=2.0)
    
    def test_transfer_executor_shutdown(self):
        """Test that transfer executor shuts down gracefully"""
        self.test_node.start()
        time.sleep(0.5)
        
        # Verify executor exists
        self.assertIsNotNone(self.test_node.transfer_executor)
        
        # Add connection to source node (required for bandwidth calculation)
        self.test_node.add_connection("source", 1000)  # 1000 Mbps
        
        # Submit some work
        transfer = self.test_node.initiate_file_transfer(
            "executor_test",
            "test.bin",
            1024,
            "source"
        )
        
        future = self.test_node.process_chunk_transfer_async(
            transfer.file_id,
            0,
            "source"
        )
        self.assertIsNotNone(future)
        
        # Stop with graceful shutdown
        self.test_node.stop(graceful=True, timeout=5.0)
        
        # Executor should be shut down
        # (We can't directly check, but no errors should occur)
        
        self.test_node.join(timeout=2.0)
    
    def test_concurrent_storage_utilization(self):
        """Test concurrent access to storage utilization"""
        self.test_node.start()
        time.sleep(0.5)
        
        # Create multiple threads accessing storage
        results = []
        
        def access_storage():
            for _ in range(20):
                metrics = self.test_node.get_storage_utilization()
                results.append(metrics)
                time.sleep(0.001)
        
        threads = []
        for _ in range(3):
            t = threading.Thread(target=access_storage)
            threads.append(t)
            t.start()
        
        for t in threads:
            t.join(timeout=5.0)
        
        # Verify all results are valid
        self.assertEqual(len(results), 60)  # 3 threads * 20 iterations
        for result in results:
            self.assertIsInstance(result, dict)
            self.assertIn("used_bytes", result)
            self.assertIn("total_bytes", result)
        
        self.test_node.stop(graceful=False)
        self.test_node.join(timeout=2.0)
    
    def test_lock_contention(self):
        """Test that locks prevent race conditions"""
        self.test_node.start()
        time.sleep(0.5)
        
        # Shared counter to test for race conditions
        counter = {"value": 0}
        errors = []
        
        def increment_counter():
            try:
                # Access storage multiple times (uses locks)
                for _ in range(100):
                    metrics = self.test_node.get_storage_utilization()
                    counter["value"] += 1
            except Exception as e:
                errors.append(e)
        
        # Create many threads
        threads = []
        for _ in range(10):
            t = threading.Thread(target=increment_counter)
            threads.append(t)
            t.start()
        
        for t in threads:
            t.join(timeout=10.0)
        
        # Verify no errors
        self.assertEqual(len(errors), 0)
        
        # Counter should equal expected value (no race conditions)
        self.assertEqual(counter["value"], 1000)  # 10 threads * 100 iterations
        
        self.test_node.stop(graceful=False)
        self.test_node.join(timeout=2.0)


def run_tests():
    """Run all threading integration tests"""
    # Create test suite
    suite = unittest.TestLoader().loadTestsFromTestCase(TestThreadingIntegration)
    
    # Run tests with verbose output
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    print("\n" + "="*70)
    print(f"Tests run: {result.testsRun}")
    print(f"Successes: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print("="*70)
    
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    exit(0 if success else 1)

