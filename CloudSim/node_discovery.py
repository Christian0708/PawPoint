"""
NodeDiscovery - Implements node discovery mechanism for the distributed storage network
Allows nodes to find and connect to each other automatically
"""

import socket
import json
import threading
import time
from typing import Dict, List, Optional, Tuple
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime


class DiscoveryMessageType(Enum):
    """Types of discovery messages"""
    DISCOVERY_REQUEST = "DISCOVERY_REQUEST"
    DISCOVERY_RESPONSE = "DISCOVERY_RESPONSE"
    HEARTBEAT = "HEARTBEAT"
    NODE_ANNOUNCE = "NODE_ANNOUNCE"
    NODE_GOODBYE = "NODE_GOODBYE"


@dataclass
class DiscoveredNode:
    """Represents a discovered node in the network"""
    node_id: str
    host: str
    port: int
    last_seen: float = field(default_factory=time.time)
    is_active: bool = True
    metadata: Dict = field(default_factory=dict)  # Additional node info (capacity, etc.)


class NodeDiscovery:
    """
    Handles automatic discovery of nodes on the network
    Maintains a registry of active nodes and their addresses
    """
    
    def __init__(
        self,
        node_id: str,
        host: str = "localhost",
        port: int = 5000,
        discovery_port: int = 9999,
        broadcast_interval: float = 30.0,
        node_timeout: float = 90.0
    ):
        """
        Initialize NodeDiscovery
        
        Args:
            node_id: ID of this node
            host: Host address of this node
            port: Port this node listens on
            discovery_port: Port for discovery protocol (default: 9999)
            broadcast_interval: Seconds between discovery broadcasts (default: 30)
            node_timeout: Seconds before marking a node as inactive (default: 90)
        """
        self.node_id = node_id
        self.host = host
        self.port = port
        self.discovery_port = discovery_port
        
        # Discovered nodes registry {node_id: DiscoveredNode}
        self.discovered_nodes: Dict[str, DiscoveredNode] = {}
        self.discovery_lock = threading.Lock()
        
        # Discovery socket (UDP for broadcast)
        self.discovery_socket: Optional[socket.socket] = None
        
        # Thread control
        self.running = False
        self.broadcast_thread: Optional[threading.Thread] = None
        self.listener_thread: Optional[threading.Thread] = None
        self.cleanup_thread: Optional[threading.Thread] = None
        
        # Configuration
        self.broadcast_interval = broadcast_interval
        self.node_timeout = node_timeout
        
        # Callbacks
        self.on_node_discovered: Optional[callable] = None
        self.on_node_lost: Optional[callable] = None
        
        print(f"[NodeDiscovery-{self.node_id}] Initialized on {self.host}:{self.port} (discovery port: {self.discovery_port})")
    
    def start(self):
        """Start the discovery service"""
        if self.running:
            print(f"[NodeDiscovery-{self.node_id}] Already running")
            return
        
        try:
            # Create UDP socket for discovery
            self.discovery_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.discovery_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.discovery_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            self.discovery_socket.bind(('', self.discovery_port))
            self.discovery_socket.settimeout(1.0)  # Non-blocking with timeout
            
            self.running = True
            
            # Start listener thread
            self.listener_thread = threading.Thread(
                target=self._discovery_listener,
                name=f"DiscoveryListener-{self.node_id}",
                daemon=True
            )
            self.listener_thread.start()
            
            # Start broadcast thread
            self.broadcast_thread = threading.Thread(
                target=self._broadcast_loop,
                name=f"DiscoveryBroadcast-{self.node_id}",
                daemon=True
            )
            self.broadcast_thread.start()
            
            # Start cleanup thread
            self.cleanup_thread = threading.Thread(
                target=self._cleanup_loop,
                name=f"DiscoveryCleanup-{self.node_id}",
                daemon=True
            )
            self.cleanup_thread.start()
            
            print(f"[NodeDiscovery-{self.node_id}] Discovery service started")
            
        except Exception as e:
            print(f"[NodeDiscovery-{self.node_id}] Error starting discovery: {e}")
            self.running = False
    
    def stop(self):
        """Stop the discovery service"""
        if not self.running:
            return
        
        self.running = False
        
        # Close socket
        if self.discovery_socket:
            try:
                self.discovery_socket.close()
            except Exception:
                pass
        
        # Wait for threads to finish
        if self.broadcast_thread:
            self.broadcast_thread.join(timeout=2.0)
        if self.listener_thread:
            self.listener_thread.join(timeout=2.0)
        if self.cleanup_thread:
            self.cleanup_thread.join(timeout=2.0)
        
        print(f"[NodeDiscovery-{self.node_id}] Discovery service stopped")
    
    def _discovery_listener(self):
        """Listen for discovery messages from other nodes"""
        while self.running:
            try:
                if not self.discovery_socket:
                    break
                
                # Receive UDP message
                data, addr = self.discovery_socket.recvfrom(4096)
                
                try:
                    message = json.loads(data.decode('utf-8'))
                    self._handle_discovery_message(message, addr)
                except json.JSONDecodeError:
                    continue
                except Exception as e:
                    print(f"[NodeDiscovery-{self.node_id}] Error handling discovery message: {e}")
                    
            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    print(f"[NodeDiscovery-{self.node_id}] Error in discovery listener: {e}")
                break
    
    def _handle_discovery_message(self, message: Dict, addr: Tuple[str, int]):
        """Handle incoming discovery message"""
        msg_type = message.get("type")
        
        if msg_type == DiscoveryMessageType.DISCOVERY_REQUEST.value:
            # Respond to discovery request
            self._send_discovery_response(addr)
            
        elif msg_type == DiscoveryMessageType.DISCOVERY_RESPONSE.value:
            # Process discovery response
            node_id = message.get("node_id")
            node_host = message.get("host", addr[0])
            node_port = message.get("port")
            
            if node_id and node_id != self.node_id and node_port:
                self._register_discovered_node(node_id, node_host, node_port, message.get("metadata", {}))
        
        elif msg_type == DiscoveryMessageType.HEARTBEAT.value:
            # Update last seen time
            node_id = message.get("node_id")
            if node_id and node_id != self.node_id:
                with self.discovery_lock:
                    if node_id in self.discovered_nodes:
                        self.discovered_nodes[node_id].last_seen = time.time()
                        self.discovered_nodes[node_id].is_active = True
        
        elif msg_type == DiscoveryMessageType.NODE_ANNOUNCE.value:
            # New node announcement
            node_id = message.get("node_id")
            node_host = message.get("host", addr[0])
            node_port = message.get("port")
            
            if node_id and node_id != self.node_id and node_port:
                self._register_discovered_node(node_id, node_host, node_port, message.get("metadata", {}))
        
        elif msg_type == DiscoveryMessageType.NODE_GOODBYE.value:
            # Node is shutting down
            node_id = message.get("node_id")
            if node_id:
                self._unregister_node(node_id)
    
    def _register_discovered_node(self, node_id: str, host: str, port: int, metadata: Dict):
        """Register or update a discovered node"""
        with self.discovery_lock:
            is_new = node_id not in self.discovered_nodes
            
            self.discovered_nodes[node_id] = DiscoveredNode(
                node_id=node_id,
                host=host,
                port=port,
                last_seen=time.time(),
                is_active=True,
                metadata=metadata
            )
        
        if is_new:
            print(f"[NodeDiscovery-{self.node_id}] Discovered new node: {node_id} at {host}:{port}")
            if self.on_node_discovered:
                try:
                    self.on_node_discovered(node_id, host, port)
                except Exception as e:
                    print(f"[NodeDiscovery-{self.node_id}] Error in on_node_discovered callback: {e}")
        else:
            # Update existing node
            with self.discovery_lock:
                if node_id in self.discovered_nodes:
                    self.discovered_nodes[node_id].last_seen = time.time()
                    self.discovered_nodes[node_id].is_active = True
    
    def _unregister_node(self, node_id: str):
        """Unregister a node (node went offline)"""
        with self.discovery_lock:
            if node_id in self.discovered_nodes:
                node = self.discovered_nodes[node_id]
                del self.discovered_nodes[node_id]
                print(f"[NodeDiscovery-{self.node_id}] Node {node_id} went offline")
                
                if self.on_node_lost:
                    try:
                        self.on_node_lost(node_id, node.host, node.port)
                    except Exception as e:
                        print(f"[NodeDiscovery-{self.node_id}] Error in on_node_lost callback: {e}")
    
    def _broadcast_loop(self):
        """Periodically broadcast discovery messages"""
        while self.running:
            try:
                # Send discovery announcement
                self._send_node_announcement()
                
                # Send discovery request to find other nodes
                self._send_discovery_request()
                
                # Sleep until next broadcast
                time.sleep(self.broadcast_interval)
                
            except Exception as e:
                if self.running:
                    print(f"[NodeDiscovery-{self.node_id}] Error in broadcast loop: {e}")
                break
    
    def _send_discovery_request(self):
        """Send a discovery request to find other nodes"""
        message = {
            "type": DiscoveryMessageType.DISCOVERY_REQUEST.value,
            "node_id": self.node_id,
            "host": self.host,
            "port": self.port,
            "timestamp": time.time()
        }
        self._send_broadcast(message)
    
    def _send_discovery_response(self, target_addr: Tuple[str, int]):
        """Send discovery response to a specific address"""
        message = {
            "type": DiscoveryMessageType.DISCOVERY_RESPONSE.value,
            "node_id": self.node_id,
            "host": self.host,
            "port": self.port,
            "metadata": {},
            "timestamp": time.time()
        }
        self._send_message(message, target_addr)
    
    def _send_node_announcement(self):
        """Announce this node's presence"""
        message = {
            "type": DiscoveryMessageType.NODE_ANNOUNCE.value,
            "node_id": self.node_id,
            "host": self.host,
            "port": self.port,
            "metadata": {},
            "timestamp": time.time()
        }
        self._send_broadcast(message)
    
    def _send_heartbeat(self):
        """Send heartbeat to keep node registry updated"""
        message = {
            "type": DiscoveryMessageType.HEARTBEAT.value,
            "node_id": self.node_id,
            "timestamp": time.time()
        }
        self._send_broadcast(message)
    
    def send_goodbye(self):
        """Send goodbye message when shutting down"""
        message = {
            "type": DiscoveryMessageType.NODE_GOODBYE.value,
            "node_id": self.node_id,
            "timestamp": time.time()
        }
        self._send_broadcast(message)
    
    def _send_broadcast(self, message: Dict):
        """Send UDP broadcast message"""
        try:
            data = json.dumps(message).encode('utf-8')
            # Broadcast to all interfaces
            self.discovery_socket.sendto(data, ('<broadcast>', self.discovery_port))
        except Exception as e:
            print(f"[NodeDiscovery-{self.node_id}] Error sending broadcast: {e}")
    
    def _send_message(self, message: Dict, target_addr: Tuple[str, int]):
        """Send UDP message to specific address"""
        try:
            data = json.dumps(message).encode('utf-8')
            self.discovery_socket.sendto(data, target_addr)
        except Exception as e:
            print(f"[NodeDiscovery-{self.node_id}] Error sending message: {e}")
    
    def _cleanup_loop(self):
        """Periodically clean up inactive nodes"""
        while self.running:
            try:
                current_time = time.time()
                inactive_nodes = []
                
                with self.discovery_lock:
                    for node_id, node in self.discovered_nodes.items():
                        if current_time - node.last_seen > self.node_timeout:
                            inactive_nodes.append(node_id)
                
                # Unregister inactive nodes
                for node_id in inactive_nodes:
                    self._unregister_node(node_id)
                
                # Sleep before next cleanup
                time.sleep(self.broadcast_interval)
                
            except Exception as e:
                if self.running:
                    print(f"[NodeDiscovery-{self.node_id}] Error in cleanup loop: {e}")
                break
    
    def get_discovered_nodes(self) -> List[DiscoveredNode]:
        """Get list of all discovered nodes"""
        with self.discovery_lock:
            return list(self.discovered_nodes.values())
    
    def get_active_nodes(self) -> List[DiscoveredNode]:
        """Get list of active discovered nodes"""
        with self.discovery_lock:
            return [node for node in self.discovered_nodes.values() if node.is_active]
    
    def get_node_address(self, node_id: str) -> Optional[Tuple[str, int]]:
        """Get address of a discovered node"""
        with self.discovery_lock:
            node = self.discovered_nodes.get(node_id)
            if node:
                return (node.host, node.port)
            return None
    
    def get_discovery_stats(self) -> Dict:
        """Get statistics about discovered nodes"""
        with self.discovery_lock:
            total = len(self.discovered_nodes)
            active = sum(1 for node in self.discovered_nodes.values() if node.is_active)
        
        return {
            "total_discovered": total,
            "active_nodes": active,
            "inactive_nodes": total - active,
            "node_ids": [node.node_id for node in self.discovered_nodes.values()]
        }
    
    def __repr__(self):
        """String representation of NodeDiscovery"""
        stats = self.get_discovery_stats()
        return f"NodeDiscovery(node_id={self.node_id}, discovered={stats['total_discovered']}, active={stats['active_nodes']})"

