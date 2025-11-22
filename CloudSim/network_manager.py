"""
NetworkManager - Handles real TCP/IP network communication between nodes
Manages socket connections and facilitates data transfer operations
"""

import socket
import json
from typing import Optional, Dict, Any
from enum import Enum


class MessageType(Enum):
    """Types of messages that can be sent between nodes"""
    TRANSFER_REQUEST = "TRANSFER_REQUEST"
    TRANSFER_RESPONSE = "TRANSFER_RESPONSE"
    CHUNK_DATA = "CHUNK_DATA"
    CHUNK_ACK = "CHUNK_ACK"
    STATUS_QUERY = "STATUS_QUERY"
    STATUS_RESPONSE = "STATUS_RESPONSE"
    ERROR = "ERROR"


class NetworkManager:
    """
    Manages network communication between storage nodes
    Handles socket connections, message serialization, and data transfer
    """
    
    def __init__(self, node_id: str, host: str = "localhost", port: int = 5000):
        """
        Initialize NetworkManager
        
        Args:
            node_id: Unique identifier for this node
            host: Host address to bind to (default: localhost)
            port: Port number to listen on (default: 5000)
        """
        self.node_id = node_id
        self.host = host
        self.port = port
        
        # Socket for listening to incoming connections
        self.server_socket: Optional[socket.socket] = None
        
        # Active connections to other nodes {node_id: socket}
        self.connections: Dict[str, socket.socket] = {}
        
        # Connection metadata {node_id: (host, port)}
        self.node_addresses: Dict[str, tuple] = {}
        
        # Flag to control server loop
        self.running = False
        
        print(f"[NetworkManager-{self.node_id}] Initialized on {self.host}:{self.port}")
    
    def connect_to_node(self, target_node_id: str, target_host: str, target_port: int) -> bool:
        """
        Establish a TCP connection to another node
        
        Args:
            target_node_id: ID of the node to connect to
            target_host: Host address of target node
            target_port: Port number of target node
            
        Returns:
            bool: True if connection successful, False otherwise
        """
        # Check if already connected
        if target_node_id in self.connections:
            print(f"[NetworkManager-{self.node_id}] Already connected to {target_node_id}")
            return True
        
        try:
            # Create TCP socket
            client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            
            # Set socket options
            client_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            
            # Set timeout for connection attempt
            client_socket.settimeout(5.0)
            
            # Attempt to connect
            print(f"[NetworkManager-{self.node_id}] Connecting to {target_node_id} at {target_host}:{target_port}...")
            client_socket.connect((target_host, target_port))
            
            # Connection successful
            self.connections[target_node_id] = client_socket
            self.node_addresses[target_node_id] = (target_host, target_port)
            
            print(f"[NetworkManager-{self.node_id}] Successfully connected to {target_node_id}")
            return True
            
        except socket.timeout:
            print(f"[NetworkManager-{self.node_id}] Connection to {target_node_id} timed out")
            return False
        except ConnectionRefusedError:
            print(f"[NetworkManager-{self.node_id}] Connection refused by {target_node_id} at {target_host}:{target_port}")
            return False
        except Exception as e:
            print(f"[NetworkManager-{self.node_id}] Error connecting to {target_node_id}: {e}")
            return False
    
    def send_message(self, target_node_id: str, message: Dict[str, Any]) -> bool:
        """
        Send a message to a connected node
        
        Args:
            target_node_id: ID of the node to send message to
            message: Dictionary containing message data
            
        Returns:
            bool: True if message sent successfully, False otherwise
        """
        # Placeholder - will be implemented in later commit
        pass
    
    def receive_message(self, connection: socket.socket) -> Optional[Dict[str, Any]]:
        """
        Receive and parse a message from a connection
        
        Args:
            connection: Socket connection to receive from
            
        Returns:
            Dict containing parsed message, or None if error
        """
        # Placeholder - will be implemented in later commit
        pass
    
    def start_server(self):
        """
        Start listening for incoming connections
        This will be run in a separate thread
        """
        # Placeholder - will be implemented in Phase 3
        pass
    
    def stop_server(self):
        """
        Stop the server and close all connections
        """
        # Placeholder - will be implemented in Phase 3
        pass
    
    def close_connection(self, node_id: str):
        """
        Close connection to a specific node
        
        Args:
            node_id: ID of the node to disconnect from
        """
        if node_id in self.connections:
            try:
                self.connections[node_id].close()
                del self.connections[node_id]
                print(f"[NetworkManager-{self.node_id}] Closed connection to {node_id}")
            except Exception as e:
                print(f"[NetworkManager-{self.node_id}] Error closing connection to {node_id}: {e}")
    
    def get_connection_info(self) -> Dict[str, Any]:
        """
        Get information about current network state
        
        Returns:
            Dictionary containing connection statistics
        """
        return {
            "node_id": self.node_id,
            "host": self.host,
            "port": self.port,
            "active_connections": len(self.connections),
            "connected_nodes": list(self.connections.keys()),
            "known_addresses": len(self.node_addresses)
        }
    
    def __repr__(self):
        """String representation of NetworkManager"""
        return f"NetworkManager(node_id='{self.node_id}', host='{self.host}', port={self.port})"

