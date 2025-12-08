import time
import math
import os
import threading
import signal
import socket
import json
from concurrent.futures import ThreadPoolExecutor, Future
from dataclasses import dataclass
from typing import Dict, List, Optional, Union, Callable
from enum import Enum, auto
import hashlib
from network_manager import NetworkManager, MessageType

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
        bandwidth: int,  # in Mbps
        host: str = "localhost",
        port: int = 5000,
        enable_network_check: bool = True,  # Enable network checking on boot
        storage_root: Optional[str] = None
    ):
        # Initialize thread
        super().__init__(name=f"Node-{node_id}", daemon=True)
        
        self.node_id = node_id
        self.cpu_capacity = cpu_capacity
        self.memory_capacity = memory_capacity
        self.total_storage = storage_capacity * 1024 * 1024 * 1024  # Convert GB to bytes
        self.bandwidth = bandwidth * 1000000  # Convert Mbps to bits per second
        
        # Network configuration
        self.host = host
        self.port = port
        self.ip_address = self._get_ip_address(host)
        self.mac_address = self._get_mac_address()
        
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
        self.shutting_down = False  # Flag to indicate shutdown in progress
        self.shutdown_complete = threading.Event()  # Event to signal shutdown complete
        
        # Thread locks for thread-safe operations
        self.storage_lock = threading.Lock()  # Protects storage operations
        self.transfer_lock = threading.Lock()  # Protects active_transfers
        self.metrics_lock = threading.Lock()  # Protects performance metrics
        self.network_lock = threading.Lock()  # Protects network operations
        
        # Shutdown callbacks
        self.shutdown_callbacks: List[Callable[[], None]] = []
        
        # Persist configured storage root
        self.storage_root = storage_root

        # Network manager for real network communication
        self.network_manager = NetworkManager(node_id, host, port)
        self.network_manager.on_chunk_received = self._on_chunk_received
        self.network_manager.on_chunk_request = self._on_chunk_request
        self.network_manager.on_shutdown_requested = self._on_shutdown_request
        
        # Network service configuration
        self.discovery_port = 9999  # Default discovery port
        self.network_connected = False
        self.enable_network_check = enable_network_check  # Whether to check for network
        self.network_check_interval = 5.0  # Check for network every 5 seconds
        self.network_check_timeout = 30.0  # Wait up to 30 seconds for network
        
        # Network listener thread (will be started separately)
        self.listener_thread: Optional[threading.Thread] = None

        # Thread pool for asynchronous file transfer processing
        self.transfer_executor: Optional[ThreadPoolExecutor] = None
        self.max_concurrent_transfers = max(1, int(cpu_capacity))
        self.active_transfer_futures: Dict[str, Future] = {}  # Track transfer futures
        
        # Create storage directory structure
        self.create_storage_structure()
        
        # Set up signal handlers for graceful shutdown
        self._setup_signal_handlers()

    def _get_ip_address(self, host: str) -> str:
        """Get IP address for the given host"""
        try:
            if host == "localhost" or host == "127.0.0.1":
                # Get local machine's IP address
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                try:
                    # Connect to a remote address (doesn't actually send data)
                    s.connect(('8.8.8.8', 80))
                    ip = s.getsockname()[0]
                except Exception:
                    ip = "127.0.0.1"
                finally:
                    s.close()
                return ip
            else:
                # Resolve hostname to IP
                return socket.gethostbyname(host)
        except Exception:
            return host  # Return host as-is if resolution fails

    def _get_mac_address(self) -> str:
        """Get MAC address of the network interface"""
        try:
            import uuid
            # Get MAC address as hex string
            mac = uuid.getnode()
            # Format as XX:XX:XX:XX:XX:XX
            mac_str = ':'.join(['{:02x}'.format((mac >> elements) & 0xff) 
                               for elements in range(0, 8*6, 8)][::-1])
            return mac_str
        except Exception:
            return "00:00:00:00:00:00"  # Default MAC if unable to get

    def create_storage_structure(self):
        """Create directory structure for node storage on the host machine"""
        # Define storage paths
        base_root = self.storage_root if hasattr(self, 'storage_root') and self.storage_root else os.path.abspath("storage")
        base_path = os.path.join(base_root, self.node_id)
        chunks_path = os.path.join(base_path, "chunks")
        
        # Create directories if they don't exist
        os.makedirs(chunks_path, exist_ok=True)
        
        # Store paths as instance variables for later use
        self.storage_path = base_path
        self.chunks_path = chunks_path
        
        print(f"[{self.node_id}] Created storage structure at {base_path}")

    def _setup_signal_handlers(self):
        """
        Set up signal handlers for graceful shutdown on SIGINT/SIGTERM
        Note: Signal handlers only work in main thread
        """
        def signal_handler(signum, frame):
            print(f"\n[{self.node_id}] Received signal {signum}, initiating graceful shutdown...")
            self.stop(graceful=True, timeout=10.0)
        
        # Only set up signal handlers if we're in the main thread
        if threading.current_thread() is threading.main_thread():
            try:
                signal.signal(signal.SIGINT, signal_handler)
                signal.signal(signal.SIGTERM, signal_handler)
                print(f"[{self.node_id}] Signal handlers registered for graceful shutdown")
            except (ValueError, OSError) as e:
                # Signal handling may not be available on all platforms
                print(f"[{self.node_id}] Could not set up signal handlers: {e}")

    def _run_network_listener(self):
        """
        Run network listener in a separate thread
        This method is executed by the listener thread
        """
        # Initialize and start the network listener
        if self.network_manager.initialize_listener():
            self.network_manager.start_server()
        else:
            print(f"[{self.node_id}] Failed to initialize network listener")
    
    def run(self):
        """
        Main thread execution method
        Runs when thread.start() is called
        Node operates autonomously in this thread
        """
        self.running = True
        print(f"[{self.node_id}] Node thread started")
        
        # Initialize thread pool for asynchronous transfers
        self.transfer_executor = ThreadPoolExecutor(
            max_workers=self.max_concurrent_transfers,
            thread_name_prefix=f"Transfer-{self.node_id}"
        )
        print(f"[{self.node_id}] Transfer executor initialized (max {self.max_concurrent_transfers} workers)")
        
        # Start network listener in a separate thread
        self.listener_thread = threading.Thread(
            target=self._run_network_listener,
            name=f"Listener-{self.node_id}",
            daemon=True
        )
        self.listener_thread.start()
        print(f"[{self.node_id}] Network listener thread started on {self.host}:{self.port}")
        
        # Check for network and connect when available (if enabled)
        if self.enable_network_check:
            print(f"[{self.node_id}] Checking for network availability...")
            network_found = self._check_and_connect_to_network()
            
            if network_found:
                print(f"[{self.node_id}] Connected to cloud network")
            else:
                print(f"[{self.node_id}] Network not available. Node will continue checking...")
        else:
            print(f"[{self.node_id}] Network checking disabled")
        
        # Main node loop - periodically check for network if not connected
        while self.running and not self.stop_event.is_set() and not self.shutting_down:
            try:
                # If network checking is enabled and not connected, check periodically
                if self.enable_network_check and not self.network_connected:
                    network_found = self._check_and_connect_to_network()
                    if network_found:
                        print(f"[{self.node_id}] Connected to cloud network")
                
                # Node autonomous operations will be added here
                # Send heartbeat if connected
                if self.network_connected:
                    self._send_heartbeat()
                # Check stop condition periodically
                self.stop_event.wait(timeout=1.0)  # Check every second
            except Exception as e:
                print(f"[{self.node_id}] Error in node thread: {e}")
                break
        
        # Final cleanup before thread exits
        if self.shutting_down:
            print(f"[{self.node_id}] Node thread stopping due to shutdown request")
        else:
            print(f"[{self.node_id}] Node thread stopped")

    def _on_shutdown_request(self, reason: str = ""):
        try:
            print(f"[{self.node_id}] Remote shutdown requested: {reason}")
            # Initiate graceful shutdown
            self.stop(graceful=True, timeout=5.0)
        except Exception as e:
            print(f"[{self.node_id}] Error during remote shutdown: {e}")
    
    def _check_and_connect_to_network(self) -> bool:
        """
        Check if network is available and connect to it
        Returns True if network is found and connected
        
        Returns:
            bool: True if network is available and connected
        """
        try:
            # Create a UDP socket to query network
            query_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            query_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            query_socket.settimeout(2.0)  # 2 second timeout
            
            # Send network query
            query_msg = {
                'type': 'NETWORK_QUERY',
                'node_id': self.node_id,
                'host': self.host,
                'port': self.port
            }
            
            # Try to send query and wait for response
            query_socket.sendto(
                json.dumps(query_msg).encode('utf-8'),
                ('255.255.255.255', self.discovery_port)
            )
            
            # Wait for network response
            try:
                data, addr = query_socket.recvfrom(4096)
                response = json.loads(data.decode('utf-8'))
                
                if response.get('type') == 'NETWORK_RESPONSE' and response.get('network_available'):
                    # Network is available, register this node
                    self._register_with_network(addr[0])
                    query_socket.close()
                    return True
            except socket.timeout:
                # Network not responding, try to register anyway (network might be starting)
                pass
            
            query_socket.close()
            
            # Try to register with network (might be starting up)
            return self._register_with_network()
            
        except Exception as e:
            # Network check failed, will retry later
            return False
    
    def _register_with_network(self, network_host: str = '255.255.255.255') -> bool:
        """
        Register this node with the network
        
        Args:
            network_host: Host address of the network service
            
        Returns:
            bool: True if registration successful
        """
        try:
            reg_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            reg_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            reg_socket.settimeout(2.0)
            
            # Send registration request
            reg_msg = {
                'type': 'NODE_REGISTER',
                'node_id': self.node_id,
                'host': self.host,
                'port': self.port,
                'cpu_capacity': self.cpu_capacity,
                'memory_capacity': self.memory_capacity,
                'storage_capacity': self.total_storage,
                'bandwidth': self.bandwidth
            }
            
            reg_socket.sendto(
                json.dumps(reg_msg).encode('utf-8'),
                (network_host, self.discovery_port)
            )
            
            # Wait for confirmation
            try:
                data, addr = reg_socket.recvfrom(4096)
                response = json.loads(data.decode('utf-8'))
                
                if response.get('type') == 'REGISTRATION_CONFIRMED':
                    self.network_connected = True
                    print(f"[{self.node_id}] Successfully registered with network")
                    # Populate known addresses from handshake
                    nodes_info = response.get('nodes', {})
                    if isinstance(nodes_info, dict):
                        for nid, info in nodes_info.items():
                            if nid != self.node_id:
                                host = info.get('host', 'localhost')
                                port = info.get('port')
                                if host and port:
                                    self.network_manager.node_addresses[nid] = (host, int(port))
                    reg_socket.close()
                    return True
            except socket.timeout:
                # No response, network might not be available yet
                pass
            
            reg_socket.close()
            return False
            
        except Exception as e:
            print(f"[{self.node_id}] Error registering with network: {e}")
            return False

    def _send_heartbeat(self):
        try:
            hb_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            hb_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            msg = {
                'type': 'NODE_HEARTBEAT',
                'node_id': self.node_id,
                'host': self.host,
                'port': self.port,
                'timestamp': time.time()
            }
            hb_socket.sendto(json.dumps(msg).encode('utf-8'), ('255.255.255.255', self.discovery_port))
            hb_socket.close()
        except Exception:
            pass
    
    def register_shutdown_callback(self, callback: Callable[[], None]):
        """
        Register a callback to be called during graceful shutdown
        
        Args:
            callback: Function to call during shutdown (no arguments)
        """
        self.shutdown_callbacks.append(callback)
        print(f"[{self.node_id}] Registered shutdown callback")
    
    def _wait_for_active_transfers(self, timeout: float = 10.0) -> bool:
        """
        Wait for active transfers to complete
        
        Args:
            timeout: Maximum time to wait in seconds
            
        Returns:
            True if all transfers completed, False if timeout
        """
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            with self.transfer_lock:
                if len(self.active_transfers) == 0 and len(self.active_transfer_futures) == 0:
                    return True
            
            time.sleep(0.5)  # Check every 500ms
        
        # Timeout reached
        with self.transfer_lock:
            remaining = len(self.active_transfers)
            remaining_futures = len(self.active_transfer_futures)
        
        if remaining > 0 or remaining_futures > 0:
            print(f"[{self.node_id}] Warning: {remaining} active transfers and {remaining_futures} futures still pending after timeout")
            return False
        
        return True
    
    def stop(self, graceful: bool = True, timeout: float = 10.0):
        """
        Stop the node thread and network listener gracefully
        
        Args:
            graceful: If True, wait for operations to complete
            timeout: Maximum time to wait for graceful shutdown (seconds)
        """
        if self.shutting_down:
            print(f"[{self.node_id}] Shutdown already in progress")
            return
        
        self.shutting_down = True
        print(f"[{self.node_id}] Initiating graceful shutdown...")
        
        # Set stop flags
        self.running = False
        self.stop_event.set()
        
        # Execute shutdown callbacks
        for callback in self.shutdown_callbacks:
            try:
                callback()
            except Exception as e:
                print(f"[{self.node_id}] Error in shutdown callback: {e}")
        
        if graceful:
            # Wait for active transfers to complete
            print(f"[{self.node_id}] Waiting for active transfers to complete (timeout: {timeout}s)...")
            transfers_complete = self._wait_for_active_transfers(timeout)
            
            if not transfers_complete:
                print(f"[{self.node_id}] Some transfers did not complete within timeout")
        
        # Shutdown transfer executor
        if self.transfer_executor:
            print(f"[{self.node_id}] Shutting down transfer executor...")
            try:
                # ThreadPoolExecutor.shutdown() timeout parameter available in Python 3.9+
                # Use graceful shutdown with wait parameter
                if graceful:
                    self.transfer_executor.shutdown(wait=True)
                else:
                    self.transfer_executor.shutdown(wait=False)
                print(f"[{self.node_id}] Transfer executor shut down")
            except Exception as e:
                print(f"[{self.node_id}] Error shutting down transfer executor: {e}")
        
        # Stop network manager
        if self.network_manager:
            try:
                self.network_manager.stop_server()
                print(f"[{self.node_id}] Network manager stopped")
            except Exception as e:
                print(f"[{self.node_id}] Error stopping network manager: {e}")
        # Unregister from network service immediately
        try:
            reg_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            reg_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            msg = {
                'type': 'NODE_UNREGISTER',
                'node_id': self.node_id,
                'host': self.host,
                'port': self.port
            }
            reg_socket.sendto(json.dumps(msg).encode('utf-8'), ('255.255.255.255', self.discovery_port))
            reg_socket.close()
        except Exception:
            pass
        
        # Wait for listener thread to finish
        if self.listener_thread and self.listener_thread.is_alive():
            print(f"[{self.node_id}] Waiting for listener thread to finish...")
            self.listener_thread.join(timeout=2.0)
            if self.listener_thread.is_alive():
                print(f"[{self.node_id}] Warning: Listener thread did not stop within timeout")
            else:
                print(f"[{self.node_id}] Listener thread stopped")
        
        # Signal shutdown complete
        self.shutdown_complete.set()
        print(f"[{self.node_id}] Graceful shutdown complete")
    
    def wait_for_shutdown(self, timeout: Optional[float] = None) -> bool:
        """
        Wait for shutdown to complete
        
        Args:
            timeout: Maximum time to wait (None = wait indefinitely)
            
        Returns:
            True if shutdown completed, False if timeout
        """
        return self.shutdown_complete.wait(timeout=timeout)

    def write_chunk_to_disk(self, file_id: str, chunk_id: int, data: bytes) -> tuple[bool, str]:
        """Write a chunk to disk as a binary file and return checksum"""
        try:
            # Check if we have enough storage space before writing
            with self.storage_lock:
                actual_usage = self.get_actual_disk_usage()
                chunk_size = len(data)
                if actual_usage + chunk_size > self.total_storage:
                    print(f"[{self.node_id}] Insufficient storage for chunk {chunk_id}: need {chunk_size} bytes, available {self.total_storage - actual_usage} bytes")
                    return False, ""
            
            # Create filename for this chunk
            chunk_filename = f"{file_id}_chunk_{chunk_id}.bin"
            chunk_path = os.path.join(self.chunks_path, chunk_filename)
            
            # Calculate real MD5 checksum from actual data
            checksum = hashlib.md5(data).hexdigest()
            
            # Write chunk data to disk
            with open(chunk_path, 'wb') as f:
                f.write(data)
            
            print(f"[{self.node_id}] Wrote chunk {chunk_id} to {chunk_filename} ({len(data)} bytes, checksum: {checksum[:8]}...)")
            with self.metrics_lock:
                self.total_data_transferred += len(data)
            self.sync_storage_metrics()
            return True, checksum
        except OSError as e:
            # Handle disk full errors specifically
            if "No space left" in str(e) or "not enough space" in str(e).lower():
                print(f"[{self.node_id}] Disk full: Cannot write chunk {chunk_id} ({len(data)} bytes)")
                with self.storage_lock:
                    actual_usage = self.get_actual_disk_usage()
                    print(f"[{self.node_id}] Current usage: {actual_usage}/{self.total_storage} bytes ({actual_usage/self.total_storage*100:.1f}%)")
            else:
                print(f"[{self.node_id}] Error writing chunk {chunk_id}: {e}")
            return False, ""
        except Exception as e:
            print(f"[{self.node_id}] Error writing chunk {chunk_id}: {e}")
            return False, ""

    def send_chunk_to_node(self, target_node_id: str, file_id: str, chunk_id: int) -> bool:
        try:
            data = self.read_chunk_from_disk(file_id, chunk_id)
            if data is None:
                return False
            checksum = hashlib.md5(data).hexdigest()
            return self.network_manager.send_chunk_data(target_node_id, file_id, chunk_id, data, checksum)
        except Exception:
            return False

    def _on_chunk_received(self, file_id: str, chunk_id: int, data: bytes, checksum: Optional[str]) -> None:
        try:
            if checksum:
                actual = hashlib.md5(data).hexdigest()
                if actual != checksum:
                    print(f"[{self.node_id}] Received chunk checksum mismatch for {file_id}:{chunk_id}")
                    return
            success, cs = self.write_chunk_to_disk(file_id, chunk_id, data)
            if success:
                with self.metrics_lock:
                    self.total_data_transferred += len(data)
        except Exception as e:
            print(f"[{self.node_id}] Error handling received chunk: {e}")

    def _on_chunk_request(self, file_id: str, chunk_id: int) -> Optional[bytes]:
        """Handle chunk request (for downloads) - returns chunk data if found"""
        try:
            return self.read_chunk_from_disk(file_id, chunk_id)
        except Exception as e:
            print(f"[{self.node_id}] Error handling chunk request for {file_id}:{chunk_id}: {e}")
            return None

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

    def delete_file_by_id(self, file_id: str) -> int:
        """Delete all chunk files belonging to a file_id and return total bytes removed"""
        removed_bytes = 0
        try:
            for filename in os.listdir(self.chunks_path):
                if filename.startswith(f"{file_id}_chunk_") and filename.endswith('.bin'):
                    file_path = os.path.join(self.chunks_path, filename)
                    if os.path.isfile(file_path):
                        try:
                            size = os.path.getsize(file_path)
                        except Exception:
                            size = 0
                        try:
                            os.remove(file_path)
                            removed_bytes += size
                            print(f"[{self.node_id}] Deleted chunk file {filename} ({size} bytes)")
                        except Exception as e:
                            print(f"[{self.node_id}] Error deleting {filename}: {e}")
            with self.storage_lock:
                self.sync_storage_metrics()
                if file_id in self.stored_files:
                    del self.stored_files[file_id]
            return removed_bytes
        except Exception as e:
            print(f"[{self.node_id}] Error deleting file {file_id}: {e}")
            return removed_bytes

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
        """Synchronize storage metrics with actual disk usage (thread-safe)"""
        with self.storage_lock:
            actual_usage = self.get_actual_disk_usage()
            if actual_usage != self.used_storage:
                print(f"[{self.node_id}] Syncing storage: tracked={self.used_storage}, actual={actual_usage}")
                self.used_storage = actual_usage

    def add_connection(self, node_id: str, bandwidth: int):
        """Add a network connection to another node (thread-safe)"""
        with self.network_lock:
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
        """Initiate a file storage request to this node (thread-safe)"""
        # Reject new transfers during shutdown
        if self.shutting_down:
            print(f"[{self.node_id}] Rejecting new transfer request - node is shutting down")
            return None
        
        # Check if we have enough storage space using actual disk usage
        with self.storage_lock:
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
        
        # Add to active transfers (thread-safe)
        with self.transfer_lock:
            self.active_transfers[file_id] = transfer
        
        return transfer

    def process_chunk_transfer(
        self,
        file_id: str,
        chunk_id: int,
        source_node: str
    ) -> bool:
        """Process an incoming file chunk (thread-safe)"""
        # Get transfer (thread-safe)
        with self.transfer_lock:
            if file_id not in self.active_transfers:
                return False
            transfer = self.active_transfers[file_id]
        
        try:
            chunk = next(c for c in transfer.chunks if c.chunk_id == chunk_id)
        except StopIteration:
            return False
        
        # Get network bandwidth (thread-safe)
        with self.network_lock:
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
        
        # Update network metrics (thread-safe)
        with self.network_lock:
            self.network_utilization += available_bandwidth * 0.8  # Simulate some fluctuation
        
        # Update performance metrics (thread-safe)
        with self.metrics_lock:
            self.total_data_transferred += chunk.size
        
        # Check if all chunks are completed (thread-safe)
        with self.transfer_lock:
            if all(c.status == TransferStatus.COMPLETED for c in transfer.chunks):
                transfer.status = TransferStatus.COMPLETED
                transfer.completed_at = time.time()
                
                # Move to stored files (thread-safe)
                with self.storage_lock:
                    self.stored_files[file_id] = transfer
                
                # Remove from active transfers
                del self.active_transfers[file_id]
                
                # Update metrics (thread-safe)
                with self.metrics_lock:
                    self.total_requests_processed += 1
                
                # Sync storage metrics with actual disk usage
                self.sync_storage_metrics()
        
        return True

    def process_chunk_transfer_async(
        self,
        file_id: str,
        chunk_id: int,
        source_node: str
    ) -> Optional[Future]:
        """
        Process an incoming file chunk asynchronously using thread pool
        
        Args:
            file_id: ID of the file being transferred
            chunk_id: ID of the chunk to process
            source_node: ID of the source node
            
        Returns:
            Future object representing the async operation, or None if error
        """
        # Reject new transfers during shutdown
        if self.shutting_down:
            print(f"[{self.node_id}] Rejecting async transfer - node is shutting down")
            return None
        
        if not self.transfer_executor:
            print(f"[{self.node_id}] Transfer executor not initialized")
            return None
        
        # Submit chunk processing to thread pool
        future = self.transfer_executor.submit(
            self.process_chunk_transfer,
            file_id,
            chunk_id,
            source_node
        )
        
        # Track the future
        transfer_key = f"{file_id}_{chunk_id}"
        with self.transfer_lock:
            self.active_transfer_futures[transfer_key] = future
        
        # Add callback to clean up future when done
        def cleanup_future(f):
            with self.transfer_lock:
                if transfer_key in self.active_transfer_futures:
                    del self.active_transfer_futures[transfer_key]
        
        future.add_done_callback(cleanup_future)
        
        print(f"[{self.node_id}] Submitted chunk {chunk_id} of file {file_id} for async processing")
        return future

    def get_async_transfer_status(self) -> Dict[str, int]:
        """
        Get status of asynchronous transfers
        
        Returns:
            Dictionary with counts of pending, running, and completed transfers
        """
        pending = 0
        running = 0
        completed = 0
        
        with self.transfer_lock:
            for future in self.active_transfer_futures.values():
                if future.done():
                    completed += 1
                elif future.running():
                    running += 1
                else:
                    pending += 1
        
        return {
            "pending": pending,
            "running": running,
            "completed": completed,
            "total": pending + running + completed
        }

    def retrieve_file(
        self,
        file_id: str,
        destination_node: str
    ) -> Optional[FileTransfer]:
        """Initiate file retrieval to another node by reading chunks from disk (thread-safe)"""
        with self.storage_lock:
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

    def store_local_file(self, file_path: str, file_id: Optional[str] = None, source_node: Optional[str] = None) -> Optional[FileTransfer]:
        try:
            if not os.path.exists(file_path):
                return None
            file_name = os.path.basename(file_path)
            file_size = os.path.getsize(file_path)
            if not file_id:
                file_id = hashlib.md5(f"{file_name}-{time.time()}".encode()).hexdigest()
            transfer = self.initiate_file_transfer(file_id, file_name, file_size, source_node)
            if not transfer:
                return None
            with open(file_path, 'rb') as f:
                for chunk in transfer.chunks:
                    data = f.read(chunk.size)
                    success, checksum = self.write_chunk_to_disk(file_id, chunk.chunk_id, data)
                    if not success:
                        with self.transfer_lock:
                            self.failed_transfers += 1
                        return None
                    chunk.checksum = checksum
                    chunk.status = TransferStatus.COMPLETED
                    chunk.stored_node = self.node_id
                    with self.metrics_lock:
                        self.total_data_transferred += chunk.size
            transfer.status = TransferStatus.COMPLETED
            transfer.completed_at = time.time()
            with self.storage_lock:
                self.stored_files[file_id] = transfer
            with self.transfer_lock:
                if file_id in self.active_transfers:
                    del self.active_transfers[file_id]
            with self.metrics_lock:
                self.total_requests_processed += 1
            self.sync_storage_metrics()
            return transfer
        except Exception:
            return None

    def export_file_to_path(self, file_id: str, destination_path: str) -> bool:
        try:
            with self.storage_lock:
                transfer = self.stored_files.get(file_id)
            if transfer:
                with open(destination_path, 'wb') as out:
                    for chunk in transfer.chunks:
                        data = self.read_chunk_from_disk(file_id, chunk.chunk_id, chunk.checksum)
                        if data is None:
                            return False
                        out.write(data)
                return True
            chunk_files = [f for f in os.listdir(self.chunks_path) if f.startswith(f"{file_id}_chunk_")]
            if not chunk_files:
                return False
            def _chunk_index(name: str) -> int:
                try:
                    return int(name.split("_chunk_")[-1].split(".bin")[0])
                except Exception:
                    return 0
            chunk_files.sort(key=_chunk_index)
            with open(destination_path, 'wb') as out:
                for fname in chunk_files:
                    fpath = os.path.join(self.chunks_path, fname)
                    with open(fpath, 'rb') as cfile:
                        out.write(cfile.read())
            return True
        except Exception:
            return False

    def get_storage_utilization(self) -> Dict[str, Union[int, float, List[str]]]:
        """Get current storage utilization metrics using actual disk usage (thread-safe)"""
        # Get real disk usage
        actual_disk_usage = self.get_actual_disk_usage()
        
        with self.storage_lock:
            tracked_storage = self.used_storage
            files_stored = len(self.stored_files)
        
        with self.transfer_lock:
            active_transfers = len(self.active_transfers)
        
        return {
            "used_bytes": actual_disk_usage,  # int - actual disk usage
            "tracked_bytes": tracked_storage,  # int - tracked usage (may differ)
            "total_bytes": self.total_storage,  # int
            "utilization_percent": (actual_disk_usage / self.total_storage) * 100,  # float
            "files_stored": files_stored,  # int
            "active_transfers": active_transfers,  # int
            "chunk_count": len(os.listdir(self.chunks_path)) if os.path.exists(self.chunks_path) else 0  # int
        }

    def get_network_utilization(self) -> Dict[str, Union[int, float, List[str]]]:
        """Get current network utilization metrics (thread-safe)"""
        total_bandwidth_bps = self.bandwidth
        
        with self.network_lock:
            current_utilization = self.network_utilization
            connections_list = list(self.connections.keys())
        
        return {
            "current_utilization_bps": current_utilization,  # float
            "max_bandwidth_bps": total_bandwidth_bps,  # int
            "utilization_percent": (current_utilization / total_bandwidth_bps) * 100,  # float
            "connections": connections_list  # List[str]
        }

    def get_performance_metrics(self) -> Dict[str, int]:
        """Get node performance metrics (thread-safe)"""
        with self.metrics_lock:
            requests_processed = self.total_requests_processed
            data_transferred = self.total_data_transferred
            failed = self.failed_transfers
        
        with self.transfer_lock:
            active_transfers = len(self.active_transfers)
        
        return {
            "total_requests_processed": requests_processed,
            "total_data_transferred_bytes": data_transferred,
            "failed_transfers": failed,
            "current_active_transfers": active_transfers
        }
