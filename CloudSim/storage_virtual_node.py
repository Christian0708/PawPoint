import time
import math
import os
import threading
from dataclasses import dataclass
from typing import Dict, List, Optional, Union
from enum import Enum, auto
import hashlib

class TransferStatus(Enum):
    PENDING = auto()
    IN_PROGRESS = auto()
    COMPLETED = auto()
    FAILED = auto()

@dataclass
class FileChunk:
    chunk_id: int
    size: int  # in bytes
    checksum: str
    status: TransferStatus = TransferStatus.PENDING
    stored_node: Optional[str] = None

@dataclass
class FileTransfer:
    file_id: str
    file_name: str
    total_size: int  # in bytes
    chunks: List[FileChunk]
    status: TransferStatus = TransferStatus.PENDING
    created_at: float = time.time()
    completed_at: Optional[float] = None

class StorageVirtualNode(threading.Thread):
    def __init__(
        self,
        node_id: str,
        cpu_capacity: int,  # in vCPUs
        memory_capacity: int,  # in GB
        storage_capacity: int,  # in GB
        bandwidth: int  # in Mbps
    ):
        # Initialize thread
        super().__init__(name=f"Node-{node_id}", daemon=True)
        
        self.node_id = node_id
        self.cpu_capacity = cpu_capacity
        self.memory_capacity = memory_capacity
        self.total_storage = storage_capacity * 1024 * 1024 * 1024  # Convert GB to bytes
        self.bandwidth = bandwidth * 1000000  # Convert Mbps to bits per second
        
        # Current utilization
        self.used_storage = 0
        self.active_transfers: Dict[str, FileTransfer] = {}
        self.stored_files: Dict[str, FileTransfer] = {}
        self.network_utilization = 0  # Current bandwidth usage
        
        # Performance metrics
        self.total_requests_processed = 0
        self.total_data_transferred = 0  # in bytes
        self.failed_transfers = 0
        
        # Network connections (node_id: bandwidth_available)
        self.connections: Dict[str, int] = {}
        
        # Thread control
        self.running = False
        self.stop_event = threading.Event()
        
        # Create storage directory structure
        self.create_storage_structure()

    def create_storage_structure(self):
        """Create directory structure for node storage on the host machine"""
        # Define storage paths
        base_path = os.path.join("storage", self.node_id)
        chunks_path = os.path.join(base_path, "chunks")
        
        # Create directories if they don't exist
        os.makedirs(chunks_path, exist_ok=True)
        
        # Store paths as instance variables for later use
        self.storage_path = base_path
        self.chunks_path = chunks_path
        
        print(f"[{self.node_id}] Created storage structure at {base_path}")

    def run(self):
        """
        Main thread execution method
        Runs when thread.start() is called
        Node operates autonomously in this thread
        """
        self.running = True
        print(f"[{self.node_id}] Node thread started")
        
        # Main node loop - will be extended in later commits
        while self.running and not self.stop_event.is_set():
            try:
                # Node autonomous operations will be added here
                # For now, just check stop condition periodically
                self.stop_event.wait(timeout=1.0)  # Check every second
            except Exception as e:
                print(f"[{self.node_id}] Error in node thread: {e}")
                break
        
        print(f"[{self.node_id}] Node thread stopped")
    
    def stop(self):
        """
        Stop the node thread gracefully
        """
        self.running = False
        self.stop_event.set()
        print(f"[{self.node_id}] Stop signal sent")

    def write_chunk_to_disk(self, file_id: str, chunk_id: int, data: bytes) -> tuple[bool, str]:
        """Write a chunk to disk as a binary file and return checksum"""
        try:
            # Create filename for this chunk
            chunk_filename = f"{file_id}_chunk_{chunk_id}.bin"
            chunk_path = os.path.join(self.chunks_path, chunk_filename)
            
            # Calculate real MD5 checksum from actual data
            checksum = hashlib.md5(data).hexdigest()
            
            # Write chunk data to disk
            with open(chunk_path, 'wb') as f:
                f.write(data)
            
            print(f"[{self.node_id}] Wrote chunk {chunk_id} to {chunk_filename} ({len(data)} bytes, checksum: {checksum[:8]}...)")
            return True, checksum
        except Exception as e:
            print(f"[{self.node_id}] Error writing chunk {chunk_id}: {e}")
            return False, ""

    def read_chunk_from_disk(self, file_id: str, chunk_id: int, expected_checksum: Optional[str] = None) -> Optional[bytes]:
        """Read a chunk from disk and verify checksum if provided"""
        try:
            # Create filename for this chunk
            chunk_filename = f"{file_id}_chunk_{chunk_id}.bin"
            chunk_path = os.path.join(self.chunks_path, chunk_filename)
            
            # Check if file exists
            if not os.path.exists(chunk_path):
                print(f"[{self.node_id}] Chunk {chunk_id} not found: {chunk_filename}")
                return None
            
            # Read chunk data from disk
            with open(chunk_path, 'rb') as f:
                data = f.read()
            
            # Verify checksum if provided
            if expected_checksum:
                actual_checksum = hashlib.md5(data).hexdigest()
                if actual_checksum != expected_checksum:
                    print(f"[{self.node_id}] Checksum mismatch for chunk {chunk_id}! Expected: {expected_checksum[:8]}..., Got: {actual_checksum[:8]}...")
                    return None
                print(f"[{self.node_id}] Read chunk {chunk_id} from {chunk_filename} ({len(data)} bytes, checksum verified)")
            else:
                print(f"[{self.node_id}] Read chunk {chunk_id} from {chunk_filename} ({len(data)} bytes)")
            
            return data
        except Exception as e:
            print(f"[{self.node_id}] Error reading chunk {chunk_id}: {e}")
            return None

    def get_actual_disk_usage(self) -> int:
        """Calculate actual disk space used by reading file sizes from disk"""
        total_size = 0
        try:
            # Walk through all files in the chunks directory
            for filename in os.listdir(self.chunks_path):
                file_path = os.path.join(self.chunks_path, filename)
                if os.path.isfile(file_path):
                    total_size += os.path.getsize(file_path)
            return total_size
        except Exception as e:
            print(f"[{self.node_id}] Error calculating disk usage: {e}")
            return 0

    def sync_storage_metrics(self):
        """Synchronize storage metrics with actual disk usage"""
        actual_usage = self.get_actual_disk_usage()
        if actual_usage != self.used_storage:
            print(f"[{self.node_id}] Syncing storage: tracked={self.used_storage}, actual={actual_usage}")
            self.used_storage = actual_usage

    def add_connection(self, node_id: str, bandwidth: int):
        """Add a network connection to another node"""
        self.connections[node_id] = bandwidth * 1000000  # Store in bits per second

    def _calculate_chunk_size(self, file_size: int) -> int:
        """Determine optimal chunk size based on file size"""
        # Simple heuristic: larger files get larger chunks
        if file_size < 10 * 1024 * 1024:  # < 10MB
            return 512 * 1024  # 512KB chunks
        elif file_size < 100 * 1024 * 1024:  # < 100MB
            return 2 * 1024 * 1024  # 2MB chunks
        else:
            return 10 * 1024 * 1024  # 10MB chunks

    def _generate_chunks(self, file_id: str, file_size: int) -> List[FileChunk]:
        """Break file into chunks for transfer"""
        chunk_size = self._calculate_chunk_size(file_size)
        num_chunks = math.ceil(file_size / chunk_size)
        
        chunks = []
        for i in range(num_chunks):
            # Checksum will be computed when actual data is written
            # Initialize with empty string for now
            actual_chunk_size = min(chunk_size, file_size - i * chunk_size)
            chunks.append(FileChunk(
                chunk_id=i,
                size=actual_chunk_size,
                checksum=""  # Will be computed from actual data
            ))
        
        return chunks

    def initiate_file_transfer(
        self,
        file_id: str,
        file_name: str,
        file_size: int,
        source_node: Optional[str] = None
    ) -> Optional[FileTransfer]:
        """Initiate a file storage request to this node"""
        # Check if we have enough storage space using actual disk usage
        actual_usage = self.get_actual_disk_usage()
        if actual_usage + file_size > self.total_storage:
            print(f"[{self.node_id}] Insufficient storage: need {file_size} bytes, available {self.total_storage - actual_usage} bytes")
            return None
        
        # Create file transfer record
        chunks = self._generate_chunks(file_id, file_size)
        transfer = FileTransfer(
            file_id=file_id,
            file_name=file_name,
            total_size=file_size,
            chunks=chunks
        )
        
        self.active_transfers[file_id] = transfer
        return transfer

    def process_chunk_transfer(
        self,
        file_id: str,
        chunk_id: int,
        source_node: str
    ) -> bool:
        """Process an incoming file chunk"""
        if file_id not in self.active_transfers:
            return False
        
        transfer = self.active_transfers[file_id]
        
        try:
            chunk = next(c for c in transfer.chunks if c.chunk_id == chunk_id)
        except StopIteration:
            return False
        
        # Simulate network transfer time
        chunk_size_bits = chunk.size * 8  # Convert bytes to bits
        available_bandwidth = min(
            self.bandwidth - self.network_utilization,
            self.connections.get(source_node, 0)
        )
        
        if available_bandwidth <= 0:
            return False
        
        # Calculate transfer time (in seconds)
        transfer_time = chunk_size_bits / available_bandwidth
        time.sleep(transfer_time)  # Simulate transfer delay
        
        # Generate simulated chunk data (in real system, this would come from network)
        chunk_data = os.urandom(chunk.size)  # Random bytes to simulate file data
        
        # Write chunk to disk and get real checksum
        success, checksum = self.write_chunk_to_disk(file_id, chunk_id, chunk_data)
        if not success:
            return False
        
        # Update chunk with real checksum and status
        chunk.checksum = checksum
        chunk.status = TransferStatus.COMPLETED
        chunk.stored_node = self.node_id
        
        # Update metrics
        self.network_utilization += available_bandwidth * 0.8  # Simulate some fluctuation
        self.total_data_transferred += chunk.size
        
        # Check if all chunks are completed
        if all(c.status == TransferStatus.COMPLETED for c in transfer.chunks):
            transfer.status = TransferStatus.COMPLETED
            transfer.completed_at = time.time()
            self.stored_files[file_id] = transfer
            del self.active_transfers[file_id]
            self.total_requests_processed += 1
            
            # Sync storage metrics with actual disk usage
            self.sync_storage_metrics()
        
        return True

    def retrieve_file(
        self,
        file_id: str,
        destination_node: str
    ) -> Optional[FileTransfer]:
        """Initiate file retrieval to another node by reading chunks from disk"""
        if file_id not in self.stored_files:
            print(f"[{self.node_id}] File {file_id} not found in stored files")
            return None
        
        file_transfer = self.stored_files[file_id]
        
        # Verify all chunks can be read from disk and checksums match
        print(f"[{self.node_id}] Retrieving file {file_transfer.file_name} ({len(file_transfer.chunks)} chunks)")
        for chunk in file_transfer.chunks:
            chunk_data = self.read_chunk_from_disk(file_id, chunk.chunk_id, chunk.checksum)
            if chunk_data is None:
                print(f"[{self.node_id}] Failed to retrieve chunk {chunk.chunk_id}")
                return None
        
        # Create a new transfer record for the retrieval
        new_transfer = FileTransfer(
            file_id=f"retr-{file_id}-{time.time()}",
            file_name=file_transfer.file_name,
            total_size=file_transfer.total_size,
            chunks=[
                FileChunk(
                    chunk_id=c.chunk_id,
                    size=c.size,
                    checksum=c.checksum,
                    stored_node=destination_node
                )
                for c in file_transfer.chunks
            ]
        )
        
        print(f"[{self.node_id}] Successfully retrieved all chunks for {file_transfer.file_name}")
        return new_transfer

    def get_storage_utilization(self) -> Dict[str, Union[int, float, List[str]]]:
        """Get current storage utilization metrics using actual disk usage"""
        # Get real disk usage
        actual_disk_usage = self.get_actual_disk_usage()
        
        return {
            "used_bytes": actual_disk_usage,  # int - actual disk usage
            "tracked_bytes": self.used_storage,  # int - tracked usage (may differ)
            "total_bytes": self.total_storage,  # int
            "utilization_percent": (actual_disk_usage / self.total_storage) * 100,  # float
            "files_stored": len(self.stored_files),  # int
            "active_transfers": len(self.active_transfers),  # int
            "chunk_count": len(os.listdir(self.chunks_path)) if os.path.exists(self.chunks_path) else 0  # int
        }

    def get_network_utilization(self) -> Dict[str, Union[int, float, List[str]]]:
        """Get current network utilization metrics"""
        total_bandwidth_bps = self.bandwidth
        return {
            "current_utilization_bps": self.network_utilization,  # float
            "max_bandwidth_bps": total_bandwidth_bps,  # int
            "utilization_percent": (self.network_utilization / total_bandwidth_bps) * 100,  # float
            "connections": list(self.connections.keys())  # List[str]
        }

    def get_performance_metrics(self) -> Dict[str, int]:
        """Get node performance metrics"""
        return {
            "total_requests_processed": self.total_requests_processed,
            "total_data_transferred_bytes": self.total_data_transferred,
            "failed_transfers": self.failed_transfers,
            "current_active_transfers": len(self.active_transfers)
        }