"""
NetworkService - Independent network service for the cloud
Manages the discovery network that nodes connect to
Can be started independently from nodes
"""

import socket
import threading
import time
import json
from typing import Dict, Optional, Set
from datetime import datetime


class NetworkService:
    """
    Independent network service that manages the cloud discovery network
    Nodes connect to this service when they boot
    """
    
    def __init__(
        self,
        discovery_port: int = 9999,
        broadcast_interval: float = 30.0,
        network_name: str = "CloudSim_Network"
    ):
        """
        Initialize NetworkService
        
        Args:
            discovery_port: UDP port for discovery protocol (default: 9999)
            broadcast_interval: Seconds between network announcements (default: 30)
            network_name: Name of the network/cloud
        """
        self.discovery_port = discovery_port
        self.broadcast_interval = broadcast_interval
        self.network_name = network_name
        
        # Network status
        self.running = False
        self.network_available = False
        
        # Discovery socket
        self.discovery_socket: Optional[socket.socket] = None
        
        # Registered nodes {node_id: (host, port, last_seen)}
        self.registered_nodes: Dict[str, Dict] = {}
        self.registration_lock = threading.Lock()
        
        # Threads
        self.broadcast_thread: Optional[threading.Thread] = None
        self.listener_thread: Optional[threading.Thread] = None
        
        print(f"[NetworkService] Initialized: {network_name} (discovery port: {discovery_port})")
    
    def start(self):
        """Start the network service"""
        if self.running:
            print("[NetworkService] Network service already running")
            return
        
        try:
            # Create UDP socket for discovery
            self.discovery_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.discovery_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.discovery_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            self.discovery_socket.bind(('', self.discovery_port))
            self.discovery_socket.settimeout(1.0)  # Non-blocking with timeout
            
            self.running = True
            self.network_available = True
            
            # Start listener thread
            self.listener_thread = threading.Thread(
                target=self._listener_loop,
                name="NetworkService-Listener",
                daemon=True
            )
            self.listener_thread.start()
            
            # Start broadcast thread
            self.broadcast_thread = threading.Thread(
                target=self._broadcast_loop,
                name="NetworkService-Broadcast",
                daemon=True
            )
            self.broadcast_thread.start()
            
            print(f"[NetworkService] Network service started on port {self.discovery_port}")
            print(f"[NetworkService] Network '{self.network_name}' is now available")
            
        except Exception as e:
            print(f"[NetworkService] Error starting network service: {e}")
            self.running = False
            self.network_available = False
    
    def stop(self):
        """Stop the network service"""
        if not self.running:
            return
        
        self.running = False
        self.network_available = False
        
        if self.discovery_socket:
            try:
                self.discovery_socket.close()
            except Exception:
                pass
        
        print("[NetworkService] Network service stopped")
    
    def _listener_loop(self):
        """Listen for node registration requests"""
        while self.running:
            try:
                data, addr = self.discovery_socket.recvfrom(4096)
                message = json.loads(data.decode('utf-8'))
                
                msg_type = message.get('type')
                
                if msg_type == 'NODE_REGISTER':
                    # Node wants to register with the network
                    self._handle_node_registration(message, addr)
                elif msg_type == 'NETWORK_QUERY':
                    # Node is checking if network is available
                    self._handle_network_query(addr)
                elif msg_type == 'NODE_HEARTBEAT':
                    # Node heartbeat to stay registered
                    self._handle_heartbeat(message)
                elif msg_type == 'NETWORK_SHUTDOWN':
                    # Request to shutdown the network service
                    self._handle_shutdown_request(message, addr)
                    
            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    print(f"[NetworkService] Error in listener: {e}")
    
    def _handle_node_registration(self, message: Dict, addr: tuple):
        """Handle node registration request"""
        node_id = message.get('node_id')
        host = message.get('host', addr[0])
        port = message.get('port')
        
        if not node_id or not port:
            return
        
        with self.registration_lock:
            self.registered_nodes[node_id] = {
                'host': host,
                'port': port,
                'last_seen': time.time(),
                'registered_at': datetime.now().isoformat()
            }
        
        # Send registration confirmation
        response = {
            'type': 'REGISTRATION_CONFIRMED',
            'network_name': self.network_name,
            'network_available': True,
            'discovery_port': self.discovery_port,
            'registered_nodes': len(self.registered_nodes)
        }
        
        try:
            self.discovery_socket.sendto(
                json.dumps(response).encode('utf-8'),
                addr
            )
        except Exception as e:
            print(f"[NetworkService] Error sending registration confirmation: {e}")
        
        print(f"[NetworkService] Node {node_id} registered from {host}:{port}")
    
    def _handle_network_query(self, addr: tuple):
        """Handle network availability query"""
        response = {
            'type': 'NETWORK_RESPONSE',
            'network_name': self.network_name,
            'network_available': True,
            'discovery_port': self.discovery_port,
            'registered_nodes': len(self.registered_nodes)
        }
        
        try:
            self.discovery_socket.sendto(
                json.dumps(response).encode('utf-8'),
                addr
            )
        except Exception as e:
            print(f"[NetworkService] Error sending network response: {e}")
    
    def _handle_heartbeat(self, message: Dict):
        """Handle node heartbeat"""
        node_id = message.get('node_id')
        if node_id and node_id in self.registered_nodes:
            with self.registration_lock:
                self.registered_nodes[node_id]['last_seen'] = time.time()
    
    def _handle_shutdown_request(self, message: Dict, addr: tuple):
        """Handle network shutdown request"""
        # Verify it's a valid shutdown request (could add authentication here)
        print(f"[NetworkService] Received shutdown request from {addr[0]}:{addr[1]}")
        print("[NetworkService] Shutting down network service...")
        self.stop()
    
    def _broadcast_loop(self):
        """Broadcast network availability"""
        while self.running:
            try:
                # Broadcast network availability
                broadcast_msg = {
                    'type': 'NETWORK_ANNOUNCE',
                    'network_name': self.network_name,
                    'network_available': True,
                    'discovery_port': self.discovery_port,
                    'timestamp': datetime.now().isoformat()
                }
                
                # Broadcast to all interfaces
                broadcast_addr = ('255.255.255.255', self.discovery_port)
                self.discovery_socket.sendto(
                    json.dumps(broadcast_msg).encode('utf-8'),
                    broadcast_addr
                )
                
                time.sleep(self.broadcast_interval)
                
            except Exception as e:
                if self.running:
                    print(f"[NetworkService] Error in broadcast: {e}")
                time.sleep(self.broadcast_interval)
    
    def get_registered_nodes(self) -> Dict:
        """Get list of registered nodes"""
        with self.registration_lock:
            return dict(self.registered_nodes)
    
    def _check_port_in_use(self, port: int) -> bool:
        """Check if network is actually running by sending a query and waiting for response"""
        try:
            # Try to query the network to see if it responds
            query_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            query_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            query_socket.settimeout(1.0)  # Short timeout
            
            # Send a network query
            query_msg = {
                'type': 'NETWORK_QUERY',
                'node_id': 'status_check',
                'host': 'localhost',
                'port': 0
            }
            
            query_socket.sendto(
                json.dumps(query_msg).encode('utf-8'),
                ('127.0.0.1', port)  # Try localhost first
            )
            
            # Wait for response
            try:
                data, addr = query_socket.recvfrom(4096)
                response = json.loads(data.decode('utf-8'))
                query_socket.close()
                # If we got a valid network response, network is running
                return response.get('type') == 'NETWORK_RESPONSE' and response.get('network_available', False)
            except socket.timeout:
                # No response - network might not be running
                query_socket.close()
                return False
        except Exception:
            # On any error, assume network is not running
            return False
    
    def get_network_status(self) -> Dict:
        """Get network status"""
        # Check if port is actually in use (network might be running in another process)
        port_in_use = self._check_port_in_use(self.discovery_port)
        
        # If port is in use but we think we're not running, network is running in another process
        # Only report as running if it's actually running in THIS process OR responding to queries
        actual_running = self.running or port_in_use
        
        return {
            'network_name': self.network_name,
            'running': actual_running,
            'network_available': actual_running,
            'discovery_port': self.discovery_port,
            'registered_nodes': len(self.registered_nodes),
            'nodes': dict(self.registered_nodes),
            'running_in_this_process': self.running,
            'port_in_use': port_in_use,
            'running_in_another_process': port_in_use and not self.running
        }
    
    def is_network_available(self) -> bool:
        """Check if network is available"""
        return self.network_available and self.running

