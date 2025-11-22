"""
NetworkManager - Handles real TCP/IP network communication between nodes
Manages socket connections and facilitates data transfer operations
"""

import socket
import json
import time
from typing import Optional, Dict, Any, Callable
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


class ProtocolMessage:
    """
    Factory class for creating protocol-compliant messages
    All messages are JSON-serializable dictionaries
    """
    
    @staticmethod
    def create_transfer_request(file_id: str, file_name: str, file_size: int, 
                               source_node_id: str, num_chunks: int) -> Dict[str, Any]:
        """Create a file transfer request message"""
        return {
            "type": MessageType.TRANSFER_REQUEST.value,
            "file_id": file_id,
            "file_name": file_name,
            "file_size": file_size,
            "source_node_id": source_node_id,
            "num_chunks": num_chunks,
            "timestamp": None  # Will be set when sent
        }
    
    @staticmethod
    def create_transfer_response(file_id: str, accepted: bool, reason: str = "") -> Dict[str, Any]:
        """Create a transfer response message"""
        return {
            "type": MessageType.TRANSFER_RESPONSE.value,
            "file_id": file_id,
            "accepted": accepted,
            "reason": reason,
            "timestamp": None
        }
    
    @staticmethod
    def create_chunk_data(file_id: str, chunk_id: int, chunk_size: int, 
                         checksum: str) -> Dict[str, Any]:
        """Create a chunk data message (data sent separately)"""
        return {
            "type": MessageType.CHUNK_DATA.value,
            "file_id": file_id,
            "chunk_id": chunk_id,
            "chunk_size": chunk_size,
            "checksum": checksum,
            "timestamp": None
        }
    
    @staticmethod
    def create_chunk_ack(file_id: str, chunk_id: int, success: bool, 
                        checksum_verified: bool = True) -> Dict[str, Any]:
        """Create a chunk acknowledgment message"""
        return {
            "type": MessageType.CHUNK_ACK.value,
            "file_id": file_id,
            "chunk_id": chunk_id,
            "success": success,
            "checksum_verified": checksum_verified,
            "timestamp": None
        }
    
    @staticmethod
    def create_status_query(query_type: str = "general") -> Dict[str, Any]:
        """Create a status query message"""
        return {
            "type": MessageType.STATUS_QUERY.value,
            "query_type": query_type,
            "timestamp": None
        }
    
    @staticmethod
    def create_status_response(storage_used: int, storage_total: int, 
                              active_transfers: int, files_stored: int) -> Dict[str, Any]:
        """Create a status response message"""
        return {
            "type": MessageType.STATUS_RESPONSE.value,
            "storage_used": storage_used,
            "storage_total": storage_total,
            "active_transfers": active_transfers,
            "files_stored": files_stored,
            "timestamp": None
        }
    
    @staticmethod
    def create_error(error_code: str, error_message: str) -> Dict[str, Any]:
        """Create an error message"""
        return {
            "type": MessageType.ERROR.value,
            "error_code": error_code,
            "error_message": error_message,
            "timestamp": None
        }
    
    @staticmethod
    def validate_message(message: Dict[str, Any]) -> bool:
        """
        Validate that a message has required fields
        
        Args:
            message: Message dictionary to validate
            
        Returns:
            bool: True if message is valid, False otherwise
        """
        if not isinstance(message, dict):
            return False
        
        if "type" not in message:
            return False
        
        # Check if type is valid
        valid_types = [mt.value for mt in MessageType]
        if message["type"] not in valid_types:
            return False
        
        return True


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
        
        # Message handler registry {message_type: handler_function}
        self.message_handlers: Dict[str, Callable] = {}
        
        # Register default handlers (can be overridden)
        self._register_default_handlers()
        
        print(f"[NetworkManager-{self.node_id}] Initialized on {self.host}:{self.port}")
    
    def _register_default_handlers(self):
        """Register default message handlers"""
        self.message_handlers[MessageType.TRANSFER_REQUEST.value] = self._handle_transfer_request
        self.message_handlers[MessageType.TRANSFER_RESPONSE.value] = self._handle_transfer_response
        self.message_handlers[MessageType.CHUNK_DATA.value] = self._handle_chunk_data
        self.message_handlers[MessageType.CHUNK_ACK.value] = self._handle_chunk_ack
        self.message_handlers[MessageType.STATUS_QUERY.value] = self._handle_status_query
        self.message_handlers[MessageType.STATUS_RESPONSE.value] = self._handle_status_response
        self.message_handlers[MessageType.ERROR.value] = self._handle_error
    
    def register_handler(self, message_type: str, handler: Callable):
        """
        Register a custom handler for a message type
        
        Args:
            message_type: Message type string (from MessageType enum)
            handler: Function that takes (message, client_socket, client_address) as arguments
        """
        self.message_handlers[message_type] = handler
        print(f"[NetworkManager-{self.node_id}] Registered handler for {message_type}")
    
    def dispatch_request(self, message: Dict[str, Any], client_socket: socket.socket, 
                        client_address: tuple) -> bool:
        """
        Dispatch a received message to the appropriate handler
        
        Args:
            message: Parsed message dictionary
            client_socket: Socket connection from client
            client_address: Tuple of (host, port) of client
            
        Returns:
            bool: True if message was handled, False otherwise
        """
        message_type = message.get("type")
        
        if message_type not in self.message_handlers:
            print(f"[NetworkManager-{self.node_id}] No handler registered for message type: {message_type}")
            return False
        
        try:
            # Call the appropriate handler
            handler = self.message_handlers[message_type]
            handler(message, client_socket, client_address)
            return True
        except Exception as e:
            print(f"[NetworkManager-{self.node_id}] Error in handler for {message_type}: {e}")
            return False
    
    # Default handler methods (placeholders - can be overridden)
    def _handle_transfer_request(self, message: Dict[str, Any], client_socket: socket.socket, 
                                 client_address: tuple):
        """Handle transfer request message"""
        print(f"[NetworkManager-{self.node_id}] Transfer request from {client_address}: {message.get('file_name')}")
        # Placeholder - will be implemented when integrating with StorageVirtualNode
    
    def _handle_transfer_response(self, message: Dict[str, Any], client_socket: socket.socket, 
                                  client_address: tuple):
        """Handle transfer response message"""
        print(f"[NetworkManager-{self.node_id}] Transfer response: {message.get('accepted')}")
    
    def _handle_chunk_data(self, message: Dict[str, Any], client_socket: socket.socket, 
                           client_address: tuple):
        """Handle chunk data message"""
        print(f"[NetworkManager-{self.node_id}] Chunk data: file_id={message.get('file_id')}, chunk_id={message.get('chunk_id')}")
    
    def _handle_chunk_ack(self, message: Dict[str, Any], client_socket: socket.socket, 
                          client_address: tuple):
        """Handle chunk acknowledgment message"""
        print(f"[NetworkManager-{self.node_id}] Chunk ACK: file_id={message.get('file_id')}, chunk_id={message.get('chunk_id')}")
    
    def _handle_status_query(self, message: Dict[str, Any], client_socket: socket.socket, 
                             client_address: tuple):
        """Handle status query message"""
        print(f"[NetworkManager-{self.node_id}] Status query from {client_address}")
    
    def _handle_status_response(self, message: Dict[str, Any], client_socket: socket.socket, 
                                client_address: tuple):
        """Handle status response message"""
        print(f"[NetworkManager-{self.node_id}] Status response received")
    
    def _handle_error(self, message: Dict[str, Any], client_socket: socket.socket, 
                     client_address: tuple):
        """Handle error message"""
        error_code = message.get('error_code', 'UNKNOWN')
        error_msg = message.get('error_message', 'No message')
        print(f"[NetworkManager-{self.node_id}] Error from {client_address}: [{error_code}] {error_msg}")
    
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
        
        client_socket = None
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
            print(f"[NetworkManager-{self.node_id}] Connection to {target_node_id} timed out after 5 seconds")
            return False
        except ConnectionRefusedError:
            print(f"[NetworkManager-{self.node_id}] Connection refused by {target_node_id} at {target_host}:{target_port}")
            return False
        except OSError as e:
            if e.errno == 10061:  # Connection refused (Windows)
                print(f"[NetworkManager-{self.node_id}] Connection refused by {target_node_id} at {target_host}:{target_port}")
            elif e.errno == 10060:  # Connection timed out (Windows)
                print(f"[NetworkManager-{self.node_id}] Connection to {target_node_id} timed out")
            else:
                print(f"[NetworkManager-{self.node_id}] OS error connecting to {target_node_id}: {e}")
            return False
        except Exception as e:
            print(f"[NetworkManager-{self.node_id}] Unexpected error connecting to {target_node_id}: {e}")
            return False
        finally:
            # Clean up socket if connection failed
            if target_node_id not in self.connections and client_socket is not None:
                try:
                    client_socket.close()
                except:
                    pass
    
    def send_message(self, target_node_id: str, message: Dict[str, Any]) -> bool:
        """
        Send a JSON message to a connected node over TCP socket
        Uses length-prefixed protocol: 4-byte header + JSON data
        
        Args:
            target_node_id: ID of the node to send message to
            message: Dictionary containing message data
            
        Returns:
            bool: True if message sent successfully, False otherwise
        """
        # Check if connected to target node
        if target_node_id not in self.connections:
            print(f"[NetworkManager-{self.node_id}] Not connected to {target_node_id}")
            return False
        
        # Validate message
        if not ProtocolMessage.validate_message(message):
            print(f"[NetworkManager-{self.node_id}] Invalid message format")
            return False
        
        try:
            # Add timestamp
            message["timestamp"] = time.time()
            
            # Add sender information
            message["sender_node_id"] = self.node_id
            
            # Serialize message to JSON
            json_data = json.dumps(message)
            json_bytes = json_data.encode('utf-8')
            
            # Calculate message length
            message_length = len(json_bytes)
            
            # Send message length first (4 bytes, big-endian)
            length_header = message_length.to_bytes(4, byteorder='big')
            
            # Get socket connection
            sock = self.connections[target_node_id]
            
            # Send length header
            sock.sendall(length_header)
            
            # Send actual message
            sock.sendall(json_bytes)
            
            print(f"[NetworkManager-{self.node_id}] Sent {message['type']} to {target_node_id} ({message_length} bytes)")
            return True
            
        except BrokenPipeError:
            print(f"[NetworkManager-{self.node_id}] Connection to {target_node_id} broken (pipe broken)")
            self.close_connection(target_node_id)
            return False
        except ConnectionResetError:
            print(f"[NetworkManager-{self.node_id}] Connection to {target_node_id} reset by peer")
            self.close_connection(target_node_id)
            return False
        except OSError as e:
            print(f"[NetworkManager-{self.node_id}] OS error sending message to {target_node_id}: {e}")
            self.close_connection(target_node_id)
            return False
        except socket.timeout:
            print(f"[NetworkManager-{self.node_id}] Timeout sending message to {target_node_id}")
            return False
        except Exception as e:
            print(f"[NetworkManager-{self.node_id}] Unexpected error sending message to {target_node_id}: {e}")
            return False
    
    def receive_message(self, connection: socket.socket) -> Optional[Dict[str, Any]]:
        """
        Receive and parse a JSON message from a TCP socket connection
        Uses length-prefixed protocol: 4-byte header + JSON data
        
        Args:
            connection: Socket connection to receive from
            
        Returns:
            Dict containing parsed message, or None if error
        """
        try:
            # First, receive the 4-byte length header
            length_header = self._receive_exact(connection, 4)
            if length_header is None:
                return None
            
            # Parse message length
            message_length = int.from_bytes(length_header, byteorder='big')
            
            # Validate reasonable message length (max 100MB)
            if message_length > 100 * 1024 * 1024:
                print(f"[NetworkManager-{self.node_id}] Message too large: {message_length} bytes")
                return None
            
            # Receive the actual message data
            json_bytes = self._receive_exact(connection, message_length)
            if json_bytes is None:
                return None
            
            # Decode and parse JSON
            json_data = json_bytes.decode('utf-8')
            message = json.loads(json_data)
            
            # Validate message structure
            if not ProtocolMessage.validate_message(message):
                print(f"[NetworkManager-{self.node_id}] Received invalid message")
                return None
            
            print(f"[NetworkManager-{self.node_id}] Received {message['type']} from {message.get('sender_node_id', 'unknown')} ({message_length} bytes)")
            return message
            
        except json.JSONDecodeError as e:
            print(f"[NetworkManager-{self.node_id}] JSON decode error: {e}")
            return None
        except ConnectionResetError:
            print(f"[NetworkManager-{self.node_id}] Connection reset by peer while receiving")
            return None
        except BrokenPipeError:
            print(f"[NetworkManager-{self.node_id}] Broken pipe while receiving message")
            return None
        except OSError as e:
            print(f"[NetworkManager-{self.node_id}] OS error receiving message: {e}")
            return None
        except ValueError as e:
            print(f"[NetworkManager-{self.node_id}] Value error parsing message: {e}")
            return None
        except Exception as e:
            print(f"[NetworkManager-{self.node_id}] Unexpected error receiving message: {e}")
            return None
    
    def _receive_exact(self, connection: socket.socket, num_bytes: int) -> Optional[bytes]:
        """
        Receive exactly num_bytes from socket connection
        Handles partial receives by looping until all bytes received
        
        Args:
            connection: Socket to receive from
            num_bytes: Exact number of bytes to receive
            
        Returns:
            bytes: Received data, or None if connection closed/error
        """
        data = b''
        bytes_remaining = num_bytes
        
        while bytes_remaining > 0:
            try:
                chunk = connection.recv(min(bytes_remaining, 4096))
                if not chunk:
                    # Connection closed
                    return None
                data += chunk
                bytes_remaining -= len(chunk)
            except socket.timeout:
                print(f"[NetworkManager-{self.node_id}] Receive timeout after {num_bytes} bytes")
                return None
            except ConnectionResetError:
                print(f"[NetworkManager-{self.node_id}] Connection reset while receiving {num_bytes} bytes")
                return None
            except BrokenPipeError:
                print(f"[NetworkManager-{self.node_id}] Broken pipe while receiving {num_bytes} bytes")
                return None
            except OSError as e:
                print(f"[NetworkManager-{self.node_id}] OS error receiving {num_bytes} bytes: {e}")
                return None
            except Exception as e:
                print(f"[NetworkManager-{self.node_id}] Unexpected error receiving {num_bytes} bytes: {e}")
                return None
        
        return data
    
    def initialize_listener(self) -> bool:
        """
        Initialize and bind the server socket for listening
        Must be called before start_server()
        
        Returns:
            bool: True if initialization successful, False otherwise
        """
        if self.server_socket is not None:
            print(f"[NetworkManager-{self.node_id}] Listener already initialized")
            return True
        
        try:
            # Create TCP socket
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            
            # Set socket options
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            
            # Set socket timeout (for checking self.running flag)
            self.server_socket.settimeout(1.0)
            
            # Bind to host and port
            self.server_socket.bind((self.host, self.port))
            
            # Start listening (backlog of 5 pending connections)
            self.server_socket.listen(5)
            
            print(f"[NetworkManager-{self.node_id}] Listener initialized and bound to {self.host}:{self.port}")
            return True
            
        except OSError as e:
            if e.errno == 98 or e.errno == 10048:  # Address already in use
                print(f"[NetworkManager-{self.node_id}] Port {self.port} already in use")
            else:
                print(f"[NetworkManager-{self.node_id}] Error binding to {self.host}:{self.port}: {e}")
            self.server_socket = None
            return False
        except Exception as e:
            print(f"[NetworkManager-{self.node_id}] Error initializing listener: {e}")
            self.server_socket = None
            return False
    
    def start_server(self):
        """
        Start listening for incoming connections
        This will be run in a separate thread
        Accepts connections and handles them
        """
        # Check if listener is initialized
        if self.server_socket is None:
            print(f"[NetworkManager-{self.node_id}] Listener not initialized. Call initialize_listener() first")
            return
        
        # Set running flag
        self.running = True
        print(f"[NetworkManager-{self.node_id}] Server started, listening on {self.host}:{self.port}")
        
        # Main server loop
        while self.running:
            try:
                # Accept incoming connection (with timeout to check running flag)
                client_socket, client_address = self.server_socket.accept()
                
                # Set socket timeout for receiving
                client_socket.settimeout(30.0)
                
                print(f"[NetworkManager-{self.node_id}] Accepted connection from {client_address[0]}:{client_address[1]}")
                
                # Handle the connection (will be dispatched in next commit)
                # For now, just store it temporarily
                # In next commit, we'll dispatch to appropriate handler
                self._handle_incoming_connection(client_socket, client_address)
                
            except socket.timeout:
                # Timeout is expected - allows checking self.running flag
                continue
            except OSError as e:
                if self.running:
                    # Only print error if we're still supposed to be running
                    print(f"[NetworkManager-{self.node_id}] Error accepting connection: {e}")
                break
            except Exception as e:
                if self.running:
                    print(f"[NetworkManager-{self.node_id}] Unexpected error in server loop: {e}")
                break
        
        print(f"[NetworkManager-{self.node_id}] Server stopped")
    
    def _handle_incoming_connection(self, client_socket: socket.socket, client_address: tuple):
        """
        Handle an incoming connection
        Receives messages and dispatches them to appropriate handlers
        
        Args:
            client_socket: Socket connection from client
            client_address: Tuple of (host, port) of client
        """
        try:
            # Receive message from client
            message = self.receive_message(client_socket)
            
            if message is None:
                print(f"[NetworkManager-{self.node_id}] Failed to receive message from {client_address[0]}:{client_address[1]}")
                client_socket.close()
                return
            
            # Dispatch message to appropriate handler
            handled = self.dispatch_request(message, client_socket, client_address)
            
            if not handled:
                print(f"[NetworkManager-{self.node_id}] Message from {client_address[0]}:{client_address[1]} was not handled")
            
        except ConnectionResetError:
            print(f"[NetworkManager-{self.node_id}] Connection reset by {client_address[0]}:{client_address[1]}")
        except BrokenPipeError:
            print(f"[NetworkManager-{self.node_id}] Broken pipe with {client_address[0]}:{client_address[1]}")
        except socket.timeout:
            print(f"[NetworkManager-{self.node_id}] Timeout handling connection from {client_address[0]}:{client_address[1]}")
        except OSError as e:
            print(f"[NetworkManager-{self.node_id}] OS error handling connection from {client_address[0]}:{client_address[1]}: {e}")
        except Exception as e:
            print(f"[NetworkManager-{self.node_id}] Unexpected error handling connection from {client_address[0]}:{client_address[1]}: {e}")
        finally:
            # Close the connection after handling
            try:
                client_socket.close()
            except ConnectionResetError:
                pass  # Already closed
            except Exception as e:
                print(f"[NetworkManager-{self.node_id}] Error closing client connection: {e}")
    
    def stop_server(self):
        """
        Stop the server and close all connections
        """
        self.running = False
        
        # Close server socket
        if self.server_socket is not None:
            try:
                self.server_socket.close()
                print(f"[NetworkManager-{self.node_id}] Server socket closed")
            except Exception as e:
                print(f"[NetworkManager-{self.node_id}] Error closing server socket: {e}")
            finally:
                self.server_socket = None
        
        # Close all client connections
        for node_id in list(self.connections.keys()):
            self.close_connection(node_id)
    
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

