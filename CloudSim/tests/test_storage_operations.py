"""
Unit tests for file storage operations in CloudSim
Tests write, read, checksum verification, and disk space tracking
"""

import sys
import os

# Add parent directory to path to import CloudSim modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unittest
import shutil
import hashlib
from storage_virtual_node import StorageVirtualNode, TransferStatus


class TestStorageOperations(unittest.TestCase):
    """Test suite for storage operations"""
    
    def setUp(self):
        """Set up test fixtures before each test"""
        # Create a test node (disable network checking for tests)
        self.test_node = StorageVirtualNode(
            node_id="test_node",
            cpu_capacity=4,
            memory_capacity=16,
            storage_capacity=10,  # 10 GB
            bandwidth=1000,
            enable_network_check=False  # Disable network checking in tests
        )
        
    def tearDown(self):
        """Clean up after each test"""
        # Remove test storage directory
        if os.path.exists("storage/test_node"):
            shutil.rmtree("storage/test_node")
    
    def test_storage_structure_creation(self):
        """Test that storage directories are created correctly"""
        expected_base = os.path.join("storage", "test_node")
        expected_chunks = os.path.join("storage", "test_node", "chunks")
        
        self.assertTrue(os.path.exists(expected_base))
        self.assertTrue(os.path.exists(expected_chunks))
        self.assertEqual(self.test_node.storage_path, expected_base)
        self.assertTrue(self.test_node.chunks_path.endswith("chunks"))
    
    def test_write_chunk_to_disk(self):
        """Test writing a chunk to disk"""
        file_id = "test_file_001"
        chunk_id = 0
        test_data = b"Hello, CloudSim! This is test data."
        
        # Write chunk
        success, checksum = self.test_node.write_chunk_to_disk(file_id, chunk_id, test_data)
        
        # Verify write succeeded
        self.assertTrue(success)
        self.assertIsNotNone(checksum)
        self.assertEqual(len(checksum), 32)  # MD5 hash is 32 hex chars
        
        # Verify file exists
        chunk_path = os.path.join(self.test_node.chunks_path, f"{file_id}_chunk_{chunk_id}.bin")
        self.assertTrue(os.path.exists(chunk_path))
        
        # Verify file size
        file_size = os.path.getsize(chunk_path)
        self.assertEqual(file_size, len(test_data))
    
    def test_read_chunk_from_disk(self):
        """Test reading a chunk from disk"""
        file_id = "test_file_002"
        chunk_id = 0
        test_data = b"Test data for reading operation."
        
        # First write the chunk
        success, checksum = self.test_node.write_chunk_to_disk(file_id, chunk_id, test_data)
        self.assertTrue(success)
        
        # Now read it back
        read_data = self.test_node.read_chunk_from_disk(file_id, chunk_id)
        
        # Verify data matches
        self.assertIsNotNone(read_data)
        self.assertEqual(read_data, test_data)
    
    def test_checksum_verification(self):
        """Test that checksum verification works correctly"""
        file_id = "test_file_003"
        chunk_id = 0
        test_data = b"Data for checksum verification test."
        
        # Write chunk and get checksum
        success, checksum = self.test_node.write_chunk_to_disk(file_id, chunk_id, test_data)
        self.assertTrue(success)
        
        # Read with correct checksum - should succeed
        read_data = self.test_node.read_chunk_from_disk(file_id, chunk_id, checksum)
        self.assertIsNotNone(read_data)
        self.assertEqual(read_data, test_data)
        
        # Read with incorrect checksum - should fail
        wrong_checksum = "0" * 32
        read_data_fail = self.test_node.read_chunk_from_disk(file_id, chunk_id, wrong_checksum)
        self.assertIsNone(read_data_fail)
    
    def test_real_checksum_computation(self):
        """Test that real MD5 checksums are computed correctly"""
        file_id = "test_file_004"
        chunk_id = 0
        test_data = b"Checksum computation test data."
        
        # Calculate expected checksum
        expected_checksum = hashlib.md5(test_data).hexdigest()
        
        # Write chunk
        success, actual_checksum = self.test_node.write_chunk_to_disk(file_id, chunk_id, test_data)
        
        # Verify checksum matches
        self.assertTrue(success)
        self.assertEqual(actual_checksum, expected_checksum)
    
    def test_disk_usage_tracking(self):
        """Test that actual disk usage is tracked correctly"""
        # Initial disk usage should be 0
        initial_usage = self.test_node.get_actual_disk_usage()
        self.assertEqual(initial_usage, 0)
        
        # Write some chunks
        file_id = "test_file_005"
        chunk_size = 1024  # 1 KB
        num_chunks = 5
        
        for i in range(num_chunks):
            test_data = os.urandom(chunk_size)
            self.test_node.write_chunk_to_disk(file_id, i, test_data)
        
        # Check disk usage
        disk_usage = self.test_node.get_actual_disk_usage()
        expected_usage = chunk_size * num_chunks
        self.assertEqual(disk_usage, expected_usage)
    
    def test_storage_utilization_metrics(self):
        """Test that storage utilization metrics are accurate"""
        # Write some test data
        file_id = "test_file_006"
        test_data = os.urandom(2048)  # 2 KB
        self.test_node.write_chunk_to_disk(file_id, 0, test_data)
        
        # Get storage utilization
        metrics = self.test_node.get_storage_utilization()
        
        # Verify metrics
        self.assertIn("used_bytes", metrics)
        self.assertIn("total_bytes", metrics)
        self.assertIn("utilization_percent", metrics)
        self.assertIn("chunk_count", metrics)
        
        # Verify values
        self.assertEqual(metrics["used_bytes"], 2048)
        self.assertEqual(metrics["chunk_count"], 1)
        self.assertGreater(metrics["total_bytes"], 0)
    
    def test_read_nonexistent_chunk(self):
        """Test reading a chunk that doesn't exist"""
        file_id = "nonexistent_file"
        chunk_id = 999
        
        # Try to read nonexistent chunk
        data = self.test_node.read_chunk_from_disk(file_id, chunk_id)
        
        # Should return None
        self.assertIsNone(data)
    
    def test_sync_storage_metrics(self):
        """Test that storage metrics sync with actual disk usage"""
        # Manually set tracked storage to wrong value
        self.test_node.used_storage = 5000
        
        # Write actual data
        file_id = "test_file_007"
        test_data = os.urandom(1024)  # 1 KB
        self.test_node.write_chunk_to_disk(file_id, 0, test_data)
        
        # Sync metrics
        self.test_node.sync_storage_metrics()
        
        # Verify tracked storage now matches actual
        actual_usage = self.test_node.get_actual_disk_usage()
        self.assertEqual(self.test_node.used_storage, actual_usage)
        self.assertEqual(actual_usage, 1024)
    
    def test_multiple_chunks_same_file(self):
        """Test writing and reading multiple chunks of the same file"""
        file_id = "test_file_008"
        num_chunks = 10
        chunk_data = {}
        checksums = {}
        
        # Write multiple chunks
        for i in range(num_chunks):
            data = os.urandom(512)
            chunk_data[i] = data
            success, checksum = self.test_node.write_chunk_to_disk(file_id, i, data)
            checksums[i] = checksum
            self.assertTrue(success)
        
        # Read all chunks back and verify
        for i in range(num_chunks):
            read_data = self.test_node.read_chunk_from_disk(file_id, i, checksums[i])
            self.assertIsNotNone(read_data)
            self.assertEqual(read_data, chunk_data[i])
        
        # Verify total disk usage
        expected_usage = 512 * num_chunks
        actual_usage = self.test_node.get_actual_disk_usage()
        self.assertEqual(actual_usage, expected_usage)


def run_tests():
    """Run all tests"""
    # Create test suite
    suite = unittest.TestLoader().loadTestsFromTestCase(TestStorageOperations)
    
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

